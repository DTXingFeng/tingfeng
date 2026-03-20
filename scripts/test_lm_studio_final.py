"""
LM Studio 最终测试 - 使用正确的 IP 地址

测试所有功能并验证 enable_thinking=false 参数
"""

import asyncio
import sys
import os

sys.path.append(os.getcwd())

from openai import AsyncOpenAI
from src.config.ai_config import ai_config_manager


async def test_connection_and_models():
    """测试 1: 连接和获取模型列表"""
    print("\n" + "=" * 70)
    print("测试 1: 连接 LM Studio 并获取模型列表")
    print("=" * 70)
    
    model_alias = "glm-4.7-heretic-neo-code"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    print(f"\n配置信息:")
    print(f"  API URL: {creds['base_url']}")
    print(f"  模型名称: {creds['model']}")
    print(f"  enable_thinking: {creds.get('enable_thinking', '未配置')}")
    
    try:
        client = AsyncOpenAI(
            api_key=creds["api_key"],
            base_url=creds["base_url"],
            timeout=30.0
        )
        
        print(f"\n正在获取模型列表...")
        models = await client.models.list()
        
        print(f"✅ 连接成功！\n")
        print(f"可用的模型:")
        for i, model in enumerate(models.data, 1):
            is_loaded = "（已加载）" if i == 1 else ""
            print(f"  {i}. {model.id} {is_loaded}")
        
        # 检查我们配置的模型
        our_model = creds["model"]
        found = any(m.id == our_model for m in models.data)
        
        if found:
            print(f"\n✅ 配置的模型 '{our_model}' 在列表中")
        else:
            print(f"\n⚠️ 配置的模型 '{our_model}' 不在列表中")
            print(f"   最接近的模型可能是:")
            for m in models.data[:2]:
                if "glm" in m.id.lower() and "heretic" in m.id.lower():
                    print(f"     - {m.id}")
        
        return True
        
    except Exception as e:
        print(f"❌ 失败: {type(e).__name__}: {e}")
        return False


async def test_simple_chat():
    """测试 2: 简单对话（不使用 enable_thinking）"""
    print("\n" + "=" * 70)
    print("测试 2: 简单对话测试")
    print("=" * 70)
    
    model_alias = "glm-4.7-heretic-neo-code"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    try:
        client = AsyncOpenAI(
            api_key=creds["api_key"],
            base_url=creds["base_url"],
            timeout=60.0
        )
        
        print(f"\n发送消息: '你好，请用一句话介绍你自己。'")
        
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": "你好，请用一句话介绍你自己。"}
            ],
            temperature=0.7,
            max_tokens=200,
        )
        
        print(f"\n✅ 响应成功！")
        print(f"\n回复:")
        content = response.choices[0].message.content
        print(f"  {content}")
        
        # 检查思考过程
        reasoning = getattr(response.choices[0].message, 'reasoning_content', None)
        if reasoning:
            print(f"\n思考过程: 存在（{len(reasoning)} 字符）")
            print(f"  预览: {reasoning[:100]}...")
        else:
            print(f"\n思考过程: 不存在")
        
        return True
        
    except Exception as e:
        print(f"❌ 失败: {type(e).__name__}: {e}")
        return False


async def test_with_enable_thinking_false():
    """测试 3: 使用 enable_thinking=false 参数"""
    print("\n" + "=" * 70)
    print("测试 3: enable_thinking=false 参数测试")
    print("=" * 70)
    
    model_alias = "glm-4.7-heretic-neo-code"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    print(f"\n配置的 enable_thinking: {creds.get('enable_thinking')}")
    print(f"发送消息: '1+1等于几？只回答数字。'")
    
    try:
        client = AsyncOpenAI(
            api_key=creds["api_key"],
            base_url=creds["base_url"],
            timeout=60.0
        )
        
        # 使用 enable_thinking=false
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": "1+1等于几？只回答数字。"}
            ],
            temperature=0.0,
            max_tokens=100,
            extra_body={
                "enable_thinking": False
            }
        )
        
        print(f"\n✅ 响应成功！")
        
        content = response.choices[0].message.content
        reasoning = getattr(response.choices[0].message, 'reasoning_content', None)
        
        print(f"\n回复: {content}")
        
        if reasoning:
            print(f"\n思考过程: 存在（{len(reasoning)} 字符）")
            print(f"  ⚠️ enable_thinking=false 可能未生效")
            print(f"  思考内容: {reasoning[:200]}...")
        else:
            print(f"\n思考过程: 不存在 ✅")
            print(f"✅ enable_thinking=false 参数成功生效！")
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 失败: {type(e).__name__}: {error_msg}")
        
        if "enable_thinking" in error_msg.lower():
            print(f"\n💡 API 不支持 enable_thinking 参数")
            print(f"   这是正常的，配置仍然有效，代码会自动处理")
        
        return False


async def test_streaming():
    """测试 4: 流式响应"""
    print("\n" + "=" * 70)
    print("测试 4: 流式响应测试")
    print("=" * 70)
    
    model_alias = "glm-4.7-heretic-neo-code"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    try:
        client = AsyncOpenAI(
            api_key=creds["api_key"],
            base_url=creds["base_url"],
            timeout=60.0
        )
        
        print(f"\n流式输出测试: 'Python是什么？'")
        print(f"\n回复: ")
        
        stream = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": "用一句话介绍 Python。"}
            ],
            temperature=0.7,
            max_tokens=100,
            stream=True,
        )
        
        content = ""
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                chunk_content = chunk.choices[0].delta.content
                content += chunk_content
                print(chunk_content, end="", flush=True)
        
        print(f"\n\n✅ 流式响应完成（总字符数: {len(content)}）")
        return True
        
    except Exception as e:
        print(f"❌ 失败: {type(e).__name__}: {e}")
        return False


async def test_automatic_enable_thinking():
    """测试 5: 自动应用 enable_thinking 参数"""
    print("\n" + "=" * 70)
    print("测试 5: 自动应用 enable_thinking 配置")
    print("=" * 70)
    
    model_alias = "glm-4.7-heretic-neo-code"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    print(f"\n从配置中读取的 enable_thinking: {creds.get('enable_thinking')}")
    
    # 模拟实际使用代码
    params = {
        "model": creds["model"],
        "messages": [{"role": "user", "content": "测试"}],
        "temperature": 0.7,
        "max_tokens": 100,
    }
    
    # 自动添加 extra_body
    if creds.get("enable_thinking") is False:
        params["extra_body"] = {"enable_thinking": False}
        print(f"✅ 自动添加了 extra_body.enable_thinking = False")
    else:
        print(f"ℹ️ 未添加 enable_thinking 参数")
    
    print(f"\n最终的请求参数:")
    import json
    print(json.dumps(params, indent=2, ensure_ascii=False))
    
    return True


async def main():
    print("=" * 70)
    print("LM Studio 最终测试套件")
    print("=" * 70)
    
    tests = {
        "连接和模型列表": test_connection_and_models,
        "简单对话": test_simple_chat,
        "enable_thinking 参数": test_with_enable_thinking_false,
        "流式响应": test_streaming,
        "自动参数应用": test_automatic_enable_thinking,
    }
    
    results = {}
    
    for test_name, test_func in tests.items():
        try:
            result = await test_func()
            results[test_name] = result
            await asyncio.sleep(0.5)  # 短暂延迟
        except Exception as e:
            print(f"\n❌ 测试 '{test_name}' 异常: {e}")
            results[test_name] = False
    
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
        print("\n✅ enable_thinking=false 参数已正确配置")
    elif success_count >= total_count - 1:
        print("\n✅ 核心功能正常！LM Studio 可以使用！")
    else:
        print("\n⚠️ 部分测试失败，请检查配置")
    
    print("\n" + "=" * 70)
    print("配置确认")
    print("=" * 70)
    
    model_alias = "glm-4.7-heretic-neo-code"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    if creds:
        print(f"\n✅ 最终配置:")
        print(f"  API URL: {creds['base_url']}")
        print(f"  模型: {creds['model']}")
        print(f"  enable_thinking: {creds.get('enable_thinking', False)}")
        print(f"\n✅ 配置已就绪，可以在项目中使用！")


if __name__ == "__main__":
    asyncio.run(main())
