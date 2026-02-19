"""
测试合并转发消息 API
用于调试 OneBot V11 get_forward_msg 接口的返回数据结构
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def test_forward_msg(message_id: str = "7606175198650574508"):
    """测试获取合并转发消息"""
    from nonebot import get_bot
    import nonebot

    # 初始化 NoneBot（但不启动）
    nonebot.get_driver()

    # 等待 bot 连接
    await asyncio.sleep(1)

    try:
        bot = get_bot()
        print(f"✓ Bot 已连接: {bot.self_id}")

        print(f"\n正在调用 get_forward_msg API...")
        print(f"参数: message_id={message_id}")

        result = await bot.call_api("get_forward_msg", message_id=message_id)

        print(f"\n{'='*60}")
        print(f"API 返回数据类型: {type(result)}")
        print(f"API 返回数据: {result}")
        print(f"{'='*60}\n")

        if isinstance(result, dict):
            print(f"字典键: {list(result.keys())}")
            for key, value in result.items():
                print(f"  {key}: {type(value)} = {value if len(str(value)) < 100 else str(value)[:100] + '...'}")

        elif isinstance(result, list):
            print(f"列表长度: {len(result)}")
            if len(result) > 0:
                print(f"第一个元素类型: {type(result[0])}")
                print(f"第一个元素: {result[0]}")

    except Exception as e:
        print(f"✗ 错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        msg_id = sys.argv[1]
        print(f"使用命令行参数: message_id={msg_id}\n")
    else:
        msg_id = "7606175198650574508"
        print(f"使用默认 message_id: {msg_id}")
        print("提示: 可以通过命令行参数指定其他消息 ID")
        print("用法: python test_forward_api.py <message_id>\n")

    asyncio.run(test_forward_msg(msg_id))
