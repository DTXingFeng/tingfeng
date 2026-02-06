"""
实用工具 MCP 工具
提供时间、数据处理等基础功能
"""

from typing import Dict, Any
from src.mcp.base_tool import BaseTool
import datetime


class GetCurrentTimeTool(BaseTool):
    """
    获取当前时间工具
    返回当前时间信息
    """

    name = "get_current_time"
    description = "获取当前的时间信息（时间、日期、星期等）"
    parameters = {}

    async def execute(self) -> Dict[str, Any]:
        """
        执行获取当前时间

        Returns:
            dict: 时间信息
        """
        now = datetime.datetime.now()

        return {
            "timestamp": now.timestamp(),
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "weekday": now.strftime("%A"),
            "weekday_number": now.weekday(),
            "is_weekend": now.weekday() >= 5,
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "hour": now.hour,
            "minute": now.minute,
        }


class IsWithinScheduleTool(BaseTool):
    """
    作息表检查工具
    检查当前时间是否在可回复时间段内
    """

    name = "is_within_schedule"
    description = "检查当前时间是否在 bot 作息表允许的'水群'时间段内"
    parameters = {"group_id": {"type": "integer", "description": "群组 ID", "required": True}}

    async def execute(self, group_id: int) -> Dict[str, Any]:
        """
        执行作息表检查

        Args:
            group_id: 群组 ID

        Returns:
            dict: 检查结果
        """
        from src.utils.db_manager import db_manager

        # 获取今天的作息表
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        schedule = await db_manager.get_bot_schedule(group_id, today)

        if not schedule:
            return {"can_chat": True, "reason": "未设置作息表，默认允许回复", "schedule": None}

        # 检查当前时间段
        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M")

        can_chat = False
        current_activity = None

        for item in schedule:
            if not isinstance(item, dict):
                continue

            start = item.get("start")
            end = item.get("end")
            activity = item.get("activity")
            chat_allowed = item.get("can_chat", False)

            if start and end and start <= current_time <= end:
                can_chat = chat_allowed
                current_activity = activity
                break

        return {
            "can_chat": can_chat,
            "current_time": current_time,
            "current_activity": current_activity,
            "schedule": schedule,
        }


class FormatTextTool(BaseTool):
    """
    文本格式化工具
    格式化文本（去除多余空格、换行等）
    """

    name = "format_text"
    description = "格式化文本，去除多余空格、标准化标点等"
    parameters = {
        "text": {"type": "string", "description": "要格式化的文本", "required": True},
        "remove_punctuation": {"type": "boolean", "description": "是否去除标点符号", "required": False},
        "to_lowercase": {"type": "boolean", "description": "是否转为小写", "required": False},
    }

    async def execute(self, text: str, remove_punctuation: bool = False, to_lowercase: bool = False) -> Dict[str, Any]:
        """
        执行文本格式化

        Args:
            text: 要格式化的文本
            remove_punctuation: 是否去除标点
            to_lowercase: 是否转为小写

        Returns:
            dict: 格式化结果
        """
        result = text

        # 去除多余空格
        result = " ".join(result.split())

        # 去除标点
        if remove_punctuation:
            import string

            result = result.translate(str.maketrans("", "", string.punctuation))

        # 转小写
        if to_lowercase:
            result = result.lower()

        return {"original": text, "formatted": result, "length": len(result)}


class CountWordsTool(BaseTool):
    """
    字数统计工具
    统计文本的字数、词数
    """

    name = "count_words"
    description = "统计文本的字数、词数、字符数"
    parameters = {"text": {"type": "string", "description": "要统计的文本", "required": True}}

    async def execute(self, text: str) -> Dict[str, Any]:
        """
        执行字数统计

        Args:
            text: 要统计的文本

        Returns:
            dict: 统计结果
        """
        char_count = len(text)
        word_count = len(text.split())
        line_count = len(text.split("\n"))

        # 去除空格后的字符数
        no_space_count = len(text.replace(" ", "").replace("\n", ""))

        return {
            "character_count": char_count,
            "word_count": word_count,
            "line_count": line_count,
            "character_count_no_spaces": no_space_count,
            "original_length": len(text),
        }
