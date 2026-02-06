import asyncio
from nonebot import get_driver, logger
from src.utils.db_manager import db_manager
from src.config.config import bot_config

driver = get_driver()


async def mood_natural_drift():
    """
    每 5 分钟自动运行一次，使所有群组的心情值向 50 回正。
    """
    while True:
        try:
            # 等待 5 分钟 (300 秒)
            await asyncio.sleep(300)

            if not bot_config.enable_mood:
                continue

            group_moods = await db_manager.get_all_group_moods()
            if not group_moods:
                continue

            for group_id, current_mood in group_moods:
                if current_mood == 50:
                    continue

                # 计算回正步长：向 50 偏移，步长根据距离调整
                drift = 0
                distance = abs(current_mood - 50)
                
                if current_mood < 50:
                    # 心情过低时，回正速度更快
                    step = min(5, max(2, distance // 5))
                    drift = min(step, 50 - current_mood)
                else:
                    # 心情过高时，也加快回正
                    step = min(5, max(2, distance // 5))
                    drift = max(-step, 50 - current_mood)

                if drift != 0:
                    new_mood = await db_manager.update_mood(group_id, drift)
                    logger.debug(f"群 {group_id} 心情自然回正: {current_mood} -> {new_mood}")

        except Exception as e:
            logger.error(f"心情自然回正定时任务出错: {e}")
            await asyncio.sleep(60)  # 出错后等 1 分钟再试


@driver.on_startup
async def start_mood_timer():
    """机器人启动时开启定时任务"""
    asyncio.create_task(mood_natural_drift())
    logger.info("心情自然回正定时任务已启动 (5分钟/次)")
