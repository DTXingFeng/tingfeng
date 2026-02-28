"""
消息相关 MCP 工具
提供获取消息信息的能力
"""

from typing import Dict, Any, Optional
from src.mcp.base_tool import BaseTool
from src.utils.db_manager import db_manager


class GetRecentMessagesTool(BaseTool):
    """
    获取最近消息工具
    获取群组最近的聊天记录
    """

    name = "get_recent_messages"
    description = "获取群组最近的聊天记录，帮助理解当前对话的上下文"
    parameters = {
        "group_id": {"type": "integer", "description": "群组 ID", "required": True},
        "limit": {"type": "integer", "description": "返回消息数量，默认 10", "required": False},
    }

    async def execute(self, group_id: int, limit: int = 10) -> Dict[str, Any]:
        """
        执行获取最近消息

        Args:
            group_id: 群组 ID
            limit: 返回消息数量

        Returns:
            dict: 最近的消息列表
        """
        try:
            # 从数据库获取最近的聊天记录
            chat_logs = await db_manager.get_chat_log(group_id, limit=limit)

            messages = []
            for log in chat_logs:
                # 新格式返回字典：{"message": "名字:内容", "message_id": int}
                msg_text = log["message"]
                # 解析日志格式 "名字:内容"
                if ":" in msg_text:
                    parts = msg_text.split(":", 1)
                    if len(parts) == 2:
                        sender = parts[0].strip()
                        content = parts[1].strip()
                        messages.append({"sender": sender, "content": content})

            return {"group_id": group_id, "messages": messages, "count": len(messages)}
        except Exception as e:
            return {"group_id": group_id, "messages": [], "count": 0, "error": str(e)}


class GetMessageContextTool(BaseTool):
    """
    获取消息上下文工具
    获取消息周围的对话内容，帮助理解话题
    """

    name = "get_message_context"
    description = "获取群组最近的对话上下文（前后几条消息），用于理解对话流程"
    parameters = {
        "group_id": {"type": "integer", "description": "群组 ID", "required": True},
        "before": {"type": "integer", "description": "获取前面的消息数量，默认 5", "required": False},
        "after": {"type": "integer", "description": "获取后面的消息数量，默认 0", "required": False},
    }

    async def execute(self, group_id: int, before: int = 5, after: int = 0) -> Dict[str, Any]:
        """
        执行获取消息上下文

        Args:
            group_id: 群组 ID
            before: 前面的消息数量
            after: 后面的消息数量

        Returns:
            dict: 上下文消息
        """
        try:
            # 获取前面的消息
            total = before + after
            chat_logs = await db_manager.get_chat_log(group_id, limit=total)

            context_before = []
            context_after = []

            # 简单处理：所有消息都算作"前面"
            for log in chat_logs:
                # 新格式返回字典：{"message": "名字:内容", "message_id": int}
                msg_text = log["message"]
                if ":" in msg_text:
                    parts = msg_text.split(":", 1)
                    if len(parts) == 2:
                        sender = parts[0].strip()
                        content = parts[1].strip()
                        context_before.append({"sender": sender, "content": content})

            return {
                "group_id": group_id,
                "context_before": context_before,
                "context_after": context_after,
                "total_messages": len(context_before) + len(context_after),
            }
        except Exception as e:
            return {"group_id": group_id, "context_before": [], "context_after": [], "error": str(e)}
