import asyncio
from nonebot import get_driver, logger
from src.utils.db_manager import db_manager
from src.aimodel.reply.personality import personality_manager

driver = get_driver()


async def analyze_all_groups_vibe():
    """
    每 1 小时自动运行一次，分析各群氛围。
    """
    while True:
        try:
            # 等待 1 小时
            await asyncio.sleep(3600)

            # 获取所有活跃群组
            group_moods = await db_manager.get_all_group_moods()
            if not group_moods:
                continue

            for group_id, _ in group_moods:
                logger.info(f"开始分析群 {group_id} 的聊天氛围...")
                await personality_manager.update_group_vibe(group_id)

        except Exception as e:
            logger.error(f"群氛围分析定时任务出错: {e}")
            await asyncio.sleep(600)


@driver.on_startup
async def start_vibe_timer():
    """机器人启动时开启定时任务"""
    asyncio.create_task(analyze_all_groups_vibe())
    logger.info("群氛围分析定时任务已启动 (1小时/次)")
