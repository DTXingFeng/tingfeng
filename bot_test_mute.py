import nonebot
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11_Adapter
import sys
from pathlib import Path

root_path = Path(__file__).parent.absolute()
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(ONEBOT_V11_Adapter)

nonebot.load_builtin_plugins("echo")

from src.plugins import mute_handler

if __name__ == "__main__":
    print("=" * 50)
    print("测试模式：仅加载禁言检查插件 (mute_handler)")
    print("=" * 50)
    nonebot.run()
