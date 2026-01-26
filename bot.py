import nonebot
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11_Adapter
from nonebot.message import event_preprocessor
from nonebot.exception import IgnoredException
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent

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

if __name__ == "__main__":
    nonebot.run()
