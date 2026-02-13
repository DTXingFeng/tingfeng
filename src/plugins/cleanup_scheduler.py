"""
定时清理任务插件
定期清理旧数据、优化数据库、清理向量库
"""

import asyncio
from nonebot import get_driver, logger
from src.utils.db_manager import db_manager
from src.aimodel.memory.vector_db import vector_db

driver = get_driver()


async def cleanup_database_task():
    """
    每 24 小时运行一次，清理 SQLite 数据库中的旧数据
    """
    while True:
        try:
            await asyncio.sleep(3600 * 24)

            logger.info("开始执行数据库清理任务...")

            deleted_counts = await db_manager.cleanup_old_data(days=30)

            total_deleted = sum(deleted_counts.values())
            logger.info(f"数据库清理完成，共删除 {total_deleted} 条记录: {deleted_counts}")

        except Exception as e:
            logger.error(f"数据库清理任务出错: {e}")
            await asyncio.sleep(3600)


async def vacuum_database_task():
    """
    每周运行一次，优化数据库空间
    """
    while True:
        try:
            await asyncio.sleep(3600 * 24 * 7)

            logger.info("开始执行数据库优化 (VACUUM)...")

            await db_manager.vacuum_database()

            logger.info("数据库优化完成")

        except Exception as e:
            logger.error(f"数据库优化任务出错: {e}")
            await asyncio.sleep(3600)


async def cleanup_reply_history_task():
    """
    每 12 小时运行一次，清理旧的回复历史
    """
    while True:
        try:
            await asyncio.sleep(3600 * 12)

            logger.info("开始清理回复历史记录...")

            await db_manager.cleanup_old_reply_history(days=7)

            logger.info("回复历史清理完成")

        except Exception as e:
            logger.error(f"回复历史清理任务出错: {e}")
            await asyncio.sleep(3600)


async def cleanup_vector_db_task():
    """
    每 48 小时运行一次，清理向量数据库中的过期数据
    """
    while True:
        try:
            await asyncio.sleep(3600 * 48)

            logger.info("开始清理向量数据库过期数据...")

            groups = await db_manager.get_all_groups()
            total_cleaned = 0

            for group_id in groups:
                try:
                    cleaned = await vector_db.cleanup_old_memories(group_id, max_age_days=60)
                    if cleaned > 0:
                        total_cleaned += cleaned
                        logger.debug(f"群 {group_id} 向量库清理了 {cleaned} 条过期记忆")
                except Exception as e:
                    logger.warning(f"群 {group_id} 向量库清理失败: {e}")

            logger.info(f"向量数据库清理完成，共清理 {total_cleaned} 条过期记忆")

        except Exception as e:
            logger.error(f"向量数据库清理任务出错: {e}")
            await asyncio.sleep(3600)


@driver.on_startup
async def start_cleanup_scheduler():
    """机器人启动时开启所有清理定时任务"""
    asyncio.create_task(cleanup_database_task())
    asyncio.create_task(vacuum_database_task())
    asyncio.create_task(cleanup_reply_history_task())
    asyncio.create_task(cleanup_vector_db_task())

    logger.info(
        "清理调度器已启动: " "数据库清理(24h/次), " "数据库优化(7天/次), " "回复历史清理(12h/次), " "向量库清理(48h/次)"
    )
