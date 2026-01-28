from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageSegment
from src.utils.message_processor import process_message_for_llm, split_text_to_segments
from src.aimodel.image_processing.vlm import get_vlm_description
from src.config.config import bot_config
from src.utils.db_manager import db_manager
from src.aimodel.reply.chat import get_chat_reply
from src.aimodel.memory.embeddings import get_embeddings
from src.aimodel.memory.vector_db import vector_db
from src.aimodel.memory.consolidation import consolidate_memories
from src.aimodel.decision.decide import should_i_reply
import random
import asyncio
import time
import re
import datetime

# 记录每个群组最后一次被“强行唤醒”的时间（如被艾特或被提及）
last_wake_up_times = {}

def is_within_chat_time(group_id: int) -> bool:
    """检查当前时间是否在作息表的‘水群’时间段内，或处于强行唤醒后的关注期内"""
    now = datetime.datetime.now()
    
    # 1. 检查是否处于“强行唤醒”后的关注期（默认 5 分钟）
    last_wake = last_wake_up_times.get(group_id, 0)
    if time.time() - last_wake < 300: # 300秒 = 5分钟
        return True

    # 2. 检查作息表
    today_str = now.strftime("%Y-%m-%d")
    current_time_str = now.strftime("%H:%M")
    
    schedule = db_manager.get_bot_schedule(group_id, today_str)
    
    if not schedule:
        return True
        
    for item in schedule:
        start = item.get("start")
        end = item.get("end")
        can_chat = item.get("can_chat", False)
        
        if can_chat and start <= current_time_str <= end:
            return True
            
    return False

# 记录每个群最后一次进行 AI 决策的时间
last_decision_times = {}
# 记录每个群是否有未被决策评估的消息
pending_decisions = {}
# 存储每个群组最新的上下文信息，用于延迟决策
group_contexts = {}
# 记录正在运行的延迟决策任务
active_deferred_tasks = {}
# 记录每个群组是否正在进行 AI 决策，防止并发冲突
deciding_groups = set()

async def deferred_decision_worker(group_id: int, bot: Bot):
    """
    延迟决策工人：等待冷却期结束并执行决策
    """
    try:
        while True:
            last_time = last_decision_times.get(group_id, 0)
            now = time.time()
            remaining = bot_config.decision_interval - (now - last_time)
            
            if remaining <= 0:
                # 冷却期已过，检查是否有待处理消息
                if pending_decisions.get(group_id) and group_id not in deciding_groups:
                    ctx = group_contexts.get(group_id)
                    if ctx:
                        # 标记为已处理，防止重复触发
                        pending_decisions[group_id] = False
                        deciding_groups.add(group_id)
                        
                        try:
                            last_decision_times[group_id] = time.time()
                            # 执行决策
                            decision = await should_i_reply(
                                group_id, 
                                ctx['display_name'], 
                                ctx['llm_text'], 
                                is_at_me=False,
                                user_id=ctx['user_id']
                            )
                                
                            # 更新心情
                            mood_impact = decision.get("mood_impact", 0)
                            if mood_impact != 0:
                                db_manager.update_mood(group_id, mood_impact)
                                
                            if decision.get("should_reply"):
                                # 执行回复逻辑
                                await process_my_logic(
                                    bot=bot,
                                    event=ctx['event'],
                                    message_id=ctx['message_id'],
                                    text=ctx['text'],
                                    llm_text=ctx['llm_text'],
                                    normal_images=ctx['normal_images'],
                                    stickers=ctx['stickers'],
                                    flash_images=ctx['flash_images'],
                                    faces=ctx['faces'],
                                    group_id=group_id,
                                    user_id=ctx['user_id'],
                                    nickname=ctx['nickname'],
                                    card=decision.get("reply_to_user", ctx['display_name']),
                                    role=ctx['role'],
                                    raw_msg=ctx['raw_msg']
                                )
                        finally:
                            deciding_groups.remove(group_id)
                break
            
            # 每隔一小段时间检查一次，或者直接睡完剩余时间
            await asyncio.sleep(max(remaining, 0.5))
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"延迟决策任务出错: {e}")
    finally:
        active_deferred_tasks.pop(group_id, None)

# 创建一个响应所有消息的响应器
# 因为已经在 bot.py 做了全局过滤，所以这里的 on_message() 实际上只会收到群消息
group_msg_matcher = on_message()

@group_msg_matcher.handle()
async def handle_group_message(bot: Bot, event: GroupMessageEvent):
    """
    当接收到群消息时，NoneBot 会调用这个方法。
    """
    # 0. 群组过滤 (白名单/黑名单)
    group_id = event.group_id
    if bot_config.blocked_groups and group_id in bot_config.blocked_groups:
        return # 黑名单群组直接忽略
    
    if bot_config.allowed_groups and group_id not in bot_config.allowed_groups:
        return # 不在白名单中的群组直接忽略

    # 1. 基础信息
    message_id = event.message_id        # 消息 ID
    message_text = event.get_plaintext() # 纯文本内容
    group_id = event.group_id            # 群号
    user_id = event.user_id              # 发送者 QQ 号
    
    # 2. 发送者详细信息
    sender = event.sender
    nickname = sender.nickname
    card = sender.card or nickname
    # 使用全局昵称作为 AI 识别的名称，因为群名片更改太频繁
    display_name = nickname
    role = sender.role
    
    # 3. 提取各种消息段
    normal_images = []  # 普通图片 URL
    stickers = []       # 表情包 URL (sub_type=1)
    flash_images = []    # 闪照 URL (type=flash)
    faces = []          # 系统表情 ID (例如: 124 代表 [呲牙])
    
    for segment in event.get_message():
        # 处理图片
        if segment.type == "image":
            url = segment.data.get("url")
            sub_type = str(segment.data.get("sub_type", "0"))
            img_type = segment.data.get("type")
            
            if img_type == "flash":
                flash_images.append(url)
            elif sub_type == "1":
                stickers.append(url)
            else:
                normal_images.append(url)
                
        # 处理系统表情
        elif segment.type == "face":
            face_id = segment.data.get("id")
            if face_id:
                faces.append(face_id)
    
    # 4. 原始消息对象
    raw_message = event.get_message()
    
    # 5. 生成供 LLM 使用的清洗后文本
    llm_text = await process_message_for_llm(bot, event, vlm_func=get_vlm_description)
    
    # 6. 存入数据库 (格式: "名字:内容")
    msg_to_store = f"{display_name}:{llm_text}"
    db_manager.add_chat_log(group_id, msg_to_store)
    
    # 更新用户名与 ID 的映射，用于后续艾特功能
    # 同时存储群名片和 QQ 昵称，增加匹配成功率
    db_manager.update_user_id_map(group_id, nickname, user_id)
    if sender.card and sender.card != nickname:
        db_manager.update_user_id_map(group_id, sender.card, user_id)
    
    # 同步写入向量数据库 (长期记忆)
    # 使用 create_task 异步处理，不影响当前响应速度
    async def store_and_consolidate():
        try:
            # 1. 存入原始向量记录
            vectors = await get_embeddings([msg_to_store])
            vector_db.add_memory(group_id, msg_to_store, vectors[0])
            
            # 2. 尝试进行记忆固化 (每 20 条消息处理一次)
            # 我们直接在后台运行，不阻塞
            await consolidate_memories(group_id)
        except Exception as e:
            print(f"写入向量库或固化失败: {e}")
    
    asyncio.create_task(store_and_consolidate())
    
    # 7. 唤醒逻辑判断
    is_at_me = "@self" in llm_text or event.is_tome()
    is_mentioned = bot_config.bot_name in message_text
    is_actively_engaged = is_at_me or is_mentioned
    
    # 更新群组最新的上下文，用于可能的延迟决策
    group_contexts[group_id] = {
        "bot": bot,
        "event": event,
        "message_id": message_id,
        "text": message_text,
        "llm_text": llm_text,
        "normal_images": normal_images,
        "stickers": stickers,
        "flash_images": flash_images,
        "faces": faces,
        "user_id": user_id,
        "nickname": nickname,
        "display_name": display_name,
        "role": role,
        "raw_msg": raw_message
    }
    
    do_reply = False
    target_user = display_name
    
    if is_actively_engaged:
        # 1. 被显式叫到了，肯定要回
        # 更新强行唤醒时间，进入 5 分钟关注期
        last_wake_up_times[group_id] = time.time()
        
        # 取消已存在的延迟决策任务，因为现在就要立刻处理
        if group_id in active_deferred_tasks:
            active_deferred_tasks[group_id].cancel()
        
        pending_decisions[group_id] = False
        
        # 如果当前没有正在进行的决策，则立即执行
        if group_id not in deciding_groups:
            deciding_groups.add(group_id)
            try:
                last_decision_times[group_id] = time.time()
                # 执行决策评估心情
                decision = await should_i_reply(group_id, display_name, llm_text, is_at_me=True, user_id=user_id)
                
                # 实时更新心情 (只要决策引擎运行，就应用心情变动，无论是否决定回复)
                mood_impact = decision.get("mood_impact", 0)
                if mood_impact != 0:
                    db_manager.update_mood(group_id, mood_impact)
                    
                do_reply = True
                target_user = decision.get("reply_to_user", display_name)
            finally:
                deciding_groups.remove(group_id)
    else:
        # 2. 没被叫到，尝试进行 AI 智能决策
        # 首先检查当前是否在“作息表”允许的水群时间内
        if not is_within_chat_time(group_id):
            return # 不在水群时间，且没被叫到，直接忽略
            
        current_time = time.time()
        last_time = last_decision_times.get(group_id, 0)
        
        if current_time - last_time >= bot_config.decision_interval:
            # 过了冷却期，直接触发决策判断
            # 确保当前没有正在进行的决策
            if group_id not in deciding_groups:
                deciding_groups.add(group_id)
                try:
                    last_decision_times[group_id] = current_time
                    pending_decisions[group_id] = False
                    
                    decision = await should_i_reply(group_id, display_name, llm_text, is_at_me=False, user_id=user_id)
                    
                    # 实时更新心情 (只要决策引擎运行，就应用心情变动，无论是否决定回复)
                    mood_impact = decision.get("mood_impact", 0)
                    if mood_impact != 0:
                        db_manager.update_mood(group_id, mood_impact)
                    
                    do_reply = decision.get("should_reply", False)
                    target_user = decision.get("reply_to_user", display_name)
                finally:
                    deciding_groups.remove(group_id)
        else:
            # 还在冷却期内，只要有消息就标记为“待处理”，确保冷却结束后一定会判断
            pending_decisions[group_id] = True
            
            # 如果没有正在运行的延迟工人，则启动一个
            if group_id not in active_deferred_tasks:
                task = asyncio.create_task(deferred_decision_worker(group_id, bot))
                active_deferred_tasks[group_id] = task

    if not do_reply:
        return

    # --- 调用处理逻辑 ---
    await process_my_logic(
        bot=bot,
        event=event,
        message_id=message_id,
        text=message_text,
        llm_text=llm_text,
        normal_images=normal_images,
        stickers=stickers,
        flash_images=flash_images,
        faces=faces,
        group_id=group_id,
        user_id=user_id,
        nickname=nickname,
        card=target_user, # 使用决策引擎确定的目标用户
        role=role,
        raw_msg=raw_message
    )

async def process_my_logic(
    bot: Bot, 
    event: GroupMessageEvent, 
    message_id: int,
    text: str, 
    llm_text: str,
    normal_images: list[str], # 普通图片
    stickers: list[str],      # 表情包
    flash_images: list[str],   # 闪照
    faces: list[str],         # 系统表情 ID
    group_id: int, 
    user_id: int,
    nickname: str,
    card: str,
    role: str,
    raw_msg: any
):
    """
    这就是您要编写代码的方法。
    """
    # 1. 获取 AI 回复
    # 使用异步调用，不会阻塞其他消息的处理
    reply_data = await get_chat_reply(group_id, card, llm_text, user_id=user_id)
    reply_text = reply_data.get("text")
    sticker_url = reply_data.get("sticker")
    
    if reply_text or sticker_url:
        # 2. 存入数据库 (只存文字内容)
        if reply_text:
            db_manager.add_chat_log(group_id, f"self:{reply_text}")
        
        # 3. 处理艾特与引用标签
        # 提取 [回复] 标签
        is_reply = False
        if reply_text and "[回复]" in reply_text:
            is_reply = True
            reply_text = reply_text.replace("[回复]", "").strip()
        
        # 4. 分段发送回复，模拟真人感
        if reply_text:
            # 无论长短都尝试拆分，确保符合群聊短句习惯
            segments = split_text_to_segments(reply_text)
            for i, seg in enumerate(segments):
                # 构造消息段列表
                msg_segments = []
                
                # 只有第一段消息处理艾特和引用
                if i == 0:
                    if is_reply:
                        msg_segments.append(MessageSegment.reply(message_id))
                
                # 解析并处理 [at:用户名]
                parts = re.split(r'(\[at:.*?\])', seg)
                for part in parts:
                    if part.startswith("[at:") and part.endswith("]"):
                        target_name = part[4:-1].strip()
                        target_id = db_manager.get_user_id_by_name(group_id, target_name)
                        if target_id:
                            msg_segments.append(MessageSegment.at(target_id))
                        else:
                            msg_segments.append(MessageSegment.text(f"@{target_name}"))
                    elif part:
                        msg_segments.append(MessageSegment.text(part))
                
                if msg_segments:
                    await bot.send(event, Message(msg_segments), at_sender=False)
                
                # 模拟打字间隔：如果后面还有消息段或表情包，则延迟
                if i < len(segments) - 1 or sticker_url:
                    # 基础延迟 + 随机抖动
                    delay = min(1.5, max(0.3, len(seg) * 0.08))
                    await asyncio.sleep(delay + random.uniform(0.1, 0.5))
        
        # 发送表情包
        if sticker_url:
            await bot.send(event, MessageSegment.image(sticker_url), at_sender=False)
    
    # 打印分类信息
    print(f"[{role}] {card}({user_id}) [QQ昵称] 唤醒了{bot_config.bot_name}:")
    print(f"  - 清洗后文本 (LLM): {llm_text}")
    print(f"  - {bot_config.bot_name}回复: {reply_text}")
    
