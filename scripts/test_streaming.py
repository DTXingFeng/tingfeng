"""
测试流式传输功能
"""
import asyncio
import sys
from pathlib import Path

root_path = Path(__file__).parent.parent.absolute()
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from openai import AsyncOpenAI
from src.config.ai_config import ai_config, ai_config_manager
from src.config.config import bot_config
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_streaming_basic():
    """测试基本流式传输"""
    print("\n=== 测试 1: 基本流式传输 ===")
    
    model_alias = ai_config.reply_model
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    if not creds:
        print("❌ 无法获取模型凭证")
        return False
    
    client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=30.0)
    
    try:
        print(f"使用模型: {creds['model']}")
        print("开始流式调用...")
        
        stream = await client.chat.completions.create(
            model=creds["model"],
            messages=[{"role": "user", "content": "用一句话介绍你自己"}],
            max_tokens=100,
            temperature=0.7,
            stream=True,
        )
        
        content = ""
        chunk_count = 0
        async for chunk in stream:
            chunk_count += 1
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                content += token
                print(token, end="", flush=True)
        
        print(f"\n\n✅ 成功！接收了 {chunk_count} 个 chunks")
        print(f"📝 总内容: {content}")
        return True
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_streaming_with_tools():
    """测试带工具的流式传输"""
    print("\n=== 测试 2: 带工具的流式传输 ===")
    
    model_alias = ai_config.reply_model
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    if not creds:
        print("❌ 无法获取模型凭证")
        return False
    
    client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=30.0)
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "获取指定城市的天气",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "城市名称"
                        }
                    },
                    "required": ["city"]
                }
            }
        }
    ]
    
    try:
        print(f"使用模型: {creds['model']}")
        print("开始流式调用（带工具定义）...")
        
        stream = await client.chat.completions.create(
            model=creds["model"],
            messages=[{"role": "user", "content": "北京今天天气怎么样？"}],
            tools=tools,
            tool_choice="auto",
            max_tokens=200,
            temperature=0.7,
            stream=True,
        )
        
        content = ""
        tool_calls_dict = {}
        chunk_count = 0
        
        async for chunk in stream:
            chunk_count += 1
            
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                content += token
                print(token, end="", flush=True)
            
            if chunk.choices and chunk.choices[0].delta.tool_calls:
                for tool_call_chunk in chunk.choices[0].delta.tool_calls:
                    idx = tool_call_chunk.index
                    if idx not in tool_calls_dict:
                        tool_calls_dict[idx] = {
                            "id": tool_call_chunk.id,
                            "name": tool_call_chunk.function.name if tool_call_chunk.function.name else "",
                            "arguments": tool_call_chunk.function.arguments if tool_call_chunk.function.arguments else "",
                        }
                    else:
                        if tool_call_chunk.function.name:
                            tool_calls_dict[idx]["name"] = tool_call_chunk.function.name
                        if tool_call_chunk.function.arguments:
                            tool_calls_dict[idx]["arguments"] += tool_call_chunk.function.arguments
        
        print(f"\n\n✅ 成功！接收了 {chunk_count} 个 chunks")
        print(f"📝 文本内容: {content if content else '(无文本，可能调用了工具)'}")
        
        if tool_calls_dict:
            print(f"🔧 检测到工具调用:")
            for idx, tool_call in tool_calls_dict.items():
                print(f"  - [{idx}] {tool_call['name']}({tool_call['arguments']})")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_timeout_resistance():
    """测试流式传输的超时抵抗能力"""
    print("\n=== 测试 3: 超时抵抗（长生成时间） ===")
    
    model_alias = ai_config.reply_model
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    if not creds:
        print("❌ 无法获取模型凭证")
        return False
    
    client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=30.0)
    
    try:
        print(f"使用模型: {creds['model']}")
        print("请求生成较长内容，测试流式传输是否会超时...")
        
        import time
        start_time = time.time()
        
        stream = await client.chat.completions.create(
            model=creds["model"],
            messages=[{"role": "user", "content": "请详细介绍一下 Python 异步编程的特点和用法"}],
            max_tokens=300,
            temperature=0.7,
            stream=True,
        )
        
        content = ""
        chunk_count = 0
        
        async for chunk in stream:
            chunk_count += 1
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                content += token
                if chunk_count % 10 == 0:
                    print(".", end="", flush=True)
        
        elapsed = time.time() - start_time
        
        print(f"\n\n✅ 成功！接收了 {chunk_count} 个 chunks")
        print(f"⏱️  总耗时: {elapsed:.2f} 秒")
        print(f"📝 内容长度: {len(content)} 字符")
        print(f"📄 内容预览: {content[:100]}...")
        
        if elapsed > 30:
            print("⚠️  警告: 耗时超过 30 秒，旧的非流式 API 会超时")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    print("🚀 开始测试流式传输功能\n")
    
    results = []
    
    results.append(("基本流式传输", await test_streaming_basic()))
    results.append(("带工具的流式传输", await test_streaming_with_tools()))
    results.append(("超时抵抗能力", await test_timeout_resistance()))
    
    print("\n" + "="*60)
    print("📊 测试结果汇总:")
    print("="*60)
    
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("\n🎉 所有测试通过！流式传输功能正常")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
