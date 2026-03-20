import asyncio
from openai import AsyncOpenAI
import sys
import os

sys.path.append(os.getcwd())

from src.config.ai_config import ai_config_manager


async def test_current_model_with_high_tokens():
    """测试当前模型：增加 max_tokens 让模型完成思考+回复"""
    print("\n" + "=" * 60)
    print("方案 1：增加 max_tokens（让当前模型完成输出）")
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
    print(f"说明: 该模型是思考型模型，需要足够的 token 完成思考+回复")
    print(f"发送请求（max_tokens=2000）...")

    try:
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": "请简单介绍一下 Python，用一句话概括。"}
            ],
            temperature=0.7,
            max_tokens=2000,
        )

        print(f"✅ API 调用成功!")
        
        reasoning = response.choices[0].message.reasoning_content if hasattr(response.choices[0].message, 'reasoning_content') else None
        content = response.choices[0].message.content
        
        if reasoning:
            print(f"\n📝 思考过程: {len(reasoning)} 字符")
        
        if content:
            print(f"\n💬 最终回复:")
            print(f"{content}")
            print(f"\n✅ 成功获取回复!")
            return True
        else:
            print(f"\n⚠️ 仍然没有最终回复")
            return False
            
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return False


async def test_ds_chat_model():
    """测试方案 2：使用 DeepSeek Chat（非思考型模型）"""
    print("\n" + "=" * 60)
    print("方案 2：切换到 ds_chat 模型（非思考型）")
    print("=" * 60)
    
    model_alias = "ds_chat"
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
    print(f"说明: 这是 DeepSeek 对话模型，不会返回思考过程")
    print(f"发送请求...")

    try:
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": "请简单介绍一下 Python，用一句话概括。"}
            ],
            temperature=0.7,
            max_tokens=200,
        )

        print(f"✅ API 调用成功!")
        
        reasoning = response.choices[0].message.reasoning_content if hasattr(response.choices[0].message, 'reasoning_content') else None
        content = response.choices[0].message.content
        
        if reasoning:
            print(f"\n📝 思考过程: 存在（意外）")
        else:
            print(f"\n📝 思考过程: 不存在 ✅")
        
        if content:
            print(f"\n💬 最终回复:")
            print(f"{content}")
            print(f"\n✅ 完美！没有思考过程，直接回复!")
            return True
        else:
            print(f"\n⚠️ 没有最终回复")
            return False
            
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return False


async def test_qwen_7b_model():
    """测试方案 3：使用 Qwen 7B（非思考型模型）"""
    print("\n" + "=" * 60)
    print("方案 3：切换到 qwen_7b 模型（非思考型）")
    print("=" * 60)
    
    model_alias = "qwen_7b"
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
    print(f"说明: Qwen 7B 是标准对话模型，不会返回思考过程")
    print(f"发送请求...")

    try:
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": "请简单介绍一下 Python，用一句话概括。"}
            ],
            temperature=0.7,
            max_tokens=200,
        )

        print(f"✅ API 调用成功!")
        
        reasoning = response.choices[0].message.reasoning_content if hasattr(response.choices[0].message, 'reasoning_content') else None
        content = response.choices[0].message.content
        
        if reasoning:
            print(f"\n📝 思考过程: 存在（意外）")
        else:
            print(f"\n📝 思考过程: 不存在 ✅")
        
        if content:
            print(f"\n💬 最终回复:")
            print(f"{content}")
            print(f"\n✅ 完美！没有思考过程，直接回复!")
            return True
        else:
            print(f"\n⚠️ 没有最终回复")
            return False
            
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return False


async def main():
    print("=" * 60)
    print("yunduodsv32 思维链关闭方案测试")
    print("=" * 60)
    
    results = {}
    
    # 测试当前模型（增加 tokens）
    results["当前yunduodsv32(增加tokens)"] = await test_current_model_with_high_tokens()
    
    # 测试替代模型
    results["切换到ds_chat"] = await test_ds_chat_model()
    results["切换到qwen_7b"] = await test_qwen_7b_model()
    
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    for method, result in results.items():
        status = "✅ 成功" if result else "❌ 失败"
        print(f"{method}: {status}")
    
    print("\n" + "=" * 60)
    print("最终结论与建议")
    print("=" * 60)
    
    print("\n📊 当前状况:")
    print("  - yunduodsv32 模型实际使用 nvidia/glm4.7")
    print("  - 这是一个思考型模型，总是返回 reasoning_content")
    print("  - enable_thinking=false 参数对该 API 无效")
    
    print("\n💡 关闭思维链的方案:")
    print("  【方案 1】增加 max_tokens（继续使用 yunduodsv32）")
    print("    - 优点：保持当前配置")
    print("    - 缺点：仍会有思考过程，只是能看到最终回复")
    print("    - 建议：max_tokens 设置为 2000+")
    
    print("\n  【方案 2】切换到非思考型模型（推荐）")
    print("    - 可选模型：ds_chat, qwen_7b")
    print("    - 优点：完全无思考过程，响应更快")
    print("    - 缺点：需要修改 ai_config.yaml 配置")
    
    print("\n📝 配置修改示例（切换到 ds_chat）:")
    print("""
    # 在 ai_config.yaml 中修改：
    reply_model: "ds_chat"              # 聊天回复主模型
    decision_model: "ds_chat"           # 决策判断模型
    consolidation_model: "qwen_7b"      # 记忆固化模型
    inner_voice_model: "qwen_7b"        # 内心独白模型
    # ... 其他功能也改为非思考型模型
    """)
    
    print("\n  【方案 3】代码中处理 reasoning_content")
    print("    - 在代码中提取 content 字段，忽略 reasoning_content")
    print("    - 适用于需要保留当前模型配置的情况")
    print("    - 示例代码见：scripts/test_thinking_solution.py")


if __name__ == "__main__":
    asyncio.run(main())
