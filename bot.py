import nonebot
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11_Adapter
from nonebot.message import event_preprocessor
from nonebot.exception import IgnoredException
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent
import os
import sys
from pathlib import Path
import shutil

# 确保项目根目录在 sys.path 中，防止 Linux 下导入 src 失败
root_path = Path(__file__).parent.absolute()
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))


# 启动前检查：确保必要文件存在
def check_essential_files():
    # 检查 .env
    if not os.path.exists(".env") and os.path.exists(".env.example"):
        print("Creating .env from .env.example...")
        shutil.copy(".env.example", ".env")

    # 检查 data 目录
    Path("data").mkdir(parents=True, exist_ok=True)


# 执行检查
check_essential_files()

# 初始化 NoneBot
nonebot.init()

# 注册适配器
driver = nonebot.get_driver()
driver.register_adapter(ONEBOT_V11_Adapter)


# 全局忽略非群聊消息 (如私聊消息)
@event_preprocessor
async def stop_non_group_message(event: MessageEvent):
    if not isinstance(event, GroupMessageEvent):
        raise IgnoredException("Global ignored: not a group message")


# 加载内置插件
nonebot.load_builtin_plugins("echo")

# 加载自定义插件目录
nonebot.load_plugins("src/plugins")


# 加载 MCP 工具
@driver.on_startup
async def load_mcp_tools():
    """Bot 启动时加载所有 MCP 工具"""
    try:
        from src.mcp.loader import load_all_tools

        load_all_tools()
    except Exception as e:
        print(f"加载 MCP 工具失败: {e}")


# 初始化创造者记忆
@driver.on_startup
async def init_creator_memory():
    """Bot 启动时初始化创造者的记忆"""
    try:
        from src.utils.init_memory import initialize_all_groups

        await initialize_all_groups()
    except Exception as e:
        print(f"初始化创造者记忆失败: {e}")


if __name__ == "__main__":
    nonebot.run()
