import asyncio
from nonebot import get_driver, logger
from src.aimodel.memory.dream_agent import start_dream_cycle

driver = get_driver()

@driver.on_startup
async def launch_dream_agent():
    """机器人启动时开启梦境代理定时任务"""
    asyncio.create_task(start_dream_cycle())
    logger.info("梦境代理 (Dream Agent) 已启动，每 6 小时进行一次记忆自省。")
