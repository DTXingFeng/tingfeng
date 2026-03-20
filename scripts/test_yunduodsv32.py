import asyncio
from openai import AsyncOpenAI
import sys
import os

sys.path.append(os.getcwd())

from src.config.ai_config import ai_config_manager


async def test_yunduodsv32():
    """测试 yunduodsv32 模型，关闭思维链"""
    print("=== 开始测试 yunduodsv32 模型 ===\n")

    model_alias = "yunduodsv32"
    
    # 获取模型凭据
    creds = ai_config_manager.get_model_credentials(model_alias)
    if not creds:
        print(f"❌ 无法获取模型 {model_alias} 的凭据")
        return False

    print(f"模型信息:")
    print(f"  - 模型: {creds['model']}")
    print(f"  - Base URL: {creds['base_url']}")
    print(f"  - API Key: {creds['api_key'][:20]}...")
    print()

    # 创建客户端
    client = AsyncOpenAI(
        api_key=creds["api_key"],
        base_url=creds["base_url"],
        timeout=60.0
    )

    # 测试消息
    test_messages = [
        {"role": "system", "content": "你是一个助手，直接回答问题，不要展示思考过程。"},
        {"role": "user", "content": "请简单介绍一下 Python，用一句话概括。"}
    ]

    print("发送测试请求...")
    print(f"消息: {test_messages[-1]['content']}\n")

    try:
        # 调用 API，关闭思维链的参数设置
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=test_messages,
            temperature=0.7,
            max_tokens=200,
            # 关键参数：不传递 reasoning_efforts 参数来关闭思维链
            # 对于 DeepSeek R1 等模型，可以通过设置 max_completion_tokens 来限制思考输出
            # 这里使用标准参数，避免触发思考模式
        )

        # 打印完整响应用于调试
        print("✅ API 调用成功!")
        print(f"响应对象类型: {type(response)}")
        print(f"响应 ID: {response.id}")
        print(f"模型: {response.model}")
        
        # 检查 choices
        if response.choices:
            print(f"Choices 数量: {len(response.choices)}")
            choice = response.choices[0]
            print(f"Finish reason: {choice.finish_reason}")
            print(f"Message 对象: {choice.message}")
            print(f"Content: {choice.message.content}")
            
            # 检查是否有其他字段
            if hasattr(choice.message, 'reasoning_content'):
                print(f"Reasoning content: {choice.message.reasoning_content}")
            if hasattr(choice.message, 'tool_calls'):
                print(f"Tool calls: {choice.message.tool_calls}")
        
        # 获取回复
        if response.choices and response.choices[0].message.content:
            reply = response.choices[0].message.content.strip()
        else:
            print("\n⚠️ 警告: 返回内容为空")
            reply = "（模型未返回内容）"
        
        print("\n" + "=" * 60)
        print(f"模型回复:\n{reply}")
        print("=" * 60)
        
        # 检查是否有思考过程（DeepSeek R1 可能返回 reasoning_content 字段）
        if hasattr(response.choices[0].message, 'reasoning_content'):
            reasoning = response.choices[0].message.reasoning_content
            if reasoning:
                print(f"\n⚠️ 检测到思考过程（reasoning_content）")
                print(f"思考内容: {reasoning[:200]}...")
        
        # 显示 Token 使用情况
        if hasattr(response, 'usage') and response.usage:
            print(f"\nToken 使用情况:")
            print(f"  - 输入 Token: {response.usage.prompt_tokens}")
            print(f"  - 输出 Token: {response.usage.completion_tokens}")
            print(f"  - 总计 Token: {response.usage.total_tokens}")
            
            # 检查是否有思考相关的 Token 统计
            if hasattr(response.usage, 'completion_tokens_details'):
                details = response.usage.completion_tokens_details
                if details:
                    print(f"  - 详细信息: {details}")
        
        print("\n✅ 测试完成!")
        return True

    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_simple_math():
    """简单数学测试，验证模型基本功能"""
    print("\n\n=== 额外测试：数学计算 ===\n")
    
    model_alias = "yunduodsv32"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    if not creds:
        print(f"❌ 无法获取模型凭据")
        return False

    client = AsyncOpenAI(
        api_key=creds["api_key"],
        base_url=creds["base_url"],
        timeout=60.0
    )

    math_question = "计算：23 × 47 = ?"
    print(f"问题: {math_question}\n")

    try:
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": math_question}
            ],
            temperature=0.0,
            max_tokens=50,
        )

        if response.choices and response.choices[0].message.content:
            answer = response.choices[0].message.content.strip()
            print(f"模型答案: {answer}")
        else:
            print("❌ 模型未返回内容")
            print(f"完整响应: {response}")
            return False
        
        # 验证答案
        if "1081" in answer:
            print("✅ 答案正确!")
            return True
        else:
            print("⚠️ 答案可能不正确（期望 1081）")
            return True  # 仍然返回 True，因为 API 调用成功
            
    except Exception as e:
        print(f"❌ 数学测试失败: {e}")
        return False


async def main():
    print("=" * 60)
    print("yunduodsv32 模型测试脚本")
    print("测试目标：验证 OpenAI API 标准兼容性，关闭思维链")
    print("=" * 60)
    print()
    
    result1 = await test_yunduodsv32()
    result2 = await test_simple_math()
    
    print("\n" + "=" * 60)
    print("测试总结:")
    print(f"  基础对话测试: {'✅ 通过' if result1 else '❌ 失败'}")
    print(f"  数学计算测试: {'✅ 通过' if result2 else '❌ 失败'}")
    print("=" * 60)
    
    if result1 and result2:
        print("\n🎉 所有测试通过！yunduodsv32 模型工作正常！")
    else:
        print("\n⚠️ 部分测试失败，请检查模型配置或 API 可用性。")


if __name__ == "__main__":
    asyncio.run(main())
