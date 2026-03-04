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
from src.aimodel.reply.personality import personality_manager
from src.aimodel.decision.decide import should_i_reply
from src.utils.logger import get_logger
from src.utils.performance_monitor import ConcurrencyLimiter, RateLimiter
from src.utils.timed_cache import GroupContextManager, DecisionStateTracker
from typing import Optional
from collections import deque
import random
import asyncio
import time
import re
import datetime

logger = get_logger(__name__)

# 限制并发处理的任务数，避免资源耗尽
task_concurrency_limiter = ConcurrencyLimiter(max_concurrent=10)

# 速率限制器，防止任务过多
task_rate_limiter = RateLimiter(max_calls=50, time_window=10)

# 使用新的缓存管理器（替代全局字典，避免内存泄漏）
group_contexts = GroupContextManager(ttl_seconds=300)
decision_tracker = DecisionStateTracker()
last_wake_up_times = {}
last_slang_mining_times = {}

# 消息去重：记录已处理的消息 ID，防止重复回复
processed_messages = set()


def clean_reply_format(text: str) -> str:
    """
    清理消息文本中的QQ引用格式 [回复@名字:内容] 和富文本标签

    Args:
        text: 原始消息文本

    Returns:
        清理后的消息文本
    """
    if not text:
        return text
    # 匹配 [回复@名字:内容] 或 [回复@名字 :内容] 等格式
    pattern = r"\[回复@[^:]+:\s*\]"
    cleaned = re.sub(pattern, "", text)

    # 清理富文本标签（如图片HTML标签）
    cleaned = re.sub(r"<[^>]+>", "", cleaned)

    return cleaned.strip()


async def create_limited_task(coro):
    """
    创建受并发和速率限制的任务

    Args:
        coro: 协程对象
    """
    await task_rate_limiter.wait_for_slot()
    async with task_concurrency_limiter:
        return await coro


# 记录每个群组最后一次被"强行唤醒"的时间（如被艾特或被提及）
last_wake_up_times = {}


async def is_within_chat_time(group_id: int) -> bool:
    """检查当前时间是否在作息表的'水群'时间段内，或处于强行唤醒后的关注期内"""
    # 如果作息表系统关闭，全天候可水群
    if not bot_config.enable_schedule:
        return True

    now = datetime.datetime.now()

    # 1. 检查是否处于“强行唤醒”后的关注期（默认 5 分钟）
    last_wake = last_wake_up_times.get(group_id, 0)
    if time.time() - last_wake < 300:  # 300秒 = 5分钟
        return True

    # 2. 检查作息表
    today_str = now.strftime("%Y-%m-%d")
    current_time_str = now.strftime("%H:%M")

    schedule = await db_manager.get_bot_schedule(group_id, today_str)

    if not schedule:
        return True

    for item in schedule:
        if not isinstance(item, dict):
            continue
        start = item.get("start")
        end = item.get("end")
        can_chat = item.get("can_chat", False)

        if start and end and can_chat and start <= current_time_str <= end:
            return True

    return False


# 记录每个群最后一次进行 AI 决策的时间
last_decision_times = {}
# 记录每个群是否有未被决策评估的消息
pending_decisions = {}
# 存储每个群组待处理的消息队列（用于并发安全的上下文管理）
group_pending_contexts = {}
# 记录正在运行的延迟决策任务
active_deferred_tasks = {}
# 记录每个群组是否正在进行 AI 决策，防止并发冲突
deciding_groups = set()
# 记录每个群组是否正在生成回复（防止在生成期间进行新决策）
generating_reply_groups = set()
# 记录每个群最后一次进行黑话挖掘的时间（避免频繁调用）
last_slang_mining_times = {}
# 黑话挖掘最小间隔时间（秒）
SLANG_MINING_INTERVAL = 300  # 5分钟
# 每个群组队列的最大长度（防止内存溢出）
MAX_PENDING_CONTEXTS = 50


async def process_my_logic(
    bot: Bot,
    event: GroupMessageEvent,
    message_id: int,
    text: str,
    llm_text: str,
    normal_images: list[str],
    stickers: list[str],
    flash_images: list[str],
    faces: list[str],
    group_id: int,
    user_id: int,
    nickname: str,
    card: str,
    role: str,
    raw_msg: any,
    reply_message_id: Optional[int] = None,
    message_timestamp: Optional[str] = None,
    target_message_id: Optional[int] = None,
):
    """
    处理消息回复逻辑

    Args:
        reply_message_id: 原始消息中引用的消息 ID（如果用户在引用某条消息）
        target_message_id: 决策引擎选择要回复的消息 ID
    """
    logger.info(f"[process_my_logic] 开始处理 消息ID={message_id}, 群组={group_id}, 目标消息ID={target_message_id}")
    # 标记开始生成回复
    generating_reply_groups.add(group_id)

    try:
        # 消息去重：检查是否已处理过该消息
        # 优先使用 target_message_id（决策引擎选择要回复的消息），如果没有则使用 message_id（触发消息）
        actual_message_id = target_message_id if target_message_id else message_id
        message_key = f"{group_id}:{actual_message_id}"
        if message_key in processed_messages:
            logger.info(f"[消息去重] 消息 {actual_message_id} (目标消息) 已处理过，跳过重复回复")
            return

        logger.info(f"[消息去重] 消息 {actual_message_id} 未处理，加入已处理集合")
        processed_messages.add(message_key)

        # 定期清理旧的消息 ID，防止内存泄漏（保留最近 10000 条）
        if len(processed_messages) > 10000:
            # 保留最近的一半
            old_list = list(processed_messages)
            processed_messages.clear()
            processed_messages.update(old_list[-5000:])

        reply_data = await get_chat_reply(
            group_id,
            card,
            llm_text,
            user_id=user_id,
            reply_message_id=reply_message_id,
            bot=bot,
            message_timestamp=message_timestamp,
        )
        reply_text = reply_data.get("text")
        sticker_url = reply_data.get("sticker")

        current_time = time.time()
        if reply_text and ("无法回复" in reply_text or "异常" in reply_text or "超时" in reply_text):
            if (
                hasattr(process_my_logic, "_last_error_message")
                and process_my_logic._last_error_message == reply_text
                and hasattr(process_my_logic, "_last_error_time")
                and current_time - process_my_logic._last_error_time < 30
            ):
                logger.warning(f"检测到重复错误消息，跳过发送: {reply_text}")
                return

            process_my_logic._last_error_message = reply_text
            process_my_logic._last_error_time = current_time

        if reply_text or sticker_url:
            if reply_text:
                # 清理引用格式后再存储，避免AI模仿
                clean_reply = clean_reply_format(reply_text)
                await db_manager.add_chat_log(group_id, f"self:{clean_reply}")

            is_reply = False
            if reply_text and "[回复]" in reply_text:
                is_reply = True
                # 清理AI可能模仿的引用格式 [回复@名字:内容]
                reply_text = clean_reply_format(reply_text)
                reply_text = reply_text.replace("[回复]", "").strip()

            # 确定引用消息 ID（优先级从高到低）
            # 1. target_message_id: 决策引擎选择要回复的消息 ID（最准确）
            # 2. reply_message_id: 用户原始消息中引用的消息 ID
            # 3. message_id: 当前触发消息的 ID（兜底）
            actual_reply_id = target_message_id or reply_message_id or message_id
            logger.debug(
                f"[引用ID] target_message_id={target_message_id}, reply_message_id={reply_message_id}, message_id={message_id} -> actual_reply_id={actual_reply_id}"
            )

            # 如果决策引擎选择了没有 message_id 的旧消息，则不使用引用
            use_reply = is_reply and target_message_id is not None

            if reply_text:
                segments = split_text_to_segments(reply_text)
                for i, seg in enumerate(segments):
                    msg_segments = []

                    if i == 0:
                        if use_reply:
                            msg_segments.append(MessageSegment.reply(actual_reply_id))

                    parts = re.split(r"(\[at:.*?\])", seg)
                    for part in parts:
                        if part.startswith("[at:") and part.endswith("]"):
                            target_name = part[4:-1].strip()
                            target_id = await db_manager.get_user_id_by_name(group_id, target_name)
                            if target_id:
                                msg_segments.append(MessageSegment.at(target_id))
                            else:
                                msg_segments.append(MessageSegment.text(f"@{target_name}"))
                        elif part:
                            msg_segments.append(MessageSegment.text(part))

                    if msg_segments:
                        await bot.send(event, Message(msg_segments), at_sender=False)

                    if i < len(segments) - 1 or sticker_url:
                        delay = min(1.5, max(0.3, len(seg) * 0.08))
                        await asyncio.sleep(delay + random.uniform(0.1, 0.5))

            if sticker_url:
                try:
                    await bot.send(event, MessageSegment.image(sticker_url), at_sender=False)
                    logger.info(f"成功发送表情包: {sticker_url[:50]}...")
                except Exception as e:
                    logger.warning(f"发送表情包失败: {e}, URL: {sticker_url[:50]}...")
                    # 如果是临时链接导致的失败，删除缓存中的该表情包
                    if sticker_url.startswith("http"):
                        # 获取标签，然后删除相关的表情包缓存
                        sticker_pattern = r"\[\s*表情\s*[:：]\s*(.*?)\s*\]"
                        match = re.search(sticker_pattern, reply_text)
                        if match:
                            tag = match.group(1).strip()
                            logger.warning(f"表情包 '{tag}' 的 URL 已失效，将从缓存中移除")
                            # TODO: 可以在这里添加删除过期表情包的逻辑

            logger.info(f"[{role}] {card}({user_id}) 唤醒了{bot_config.bot_name}")
            logger.debug(f"清洗后文本 (LLM): {llm_text}")
            logger.debug(f"{bot_config.bot_name}回复: {reply_text}")

    except Exception as e:
        error_msg = str(e)
        try:
            error_type = type(e).__name__
        except:
            error_type = "Exception"
        logger.error(f"处理消息时发生异常 [{error_type}]", extra={"error_msg": error_msg}, exc_info=True)
    finally:
        # 回复处理完成，移除生成状态并更新冷却时间
        generating_reply_groups.discard(group_id)
        last_decision_times[group_id] = time.time()
        logger.debug(f"群组 {group_id} 回复完成，冷却时间已更新")


async def deferred_decision_worker(group_id: int, bot: Bot):
    """
    延迟决策工人：等待冷却期结束并执行决策
    使用队列机制确保每个消息独立处理，防止并发竞态
    """
    try:
        while True:
            last_time = last_decision_times.get(group_id, 0)
            now = time.time()
            remaining = bot_config.decision_interval - (now - last_time)

            if remaining <= 0:
                # 冷却期已过，检查是否有待处理消息
                # 确保当前没有正在进行的决策，也没有正在生成的回复
                logger.debug(
                    f"[延迟工人] 群{group_id} 冷却期已过，pending={pending_decisions.get(group_id)}, "
                    f"deciding={group_id in deciding_groups}, generating={group_id in generating_reply_groups}"
                )
                if (
                    pending_decisions.get(group_id)
                    and group_id not in deciding_groups
                    and group_id not in generating_reply_groups
                ):
                    # 从队列中获取最早的消息上下文（FIFO）
                    ctx = None
                    if group_id in group_pending_contexts and group_pending_contexts[group_id]:
                        ctx = group_pending_contexts[group_id][0]  # 查看队首元素但不移除

                    if ctx:
                        # 标记为已处理，防止重复触发
                        pending_decisions[group_id] = False
                        deciding_groups.add(group_id)

                        try:
                            # 判断是否包含表情包
                            is_sticker_msg = len(ctx.get("stickers", [])) > 0

                            # 执行决策（注意：不在此时更新冷却时间，而是在回复完成后更新）
                            decision = await should_i_reply(
                                group_id,
                                ctx["display_name"],
                                ctx["llm_text"],
                                is_at_me=False,
                                user_id=ctx["user_id"],
                                is_sticker=is_sticker_msg,
                            )

                            # 更新心情
                            mood_impact = decision.get("mood_impact", 0)
                            if mood_impact != 0:
                                await db_manager.update_mood(group_id, mood_impact)

                            # 只有 should_reply 为 True 且兴趣度足够高时才回复
                            interest_score = decision.get("interest_score", 0)
                            should_reply_flag = decision.get("should_reply")
                            logger.info(
                                f"[延迟工人-决策判断] should_reply={should_reply_flag}, "
                                f"interest_score={interest_score}, threshold={bot_config.interest_threshold}"
                            )
                            if should_reply_flag and interest_score >= bot_config.interest_threshold:
                                logger.info(f"[延迟工人-进入回复分支] 准备记录回复行为")
                                # 记录 bot 回复行为
                                await db_manager.record_bot_reply(
                                    group_id, ctx["display_name"], is_at_bot=False, interest_score=interest_score
                                )
                                logger.info(f"[延迟工人-回复行为已记录] 准备从队列移除消息")
                                # 从队列中移除已处理的消息
                                if group_id in group_pending_contexts and group_pending_contexts[group_id]:
                                    group_pending_contexts[group_id].popleft()
                                    logger.info(
                                        f"[延迟工人-消息已移除] 队列剩余: {len(group_pending_contexts[group_id])}"
                                    )

                                # 执行回复逻辑
                                selected_user = decision.get("selected_user", ctx["display_name"])  # 选定消息的发送者
                                target_user = decision.get("reply_to_user", selected_user)  # AI选择的回复对象
                                target_msg = decision.get("target_message_content", ctx["llm_text"])
                                target_msg_id = decision.get("target_message_id")  # 获取决策引擎选择的message_id
                                logger.info(
                                    f"[延迟工人-准备调用process_my_logic] 消息ID={ctx['message_id']}, 目标消息ID={target_msg_id}"
                                )
                                await process_my_logic(
                                    bot=bot,
                                    event=ctx["event"],
                                    message_id=ctx["message_id"],
                                    text=ctx["text"],
                                    llm_text=target_msg,  # 使用 AI 选择的消息内容(纯文本,不含用户名)
                                    normal_images=ctx["normal_images"],
                                    stickers=ctx["stickers"],
                                    flash_images=ctx["flash_images"],
                                    faces=ctx["faces"],
                                    group_id=group_id,
                                    user_id=ctx["user_id"],
                                    nickname=ctx["nickname"],
                                    card=selected_user,  # 使用选定消息的发送者作为回复对象
                                    role=ctx["role"],
                                    raw_msg=ctx["raw_msg"],
                                    reply_message_id=ctx.get("reply_message_id"),  # 传递引用消息 ID
                                    message_timestamp=ctx.get("timestamp"),  # 传递时间戳
                                    target_message_id=target_msg_id,  # 传递决策引擎选择的message_id
                                )
                            # 即使 AI 决定不回复，也有一定概率随机回复
                            elif random.random() < bot_config.reply_rate:
                                await db_manager.record_bot_reply(
                                    group_id, ctx["display_name"], is_at_bot=False, interest_score=0.2
                                )
                                # 从队列中移除已处理的消息
                                if group_id in group_pending_contexts and group_pending_contexts[group_id]:
                                    group_pending_contexts[group_id].popleft()

                                await process_my_logic(
                                    bot=bot,
                                    event=ctx["event"],
                                    message_id=ctx["message_id"],
                                    text=ctx["text"],
                                    llm_text=ctx["llm_text"],
                                    normal_images=ctx["normal_images"],
                                    stickers=ctx["stickers"],
                                    flash_images=ctx["flash_images"],
                                    faces=ctx["faces"],
                                    group_id=group_id,
                                    user_id=ctx["user_id"],
                                    nickname=ctx["nickname"],
                                    card=ctx["display_name"],
                                    role=ctx["role"],
                                    raw_msg=ctx["raw_msg"],
                                    reply_message_id=ctx.get("reply_message_id"),
                                    message_timestamp=ctx.get("timestamp"),
                                )
                            else:
                                # AI 决定不回复，从队列中移除该消息
                                logger.info(f"[延迟工人-不回复] 未满足回复条件或兴趣度不足，更新冷却时间")
                                if group_id in group_pending_contexts and group_pending_contexts[group_id]:
                                    group_pending_contexts[group_id].popleft()
                                # 即使不回复，也要更新冷却时间，避免频繁调用决策引擎
                                last_decision_times[group_id] = time.time()
                        finally:
                            deciding_groups.remove(group_id)
                else:
                    # 队列为空或正在处理，等待下次检查
                    pass
            else:
                # 还在冷却期，等待剩余时间
                await asyncio.sleep(min(remaining, 1.0))

                # 如果队列为空，退出延迟决策任务
                if group_id in group_pending_contexts and len(group_pending_contexts[group_id]) == 0:
                    break

                continue

            # 检查队列是否为空，为空则退出
            if group_id in group_pending_contexts and len(group_pending_contexts[group_id]) == 0:
                break

            # 短暂休眠避免 CPU 占用
            await asyncio.sleep(0.1)

    except asyncio.CancelledError:
        logger.debug(f"群组 {group_id} 的延迟决策任务被取消")
    except Exception as e:
        logger.opt(exception=True).error(f"群组 {group_id} 的延迟决策任务发生异常: {e}")
    finally:
        # 清理任务记录
        if group_id in active_deferred_tasks:
            del active_deferred_tasks[group_id]


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
        return  # 黑名单群组直接忽略

    if bot_config.allowed_groups and group_id not in bot_config.allowed_groups:
        return  # 不在白名单中的群组直接忽略

    # 1. 基础信息
    message_id = event.message_id  # 消息 ID
    message_text = event.get_plaintext()  # 纯文本内容
    group_id = event.group_id  # 群号
    user_id = event.user_id  # 发送者 QQ 号

    # 2. 发送者详细信息
    sender = event.sender
    nickname = sender.nickname
    card = sender.card or nickname
    # 使用全局昵称作为 AI 识别的名称，因为群名片更改太频繁
    display_name = nickname
    role = sender.role

    # 3. 提取各种消息段
    normal_images = []  # 普通图片 URL
    stickers = []  # 表情包 URL (sub_type=1)
    flash_images = []  # 闪照 URL (type=flash)
    faces = []  # 系统表情 ID (例如: 124 代表 [呲牙])
    reply_message_id = None  # 引用消息 ID

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

        # 处理引用消息
        elif segment.type == "reply":
            reply_message_id = segment.data.get("message_id")
            if reply_message_id:
                logger.debug(f"检测到引用消息: {reply_message_id}")

    # 4. 原始消息对象
    raw_message = event.get_message()

    # 5. 生成供 LLM 使用的清洗后文本
    llm_text = await process_message_for_llm(bot, event, vlm_func=get_vlm_description)

    # 清理QQ引用格式，避免AI模仿
    llm_text = clean_reply_format(llm_text)

    # 6. 存入数据库 (格式: "名字:内容")
    msg_to_store = f"{display_name}:{llm_text}"
    await db_manager.add_chat_log(group_id, msg_to_store, message_id=message_id)

    # 6.5 确保群组中存在创造者的记忆
    try:
        from src.utils.init_memory import initialize_creator_memory

        asyncio.create_task(create_limited_task(initialize_creator_memory(group_id)))
    except Exception as e:
        logger.debug(f"确保创造者记忆时出错: {e}")

    # 更新用户名与 ID 的映射，用于后续艾特功能
    # 同时存储群名片和 QQ 昵称，增加匹配成功率
    await db_manager.update_user_id_map(group_id, nickname, user_id)
    if sender.card and sender.card != nickname:
        await db_manager.update_user_id_map(group_id, sender.card, user_id)

    # 同步写入向量数据库 (长期记忆)
    # 使用 create_task 异步处理，不影响当前响应速度
    async def store_and_consolidate():
        try:
            # 1. 存入原始向量记录
            vectors = await get_embeddings([msg_to_store])
            await vector_db.add_memory(group_id, msg_to_store, vectors[0])

            # 2. 性格进化与好感度更新
            await personality_manager.evolve_personality(group_id, display_name, llm_text, user_id=user_id)

            # 3. 实时模仿与黑话挖掘 (采样最近 20 条历史)
            history = await db_manager.get_chat_log(group_id, limit=20)
            history_messages = [entry["message"] for entry in history]
            asyncio.create_task(
                create_limited_task(personality_manager.capture_style_patterns(group_id, history_messages))
            )

            # 黑话挖掘：限制调用频率，避免超时和API压力
            last_mining_time = last_slang_mining_times.get(group_id, 0)
            if time.time() - last_mining_time >= SLANG_MINING_INTERVAL:
                last_slang_mining_times[group_id] = time.time()
                asyncio.create_task(create_limited_task(personality_manager.mine_slang(group_id, history_messages)))
                logger.debug(f"群 {group_id} 触发黑话挖掘分析")
            else:
                logger.debug(f"群 {group_id} 黑话挖掘冷却中，跳过本次调用")

            # 4. 尝试进行记忆固化 (每 50 条消息处理一次)
            await consolidate_memories(group_id)
        except Exception as e:
            logger.opt(exception=True).error("处理背景学习逻辑失败: {}", e)

    asyncio.create_task(create_limited_task(store_and_consolidate()))

    # 获取当前消息时间戳（用于历史记录过滤）
    current_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 7. 唤醒逻辑判断
    is_at_me = "@self" in llm_text or event.is_tome()
    is_mentioned = bot_config.bot_name in message_text
    is_actively_engaged = is_at_me or is_mentioned

    # 将当前消息上下文加入待处理队列（用于并发安全的延迟决策）
    # 注意：只有非艾特消息才加入延迟队列，因为艾特消息会立即处理
    if not is_actively_engaged:
        if group_id not in group_pending_contexts:
            group_pending_contexts[group_id] = deque(maxlen=MAX_PENDING_CONTEXTS)

        message_context = {
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
            "raw_msg": raw_message,
            "reply_message_id": reply_message_id,
            "timestamp": current_timestamp,
        }
        group_pending_contexts[group_id].append(message_context)

    do_reply = False
    target_user = display_name

    # 判断是否包含表情包
    is_sticker_msg = len(stickers) > 0

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
                # 执行决策评估心情（注意：不在此时更新冷却时间，而是在回复完成后更新）
                decision = await should_i_reply(
                    group_id, display_name, llm_text, is_at_me=True, user_id=user_id, is_sticker=is_sticker_msg
                )

                # 实时更新心情 (只要决策引擎运行，就应用心情变动，无论是否决定回复)
                mood_impact = decision.get("mood_impact", 0)
                if mood_impact != 0:
                    await db_manager.update_mood(group_id, mood_impact)

                do_reply = True
                target_user = decision.get("reply_to_user", display_name)
                target_msg = decision.get("target_message_content", llm_text)  # 使用 AI 选择的消息内容
                target_msg_id = decision.get("target_message_id")  # 获取决策引擎选择的message_id
                # 记录被艾特时的回复行为
                interest_score = decision.get("interest_score", 0.8)
                await db_manager.record_bot_reply(group_id, display_name, is_at_bot=True, interest_score=interest_score)
            finally:
                deciding_groups.remove(group_id)
    else:
        # 2. 没被叫到，尝试进行 AI 智能决策
        # 首先检查当前是否在"作息表"允许的水群时间内
        if not await is_within_chat_time(group_id):
            return  # 不在水群时间，且没被叫到，直接忽略

        current_time = time.time()
        last_time = last_decision_times.get(group_id, 0)

        if current_time - last_time >= bot_config.decision_interval:
            # 过了冷却期，直接触发决策判断
            # 确保当前没有正在进行的决策，也没有正在生成的回复
            if group_id not in deciding_groups and group_id not in generating_reply_groups:
                deciding_groups.add(group_id)
                try:
                    pending_decisions[group_id] = False

                    # 执行决策（注意：不在此时更新冷却时间，而是在回复完成后更新）
                    decision = await should_i_reply(
                        group_id, display_name, llm_text, is_at_me=False, user_id=user_id, is_sticker=is_sticker_msg
                    )

                    # 实时更新心情 (只要决策引擎运行，就应用心情变动，无论是否决定回复)
                    mood_impact = decision.get("mood_impact", 0)
                    if mood_impact != 0:
                        await db_manager.update_mood(group_id, mood_impact)

                    # 只有 should_reply 为 True 且兴趣度足够高时才回复 (避免随意插话)
                    interest_score = decision.get("interest_score", 0)
                    logger.info(
                        f"[决策判断] should_reply={decision.get('should_reply', False)}, "
                        f"interest_score={interest_score}, threshold={bot_config.interest_threshold}, "
                        f"is_at_me={is_at_me}"
                    )
                    if decision.get("should_reply", False) and interest_score >= bot_config.interest_threshold:
                        do_reply = True
                        logger.info(f"[触发回复] 兴趣度 {interest_score} >= 阈值 {bot_config.interest_threshold}")
                        # 记录回复行为
                        await db_manager.record_bot_reply(
                            group_id, display_name, is_at_bot=False, interest_score=interest_score
                        )
                    # 即使 AI 决定不回复，也有一定概率随机回复
                    elif random.random() < bot_config.reply_rate:
                        do_reply = True
                        logger.info(f"[随机回复] 触发随机回复")
                        await db_manager.record_bot_reply(
                            group_id, display_name, is_at_bot=False, interest_score=bot_config.interest_threshold
                        )
                    else:
                        logger.info(f"[不回复] 未满足回复条件，更新冷却时间")
                        do_reply = False
                        # 即使不回复，也要更新冷却时间，避免频繁调用决策引擎
                        last_decision_times[group_id] = time.time()

                    selected_user = decision.get("selected_user", display_name)  # 选定消息的发送者
                    target_user = decision.get("reply_to_user", selected_user)  # AI选择的回复对象
                    target_msg = decision.get("target_message_content", llm_text)  # 使用 AI 选择的消息内容(纯文本)
                    target_msg_id = decision.get("target_message_id")  # 获取决策引擎选择的message_id
                finally:
                    deciding_groups.remove(group_id)
        else:
            # 还在冷却期内，只要有消息就标记为"待处理"，确保冷却结束后一定会判断
            pending_decisions[group_id] = True
            remaining_time = bot_config.decision_interval - (current_time - last_time)
            logger.info(f"[冷却中] 群{group_id} 剩余冷却时间 {remaining_time:.1f}秒，已加入延迟决策队列")

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
        llm_text=target_msg,  # 使用 AI 选择的消息内容进行回复
        normal_images=normal_images,
        stickers=stickers,
        flash_images=flash_images,
        faces=faces,
        group_id=group_id,
        user_id=user_id,
        nickname=nickname,
        card=target_user,  # 使用决策引擎确定的目标用户
        role=role,
        raw_msg=raw_message,
        reply_message_id=reply_message_id,  # 传递引用消息 ID
        message_timestamp=current_timestamp,  # 传递时间戳用于历史记录过滤
        target_message_id=target_msg_id,  # 传递决策引擎选择的message_id
    )
