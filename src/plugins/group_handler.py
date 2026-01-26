from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageSegment
from src.utils.message_processor import process_message_for_llm
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

# 记录每个群最后一次进行 AI 决策的时间
last_decision_times = {}

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
    
    do_reply = False
    
    # 只有在被艾特，或者满足随机触发概率且过了冷却期时，才调用决策引擎
    should_evaluate = is_actively_engaged
    if not should_evaluate:
        current_time = time.time()
        last_time = last_decision_times.get(group_id, 0)
        if current_time - last_time >= bot_config.decision_interval:
            if random.random() < bot_config.reply_rate:
                should_evaluate = True
                last_decision_times[group_id] = current_time

    if should_evaluate:
        # 核心决策逻辑：通过决策引擎评估回复和心情影响
        decision = await should_i_reply(group_id, display_name, llm_text, is_at_me=is_actively_engaged)
        
        do_reply = decision.get("should_reply", False)

        # 实时更新心情 (仅在决定回复时更新)
        if do_reply:
            mood_impact = decision.get("mood_impact", 0)
            if mood_impact != 0:
                db_manager.update_mood(group_id, mood_impact)

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
        card=display_name,
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
    reply_data = await get_chat_reply(group_id, card, llm_text)
    reply_text = reply_data.get("text")
    sticker_url = reply_data.get("sticker")
    
    if reply_text or sticker_url:
        # 2. 存入数据库 (只存文字内容)
        if reply_text:
            db_manager.add_chat_log(group_id, f"self:{reply_text}")
        
        # 3. 分段发送回复，模拟真人感
        # 先发文字
        if reply_text:
            await bot.send(event, MessageSegment.text(reply_text), at_sender=False)
        
        # 如果有表情包，稍微等一下再发，避免堆在一起
        if sticker_url:
            if reply_text:
                # 随机延迟 0.5 到 1.5 秒
                await asyncio.sleep(random.uniform(0.5, 1.5))
            await bot.send(event, MessageSegment.image(sticker_url), at_sender=False)
    
    # 打印分类信息
    print(f"[{role}] {card}({user_id}) [QQ昵称] 唤醒了{bot_config.bot_name}:")
    print(f"  - 清洗后文本 (LLM): {llm_text}")
    print(f"  - {bot_config.bot_name}回复: {reply_text}")
    
