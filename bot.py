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

    # 白名单/黑名单过滤
    from src.config.config import bot_config

    group_id = event.group_id

    # 黑名单检查
    if bot_config.blocked_groups and group_id in bot_config.blocked_groups:
        raise IgnoredException(f"Group {group_id} is in blacklist")

    # 白名单检查
    if bot_config.allowed_groups and group_id not in bot_config.allowed_groups:
        raise IgnoredException(f"Group {group_id} is not in whitelist")


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


@driver.on_startup
async def print_whitelist_config():
    """启动时打印白名单配置"""
    try:
        from src.config.config import bot_config

        print(f"\n{'='*60}")
        print(f"白名单配置:")
        print(f"  - 白名单群组: {bot_config.allowed_groups if bot_config.allowed_groups else '未设置（允许所有群组）'}")
        print(f"  - 黑名单群组: {bot_config.blocked_groups if bot_config.blocked_groups else '未设置'}")
        print(f"  - 决策间隔: {bot_config.decision_interval} 秒")
        print(f"  - 作息表: {'启用' if bot_config.enable_schedule else '禁用'}")
        print(f"{'='*60}\n")
    except Exception as e:
        print(f"打印白名单配置失败: {e}")


if __name__ == "__main__":
    nonebot.run()
