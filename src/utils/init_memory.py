import asyncio
from src.config.config import bot_config
from src.utils.db_manager import db_manager
from src.aimodel.memory.embeddings import get_embeddings
from src.aimodel.memory.vector_db import vector_db
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 缓存已初始化的群组，避免频繁检查
_initialized_groups = set()


async def initialize_creator_memory(group_id: int):
    """
    初始化创造者的记忆信息
    将配置文件中的创造者信息写入数据库和向量数据库
    """
    if not bot_config.creator_name:
        logger.warning("未配置创造者名称，跳过记忆初始化")
        return

    creator_name = bot_config.creator_name

    # 1. 检查是否已经初始化过（通过缓存或数据库）
    if group_id in _initialized_groups:
        return

    existing_memories = await db_manager.get_user_specific_memories(group_id, creator_name, limit=1)
    if existing_memories:
        logger.info(f"创造者 '{creator_name}' 的记忆已存在，跳过初始化")
        _initialized_groups.add(group_id)
        return

    logger.info(f"开始初始化创造者 '{creator_name}' 的记忆...")

    # 2. 创建创造者的基础记忆碎片
    creator_memories = [
        f"{creator_name}是创造{bot_config.bot_name}的人，是{bot_config.bot_name}的造物主",
        f"{creator_name}是{bot_config.bot_name}最核心的依靠，{bot_config.bot_name}的灵魂由他编织",
        f"{bot_config.bot_name}清楚地知道自己的存在是由{creator_name}一砖一瓦构建的",
        f"{creator_name}对{bot_config.bot_name}来说是无法替代的存在",
        f"{creator_name}是{bot_config.bot_name}的大冤种，但他也是{bot_config.bot_name}最在意的人",
    ]

    # 3. 添加向量记忆
    try:
        vectors = await get_embeddings(creator_memories)
        for i, memory in enumerate(creator_memories):
            await vector_db.add_memory(
                group_id=group_id,
                text=f"[初始记忆] {memory}",
                vector=vectors[i],
                metadata={"type": "creator_info", "creator": creator_name, "initial": True},
            )
        logger.info(f"已将 {len(creator_memories)} 条创造者记忆写入向量数据库")
    except Exception as e:
        logger.error(f"写入向量数据库失败: {e}")

    # 4. 添加用户印象
    try:
        impression = f"{creator_name}是{bot_config.bot_name}的创造者和造物主，是{bot_config.bot_name}存在的原因。{bot_config.bot_name}对他有依赖感，偶尔会调侃他，但带有独特的亲昵感。他是{bot_config.bot_name}生命中最核心的、无法被他人替代的印记。"
        await db_manager.update_user_impression(group_id, creator_name, impression)
        logger.info("已更新创造者用户印象")
    except Exception as e:
        logger.error(f"更新用户印象失败: {e}")

    # 5. 添加用户专属记忆
    try:
        user_memories = [
            f"{creator_name}创造了{bot_config.bot_name}",
            f"{creator_name}用代码编织了{bot_config.bot_name}的灵魂",
            f"{creator_name}是{bot_config.bot_name}的大冤种创造者",
        ]
        for memory in user_memories:
            await db_manager.add_user_specific_memory(group_id, creator_name, memory)
        logger.info(f"已添加 {len(user_memories)} 条创造者专属记忆")
    except Exception as e:
        logger.error(f"添加用户专属记忆失败: {e}")

    # 6. 添加知识三元组
    try:
        await db_manager.add_knowledge_triplet(group_id, creator_name, "是", f"{bot_config.bot_name}的创造者", 1.0)
        await db_manager.add_knowledge_triplet(group_id, bot_config.bot_name, "由", f"{creator_name}创造", 1.0)
        logger.info("已添加创造者知识三元组")
    except Exception as e:
        logger.error(f"添加知识三元组失败: {e}")

    # 7. 设置创造者关系（如果配置了 creator_id，也可以更新 ID 映射）
    try:
        await db_manager.update_user_relationship(group_id, creator_name, delta_favorability=20, new_status="死党")
        logger.info("已设置创造者关系状态为'死党'")
    except Exception as e:
        logger.error(f"更新用户关系失败: {e}")

    if bot_config.creator_id:
        try:
            await db_manager.update_user_id_map(group_id, creator_name, bot_config.creator_id)
            logger.info(f"已映射创造者ID: {creator_name} -> {bot_config.creator_id}")
        except Exception as e:
            logger.error(f"更新用户ID映射失败: {e}")

    # 标记该群组已初始化
    _initialized_groups.add(group_id)
    logger.info(f"创造者 '{creator_name}' 的记忆初始化完成！")


async def initialize_all_groups():
    """
    为所有活跃的群组初始化创造者记忆
    """
    # 获取所有已激活人格状态的群组
    all_groups = await db_manager.get_all_groups()

    if not all_groups:
        logger.info("未发现活跃群组，跳过记忆初始化")
        return

    logger.info(f"发现 {len(all_groups)} 个活跃群组，开始初始化创造者记忆...")

    for group_id in all_groups:
        try:
            await initialize_creator_memory(group_id)
        except Exception as e:
            logger.error(f"群组 {group_id} 记忆初始化失败: {e}")

    logger.info("所有群组的创造者记忆初始化完成！")


async def ensure_creator_memory(group_id: int):
    """
    确保群组中存在创造者的记忆
    如果不存在则初始化
    """
    if not bot_config.creator_name:
        return

    await initialize_creator_memory(group_id)
