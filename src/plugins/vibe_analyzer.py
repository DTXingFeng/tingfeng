import asyncio
import json
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

            logger.info(f"开始检查 {len(active_groups)} 个群组的氛围更新")
            success_count = 0
            fail_count = 0

            for group_id in active_groups:
                try:
                    # 检查是否应该更新群氛围
                    should_update, msg_count, last_time = await db_manager.should_update_vibe(
                        group_id, MIN_NEW_MESSAGES
                    )

                    if not should_update:
                        logger.debug(
                            f"群 {group_id} 跳过氛围分析：消息数量不足 ({msg_count}/{MIN_NEW_MESSAGES})，上次更新：{last_time}"
                        )
                        continue

                    logger.info(
                        f"群 {group_id} 开始氛围分析：检测到 {msg_count} 条新消息，上次更新：{last_time or '从未'}"
                    )

                    # 获取更新前的氛围
                    old_state = await db_manager.get_personality_state(group_id)
                    old_vibe = old_state.get("style_vibe", "{}")
                    try:
                        if isinstance(old_vibe, str):
                            old_vibe_data = json.loads(old_vibe)
                        else:
                            old_vibe_data = old_vibe
                    except:
                        old_vibe_data = {"vibe": "解析失败"}

                    # 执行更新
                    await personality_manager.update_group_vibe(group_id)

                    # 验证更新是否成功
                    new_state = await db_manager.get_personality_state(group_id)
                    new_vibe = new_state.get("style_vibe", "{}")
                    try:
                        if isinstance(new_vibe, str):
                            new_vibe_data = json.loads(new_vibe)
                        else:
                            new_vibe_data = new_vibe
                    except:
                        new_vibe_data = {"vibe": "解析失败"}

                    # 检查是否真的更新了
                    if old_vibe_data.get("vibe") != new_vibe_data.get("vibe") or old_vibe != new_vibe:
                        logger.success(
                            f"群 {group_id} 氛围更新成功：{old_vibe_data.get('vibe', '无')} → {new_vibe_data.get('vibe', '无')}"
                        )
                        success_count += 1
                    else:
                        logger.warning(f"群 {group_id} 氛围未发生变化，可能更新失败")
                        fail_count += 1

                except Exception as e:
                    fail_count += 1
                    logger.error(f"分析群 {group_id} 氛围时出错: {e}", exc_info=True)

            logger.info(f"氛围分析完成：成功 {success_count} 个，失败 {fail_count} 个")

        except Exception as e:
            logger.error(f"群氛围分析定时任务出错: {e}", exc_info=True)
            await asyncio.sleep(600)


@driver.on_startup
async def start_vibe_timer():
    """机器人启动时开启定时任务"""
    asyncio.create_task(analyze_all_groups_vibe())
    logger.info(f"群氛围分析定时任务已启动 ({VIBE_UPDATE_INTERVAL//3600}小时/次，至少{MIN_NEW_MESSAGES}条新消息才更新)")
