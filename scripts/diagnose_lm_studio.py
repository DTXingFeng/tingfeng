"""
LM Studio 连接诊断脚本

更详细的诊断和更长的超时时间
"""

import asyncio
import sys
import os

sys.path.append(os.getcwd())

from openai import AsyncOpenAI
import aiohttp


async def test_basic_connection(base_url: str = "http://localhost:1234/v1"):
    """测试基本的 HTTP 连接"""
    print("\n" + "=" * 70)
    print("步骤 1：测试基本 HTTP 连接")
    print("=" * 70)
    
    # 移除 /v1 后缀进行基础连接测试
    root_url = base_url.replace("/v1", "")
    print(f"尝试连接到: {root_url}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(root_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                print(f"✅ HTTP 连接成功！")
                print(f"   状态码: {response.status}")
                print(f"   响应头: {dict(response.headers)}")
                return True
    except asyncio.TimeoutError:
        print(f"❌ 连接超时（5秒）")
        return False
    except Exception as e:
        print(f"❌ 连接失败: {type(e).__name__}: {e}")
        return False


async def test_models_list(base_url: str = "http://localhost:1234/v1"):
    """测试模型列表 API"""
    print("\n" + "=" * 70)
    print("步骤 2：测试模型列表 API (GET /v1/models)")
    print("=" * 70)
    
    print(f"请求: {base_url}/models")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base_url}/models",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ 成功获取模型列表")
                    print(f"\n可用的模型:")
                    if "data" in data:
                        for model in data["data"]:
                            print(f"  - {model.get('id', 'Unknown')}")
                    return True
                else:
                    print(f"⚠️ 状态码: {response.status}")
                    text = await response.text()
                    print(f"   响应: {text[:200]}")
                    return False
    except asyncio.TimeoutError:
        print(f"❌ 请求超时（10秒）")
        return False
    except Exception as e:
        print(f"❌ 请求失败: {type(e).__name__}: {e}")
        return False


async def test_simple_chat_completion():
    """测试简单的对话完成（使用更长的超时时间）"""
    print("\n" + "=" * 70)
    print("步骤 3：测试对话完成 API")
    print("=" * 70)
    
    from src.config.ai_config import ai_config_manager
    
    model_alias = "glm-4.7-heretic-neo-code"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    if not creds:
        print(f"❌ 无法获取模型凭据")
        return False
    
    print(f"模型: {creds['model']}")
    print(f"API: {creds['base_url']}")
    
    try:
        client = AsyncOpenAI(
            api_key=creds["api_key"],
            base_url=creds["base_url"],
            timeout=60.0  # 增加超时时间到 60 秒
        )
        
        # 先尝试不使用 enable_thinking 参数
        print(f"\n测试 1：不使用 enable_thinking 参数")
        print(f"发送请求: '你好'")
        
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {"role": "user", "content": "你好，请用一句话介绍你自己。"}
            ],
            temperature=0.7,
            max_tokens=200,
        )
        
        print(f"✅ 请求成功！")
        print(f"\n响应信息:")
        print(f"  - 模型: {response.model}")
        print(f"  - Finish Reason: {response.choices[0].finish_reason}")
        
        content = response.choices[0].message.content
        print(f"  - 回复: {content}")
        
        # 检查是否有思考过程
        reasoning = response.choices[0].message.reasoning_content if hasattr(response.choices[0].message, 'reasoning_content') else None
        
        if reasoning:
            print(f"  - 思考过程: 存在（{len(reasoning)} 字符）")
            print(f"    预览: {reasoning[:100]}...")
        else:
            print(f"  - 思考过程: 不存在")
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 请求失败")
        print(f"   错误类型: {type(e).__name__}")
        print(f"   错误信息: {error_msg}")
        
        # 详细错误分析
        if "timeout" in error_msg.lower():
            print(f"\n💡 超时原因可能包括：")
            print(f"   1. 模型还在加载中（首次加载 GGUF 模型需要较长时间）")
            print(f"   2. 系统资源不足")
            print(f"   3. 模型文件过大")
            print(f"\n   建议：等待模型完全加载后再试，或使用更小的模型")
        elif "connection" in error_msg.lower():
            print(f"\n💡 连接失败，请检查：")
            print(f"   1. LM Studio 的服务器是否已启动")
            print(f"   2. 端口号是否正确（默认 1234）")
        elif "model" in error_msg.lower():
            print(f"\n💡 模型相关错误，请检查：")
            print(f"   1. 模型名称是否正确")
            print(f"   2. 模型是否已加载到 LM Studio 中")
        
        return False


async def test_with_enable_thinking_param():
    """测试带 enable_thinking=false 参数的请求"""
    print("\n" + "=" * 70)
    print("步骤 4：测试 enable_thinking=false 参数")
    print("=" * 70)
    
    from src.config.ai_config import ai_config_manager
    
    model_alias = "glm-4.7-heretic-neo-code"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    if not creds:
        print(f"❌ 无法获取模型凭据")
        return False
    
    print(f"发送请求，使用 enable_thinking=false...")
    
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
                {"role": "user", "content": "1+1等于几？直接回答数字。"}
            ],
            temperature=0.0,
            max_tokens=100,
            extra_body={
                "enable_thinking": False
            }
        )
        
        print(f"✅ 请求成功！")
        
        content = response.choices[0].message.content
        reasoning = response.choices[0].message.reasoning_content if hasattr(response.choices[0].message, 'reasoning_content') else None
        
        print(f"\n结果:")
        print(f"  - 回复: {content}")
        print(f"  - 思考过程: {'存在' if reasoning else '不存在'}")
        
        if reasoning:
            print(f"    ⚠️ enable_thinking=false 可能未生效")
        else:
            print(f"    ✅ enable_thinking=false 成功禁用思考模式！")
        
        return True
        
    except Exception as e:
        print(f"❌ 请求失败: {type(e).__name__}: {e}")
        return False


async def main():
    print("=" * 70)
    print("LM Studio 详细连接诊断")
    print("=" * 70)
    
    base_url = "http://localhost:1234/v1"
    
    results = {}
    
    # 步骤 1：基本连接
    results["HTTP 连接"] = await test_basic_connection(base_url)
    
    # 步骤 2：模型列表
    results["模型列表"] = await test_models_list(base_url)
    
    # 如果基本连接成功，继续测试
    if results.get("HTTP 连接") or results.get("模型列表"):
        # 步骤 3：简单对话
        results["对话完成"] = await test_simple_chat_completion()
        
        # 步骤 4：enable_thinking 参数
        if results.get("对话完成"):
            results["enable_thinking 参数"] = await test_with_enable_thinking_param()
    
    # 总结
    print("\n" + "=" * 70)
    print("诊断总结")
    print("=" * 70)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:20s}: {status}")
    
    # 建议
    print("\n" + "=" * 70)
    print("故障排查建议")
    print("=" * 70)
    
    if not results.get("HTTP 连接"):
        print("❌ 无法连接到 LM Studio")
        print("\n请检查：")
        print("  1. LM Studio 应用是否已启动")
        print("  2. 在 LM Studio 右侧面板找到 'Server' 或 '开发者' 选项卡")
        print("  3. 点击 'Start Server' 启动服务器")
        print("  4. 确认端口号显示为 1234（或其他端口）")
        print("  5. 如果使用其他端口，请修改 ai_config.yaml 中的 base_url")
    
    elif not results.get("模型列表"):
        print("⚠️ 可以连接但无法获取模型列表")
        print("\n可能原因：")
        print("  - LM Studio 服务器未完全启动")
        print("  - 尚未加载任何模型")
    
    elif not results.get("对话完成"):
        print("⚠️ API 可用但对话失败")
        print("\n可能原因：")
        print("  - 模型正在加载中（首次加载大模型需要时间）")
        print("  - 模型名称不匹配")
        print("  - 内存不足")
        print("\n建议：")
        print("  1. 在 LM Studio 中检查模型是否已完全加载")
        print("  2. 尝试使用较小的模型进行测试")
        print("  3. 检查系统资源使用情况")
    
    else:
        print("✅ LM Studio 连接成功！")
        if results.get("enable_thinking 参数"):
            print("✅ enable_thinking 参数工作正常！")
        else:
            print("ℹ️ enable_thinking 参数效果需要进一步验证")


if __name__ == "__main__":
    asyncio.run(main())
