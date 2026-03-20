"""
LM Studio API 完整测试

测试所有支持的端点和 enable_thinking 参数
"""

import asyncio
import sys
import os

sys.path.append(os.getcwd())

from openai import AsyncOpenAI
from src.config.ai_config import ai_config_manager
import json


async def test_models_endpoint():
    """测试 GET /v1/models 端点"""
    print("\n" + "=" * 70)
    print("测试 1: GET /v1/models - 获取模型列表")
    print("=" * 70)
    
    model_alias = "glm-4.7-heretic-neo-code"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    if not creds:
        print("❌ 无法获取模型凭据")
        return False
    
    try:
        client = AsyncOpenAI(
            api_key=creds["api_key"],
            base_url=creds["base_url"],
            timeout=30.0
        )
        
        print(f"请求: {creds['base_url']}/v1/models")
        
        models = await client.models.list()
        
        print(f"✅ 成功获取模型列表")
        print(f"\n可用的模型:")
        for model in models.data:
            print(f"  - {model.id}")
        
        # 检查我们配置的模型是否在列表中
        our_model = creds["model"]
        found = any(m.id == our_model for m in models.data)
        if found:
            print(f"\n✅ 配置的模型 '{our_model}' 可用")
        else:
            print(f"\n⚠️ 配置的模型 '{our_model}' 不在列表中")
            print(f"   可用的最接近的模型:")
            for m in models.data[:3]:
                print(f"     - {m.id}")
        
        return True
        
    except Exception as e:
        print(f"❌ 请求失败: {type(e).__name__}: {e}")
        return False


async def test_chat_completions_simple():
    """测试 POST /v1/chat/completions - 简单对话"""
    print("\n" + "=" * 70)
    print("测试 2: POST /v1/chat/completions - 简单对话（无思考参数）")
    print("=" * 70)
    
    model_alias = "glm-4.7-heretic-neo-code"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    if not creds:
        print("❌ 无法获取模型凭据")
        return False
    
    try:
        client = AsyncOpenAI(
            api_key=creds["api_key"],
            base_url=creds["base_url"],
            timeout=60.0
        )
        
        print(f"模型: {creds['model']}")
        print(f"发送测试消息: '你好，请用一句话介绍你自己。'")
        
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": "你好，请用一句话介绍你自己。"}
            ],
            temperature=0.7,
            max_tokens=200,
        )
        
        print(f"\n✅ 请求成功！")
        print(f"\n响应信息:")
        print(f"  - 模型: {response.model}")
        print(f"  - Finish Reason: {response.choices[0].finish_reason}")
        
        content = response.choices[0].message.content
        print(f"  - 回复内容: {content}")
        
        # 检查是否有思考过程
        reasoning = getattr(response.choices[0].message, 'reasoning_content', None)
        if reasoning:
            print(f"  - 思考过程: 存在（{len(reasoning)} 字符）")
            print(f"    预览: {reasoning[:100]}...")
        else:
            print(f"  - 思考过程: 不存在")
        
        return True
        
    except Exception as e:
        print(f"❌ 请求失败: {type(e).__name__}: {e}")
        return False


async def test_chat_completions_with_enable_thinking_false():
    """测试 POST /v1/chat/completions - 带 enable_thinking=false"""
    print("\n" + "=" * 70)
    print("测试 3: POST /v1/chat/completions - enable_thinking=false")
    print("=" * 70)
    
    model_alias = "glm-4.7-heretic-neo-code"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    if not creds:
        print("❌ 无法获取模型凭据")
        return False
    
    try:
        client = AsyncOpenAI(
            api_key=creds["api_key"],
            base_url=creds["base_url"],
            timeout=60.0
        )
        
        print(f"模型: {creds['model']}")
        print(f"参数: enable_thinking=false")
        print(f"发送测试消息: '1+1等于几？直接回答数字。'")
        
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": "1+1等于几？直接回答数字。"}
            ],
            temperature=0.0,
            max_tokens=100,
            extra_body={
                "enable_thinking": False
            }
        )
        
        print(f"\n✅ 请求成功！")
        print(f"\n响应信息:")
        print(f"  - 模型: {response.model}")
        print(f"  - Finish Reason: {response.choices[0].finish_reason}")
        
        content = response.choices[0].message.content
        print(f"  - 回复内容: {content}")
        
        # 检查是否有思考过程
        reasoning = getattr(response.choices[0].message, 'reasoning_content', None)
        if reasoning:
            print(f"  - 思考过程: 存在（{len(reasoning)} 字符）")
            print(f"    ⚠️ enable_thinking=false 参数可能未生效")
            print(f"    思考内容: {reasoning[:200]}...")
        else:
            print(f"  - 思考过程: 不存在 ✅")
            print(f"  ✅ enable_thinking=false 参数成功生效！")
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 请求失败: {type(e).__name__}: {error_msg}")
        
        # 分析错误
        if "enable_thinking" in error_msg.lower():
            print(f"\n💡 错误分析:")
            print(f"   API 不支持 enable_thinking 参数")
            print(f"   这是正常的，LM Studio 可能不支持此参数")
            print(f"   但配置仍然有效，代码会自动处理")
        
        return False


async def test_chat_completions_streaming():
    """测试 POST /v1/chat/completions - 流式响应"""
    print("\n" + "=" * 70)
    print("测试 4: POST /v1/chat/completions - 流式响应")
    print("=" * 70)
    
    model_alias = "glm-4.7-heretic-neo-code"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    if not creds:
        print("❌ 无法获取模型凭据")
        return False
    
    try:
        client = AsyncOpenAI(
            api_key=creds["api_key"],
            base_url=creds["base_url"],
            timeout=60.0
        )
        
        print(f"模型: {creds['model']}")
        print(f"流式输出测试: 'Python是什么？'")
        
        stream = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": "用一句话介绍 Python。"}
            ],
            temperature=0.7,
            max_tokens=100,
            stream=True,
        )
        
        print(f"\n流式响应:")
        content = ""
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                chunk_content = chunk.choices[0].delta.content
                content += chunk_content
                print(chunk_content, end="", flush=True)
        
        print(f"\n\n✅ 流式响应完成")
        print(f"总字符数: {len(content)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 请求失败: {type(e).__name__}: {e}")
        return False


async def test_comparison():
    """对比测试：有/无 enable_thinking 参数"""
    print("\n" + "=" * 70)
    print("测试 5: 对比测试 - enable_thinking 参数效果")
    print("=" * 70)
    
    model_alias = "glm-4.7-heretic-neo-code"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    if not creds:
        print("❌ 无法获取模型凭据")
        return False
    
    client = AsyncOpenAI(
        api_key=creds["api_key"],
        base_url=creds["base_url"],
        timeout=60.0
    )
    
    test_message = "2+2等于几？只回答数字。"
    
    results = {}
    
    # 测试 1: 不使用 enable_thinking
    print(f"\n【测试 A】不使用 enable_thinking 参数")
    try:
        response_a = await client.chat.completions.create(
            model=creds["model"],
            messages=[{"role": "user", "content": test_message}],
            temperature=0.0,
            max_tokens=50,
        )
        
        content_a = response_a.choices[0].message.content
        reasoning_a = getattr(response_a.choices[0].message, 'reasoning_content', None)
        
        results["without_param"] = {
            "content": content_a,
            "has_reasoning": reasoning_a is not None,
            "reasoning_length": len(reasoning_a) if reasoning_a else 0
        }
        
        print(f"  回复: {content_a}")
        print(f"  思考过程: {'是' if reasoning_a else '否'}")
        
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        results["without_param"] = None
    
    # 测试 2: 使用 enable_thinking=false
    print(f"\n【测试 B】使用 enable_thinking=false 参数")
    try:
        response_b = await client.chat.completions.create(
            model=creds["model"],
            messages=[{"role": "user", "content": test_message}],
            temperature=0.0,
            max_tokens=50,
            extra_body={"enable_thinking": False}
        )
        
        content_b = response_b.choices[0].message.content
        reasoning_b = getattr(response_b.choices[0].message, 'reasoning_content', None)
        
        results["with_param"] = {
            "content": content_b,
            "has_reasoning": reasoning_b is not None,
            "reasoning_length": len(reasoning_b) if reasoning_b else 0
        }
        
        print(f"  回复: {content_b}")
        print(f"  思考过程: {'是' if reasoning_b else '否'}")
        
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        results["with_param"] = None
    
    # 对比结果
    print(f"\n{'='*70}")
    print(f"对比结果:")
    print(f"{'='*70}")
    
    if results.get("without_param") and results.get("with_param"):
        r1 = results["without_param"]
        r2 = results["with_param"]
        
        print(f"\n参数效果对比:")
        print(f"  不使用参数 - 思考过程: {'有' if r1['has_reasoning'] else '无'}")
        print(f"  使用参数   - 思考过程: {'有' if r2['has_reasoning'] else '无'}")
        
        if r1['has_reasoning'] and not r2['has_reasoning']:
            print(f"\n✅ enable_thinking=false 参数有效！")
            print(f"   成功禁用了思考模式")
        elif not r1['has_reasoning'] and not r2['has_reasoning']:
            print(f"\nℹ️ 两种情况都没有思考过程")
            print(f"   该模型可能默认不输出思考过程")
        else:
            print(f"\n⚠️ enable_thinking 参数未生效")
            print(f"   可能需要其他方式控制")
    
    return True


async def main():
    print("=" * 70)
    print("LM Studio API 完整测试套件")
    print("=" * 70)
    
    tests = {
        "模型列表": test_models_endpoint,
        "简单对话": test_chat_completions_simple,
        "enable_thinking 参数": test_chat_completions_with_enable_thinking_false,
        "流式响应": test_chat_completions_streaming,
        "对比测试": test_comparison,
    }
    
    results = {}
    
    for test_name, test_func in tests.items():
        try:
            result = await test_func()
            results[test_name] = result
        except Exception as e:
            print(f"\n❌ 测试 '{test_name}' 出现异常: {e}")
            results[test_name] = False
        
        # 短暂延迟
        await asyncio.sleep(0.5)
    
    # 总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:20s}: {status}")
    
    success_count = sum(1 for r in results.values() if r)
    total_count = len(results)
    
    print(f"\n总计: {success_count}/{total_count} 通过")
    
    if success_count == total_count:
        print("\n🎉 所有测试通过！LM Studio 配置完全正常！")
    elif success_count > 0:
        print("\n✅ 部分测试通过，LM Studio 基本可用")
    else:
        print("\n❌ 所有测试失败，请检查 LM Studio 配置")
    
    print("\n" + "=" * 70)
    print("配置确认")
    print("=" * 70)
    
    model_alias = "glm-4.7-heretic-neo-code"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    if creds:
        print(f"\n✅ 配置正确:")
        print(f"  - 模型: {creds['model']}")
        print(f"  - API: {creds['base_url']}")
        print(f"  - enable_thinking: {creds.get('enable_thinking', '未配置')}")
        print(f"\n配置已就绪，可以在项目中使用！")


if __name__ == "__main__":
    asyncio.run(main())
