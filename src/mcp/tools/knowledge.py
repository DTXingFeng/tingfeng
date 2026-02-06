"""
知识相关 MCP 工具
提供查询知识图谱的能力
"""

from typing import Dict, Any, List
from src.mcp.base_tool import BaseTool
from src.utils.db_manager import db_manager


class KnowledgeQueryTool(BaseTool):
    """
    知识查询工具
    从知识图谱中查询相关信息
    """

    name = "knowledge_query"
    description = "从知识图谱中查询相关信息（基于三元组：主体-谓语-客体）"
    parameters = {
        "subject": {"type": "string", "description": "要查询的主体（如：'刑风'）", "required": False},
        "group_id": {"type": "integer", "description": "群组 ID", "required": True},
        "limit": {"type": "integer", "description": "返回结果数量限制，默认 10", "required": False},
    }

    async def execute(self, group_id: int, subject: str = None, limit: int = 10) -> Dict[str, Any]:
        """
        执行知识查询

        Args:
            group_id: 群组 ID
            subject: 查询主体
            limit: 返回数量限制

        Returns:
            dict: 查询结果
        """
        triplets = await db_manager.get_knowledge_triplets(group_id, subject=subject, limit=limit)

        # 格式化结果
        formatted = []
        for t in triplets:
            formatted.append(
                {
                    "subject": t["subject"],
                    "predicate": t["predicate"],
                    "object": t["object"],
                    "confidence": t["confidence"],
                    "statement": f"{t['subject']} {t['predicate']} {t['object']}",
                }
            )

        return {"subject": subject, "results": formatted, "count": len(formatted)}


class GetCreatorKnowledgeTool(BaseTool):
    """
    创造者知识查询工具
    快速查询与创造者相关的知识
    """

    name = "get_creator_knowledge"
    description = "查询与创造者相关的所有知识（用于回答'刑风是谁'等问题）"
    parameters = {"group_id": {"type": "integer", "description": "群组 ID", "required": True}}

    async def execute(self, group_id: int) -> Dict[str, Any]:
        """
        执行查询创造者知识

        Args:
            group_id: 群组 ID

        Returns:
            dict: 创造者相关知识
        """
        from src.config.config import bot_config

        if not bot_config.creator_name:
            return {"creator": None, "knowledge": [], "message": "未配置创造者"}

        # 查询以创造者为主体的知识
        triplets = await db_manager.get_knowledge_triplets(group_id, subject=bot_config.creator_name, limit=20)

        # 查询以创造者为客体的知识
        all_triplets = await db_manager.get_knowledge_triplets(group_id, limit=50)
        object_triplets = [t for t in all_triplets if t["object"] == bot_config.creator_name]

        # 合并结果
        formatted = []
        for t in triplets:
            formatted.append(
                {"statement": f"{t['subject']} {t['predicate']} {t['object']}", "confidence": t["confidence"]}
            )
        for t in object_triplets:
            stmt = f"{t['subject']} {t['predicate']} {t['object']}"
            if stmt not in [f["statement"] for f in formatted]:
                formatted.append({"statement": stmt, "confidence": t["confidence"]})

        return {"creator": bot_config.creator_name, "knowledge": formatted, "count": len(formatted)}


class AddKnowledgeTool(BaseTool):
    """
    添加知识工具
    主动添加知识三元组
    """

    name = "add_knowledge"
    description = "添加一条知识三元组到知识图谱（谨慎使用）"
    parameters = {
        "subject": {"type": "string", "description": "主体", "required": True},
        "predicate": {"type": "string", "description": "谓语/关系", "required": True},
        "object": {"type": "string", "description": "客体", "required": True},
        "group_id": {"type": "integer", "description": "群组 ID", "required": True},
        "confidence": {"type": "number", "description": "置信度（0-1），默认 1.0", "required": False},
    }

    async def execute(
        self, subject: str, predicate: str, obj: str, group_id: int, confidence: float = 1.0
    ) -> Dict[str, Any]:
        """
        执行添加知识

        Args:
            subject: 主体
            predicate: 谓语
            obj: 客体
            group_id: 群组 ID
            confidence: 置信度

        Returns:
            dict: 添加结果
        """
        await db_manager.add_knowledge_triplet(group_id, subject, predicate, obj, confidence)

        return {"statement": f"{subject} {predicate} {obj}", "confidence": confidence, "success": True}
