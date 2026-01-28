import asyncio
import datetime
from nonebot import get_driver, logger
from src.utils.db_manager import db_manager
from src.aimodel.reply.personality import personality_manager
from src.config.config import bot_config

driver = get_driver()

async def daily_schedule_worker():
    """
    每日作息表更新工人：
    1. 启动时检查今天是否有作息表，没有则生成。
    2. 每天凌晨 00:05 左右更新第二天的作息表。
    """
    while True:
        try:
            now = datetime.datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            
            # 获取所有有记录的群组
            groups = db_manager.get_all_groups()
            
            for group_id in groups:
                schedule = db_manager.get_bot_schedule(group_id, today_str)
                if not schedule:
                    logger.info(f"正在为群 {group_id} 生成今日作息表...")
                    await personality_manager.generate_daily_schedule(group_id)
            
            # 计算距离明天凌晨 00:05 的秒数
            tomorrow = now + datetime.timedelta(days=1)
            next_run = tomorrow.replace(hour=0, minute=5, second=0, microsecond=0)
            sleep_seconds = (next_run - now).total_seconds()
            
            logger.info(f"作息表更新任务已完成，下次运行在 {sleep_seconds:.0f} 秒后")
            await asyncio.sleep(sleep_seconds)
            
        except Exception as e:
            logger.error(f"每日作息表定时任务出错: {e}")
            await asyncio.sleep(300) # 出错后等 5 分钟再试

@driver.on_startup
async def start_schedule_manager():
    """机器人启动时开启作息管理任务"""
    asyncio.create_task(daily_schedule_worker())
    logger.info("每日作息管理定时任务已启动")
