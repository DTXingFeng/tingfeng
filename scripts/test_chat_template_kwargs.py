import asyncio
from openai import AsyncOpenAI
import sys
import os

sys.path.append(os.getcwd())

from src.config.ai_config import ai_config_manager


async def test_with_chat_template_kwargs():
    """测试使用 chat_template_kwargs 参数关闭思考模式"""
    print("\n" + "=" * 60)
    print("测试：chat_template_kwargs.enable_thinking = false")
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
    print(f"测试参数:")
    print(f"  - chat_template_kwargs.enable_thinking: false")
    print(f"  - chat_template_kwargs.clear_thinking: true")
    print(f"\n发送请求...")

    try:
        # OpenAI SDK 不直接支持 chat_template_kwargs
        # 需要使用 extra_body 传递
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": "你好"}
            ],
            temperature=1.0,
            max_tokens=16384,
            stream=False,
            # 关键参数
            extra_body={
                "chat_template_kwargs": {
                    "enable_thinking": False,
                    "clear_thinking": True
                }
            }
        )

        print(f"✅ API 调用成功!")
        
        reasoning = response.choices[0].message.reasoning_content if hasattr(response.choices[0].message, 'reasoning_content') else None
        content = response.choices[0].message.content
        
        print(f"\n📝 分析结果:")
        if reasoning:
            print(f"  - 思考过程: 存在（{len(reasoning)} 字符）")
            print(f"  - 内容预览: {reasoning[:150]}...")
        else:
            print(f"  - 思考过程: 不存在 ✅")
        
        if content:
            print(f"\n💬 模型回复:")
            print(f"{content}")
            
            # 检查是否包含英伟达相关信息
            if "英伟达" in content or "NVIDIA" in content.upper() or "nvidia" in content.lower():
                print(f"\n⚠️ 检测到模型回复中包含英伟达相关信息")
                print(f"💡 这可能是模型的默认系统提示词，需要通过 system 消息覆盖")
            else:
                print(f"\n✅ 回复正常，无英伟达相关信息")
            
            return True
        else:
            print(f"\n⚠️ 没有最终回复")
            return False
            
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_with_custom_system_prompt():
    """测试使用自定义 system 提示词覆盖默认行为"""
    print("\n" + "=" * 60)
    print("测试：使用 system 提示词覆盖默认行为")
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
    print(f"说明: 添加 system 消息来覆盖模型的默认行为")

    try:
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {
                    "role": "system",
                    "content": "你是一个通用的 AI 助手。请直接回答用户的问题，不要提及任何公司或组织名称。"
                },
                {"role": "user", "content": "你好，请介绍一下自己"}
            ],
            temperature=0.7,
            max_tokens=500,
            extra_body={
                "chat_template_kwargs": {
                    "enable_thinking": False,
                    "clear_thinking": True
                }
            }
        )

        print(f"✅ API 调用成功!")
        
        reasoning = response.choices[0].message.reasoning_content if hasattr(response.choices[0].message, 'reasoning_content') else None
        content = response.choices[0].message.content
        
        if reasoning:
            print(f"\n📝 思考过程: 存在（{len(reasoning)} 字符）")
        else:
            print(f"\n📝 思考过程: 不存在 ✅")
        
        if content:
            print(f"\n💬 模型回复:")
            print(f"{content}")
            
            if "英伟达" in content or "NVIDIA" in content.upper():
                print(f"\n⚠️ 仍然包含英伟达信息")
                return False
            else:
                print(f"\n✅ 成功覆盖默认提示词！")
                return True
        else:
            print(f"\n⚠️ 没有最终回复")
            return False
            
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return False


async def test_simple_comparison():
    """对比测试：有/无 chat_template_kwargs"""
    print("\n" + "=" * 60)
    print("对比测试：参数效果对比")
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

    test_message = "1+1等于几？"

    # 测试 1：不使用 chat_template_kwargs
    print(f"\n【测试 1】不使用 chat_template_kwargs")
    try:
        response1 = await client.chat.completions.create(
            model=creds["model"],
            messages=[{"role": "user", "content": test_message}],
            temperature=0.0,
            max_tokens=200,
        )
        
        reasoning1 = response1.choices[0].message.reasoning_content if hasattr(response1.choices[0].message, 'reasoning_content') else None
        content1 = response1.choices[0].message.content
        
        print(f"  思考过程: {'存在' if reasoning1 else '不存在'} ({len(reasoning1) if reasoning1 else 0} 字符)")
        print(f"  回复: {content1 if content1 else '无'}")
        
    except Exception as e:
        print(f"  ❌ 失败: {e}")

    # 测试 2：使用 chat_template_kwargs
    print(f"\n【测试 2】使用 chat_template_kwargs")
    try:
        response2 = await client.chat.completions.create(
            model=creds["model"],
            messages=[{"role": "user", "content": test_message}],
            temperature=0.0,
            max_tokens=200,
            extra_body={
                "chat_template_kwargs": {
                    "enable_thinking": False,
                    "clear_thinking": True
                }
            }
        )
        
        reasoning2 = response2.choices[0].message.reasoning_content if hasattr(response2.choices[0].message, 'reasoning_content') else None
        content2 = response2.choices[0].message.content
        
        print(f"  思考过程: {'存在' if reasoning2 else '不存在'} ({len(reasoning2) if reasoning2 else 0} 字符)")
        print(f"  回复: {content2 if content2 else '无'}")
        
        # 对比结果
        print(f"\n📊 对比结果:")
        if reasoning1 and not reasoning2:
            print(f"  ✅ chat_template_kwargs 成功关闭思考模式！")
            return True
        elif not reasoning1 and not reasoning2:
            print(f"  ⚠️ 两种方式都没有思考过程（可能模型默认不思考）")
            return True
        elif reasoning1 and reasoning2:
            if len(reasoning2) < len(reasoning1):
                print(f"  ⚠️ 思考过程减少了，但未完全关闭")
                print(f"     减少: {len(reasoning1)} → {len(reasoning2)} 字符")
            else:
                print(f"  ⚠️ chat_template_kwargs 无效")
            return False
        else:
            print(f"  ⚠️ 意外情况")
            return False
        
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return False


async def main():
    print("=" * 60)
    print("chat_template_kwargs 参数测试")
    print("测试 enable_thinking=false 和 clear_thinking=true")
    print("=" * 60)
    
    results = {
        "使用chat_template_kwargs": await test_with_chat_template_kwargs(),
        "使用system提示词覆盖": await test_with_custom_system_prompt(),
        "对比测试": await test_simple_comparison(),
    }
    
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    for method, result in results.items():
        status = "✅ 成功" if result else "❌ 失败"
        print(f"{method}: {status}")
    
    print("\n" + "=" * 60)
    print("使用建议")
    print("=" * 60)
    print("如果 chat_template_kwargs 有效：")
    print("  在调用 API 时添加：")
    print("  ```python")
    print("  extra_body={")
    print("    'chat_template_kwargs': {")
    print("      'enable_thinking': False,")
    print("      'clear_thinking': True")
    print("    }")
    print("  }")
    print("  ```")
    print("\n如果模型仍提及英伟达：")
    print("  添加 system 消息覆盖默认提示词：")
    print("  ```python")
    print("  messages = [")
    print("    {'role': 'system', 'content': '你是一个通用助手...'},")
    print("    {'role': 'user', 'content': '...'}")
    print("  ]")
    print("  ```")


if __name__ == "__main__":
    asyncio.run(main())
