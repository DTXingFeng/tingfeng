"""
合并转发消息相关 MCP 工具
提供获取合并转发消息内容的能力
"""

from typing import Any, Dict, List

from src.mcp.base_tool import BaseTool
from src.utils.logger import get_logger

logger = get_logger(__name__)


class GetForwardMessageTool(BaseTool):
    """
    获取合并转发消息工具
    通过 OneBot V11 API 获取合并转发消息的内容
    """

    name = "get_forward_message"
    description = "获取合并转发消息的详细内容，包括所有子消息的发送者、内容和时间"
    parameters = {
        "message_id": {"type": "string", "description": "合并转发消息的 ID", "required": True},
    }

    async def execute(self, message_id: str) -> Dict[str, Any]:
        """
        执行获取合并转发消息

        Args:
            message_id: 合并转发消息的 ID

        Returns:
            dict: 合并转发的消息列表
        """
        try:
            from nonebot import get_bot

            bot = get_bot()

            logger.info(f"正在获取合并转发消息，ID: {message_id}")

            result = await bot.call_api("get_forward_msg", message_id=message_id)

            if not result:
                return {"message_id": message_id, "messages": [], "count": 0, "error": "无法获取合并转发消息"}

            messages = []
            if isinstance(result, dict):
                data = result.get("data", result.get("messages", result.get("list", [])))
            elif isinstance(result, list):
                data = result
            else:
                data = []

            for msg in data:
                sender_info = msg.get("sender", {})
                sender_nickname = sender_info.get("nickname", "未知")
                sender_id = sender_info.get("user_id", 0)
                sender_card = sender_info.get("card", "")

                # 尝试多种方式提取消息内容
                content = msg.get("content", msg.get("raw_message", ""))
                
                # 如果 content 是列表（结构化消息），则提取文本
                if isinstance(content, list):
                    text_parts = []
                    for seg in content:
                        if seg.get("type") == "text":
                            text_parts.append(seg.get("data", {}).get("text", ""))
                    content = "".join(text_parts)
                
                # 如果还是空，尝试从 message 字段提取
                if not content or content == "":
                    message_list = msg.get("message", [])
                    if isinstance(message_list, list):
                        text_parts = []
                        for seg in message_list:
                            if seg.get("type") == "text":
                                text_parts.append(seg.get("data", {}).get("text", ""))
                        content = "".join(text_parts)
                    else:
                        content = str(message_list)

                messages.append(
                    {
                        "sender_id": sender_id,
                        "sender_nickname": sender_nickname,
                        "sender_card": sender_card,
                        "content": str(content),
                        "time": msg.get("time", 0),
                    }
                )

            logger.info(f"成功获取合并转发消息，共 {len(messages)} 条子消息")

            return {"message_id": message_id, "messages": messages, "count": len(messages)}

        except Exception as e:
            logger.error(f"获取合并转发消息失败: {e}", exc_info=True)
            return {"message_id": message_id, "messages": [], "count": 0, "error": str(e)}


class ParseForwardMessageTool(BaseTool):
    """
    解析合并转发消息工具
    从消息内容中提取合并转发消息的 ID 并获取内容
    """

    name = "parse_forward_message"
    description = "从合并转发消息中提取 ID 并获取详细内容，自动处理消息 ID 的提取"
    parameters = {
        "forward_content": {"type": "string", "description": "合并转发消息的内容（包含消息 ID）", "required": True},
    }

    async def execute(self, forward_content: str) -> Dict[str, Any]:
        """
        执行解析并获取合并转发消息

        Args:
            forward_content: 合并转发消息的内容

        Returns:
            dict: 合并转发的消息列表
        """
        try:
            import re

            from nonebot import get_bot

            bot = get_bot()

            message_id = None

            pattern = r"\[type:forward,id:(\d+)\]"
            match = re.search(pattern, str(forward_content))

            if match:
                message_id = match.group(1)

            if not message_id:
                pattern = r"id[:=](\d+)"
                match = re.search(pattern, str(forward_content))
                if match:
                    message_id = match.group(1)

            if not message_id:
                return {"messages": [], "count": 0, "error": "无法从消息内容中提取合并转发消息 ID"}

            logger.info(f"从消息内容中提取到合并转发 ID: {message_id}")

            result = await bot.call_api("get_forward_msg", message_id=message_id)

            if not result:
                return {"message_id": message_id, "messages": [], "count": 0, "error": "无法获取合并转发消息"}

            messages = []
            if isinstance(result, dict):
                data = result.get("data", result.get("messages", result.get("list", [])))
            elif isinstance(result, list):
                data = result
            else:
                data = []

            for msg in data:
                sender_info = msg.get("sender", {})
                sender_nickname = sender_info.get("nickname", "未知")
                sender_id = sender_info.get("user_id", 0)
                sender_card = sender_info.get("card", "")

                # 尝试多种方式提取消息内容
                content = msg.get("content", msg.get("raw_message", ""))
                
                # 如果 content 是列表（结构化消息），则提取文本
                if isinstance(content, list):
                    text_parts = []
                    for seg in content:
                        if seg.get("type") == "text":
                            text_parts.append(seg.get("data", {}).get("text", ""))
                    content = "".join(text_parts)
                
                # 如果还是空，尝试从 message 字段提取
                if not content or content == "":
                    message_list = msg.get("message", [])
                    if isinstance(message_list, list):
                        text_parts = []
                        for seg in message_list:
                            if seg.get("type") == "text":
                                text_parts.append(seg.get("data", {}).get("text", ""))
                        content = "".join(text_parts)
                    else:
                        content = str(message_list)

                messages.append(
                    {
                        "sender_id": sender_id,
                        "sender_nickname": sender_nickname,
                        "sender_card": sender_card,
                        "content": str(content),
                        "time": msg.get("time", 0),
                    }
                )

            logger.info(f"成功获取合并转发消息，共 {len(messages)} 条子消息")

            return {"message_id": message_id, "messages": messages, "count": len(messages)}

        except Exception as e:
            logger.error(f"解析合并转发消息失败: {e}", exc_info=True)
            return {"messages": [], "count": 0, "error": str(e)}


class FormatForwardMessagesTool(BaseTool):
    """
    格式化合并转发消息工具
    将合并转发的消息格式化为易读的文本
    """

    name = "format_forward_messages"
    description = "将合并转发的消息列表格式化为易读的文本格式，便于阅读"
    parameters = {
        "messages": {
            "type": "array",
            "description": "合并转发的消息列表（来自 get_forward_message）",
            "required": True,
            "items": {
                "type": "object",
                "description": "单条消息对象",
            },
        },
        "include_time": {"type": "boolean", "description": "是否包含时间信息", "required": False},
    }

    async def execute(self, messages: List[Dict[str, Any]], include_time: bool = False) -> Dict[str, str]:
        """
        执行格式化合并转发消息

        Args:
            messages: 合并转发的消息列表
            include_time: 是否包含时间信息

        Returns:
            dict: 格式化后的文本
        """
        try:
            if not messages:
                return {"formatted_text": "（合并转发消息为空）", "count": 0}

            formatted_lines = []

            for idx, msg in enumerate(messages, 1):
                sender_nickname = msg.get("sender_nickname", "未知")
                sender_card = msg.get("sender_card", "")
                content = msg.get("content", "")
                time = msg.get("time", 0)

                display_name = sender_card if sender_card else sender_nickname

                if include_time and time:
                    from datetime import datetime

                    dt = datetime.fromtimestamp(time)
                    time_str = dt.strftime("%H:%M")
                    formatted_lines.append(f"[{idx}] {display_name} ({time_str}): {content}")
                else:
                    formatted_lines.append(f"[{idx}] {display_name}: {content}")

            formatted_text = "\n".join(formatted_lines)

            return {"formatted_text": formatted_text, "count": len(messages)}

        except Exception as e:
            logger.error(f"格式化合并转发消息失败: {e}", exc_info=True)
            return {"formatted_text": f"格式化失败: {str(e)}", "count": 0}
