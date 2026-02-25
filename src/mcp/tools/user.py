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

        # 获取印象历史
        impression_history = await db_manager.get_user_impression_history(user_id, limit=10)

        # 获取关系（跨群查询）
        relationship = await db_manager.get_user_relationship_cross_group(group_id, user_id)

        # 获取记忆数量（跨群查询）
        memories = await db_manager.get_user_specific_memories_cross_group(group_id, user_id, limit=100)

        return {
            "user_name": user_name,
            "user_id": user_id,
            "impression": impression,
            "impression_history": impression_history,
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


class UpdateImpressionTool(BaseTool):
    """
    增量更新用户印象工具
    支持添加、删除、更新特定印象特征，而不是完全覆盖
    """

    name = "update_impression"
    description = """增量更新对某个群友的印象。支持以下操作：
    - 使用 "+新特征" 添加新的印象特征（如："+喜欢打游戏"）
    - 使用 "-要删除的特征" 删除不再适用的特征（如："-"内向""）
    - 使用 "~旧特征|新特征" 更新现有特征（如："~害羞|开朗"）
    - 直接描述新的特征会自动与现有印象智能合并（去重、避免重复）
    
    示例输入："开朗，+喜欢帮人，-内向" 或 "很友善，+技术好"
    """
    parameters = {
        "user_name": {"type": "string", "description": "用户名", "required": True},
        "group_id": {"type": "integer", "description": "群组 ID", "required": True},
        "impression_updates": {
            "type": "string",
            "description": "印象更新内容，支持 +添加、-删除、~更新操作，用逗号分隔",
            "required": True,
        },
    }

    async def execute(self, user_name: str, group_id: int, impression_updates: str) -> Dict[str, Any]:
        """
        执行增量更新印象

        Args:
            user_name: 用户名
            group_id: 群组 ID
            impression_updates: 印象更新内容

        Returns:
            dict: 更新结果
        """
        # 获取 user_id
        user_id = await db_manager.get_user_id_by_name(group_id, user_name)
        if not user_id:
            raise ValueError(f"未找到用户 '{user_name}' 的 QQ 号，请让该用户先在群内发言")

        # 获取当前印象
        current_impression = await db_manager.get_user_impression(group_id, user_id)

        # 使用智能合并更新印象
        await db_manager.update_user_impression(group_id, user_id, user_name, impression_updates)

        # 获取更新后的印象
        new_impression = await db_manager.get_user_impression(group_id, user_id)

        return {
            "user_name": user_name,
            "old_impression": current_impression,
            "new_impression": new_impression,
            "updates_applied": impression_updates,
            "success": True,
        }


class ReplaceImpressionTool(BaseTool):
    """
    完全替换用户印象工具
    仅在需要完全重置印象时使用
    """

    name = "replace_impression"
    description = """完全替换对某个群友的印象（慎用）。
    这会删除所有现有印象，替换为新的内容。
    大多数情况下应该使用 update_impression 进行增量更新。
    仅在印象完全错误或需要彻底重置时使用此工具。
    """
    parameters = {
        "user_name": {"type": "string", "description": "用户名", "required": True},
        "group_id": {"type": "integer", "description": "群组 ID", "required": True},
        "new_impression": {
            "type": "string",
            "description": "新的完整印象描述",
            "required": True,
        },
    }

    async def execute(self, user_name: str, group_id: int, new_impression: str) -> Dict[str, Any]:
        """
        执行完全替换印象

        Args:
            user_name: 用户名
            group_id: 群组 ID
            new_impression: 新的完整印象

        Returns:
            dict: 替换结果
        """
        # 获取 user_id
        user_id = await db_manager.get_user_id_by_name(group_id, user_name)
        if not user_id:
            raise ValueError(f"未找到用户 '{user_name}' 的 QQ 号，请让该用户先在群内发言")

        # 获取当前印象
        current_impression = await db_manager.get_user_impression(group_id, user_id)

        # 完全替换印象
        await db_manager.replace_user_impression(group_id, user_id, user_name, new_impression)

        return {
            "user_name": user_name,
            "old_impression": current_impression,
            "new_impression": new_impression,
            "replaced": True,
            "success": True,
        }
