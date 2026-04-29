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
from src.aimodel.decision.decide import should_i_reply, should_i_scan_join
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

# 风格捕捉计数器：每N条消息触发一次（避免每条消息都调用AI）
STYLE_CAPTURE_INTERVAL = 10  # 可调整，建议5-10
style_capture_counters: dict[int, int] = {}


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


def extract_user_name(event: GroupMessageEvent) -> str:
    """从事件中提取最佳用户名"""
    if event.sender.card and event.sender.card.strip():
        return event.sender.card.strip()
    if event.sender.nickname and event.sender.nickname.strip():
        return event.sender.nickname.strip()
    return str(event.user_id)


async def is_within_chat_time(group_id: int) -> bool:
    """检查当前是否在作息表允许的水群时间内"""
    if not bot_config.enable_schedule:
        return True

    try:
        schedule = await db_manager.get_group_schedule(group_id)
        if not schedule:
            return True  # 无作息表 → 默认允许
    except Exception as e:
        logger.warning(f"获取作息表失败: {e}")
        return True  # 出错时默认允许

    current_time_str = datetime.datetime.now().strftime("%H:%M")
    for period in schedule:
        can_chat = period.get("can_chat", False)
        start = period.get("start")
        end = period.get("end")
        if start and end and can_chat and start <= current_time_str <= end:
            return True

    return False


async def create_limited_task(coro):
    """
    创建受并发和速率限制的任务
    """
    await task_rate_limiter.wait_for_slot()
    async with task_concurrency_limiter:
        return await coro


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
# 每个群组队列的最大长度（防止内存溢出）
MAX_PENDING_CONTEXTS = 50
# 扫描模式：记录每个群最后一次扫描的时间（模块级，避免协程重启丢失）
last_scan_times: dict[int, float] = {}
# 扫描最小间隔（秒，两次扫描之间至少隔这么久）
SCAN_MIN_INTERVAL = 600
# 触发扫描的最小队列积压条数
SCAN_MIN_QUEUE_SIZE = 5
# 扫描模式：每小时最多触发几次扫描（防止高频重扫）
hourly_scan_counts: dict[int, tuple[float, int]] = {}  # group_id → (小时起始时间戳, 次数)
SCAN_MAX_PER_HOUR = 2


class GroupLockManager:
    """
    群组锁管理器：使用 asyncio.Lock 为每个群组提供互斥访问
    避免竞态条件和并发冲突
    """

    def __init__(self):
        self._locks: dict[int, asyncio.Lock] = {}

    def _get_lock(self, group_id: int) -> asyncio.Lock:
        if group_id not in self._locks:
            self._locks[group_id] = asyncio.Lock()
        return self._locks[group_id]

    async def acquire(self, group_id: int, timeout: float = 30.0) -> bool:
        lock = self._get_lock(group_id)
        try:
            await asyncio.wait_for(lock.acquire(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def release(self, group_id: int):
        lock = self._get_lock(group_id)
        if lock.locked():
            lock.release()


group_lock_manager = GroupLockManager()


async def process_my_logic(
    bot: Bot,
    event: GroupMessageEvent,
    message_id: int,
    text: str,
    llm_text: str,
    normal_images: list,
    stickers: list,
    flash_images: list,
    faces: list,
    group_id: int,
    user_id: int,
    nickname: str,
    card: str,
    role: str,
    raw_msg: str,
    reply_message_id: Optional[int] = None,
    message_timestamp: Optional[str] = None,
    target_message_id: Optional[int] = None,
) -> None:
    """
    执行机器人回复逻辑的核心函数。
    使用群组锁防止同一群组的并发回复。
    """
    lock_acquired = await group_lock_manager.acquire(group_id, timeout=60.0)
    if not lock_acquired:
        logger.warning(f"群组 {group_id} 获取回复锁失败，跳过")
        return

    generating_reply_groups.add(group_id)
    try:
        user_name = card or nickname or str(user_id)

        logger.info(
            f"[回复] 群{group_id} 准备调用 AI 回复: "
            f"用户={user_name}, 目标消息ID={target_message_id}, 原始消息ID={message_id}"
        )

        reply_data = await get_chat_reply(
            group_id=group_id,
            user_name=user_name,
            current_msg=llm_text,
            user_id=user_id,
            reply_message_id=reply_message_id,
            bot=bot,
            message_timestamp=message_timestamp,
        )

        reply_text = reply_data.get("text") if reply_data else None
        sticker_url = reply_data.get("sticker") if reply_data else None

        if not reply_text and not sticker_url:
            logger.warning(f"群组 {group_id} AI 返回空回复")
            return

        logger.info(f"[回复] 群{group_id} AI 回复内容: {(reply_text or '')[:50]}...")

        if reply_text:
            clean_reply = clean_reply_format(reply_text)
            await db_manager.add_chat_log(group_id, f"self:{clean_reply}")

        # 检测 [回复] 标签 → 转换为真实 QQ 引用回复
        is_reply = False
        if reply_text and "[回复]" in reply_text:
            is_reply = True
            reply_text = clean_reply_format(reply_text)
            reply_text = reply_text.replace("[回复]", "").strip()

        # 确定引用消息 ID（优先级：决策选择 > 用户引用 > 当前消息）
        actual_reply_id = target_message_id or reply_message_id or message_id
        logger.debug(
            f"[引用ID] target={target_message_id}, reply={reply_message_id}, "
            f"msg={message_id} → actual={actual_reply_id}"
        )
        use_reply = is_reply and target_message_id is not None

        # 文字回复：按换行分段，每段独立发送
        if reply_text:
            text_segments = split_text_to_segments(reply_text)
            for i, seg in enumerate(text_segments):
                msg_segments = []

                # 仅第一段带引用标记
                if i == 0:
                    if use_reply:
                        msg_segments.append(MessageSegment.reply(actual_reply_id))

                # [at:用户名] → 真实 @
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

                # 多段消息之间延时
                if i < len(text_segments) - 1 or sticker_url:
                    delay = min(1.5, max(0.3, len(seg) * 0.08))
                    await asyncio.sleep(delay + random.uniform(0.1, 0.5))

        # 表情包发送
        if sticker_url:
            try:
                await bot.send(event, MessageSegment.image(sticker_url), at_sender=False)
                logger.info(f"成功发送表情包: {sticker_url[:50]}...")
            except Exception as e:
                logger.warning(f"发送表情包失败: {e}, URL: {sticker_url[:50]}...")
                logger.debug(f"表情包发送失败，URL可能已过期")

        logger.info(f"群组 {group_id} 回复完成")

        # 触发记忆固化
        asyncio.create_task(consolidate_memories(group_id))

    except Exception as e:
        logger.opt(exception=True).error(f"群组 {group_id} 回复出错: {type(e).__name__}: {e}")
    finally:
        generating_reply_groups.discard(group_id)
        last_decision_times[group_id] = time.time()
        group_lock_manager.release(group_id)
        logger.debug(f"群组 {group_id} 回复完成，锁已释放，冷却时间已更新")


async def _check_bot_left_recently(group_id: int, history_messages: list[str]) -> bool:
    """
    判断 bot 是否"离开较久"，值得触发扫描

    检查历史消息中 bot 是否发言过。
    如果完全没有 bot 的发言记录 → bot 离开较久 → 应该扫描
    """
    bot_name = bot_config.bot_name
    for msg in history_messages:
        if msg.startswith(f"{bot_name}:") or msg.startswith(f"{bot_name} "):
            return False
    return True


async def deferred_decision_worker(group_id: int, bot: Bot):
    """
    延迟决策工人：等待冷却期结束并执行决策
    使用队列机制确保每个消息独立处理，防止并发竞态

    新增扫描模式：当冷却结束 + 积压多条消息 + bot 离开较久时，
    先用扫描模式批量判断是否有值得加入的话题，而非逐条调用 AI
    """
    try:
        while True:
            last_time = last_decision_times.get(group_id, 0)
            now = time.time()
            remaining = bot_config.decision_interval - (now - last_time)

            if remaining <= 0:
                logger.debug(
                    f"[延迟工人] 群{group_id} 冷却期已过，pending={pending_decisions.get(group_id)}, "
                    f"deciding={group_id in deciding_groups}, generating={group_id in generating_reply_groups}"
                )
                if (
                    pending_decisions.get(group_id)
                    and group_id not in deciding_groups
                    and group_id not in generating_reply_groups
                ):
                    queue = list(group_pending_contexts.get(group_id, []))
                    if not queue:
                        pass
                    else:
                        # 判断是否应该触发扫描模式
                        # 条件1: 积压 ≥ SCAN_MIN_QUEUE_SIZE 条
                        # 条件2: 距离上次扫描 ≥ SCAN_MIN_INTERVAL 秒
                        # 条件3: 本小时扫描次数 < SCAN_MAX_PER_HOUR
                        # 条件4: bot 最近历史中发言占比 < 20%（离开较久）
                        # 条件5: 心情不低于最低阈值（心情差时不扫描）
                        last_scan_time = last_scan_times.get(group_id, 0)
                        should_scan = (
                            len(queue) >= SCAN_MIN_QUEUE_SIZE
                            and (now - last_scan_time) >= SCAN_MIN_INTERVAL
                        )

                        if should_scan:
                            # 检查每小时扫描上限
                            hour_start = int(now // 3600) * 3600
                            if group_id in hourly_scan_counts:
                                prev_hour_start, count = hourly_scan_counts[group_id]
                                if prev_hour_start != hour_start:
                                    count = 0
                            else:
                                count = 0
                            if count >= SCAN_MAX_PER_HOUR:
                                should_scan = False
                                logger.debug(
                                    f"[扫描条件] 群{group_id} 本小时已扫描{count}次≥上限{SCAN_MAX_PER_HOUR}，不触发"
                                )

                        if should_scan:
                            # 检查心情（心情过低时不扫描）
                            try:
                                mood = await db_manager.get_mood(group_id)
                            except Exception:
                                mood = 50
                            SCAN_MOOD_MIN = 35
                            if mood < SCAN_MOOD_MIN:
                                should_scan = False
                                logger.debug(
                                    f"[扫描条件] 群{group_id} 心情{mood} < {SCAN_MOOD_MIN}，不触发扫描"
                                )

                        if should_scan:
                            # 提前查一次历史，复用
                            try:
                                history = await db_manager.get_chat_log(group_id, limit=20)
                                history_messages = []
                                for item in history:
                                    clean_msg = clean_reply_format(item["message"])
                                    history_messages.append(clean_msg)
                            except Exception:
                                history_messages = []

                            should_scan = await _check_bot_left_recently(group_id, history_messages)

                        if should_scan:
                            logger.info(f"[扫描模式] 群{group_id} 积压{len(queue)}条消息，bot离开较久，触发扫描决策")
                            last_scan_times[group_id] = now
                            # 记录本小时扫描次数
                            hour_start = int(now // 3600) * 3600
                            if group_id not in hourly_scan_counts or hourly_scan_counts[group_id][0] != hour_start:
                                hourly_scan_counts[group_id] = (hour_start, 1)
                            else:
                                prev_hour, prev_count = hourly_scan_counts[group_id]
                                hourly_scan_counts[group_id] = (prev_hour, prev_count + 1)
                            pending_decisions[group_id] = False
                            deciding_groups.add(group_id)

                            try:
                                scan_decision = await should_i_scan_join(group_id, queue, history_messages)

                                mood_impact = scan_decision.get("mood_impact", 0)
                                if mood_impact != 0:
                                    await db_manager.update_mood(group_id, mood_impact)

                                if scan_decision.get("should_reply"):
                                    ctx = scan_decision.get("target_context", queue[-1])
                                    logger.info(
                                        f"[扫描模式-加入] 理由: {scan_decision.get('reason')} "
                                        f"回复: {ctx.get('display_name')}"
                                    )

                                    decision = {
                                        "should_reply": True,
                                        "mood_impact": mood_impact,
                                        "interest_score": scan_decision.get("interest_score", 0.5),
                                        "selected_user": scan_decision.get("reply_to_user", ctx.get("display_name")),
                                        "reply_to_user": scan_decision.get("reply_to_user", ctx.get("display_name")),
                                        "target_message_content": ctx.get("llm_text", ""),
                                        "target_message_id": ctx.get("message_id"),
                                    }

                                    await db_manager.record_bot_reply(
                                        group_id,
                                        ctx.get("display_name", "未知"),
                                        is_at_bot=False,
                                        interest_score=decision["interest_score"],
                                    )

                                    # 清空队列，但保留提到 bot 名字的消息（防止误丢）
                                    _safe_clear_queue(group_id, bot_config.bot_name)

                                    # 更新冷却时间（防止回复后立即再次触发）
                                    last_decision_times[group_id] = time.time()

                                    await process_my_logic(
                                        bot=bot,
                                        event=ctx["event"],
                                        message_id=ctx["message_id"],
                                        text=ctx["text"],
                                        llm_text=decision["target_message_content"],
                                        normal_images=ctx["normal_images"],
                                        stickers=ctx["stickers"],
                                        flash_images=ctx["flash_images"],
                                        faces=ctx["faces"],
                                        group_id=group_id,
                                        user_id=ctx["user_id"],
                                        nickname=ctx["nickname"],
                                        card=decision["selected_user"],
                                        role=ctx["role"],
                                        raw_msg=ctx["raw_msg"],
                                        reply_message_id=ctx.get("reply_message_id"),
                                        message_timestamp=ctx.get("timestamp"),
                                        target_message_id=decision.get("target_message_id"),
                                    )
                                else:
                                    logger.info(
                                        f"[扫描模式-不加入] 理由: {scan_decision.get('reason')}，"
                                        f"清空{len(queue)}条消息"
                                    )
                                    _safe_clear_queue(group_id, bot_config.bot_name)
                                    last_decision_times[group_id] = time.time()
                            finally:
                                deciding_groups.discard(group_id)
                            continue

                        # ===== 常规逐条处理模式 =====
                        ctx = queue[0]
                        pending_decisions[group_id] = False
                        deciding_groups.add(group_id)

                        try:
                            is_sticker_msg = len(ctx.get("stickers", [])) > 0

                            decision = await should_i_reply(
                                group_id,
                                ctx["display_name"],
                                ctx["llm_text"],
                                is_at_me=False,
                                user_id=ctx["user_id"],
                                is_sticker=is_sticker_msg,
                            )

                            mood_impact = decision.get("mood_impact", 0)
                            if mood_impact != 0:
                                await db_manager.update_mood(group_id, mood_impact)

                            interest_score = decision.get("interest_score", 0)
                            should_reply_flag = decision.get("should_reply")
                            logger.info(
                                f"[延迟工人-决策判断] should_reply={should_reply_flag}, "
                                f"interest_score={interest_score}, threshold={bot_config.interest_threshold}"
                            )
                            if should_reply_flag and interest_score >= bot_config.interest_threshold:
                                logger.info(f"[延迟工人-进入回复分支] 准备记录回复行为")
                                await db_manager.record_bot_reply(
                                    group_id, ctx["display_name"], is_at_bot=False, interest_score=interest_score
                                )
                                logger.info(f"[延迟工人-回复行为已记录] 准备从队列移除消息")
                                if group_id in group_pending_contexts and group_pending_contexts[group_id]:
                                    group_pending_contexts[group_id].popleft()
                                    logger.info(
                                        f"[延迟工人-消息已移除] 队列剩余: {len(group_pending_contexts[group_id])}"
                                    )

                                selected_user = decision.get("selected_user", ctx["display_name"])
                                target_user = decision.get("reply_to_user", selected_user)
                                target_msg = decision.get("target_message_content", ctx["llm_text"])
                                target_msg_id = decision.get("target_message_id")
                                logger.info(
                                    f"[延迟工人-准备调用process_my_logic] 消息ID={ctx['message_id']}, 目标消息ID={target_msg_id}"
                                )
                                await process_my_logic(
                                    bot=bot,
                                    event=ctx["event"],
                                    message_id=ctx["message_id"],
                                    text=ctx["text"],
                                    llm_text=target_msg,
                                    normal_images=ctx["normal_images"],
                                    stickers=ctx["stickers"],
                                    flash_images=ctx["flash_images"],
                                    faces=ctx["faces"],
                                    group_id=group_id,
                                    user_id=ctx["user_id"],
                                    nickname=ctx["nickname"],
                                    card=selected_user,
                                    role=ctx["role"],
                                    raw_msg=ctx["raw_msg"],
                                    reply_message_id=ctx.get("reply_message_id"),
                                    message_timestamp=ctx.get("timestamp"),
                                    target_message_id=target_msg_id,
                                )
                            elif random.random() < bot_config.reply_rate:
                                await db_manager.record_bot_reply(
                                    group_id, ctx["display_name"], is_at_bot=False, interest_score=0.2
                                )
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
                                logger.info(f"[延迟工人-不回复] 未满足回复条件或兴趣度不足，更新冷却时间")
                                if group_id in group_pending_contexts and group_pending_contexts[group_id]:
                                    group_pending_contexts[group_id].popleft()
                                last_decision_times[group_id] = time.time()
                        finally:
                            deciding_groups.discard(group_id)
            else:
                await asyncio.sleep(min(remaining, 1.0))

                if group_id in group_pending_contexts and len(group_pending_contexts[group_id]) == 0:
                    break

                continue

            if group_id in group_pending_contexts and len(group_pending_contexts[group_id]) == 0:
                break

            await asyncio.sleep(0.1)

    except asyncio.CancelledError:
        logger.debug(f"群组 {group_id} 的延迟决策任务被取消")
    except Exception as e:
        logger.opt(exception=True).error(f"群组 {group_id} 的延迟决策任务发生异常: {e}")
    finally:
        if group_id in active_deferred_tasks:
            del active_deferred_tasks[group_id]


def _safe_clear_queue(group_id: int, bot_name: str) -> None:
    """
    安全清空队列：移除所有非活跃消息，但保留提到 bot 名字的消息

    避免因为扫描模式清空队列时误丢"有人提到 bot"的消息
    """
    if group_id not in group_pending_contexts:
        return

    preserved = []
    for ctx in list(group_pending_contexts[group_id]):
        msg_text = ctx.get("llm_text", "")
        if bot_name in msg_text:
            preserved.append(ctx)
            logger.info(f"[队列清理] 保留提及bot的消息: {msg_text[:30]}...")

    group_pending_contexts[group_id].clear()
    for ctx in preserved:
        group_pending_contexts[group_id].append(ctx)

    if preserved:
        logger.info(f"[队列清理] 保留{len(preserved)}条提及bot的消息")
    else:
        logger.info(f"[队列清理] 队列已完全清空")


# 创建一个响应所有消息的响应器
# 因为已经在 bot.py 做了全局过滤，所以这里的 on_message() 实际上只会收到群消息
group_msg_matcher = on_message()


@group_msg_matcher.handle()
async def handle_group_message(bot: Bot, event: GroupMessageEvent):
    """
    当接收到群消息时，NoneBot 会调用这个方法。
    """
    group_id = event.group_id
    logger.debug(f"处理群 {group_id} 的消息")

    # 1. 基础信息
    message_id = event.message_id
    message_text = event.get_plaintext()
    group_id = event.group_id
    user_id = event.user_id

    # 2. 发送者详细信息
    sender = event.sender
    nickname = sender.nickname or ""
    display_name = extract_user_name(event)
    role = sender.role or "member"

    # 3. 消息类型分类
    normal_images = []
    stickers = []
    flash_images = []
    faces = []
    reply_message_id = None

    for segment in event.get_message():
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

        elif segment.type == "face":
            face_id = segment.data.get("id")
            if face_id:
                faces.append(face_id)

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

    # 更新用户名与 ID 的映射
    await db_manager.update_user_id_map(group_id, nickname, user_id)
    if sender.card and sender.card != nickname:
        await db_manager.update_user_id_map(group_id, sender.card, user_id)

    # 同步写入向量数据库 (长期记忆)
    async def store_and_consolidate():
        try:
            vectors = await get_embeddings([msg_to_store])
            await vector_db.add_memory(group_id, msg_to_store, vectors[0])
            await personality_manager.evolve_personality(group_id, display_name, llm_text, user_id=user_id)
            await consolidate_memories(group_id)
        except Exception as e:
            logger.opt(exception=True).error("处理背景学习逻辑失败: {}", e)

    asyncio.create_task(create_limited_task(store_and_consolidate()))

    current_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 7. 唤醒逻辑判断
    is_at_me = "@self" in llm_text or event.is_tome()
    is_mentioned = bot_config.bot_name in message_text
    is_actively_engaged = is_at_me or is_mentioned

    logger.info(
        f"[艾特检测] 群{group_id} is_at_me={is_at_me}, is_mentioned={is_mentioned}, "
        f"is_actively_engaged={is_actively_engaged}, event.is_tome()={event.is_tome()}"
    )

    message_segments = []
    for seg in event.get_message():
        message_segments.append(f"{seg.type}:{seg.data}")
    logger.debug(f"[消息段] 群{group_id} 消息段: {message_segments}")

    # 非艾特消息加入延迟队列
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
    is_sticker_msg = len(stickers) > 0

    if is_actively_engaged:
        logger.info(f"[艾特处理] 群{group_id} 检测到艾特，准备立即处理")
        last_wake_up_times[group_id] = time.time()

        if group_id in active_deferred_tasks:
            active_deferred_tasks[group_id].cancel()
            logger.info(f"[艾特处理] 群{group_id} 取消了延迟决策任务")

        pending_decisions[group_id] = False

        lock_acquired = await group_lock_manager.acquire(group_id, timeout=10.0)
        if not lock_acquired:
            logger.warning(f"[艾特处理] 群 {group_id} 获取锁失败，跳过本次处理")
            return

        deciding_groups.add(group_id)
        try:
            decision = await should_i_reply(
                group_id, display_name, llm_text, is_at_me=True, user_id=user_id, is_sticker=is_sticker_msg
            )

            mood_impact = decision.get("mood_impact", 0)
            if mood_impact != 0:
                await db_manager.update_mood(group_id, mood_impact)

            do_reply = True
            target_user = decision.get("reply_to_user", display_name)
            target_msg = decision.get("target_message_content", llm_text)
            target_msg_id = decision.get("target_message_id")
            interest_score = decision.get("interest_score", 0.8)
            await db_manager.record_bot_reply(group_id, display_name, is_at_bot=True, interest_score=interest_score)
        finally:
            deciding_groups.discard(group_id)
            group_lock_manager.release(group_id)
    else:
        if not await is_within_chat_time(group_id):
            return

        current_time = time.time()
        last_time = last_decision_times.get(group_id, 0)

        if current_time - last_time >= bot_config.decision_interval:
            lock_acquired = await group_lock_manager.acquire(group_id, timeout=30.0)
            if not lock_acquired:
                logger.warning(f"[智能决策] 群 {group_id} 获取锁失败，跳过本次处理")
                return

            deciding_groups.add(group_id)
            try:
                pending_decisions[group_id] = False

                decision = await should_i_reply(
                    group_id, display_name, llm_text, is_at_me=False, user_id=user_id, is_sticker=is_sticker_msg
                )

                mood_impact = decision.get("mood_impact", 0)
                if mood_impact != 0:
                    await db_manager.update_mood(group_id, mood_impact)

                interest_score = decision.get("interest_score", 0)
                logger.info(
                    f"[决策判断] should_reply={decision.get('should_reply', False)}, "
                    f"interest_score={interest_score}, threshold={bot_config.interest_threshold}"
                )
                if decision.get("should_reply", False) and interest_score >= bot_config.interest_threshold:
                    do_reply = True
                    logger.info(f"[触发回复] 兴趣度 {interest_score} >= 阈值 {bot_config.interest_threshold}")
                    await db_manager.record_bot_reply(
                        group_id, display_name, is_at_bot=False, interest_score=interest_score
                    )
                elif random.random() < bot_config.reply_rate:
                    do_reply = True
                    logger.info(f"[随机回复] 触发随机回复")
                    await db_manager.record_bot_reply(
                        group_id, display_name, is_at_bot=False, interest_score=bot_config.interest_threshold
                    )
                else:
                    logger.info(f"[不回复] 未满足回复条件，更新冷却时间")
                    do_reply = False
                    last_decision_times[group_id] = time.time()

                selected_user = decision.get("selected_user", display_name)
                target_user = decision.get("reply_to_user", selected_user)
                target_msg = decision.get("target_message_content", llm_text)
                target_msg_id = decision.get("target_message_id")
            finally:
                deciding_groups.discard(group_id)
                group_lock_manager.release(group_id)
        else:
            pending_decisions[group_id] = True
            remaining_time = bot_config.decision_interval - (current_time - last_time)
            logger.info(f"[冷却中] 群{group_id} 剩余冷却时间 {remaining_time:.1f}秒，已加入延迟决策队列")

            if group_id not in active_deferred_tasks:
                task = asyncio.create_task(deferred_decision_worker(group_id, bot))
                active_deferred_tasks[group_id] = task

    if not do_reply:
        return

    await process_my_logic(
        bot=bot,
        event=event,
        message_id=message_id,
        text=message_text,
        llm_text=target_msg,
        normal_images=normal_images,
        stickers=stickers,
        flash_images=flash_images,
        faces=faces,
        group_id=group_id,
        user_id=user_id,
        nickname=nickname,
        card=target_user,
        role=role,
        raw_msg=raw_message,
        reply_message_id=reply_message_id,
        message_timestamp=current_timestamp,
        target_message_id=target_msg_id,
    )
