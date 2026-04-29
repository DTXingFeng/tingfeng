"""
回复预过滤器 - 在调用 AI 决策前用规则快速判断是否应跳过
减少不必要的 AI API 调用，降低 token 消耗

两种模式：
- 被动模式（每收到一条消息触发）：严格过滤，减少不必要的 AI 调用
- 扫描模式（bot 主动回看群聊时触发）：放宽限制，允许 bot 寻找感兴趣的话题
"""

from dataclasses import dataclass
from typing import List
from src.config.config import bot_config


@dataclass
class PrefilterResult:
    """预过滤结果"""

    should_skip_ai: bool = False
    should_reply: bool = False
    reason: str = ""


class ReplyPrefilter:
    """回复预过滤器 - 分层规则引擎"""

    # 纯符号/数字字符集（用于识别纯技术内容）
    _TECH_CHARS = set("0123456789./\\:;,_-+*=(){}[]<> \t\n\r")

    # 无意义消息的最小长度阈值
    _MIN_MEANINGFUL_LENGTH = 3

    def should_skip_ai_decision(
        self,
        user_name: str,
        current_msg: str,
        is_at_me: bool,
        is_sticker: bool,
        history_messages: List[str],
        scan_mode: bool = False,
    ) -> PrefilterResult:
        """
        判断是否可以跳过 AI 决策

        ┌──────────────────────────────────────────────────────────┐
        │   被动模式（scan_mode=False）                             │
        │   每条新消息触发，严格过滤以节省 token                      │
        │   优先级：被艾特 > bot相关 > 消息质量 > 他人对话           │
        ├──────────────────────────────────────────────────────────┤
        │   扫描模式（scan_mode=True）                              │
        │   bot 主动回看群聊，放宽限制让他找话题                      │
        │   优先级：被艾特 > 消息质量 > 放行                         │
        │   跳过"bot相关性"和"他人对话"检查，因为扫描的目的就是找      │
        │   "离开期间有什么我感兴趣的事"                            │
        └──────────────────────────────────────────────────────────┘

        Args:
            user_name: 当前用户名称
            current_msg: 当前消息内容
            is_at_me: 是否艾特了机器人
            is_sticker: 是否是表情包消息
            history_messages: 已清理的历史消息列表
            scan_mode: 是否为扫描模式（bot 主动回看）

        Returns:
            PrefilterResult: 过滤结果
        """
        # 第一层：艾特了机器人 → 绝不跳过
        if is_at_me:
            return PrefilterResult(should_skip_ai=False, should_reply=True, reason="被艾特，必须 AI 判断")

        clean_msg = current_msg.strip()

        if scan_mode:
            # 扫描模式：跳过 bot 相关性和他人对话检查
            # bot 就是想看看别人在聊什么，所以只过滤真正无意义的消息
            quality_result = self._check_message_quality(clean_msg, is_sticker)
            if quality_result.should_skip_ai:
                return quality_result
            return PrefilterResult(should_skip_ai=False, should_reply=False, reason="扫描模式: 交给AI判断是否感兴趣")

        # 被动模式：完整四层过滤
        # 第二层：bot 相关性检查（优先级高于消息质量）
        bot_name = bot_config.bot_name
        has_bot_mention = bot_name in clean_msg
        has_bot_recent = self._bot_spoke_recently(history_messages, bot_name)
        if has_bot_mention or has_bot_recent:
            return PrefilterResult(should_skip_ai=False, should_reply=False, reason="与 bot 相关，需要 AI 判断")

        # 第三层：消息质量过滤
        quality_result = self._check_message_quality(clean_msg, is_sticker)
        if quality_result.should_skip_ai:
            return quality_result

        # 第四层：他人间对话检测
        if self._is_others_conversation(history_messages, bot_name):
            return PrefilterResult(should_skip_ai=True, should_reply=False, reason="他人间对话，不涉及 bot")

        return PrefilterResult(should_skip_ai=False, should_reply=False, reason="规则无法判断，需要 AI 决策")

    def _check_message_quality(self, clean_msg: str, is_sticker: bool) -> PrefilterResult:
        """消息质量过滤：纯表情包、极短消息、纯技术内容"""
        if is_sticker and len(clean_msg) <= self._MIN_MEANINGFUL_LENGTH:
            return PrefilterResult(should_skip_ai=True, should_reply=False, reason="纯表情包无实质内容")

        if len(clean_msg) <= 2:
            return PrefilterResult(should_skip_ai=True, should_reply=False, reason=f"消息过短({len(clean_msg)}字)")

        if len(clean_msg) > 8 and all(c in self._TECH_CHARS for c in clean_msg):
            return PrefilterResult(should_skip_ai=True, should_reply=False, reason="纯数字/技术内容")

        return PrefilterResult()

    def _bot_spoke_recently(self, history_messages: List[str], bot_name: str) -> bool:
        """检查 bot 在最近 5 条消息内是否发言"""
        recent = history_messages[-5:] if len(history_messages) > 5 else history_messages
        for msg in recent:
            if msg.startswith(f"{bot_name}:") or msg.startswith(f"{bot_name} "):
                return True
        return False

    def _is_others_conversation(self, history_messages: List[str], bot_name: str) -> bool:
        """
        判断最近消息是否是其他人之间的对话（不涉及 bot）
        策略：最近 5 条消息中，存在至少 2 个不同的非 bot 用户，
        且 bot 名字在这 3 条消息中一次都没出现 → 判定为他人对话
        """
        if len(history_messages) < 3:
            return False

        recent = history_messages[-5:] if len(history_messages) > 5 else history_messages

        senders: List[str] = []
        for msg in recent:
            if ":" in msg:
                name = msg.split(":")[0].strip()
                if not name.startswith("[回复@"):
                    senders.append(name)

        if len(senders) < 3:
            return False

        unique_non_bot = set(s for s in senders if s != bot_name and s != "self")
        if len(unique_non_bot) < 2:
            return False

        for msg_text in recent[-3:]:
            if bot_name in msg_text:
                return False

        return True


# 全局单例
reply_prefilter = ReplyPrefilter()
