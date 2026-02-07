"""
记忆相关 MCP 工具
提供查询和管理 bot 记忆的能力
"""

from typing import Dict, Any, List, Optional
from src.mcp.base_tool import BaseTool
from src.utils.db_manager import db_manager
from src.aimodel.memory.embeddings import get_embeddings
from src.aimodel.memory.vector_db import vector_db


class MemorySearchTool(BaseTool):
    """
    记忆搜索工具
    根据查询内容搜索相关的长期记忆
    """

    name = "memory_search"
    description = "根据查询内容搜索 bot 的长期记忆（向量数据库），返回最相关的记忆片段"
    parameters = {
        "query": {"type": "string", "description": "要查询的内容或问题", "required": True},
        "group_id": {"type": "integer", "description": "群组 ID", "required": True},
        "limit": {"type": "integer", "description": "返回结果数量限制，默认 3", "required": False},
    }

    async def execute(self, query: str, group_id: int, limit: int = 3) -> Dict[str, Any]:
        """
        执行记忆搜索

        Args:
            query: 查询内容
            group_id: 群组 ID
            limit: 返回数量限制

        Returns:
            dict: 搜索结果
        """
        try:
            # 向量化查询
            vectors = await get_embeddings([query])
            query_vector = vectors[0]

            # 查询向量数据库
            memories = await vector_db.query_memory(group_id, query_vector, n_results=limit)

            return {"query": query, "results": memories, "count": len(memories)}
        except Exception as e:
            raise RuntimeError(f"记忆搜索失败: {str(e)}")


class GetUserMemoriesTool(BaseTool):
    """
    获取用户特定记忆工具
    获取某个群友的具体记忆（跨群查询，通过 QQ 号聚合所有群的记忆）
    """

    name = "get_user_memories"
    description = "获取某个群友在 bot 记忆中的具体信息（印象、记忆点、关系等）。注意：支持跨群查询，会通过 QQ 号聚合该用户在所有群组的记忆。"
    parameters = {
        "user_name": {"type": "string", "description": "用户名", "required": True},
        "group_id": {"type": "integer", "description": "群组 ID", "required": True},
        "memory_limit": {"type": "integer", "description": "返回记忆点数量，默认 5", "required": False},
    }

    async def execute(self, user_name: str, group_id: int, memory_limit: int = 5) -> Dict[str, Any]:
        """
        执行获取用户记忆

        Args:
            user_name: 用户名
            group_id: 群组 ID
            memory_limit: 记忆点数量限制

        Returns:
            dict: 用户记忆信息
        """
        # 获取 user_id
        user_id = await db_manager.get_user_id_by_name(group_id, user_name)
        if not user_id:
            raise ValueError(f"未找到用户 '{user_name}' 的 QQ 号，请让该用户先在群内发言")
        
        # 获取用户印象（跨群查询）
        impression = await db_manager.get_user_impression_cross_group(group_id, user_id)

        # 获取具体记忆点（跨群查询）
        memories = await db_manager.get_user_specific_memories_cross_group(group_id, user_id, limit=memory_limit)

        # 获取关系状态（跨群查询）
        relationship = await db_manager.get_user_relationship_cross_group(group_id, user_id)

        return {
            "user_name": user_name,
            "user_id": user_id,
            "impression": impression,
            "memories": memories,
            "relationship": relationship,
            "memory_count": len(memories),
        }


class AddMemoryTool(BaseTool):
    """
    添加记忆工具
    主动为某个群友添加记忆
    """

    name = "add_memory"
    description = "主动为某个群友添加一条记忆（谨慎使用，仅用于重要信息）"
    parameters = {
        "user_name": {"type": "string", "description": "用户名", "required": True},
        "group_id": {"type": "integer", "description": "群组 ID", "required": True},
        "content": {"type": "string", "description": "记忆内容", "required": True},
    }

    async def execute(self, user_name: str, group_id: int, content: str) -> Dict[str, Any]:
        """
        执行添加记忆

        Args:
            user_name: 用户名
            group_id: 群组 ID
            content: 记忆内容

        Returns:
            dict: 添加结果
        """
        # 获取 user_id
        user_id = await db_manager.get_user_id_by_name(group_id, user_name)
        if user_id:
            await db_manager.add_user_specific_memory(group_id, user_id, user_name, content)
        else:
            raise ValueError(f"未找到用户 '{user_name}' 的 QQ 号，请让该用户先在群内发言")

        # 同时添加到向量数据库
        try:
            vectors = await get_embeddings([f"{user_name}: {content}"])
            await vector_db.add_memory(
                group_id=group_id,
                text=f"[主动添加] {content}",
                vector=vectors[0],
                metadata={"type": "manual_memory", "user": user_name},
            )
        except Exception:
            pass

        return {"user_name": user_name, "content": content, "success": True}
