import asyncio
from nonebot import get_driver, logger
from src.utils.db_manager import db_manager
from src.aimodel.reply.personality import personality_manager

driver = get_driver()

# 配置参数
VIBE_UPDATE_INTERVAL = 21600  # 6 小时（秒）
MIN_NEW_MESSAGES = 100  # 最少新消息数量才触发分析


async def analyze_all_groups_vibe():
    """
    每 6 小时自动运行一次，分析各群氛围。
    只有新消息超过 MIN_NEW_MESSAGES 条才会分析，避免频繁更新。
    """
    while True:
        try:
            # 等待 6 小时
            await asyncio.sleep(VIBE_UPDATE_INTERVAL)

            # 获取所有活跃群组（从 bot_personality 表获取，而不是 bot_moods）
            active_groups = await db_manager.get_all_groups()
            if not active_groups:
                logger.info("没有找到活跃群组，跳过氛围分析")
                continue

            for group_id in active_groups:
                try:
                    # 检查是否应该更新群氛围
                    should_update, msg_count, last_time = await db_manager.should_update_vibe(
                        group_id, MIN_NEW_MESSAGES
                    )

                    if not should_update:
                        logger.info(
                            f"群 {group_id} 跳过氛围分析：消息数量不足 ({msg_count}/{MIN_NEW_MESSAGES})，上次更新：{last_time}"
                        )
                        continue

                    logger.info(
                        f"群 {group_id} 开始氛围分析：检测到 {msg_count} 条新消息，上次更新：{last_time or '从未'}"
                    )
                    await personality_manager.update_group_vibe(group_id)

                except Exception as e:
                    logger.error(f"分析群 {group_id} 氛围时出错: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"群氛围分析定时任务出错: {e}")
            await asyncio.sleep(600)


@driver.on_startup
async def start_vibe_timer():
    """机器人启动时开启定时任务"""
    asyncio.create_task(analyze_all_groups_vibe())
    logger.info(f"群氛围分析定时任务已启动 ({VIBE_UPDATE_INTERVAL//3600}小时/次，至少{MIN_NEW_MESSAGES}条新消息才更新)")
