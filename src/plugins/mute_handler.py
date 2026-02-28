import asyncio

from nonebot import get_driver, on_notice
from nonebot.adapters.onebot.v11 import Bot, GroupBanNoticeEvent

from src.aimodel.decision.mute_reflection import generate_mute_response, reflect_on_mute
from src.utils.db_manager import db_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)

driver = get_driver()

ban_notice = on_notice()


@driver.on_startup
async def init_mute_handler():
    """插件启动时显示日志"""
    logger.info("禁言检查插件 (mute_handler) 已加载")


@ban_notice.handle()
async def handle_group_ban(bot: Bot, event: GroupBanNoticeEvent):
    """
    处理群禁言通知事件

    当 bot 或群成员被禁言/解禁时触发

    Args:
        bot: Bot 实例
        event: 群禁言通知事件
    """
    if not isinstance(event, GroupBanNoticeEvent):
        return

    try:
        group_id = event.group_id
        operator_id = event.operator_id
        user_id = event.user_id
        sub_type = event.sub_type
        duration = event.duration

        if user_id != int(bot.self_id):
            return

        if sub_type == "ban":
            duration_minutes = duration // 60

            if duration == 0:
                logger.warning(f"Bot 在群 {group_id} 被管理员 {operator_id} 禁言（时长未定）")
            else:
                hours = duration_minutes // 60
                minutes = duration_minutes % 60

                if hours > 0:
                    duration_str = f"{hours}小时{minutes}分钟" if minutes > 0 else f"{hours}小时"
                else:
                    duration_str = f"{minutes}分钟"

                logger.warning(f"Bot 在群 {group_id} 被管理员 {operator_id} 禁言，时长: {duration_str}")

            await db_manager.add_chat_log(group_id, f"系统: 被管理员 {operator_id} 禁言")

            asyncio.create_task(process_mute_reflection(group_id, operator_id, duration))

        elif sub_type == "lift_ban":
            logger.info(f"Bot 在群 {group_id} 被管理员 {operator_id} 解除禁言")

            await db_manager.add_chat_log(group_id, f"系统: 被管理员 {operator_id} 解除禁言")

            asyncio.create_task(process_unban_response(group_id))

    except Exception as e:
        logger.error(f"处理禁言通知事件失败: {e}", exc_info=True)


async def process_mute_reflection(group_id: int, operator_id: int, duration: int):
    """
    异步处理禁言反思

    Args:
        group_id: 群组 ID
        operator_id: 操作管理员 ID
        duration: 禁言时长（秒）
    """
    try:
        recent_messages = await db_manager.get_chat_log(group_id, limit=20)
        # 提取消息文本（用于传递给期望字符串列表的函数）
        recent_message_texts = [entry["message"] for entry in recent_messages]

        reflection_result = await reflect_on_mute(
            group_id=group_id,
            operator_id=operator_id,
            duration_minutes=duration // 60,
            recent_messages=recent_message_texts,
        )

        if reflection_result.get("success"):
            ban_reason = reflection_result.get("ban_reason", "未知原因")
            reflection = reflection_result.get("reflection", "")
            lesson = reflection_result.get("lesson", "")

            await db_manager.save_mute_reflection(
                group_id=group_id,
                ban_reason=ban_reason,
                trigger_context="\n".join(recent_message_texts[-5:]) if recent_message_texts else "",
                reflection_thought=reflection,
                lesson_learned=lesson,
                operator_id=operator_id,
                duration_seconds=duration,
            )

            logger.info(f"禁言反思完成 [{group_id}] | 原因: {ban_reason} | 教训: {lesson[:30]}...")
        else:
            logger.warning(f"禁言反思失败: {reflection_result.get('reason', '未知错误')}")

    except Exception as e:
        logger.error(f"处理禁言反思时出错: {e}", exc_info=True)


async def process_unban_response(group_id: int):
    """
    异步处理解禁回应

    Args:
        group_id: 群组 ID
    """
    try:
        mute_reflections = await db_manager.get_mute_reflections(group_id, limit=1)

        if not mute_reflections:
            return

        latest_reflection = mute_reflections[0]
        response = await generate_mute_response(
            group_id=group_id, reflection_data={"success": True, **latest_reflection}
        )

        if response:
            from nonebot import get_bot

            try:
                bot = get_bot()
                await bot.send_group_msg(group_id=group_id, message=response)
                logger.info(f"已发送解禁回应 [{group_id}]: {response}")
            except Exception as e:
                logger.error(f"发送解禁回应失败: {e}")

    except Exception as e:
        logger.error(f"处理解禁回应时出错: {e}", exc_info=True)
