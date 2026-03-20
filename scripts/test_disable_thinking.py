import asyncio
from openai import AsyncOpenAI
import sys
import os

sys.path.append(os.getcwd())

from src.config.ai_config import ai_config_manager


async def test_with_enable_thinking_false():
    """测试方法：使用 enable_thinking=false 参数"""
    print("\n" + "=" * 60)
    print("方法：设置 enable_thinking=false（通过 extra_body）")
    print("=" * 60)
    
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

    print(f"\n模型: {creds['model']}")
    print(f"发送请求（enable_thinking=false）...")

    try:
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": "请简单介绍一下 Python，用一句话概括。"}
            ],
            temperature=0.7,
            max_tokens=500,
            # 关键：尝试通过 extra_body 关闭思考模式
            extra_body={"enable_thinking": False}
        )

        print(f"✅ API 调用成功!")
        print(f"Finish reason: {response.choices[0].finish_reason}")
        
        content = response.choices[0].message.content
        reasoning = response.choices[0].message.reasoning_content if hasattr(response.choices[0].message, 'reasoning_content') else None
        
        if reasoning:
            print(f"\n📝 思考过程存在: 是（{len(reasoning)} 字符）")
            print(f"⚠️ enable_thinking=false 参数可能无效")
        else:
            print(f"\n📝 思考过程存在: 否")
            print(f"✅ 成功关闭思考模式!")
        
        if content:
            print(f"\n💬 最终回复:")
            print(f"{content}")
            return True
        else:
            print(f"\n⚠️ 没有最终回复")
            return False
            
    except Exception as e:
        error_str = str(e)
        if "enable_thinking" in error_str.lower() or "extra_body" in error_str.lower():
            print(f"\n⚠️ API 不支持 enable_thinking 参数")
            print(f"错误: {e}")
        else:
            print(f"\n❌ 调用失败: {e}")
        return False


async def test_without_thinking_param():
    """测试方法：不传递任何思考相关参数（默认行为）"""
    print("\n" + "=" * 60)
    print("方法：不传递任何思考参数（使用默认行为）")
    print("=" * 60)
    
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

    print(f"\n模型: {creds['model']}")
    print(f"发送请求（无思考参数）...")

    try:
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": "1+1等于几？直接回答数字。"}
            ],
            temperature=0.0,
            max_tokens=100,
        )

        print(f"✅ API 调用成功!")
        
        content = response.choices[0].message.content
        reasoning = response.choices[0].message.reasoning_content if hasattr(response.choices[0].message, 'reasoning_content') else None
        
        if reasoning:
            print(f"\n📝 思考过程: 存在（{len(reasoning)} 字符）")
            print(f"思考内容: {reasoning[:100]}...")
        else:
            print(f"\n📝 思考过程: 不存在")
        
        if content:
            print(f"\n💬 最终回复: {content}")
            return True
        else:
            print(f"\n⚠️ 没有最终回复")
            return False
            
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return False


async def test_with_low_max_tokens():
    """测试方法：使用较低的 max_tokens 限制思考空间"""
    print("\n" + "=" * 60)
    print("方法：限制 max_tokens 来减少思考（实验性）")
    print("=" * 60)
    
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

    print(f"\n模型: {creds['model']}")
    print(f"发送请求（max_tokens=50）...")

    try:
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": "2+2等于几？"}
            ],
            temperature=0.0,
            max_tokens=50,  # 非常低的 token 限制
        )

        print(f"✅ API 调用成功!")
        print(f"Finish reason: {response.choices[0].finish_reason}")
        
        content = response.choices[0].message.content
        reasoning = response.choices[0].message.reasoning_content if hasattr(response.choices[0].message, 'reasoning_content') else None
        
        if reasoning:
            print(f"\n📝 思考过程: 存在（{len(reasoning)} 字符）")
        
        if content:
            print(f"\n💬 最终回复: {content}")
            return True
        else:
            print(f"\n⚠️ 没有最终回复（可能因 token 限制被截断）")
            if reasoning:
                print(f"💡 建议：增加 max_tokens 让模型完成输出")
            return False
            
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return False


async def main():
    print("=" * 60)
    print("yunduodsv32 思考模式控制测试")
    print("尝试多种方法关闭或限制思维链")
    print("=" * 60)
    
    results = {
        "enable_thinking=false": await test_with_enable_thinking_false(),
        "无思考参数": await test_without_thinking_param(),
        "低max_tokens": await test_with_low_max_tokens(),
    }
    
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    for method, result in results.items():
        status = "✅ 成功" if result else "❌ 失败"
        print(f"{method}: {status}")
    
    print("\n" + "=" * 60)
    print("结论与建议")
    print("=" * 60)
    print("当前模型信息:")
    print(f"  - 配置名称: yunduodsv32")
    print(f"  - 实际模型: nvidia/glm4.7 (后端: z-ai/glm4.7)")
    print(f"  - 类型: 思考型模型（返回 reasoning_content）")
    
    print("\n💡 如果需要关闭思维链，建议:")
    print("  1. 切换到非思考型模型（如 ds_chat、qwen_7b）")
    print("  2. 或者使用 enable_thinking=false 参数（如果 API 支持）")
    print("  3. 在代码中处理 reasoning_content 字段，提取最终回复")


if __name__ == "__main__":
    asyncio.run(main())
