"""
用户相关 MCP 工具
提供查询和管理用户信息的能力
"""

from typing import Dict, Any
from src.mcp.base_tool import BaseTool
from src.utils.db_manager import db_manager
from src.config.config import bot_config


class UserProfileTool(BaseTool):
    """
    用户画像查询工具
    快速获取某个群友的完整画像（跨群查询）
    """

    name = "get_user_profile"
    description = "获取某个群友的完整画像，包括整体印象、关系状态、好感度等。注意：支持跨群查询，会通过 QQ 号聚合该用户在所有群组的数据。"
    parameters = {
        "user_name": {"type": "string", "description": "用户名", "required": True},
        "group_id": {"type": "integer", "description": "群组 ID", "required": True},
    }

    async def execute(self, user_name: str, group_id: int) -> Dict[str, Any]:
        """
        执行获取用户画像

        Args:
            user_name: 用户名
            group_id: 群组 ID

        Returns:
            dict: 用户画像信息
        """
        # 获取用户 ID（如果有）
        user_id = await db_manager.get_user_id_by_name(group_id, user_name)
        
        if not user_id:
            raise ValueError(f"未找到用户 '{user_name}' 的 QQ 号，请让该用户先在群内发言")
        
        # 获取用户印象（跨群查询）
        impression = await db_manager.get_user_impression_cross_group(group_id, user_id)

        # 获取关系（跨群查询）
        relationship = await db_manager.get_user_relationship_cross_group(group_id, user_id)

        # 获取记忆数量（跨群查询）
        memories = await db_manager.get_user_specific_memories_cross_group(group_id, user_id, limit=100)

        return {
            "user_name": user_name,
            "user_id": user_id,
            "impression": impression,
            "relationship": relationship,
            "memory_count": len(memories),
            "is_creator": user_id == bot_config.creator_id if bot_config.creator_id else False,
        }


class GetCreatorInfoTool(BaseTool):
    """
    创造者信息查询工具
    快速获取创造者的信息
    """

    name = "get_creator_info"
    description = "获取创造者的基本信息（名字、QQ 号等）"
    parameters = {}

    async def execute(self) -> Dict[str, Any]:
        """
        执行获取创造者信息

        Returns:
            dict: 创造者信息
        """
        return {
            "name": bot_config.creator_name,
            "id": bot_config.creator_id,
            "is_configured": bool(bot_config.creator_name),
        }


class UpdateRelationshipTool(BaseTool):
    """
    更新关系工具
    手动调整与某个群友的关系或好感度
    """

    name = "update_relationship"
    description = "更新与某个群友的关系状态或好感度（谨慎使用）"
    parameters = {
        "user_name": {"type": "string", "description": "用户名", "required": True},
        "group_id": {"type": "integer", "description": "群组 ID", "required": True},
        "delta_favorability": {
            "type": "integer",
            "description": "好感度变化量（正数增加，负数减少），默认 0",
            "required": False,
        },
        "new_status": {
            "type": "string",
            "description": "新的关系状态（如：陌生人、朋友、死党等），默认保持不变",
            "required": False,
        },
    }

    async def execute(
        self, user_name: str, group_id: int, delta_favorability: int = 0, new_status: str = None
    ) -> Dict[str, Any]:
        """
        执行更新关系

        Args:
            user_name: 用户名
            group_id: 群组 ID
            delta_favorability: 好感度变化量
            new_status: 新的关系状态

        Returns:
            dict: 更新结果
        """
        result = await db_manager.update_user_relationship(
            group_id, user_name, delta_favorability=delta_favorability, new_status=new_status
        )

        return {
            "user_name": user_name,
            "updated_relationship": result,
            "delta_favorability": delta_favorability,
            "new_status": new_status,
        }
