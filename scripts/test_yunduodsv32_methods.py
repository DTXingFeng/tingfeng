import asyncio
from openai import AsyncOpenAI
import sys
import os

sys.path.append(os.getcwd())

from src.config.ai_config import ai_config_manager


async def test_method_1_increase_tokens():
    """方法1：增加 max_tokens，让模型完成思考并生成最终回复"""
    print("\n" + "=" * 60)
    print("方法 1：增加 max_tokens（让模型完成思考+回复）")
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

    print(f"\n发送请求（max_tokens=2000）...")

    try:
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": "请简单介绍一下 Python，用一句话概括。"}
            ],
            temperature=0.7,
            max_tokens=2000,  # 大幅增加 token 限制
        )

        print(f"✅ API 调用成功!")
        print(f"Finish reason: {response.choices[0].finish_reason}")
        
        # 检查 reasoning_content
        if hasattr(response.choices[0].message, 'reasoning_content'):
            reasoning = response.choices[0].message.reasoning_content
            if reasoning:
                print(f"\n📝 思考过程（前200字符）:")
                print(f"{reasoning[:200]}...")
        
        # 检查 content
        content = response.choices[0].message.content
        if content:
            print(f"\n💬 最终回复:")
            print(f"{content}")
            return True
        else:
            print(f"\n⚠️ 仍然没有最终回复")
            return False
            
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return False


async def test_method_2_simple_prompt():
    """方法2：使用简单的提示词，避免触发思考模式"""
    print("\n" + "=" * 60)
    print("方法 2：使用简单提示词（避免触发思考）")
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

    print(f"\n发送请求（简单提示词）...")

    try:
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": "Python是什么？"}
            ],
            temperature=0.7,
            max_tokens=500,
        )

        print(f"✅ API 调用成功!")
        print(f"Finish reason: {response.choices[0].finish_reason}")
        
        content = response.choices[0].message.content
        reasoning = response.choices[0].message.reasoning_content if hasattr(response.choices[0].message, 'reasoning_content') else None
        
        if reasoning:
            print(f"\n📝 思考过程存在: 是（{len(reasoning)} 字符）")
        
        if content:
            print(f"\n💬 最终回复:")
            print(f"{content}")
            return True
        else:
            print(f"\n⚠️ 没有最终回复")
            return False
            
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return False


async def test_method_3_no_system_prompt():
    """方法3：不使用 system 提示，仅用 user 提示"""
    print("\n" + "=" * 60)
    print("方法 3：仅使用 user 提示（不使用 system）")
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

    print(f"\n发送请求（直接提问）...")

    try:
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": "直接回答，不要思考：1+1等于几？"}
            ],
            temperature=0.0,
            max_tokens=100,
        )

        print(f"✅ API 调用成功!")
        print(f"Finish reason: {response.choices[0].finish_reason}")
        
        content = response.choices[0].message.content
        reasoning = response.choices[0].message.reasoning_content if hasattr(response.choices[0].message, 'reasoning_content') else None
        
        if reasoning:
            print(f"\n📝 思考过程存在: 是（{len(reasoning)} 字符）")
            print(f"思考内容前100字符: {reasoning[:100]}...")
        
        if content:
            print(f"\n💬 最终回复:")
            print(f"{content}")
            return True
        else:
            print(f"\n⚠️ 没有最终回复")
            return False
            
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return False


async def test_method_4_temperature_zero():
    """方法4：使用 temperature=0，减少随机性"""
    print("\n" + "=" * 60)
    print("方法 4：使用 temperature=0（减少随机性）")
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

    print(f"\n发送请求（temperature=0）...")

    try:
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": "Python是什么？简短回答。"}
            ],
            temperature=0.0,
            max_tokens=500,
        )

        print(f"✅ API 调用成功!")
        print(f"Finish reason: {response.choices[0].finish_reason}")
        
        content = response.choices[0].message.content
        reasoning = response.choices[0].message.reasoning_content if hasattr(response.choices[0].message, 'reasoning_content') else None
        
        if reasoning:
            print(f"\n📝 思考过程存在: 是（{len(reasoning)} 字符）")
        
        if content:
            print(f"\n💬 最终回复:")
            print(f"{content}")
            return True
        else:
            print(f"\n⚠️ 没有最终回复")
            return False
            
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return False


async def main():
    print("=" * 60)
    print("yunduodsv32 模型思维链控制测试")
    print("测试多种方法尝试关闭或控制思维链")
    print("=" * 60)
    
    results = {
        "方法1-增加tokens": await test_method_1_increase_tokens(),
        "方法2-简单提示": await test_method_2_simple_prompt(),
        "方法3-无system提示": await test_method_3_no_system_prompt(),
        "方法4-temperature=0": await test_method_4_temperature_zero(),
    }
    
    print("\n" + "=" * 60)
    print("测试总结:")
    print("=" * 60)
    for method, result in results.items():
        status = "✅ 成功获取回复" if result else "❌ 未能获取回复"
        print(f"{method}: {status}")
    
    print("\n" + "=" * 60)
    print("分析结论:")
    print("=" * 60)
    
    if any(results.values()):
        print("✅ 模型本身工作正常，但具有思考型特性：")
        print("   - 返回 reasoning_content 字段（思考过程）")
        print("   - 需要足够的 max_tokens 才能完成思考+回复")
        print("   - 无法完全关闭思考模式，这是模型的特性")
        print("\n💡 建议使用方法：")
        print("   1. 增加 max_tokens（建议 2000+）")
        print("   2. 使用简洁的提示词")
        print("   3. 在代码中处理 reasoning_content 字段")
    else:
        print("❌ 所有方法都无法获取最终回复")
        print("   可能原因：模型配置问题或 API 限制")


if __name__ == "__main__":
    asyncio.run(main())
