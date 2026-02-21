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

            # 获取所有活跃群组
            group_moods = await db_manager.get_all_group_moods()
            if not group_moods:
                continue

            for group_id, _ in group_moods:
                try:
                    # 检查上次更新时间和新消息数量
                    last_update_time = await db_manager.get_last_vibe_update_time(group_id)
                    
                    if last_update_time:
                        # 计算自上次更新以来的新消息数量
                        new_msg_count = await db_manager.get_new_message_count_since(group_id, last_update_time)
                        
                        if new_msg_count < MIN_NEW_MESSAGES:
                            logger.info(f"群 {group_id} 新消息数量不足 ({new_msg_count}/{MIN_NEW_MESSAGES})，跳过氛围分析")
                            continue
                    
                    logger.info(f"开始分析群 {group_id} 的聊天氛围...")
                    await personality_manager.update_group_vibe(group_id)
                    
                except Exception as e:
                    logger.error(f"分析群 {group_id} 氛围时出错: {e}")

        except Exception as e:
            logger.error(f"群氛围分析定时任务出错: {e}")
            await asyncio.sleep(600)


@driver.on_startup
async def start_vibe_timer():
    """机器人启动时开启定时任务"""
    asyncio.create_task(analyze_all_groups_vibe())
    logger.info(f"群氛围分析定时任务已启动 ({VIBE_UPDATE_INTERVAL//3600}小时/次，至少{MIN_NEW_MESSAGES}条新消息才更新)")
