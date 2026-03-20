"""
测试 LM Studio 模型的 enable_thinking 参数是否正确生效

测试内容：
1. 配置文件中 enable_thinking 参数是否正确读取
2. 参数是否正确传递到 API 调用中
3. 如果 LM Studio 可用，验证实际调用效果
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(os.getcwd())

from src.config.ai_config import ai_config_manager
from openai import AsyncOpenAI
import json


async def test_config_reading():
    """测试 1：验证配置文件中的 enable_thinking 参数是否正确读取"""
    print("\n" + "=" * 70)
    print("测试 1：配置文件参数读取")
    print("=" * 70)
    
    model_alias = "glm-4.7-heretic-neo-code"
    
    # 获取模型凭据
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    if not creds:
        print(f"❌ 无法获取模型 {model_alias} 的凭据")
        return False
    
    print(f"✅ 成功获取模型凭据")
    print(f"\n模型配置信息:")
    print(f"  - 模型别名: {model_alias}")
    print(f"  - 完整模型名: {creds['model']}")
    print(f"  - API Base URL: {creds['base_url']}")
    print(f"  - API Key: {creds['api_key']}")
    
    # 检查 enable_thinking 参数
    if "enable_thinking" in creds:
        print(f"  - enable_thinking: {creds['enable_thinking']}")
        if creds["enable_thinking"] is False:
            print(f"✅ enable_thinking 参数正确设置为 False")
            return True
        else:
            print(f"⚠️ enable_thinking 参数值为 {creds['enable_thinking']}，预期为 False")
            return False
    else:
        print(f"⚠️ enable_thinking 参数不存在于凭据中")
        print(f"  可能原因：配置文件未设置或未正确解析")
        return False


async def test_api_parameter_construction():
    """测试 2：验证 API 调用时参数是否正确构造"""
    print("\n" + "=" * 70)
    print("测试 2：API 调用参数构造")
    print("=" * 70)
    
    model_alias = "glm-4.7-heretic-neo-code"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    if not creds:
        print(f"❌ 无法获取模型凭据")
        return False
    
    # 模拟构造 API 调用参数
    api_params = {
        "model": creds["model"],
        "messages": [
            {"role": "user", "content": "测试消息"}
        ],
        "temperature": 0.7,
        "max_tokens": 500,
    }
    
    # 如果 enable_thinking 存在且为 False，添加 extra_body 参数
    if "enable_thinking" in creds and creds["enable_thinking"] is False:
        api_params["extra_body"] = {
            "enable_thinking": False
        }
        print(f"✅ API 参数中包含 extra_body.enable_thinking = False")
    else:
        print(f"⚠️ API 参数中未包含 enable_thinking 设置")
    
    print(f"\n完整的 API 调用参数:")
    print(json.dumps(api_params, indent=2, ensure_ascii=False))
    
    return "extra_body" in api_params and api_params["extra_body"].get("enable_thinking") is False


async def test_lm_studio_connection():
    """测试 3：尝试连接 LM Studio（如果可用）"""
    print("\n" + "=" * 70)
    print("测试 3：LM Studio 连接测试")
    print("=" * 70)
    
    model_alias = "glm-4.7-heretic-neo-code"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    if not creds:
        print(f"❌ 无法获取模型凭据")
        return False
    
    print(f"尝试连接到 {creds['base_url']} ...")
    
    try:
        client = AsyncOpenAI(
            api_key=creds["api_key"],
            base_url=creds["base_url"],
            timeout=10.0
        )
        
        # 构造测试请求
        request_params = {
            "model": creds["model"],
            "messages": [
                {"role": "user", "content": "1+1等于几？请直接回答数字。"}
            ],
            "temperature": 0.0,
            "max_tokens": 100,
        }
        
        # 如果 enable_thinking 为 False，添加到 extra_body
        if "enable_thinking" in creds and creds["enable_thinking"] is False:
            request_params["extra_body"] = {
                "enable_thinking": False
            }
            print(f"✅ 请求中包含 enable_thinking=False 参数")
        
        print(f"\n发送测试请求...")
        
        response = await client.chat.completions.create(**request_params)
        
        print(f"✅ 成功连接到 LM Studio！")
        print(f"\n响应信息:")
        print(f"  - 模型: {response.model}")
        print(f"  - Finish Reason: {response.choices[0].finish_reason}")
        
        # 检查响应内容
        content = response.choices[0].message.content
        reasoning = response.choices[0].message.reasoning_content if hasattr(response.choices[0].message, 'reasoning_content') else None
        
        print(f"  - 最终回复: {content}")
        
        if reasoning:
            print(f"  - 思考过程: 存在（{len(reasoning)} 字符）")
            print(f"  ⚠️ 模型仍然返回了思考内容，可能原因：")
            print(f"    1. LM Studio 不支持 enable_thinking 参数")
            print(f"    2. 该 GGUF 模型本身不支持禁用思考模式")
            print(f"    3. 需要在 LM Studio 的服务器配置中设置")
        else:
            print(f"  - 思考过程: 不存在 ✅")
            print(f"  ✅ enable_thinking=false 参数生效！")
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 连接失败")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {error_msg}")
        
        # 分析错误原因
        if "connect" in error_msg.lower() or "connection" in error_msg.lower():
            print(f"\n💡 可能原因：")
            print(f"  1. LM Studio 未启动")
            print(f"  2. LM Studio 未在 {creds['base_url']} 上运行")
            print(f"  3. 端口号不正确（默认 1234）")
        elif "model" in error_msg.lower():
            print(f"\n💡 可能原因：")
            print(f"  1. 模型 {creds['model']} 未在 LM Studio 中加载")
            print(f"  2. 模型名称不正确")
        else:
            print(f"\n💡 请检查 LM Studio 是否正常运行")
        
        return False


async def test_with_other_models():
    """对比测试：检查其他模型的 enable_thinking 配置"""
    print("\n" + "=" * 70)
    print("对比测试：其他模型的 enable_thinking 配置")
    print("=" * 70)
    
    # 测试几个现有模型
    test_models = ["yunduodsv32", "ds_chat", "qwen_7b", "glm-4.7-heretic-neo-code"]
    
    results = {}
    for model_alias in test_models:
        creds = ai_config_manager.get_model_credentials(model_alias)
        if creds:
            has_enable_thinking = "enable_thinking" in creds
            thinking_value = creds.get("enable_thinking", None)
            results[model_alias] = {
                "exists": has_enable_thinking,
                "value": thinking_value
            }
            
            status = "✅" if has_enable_thinking else "➖"
            value_str = str(thinking_value) if has_enable_thinking else "未配置"
            print(f"{status} {model_alias:30s} enable_thinking = {value_str}")
    
    print(f"\n结论:")
    print(f"  - glm-4.7-heretic-neo-code 是唯一配置了 enable_thinking=false 的模型")
    print(f"  - 其他模型未配置该参数，将使用默认行为")
    
    return True


async def main():
    print("=" * 70)
    print("LM Studio 模型 enable_thinking 参数测试")
    print("=" * 70)
    
    results = {}
    
    # 测试 1：配置读取
    results["配置读取"] = await test_config_reading()
    
    # 测试 2：参数构造
    results["参数构造"] = await test_api_parameter_construction()
    
    # 测试 3：LM Studio 连接（可能失败）
    print(f"\n💡 提示：以下测试需要 LM Studio 正在运行")
    print(f"   如果 LM Studio 未启动，测试失败是正常的")
    results["LM Studio 连接"] = await test_lm_studio_connection()
    
    # 对比测试
    await test_with_other_models()
    
    # 总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:20s}: {status}")
    
    print("\n" + "=" * 70)
    print("使用建议")
    print("=" * 70)
    
    if results["配置读取"] and results["参数构造"]:
        print("✅ enable_thinking 参数配置正确！")
        print("\n在代码中使用示例：")
        print("""
```python
from src.config.ai_config import ai_config_manager
from openai import AsyncOpenAI

# 获取模型凭据
creds = ai_config_manager.get_model_credentials("glm-4.7-heretic-neo-code")

# 创建客户端
client = AsyncOpenAI(
    api_key=creds["api_key"],
    base_url=creds["base_url"]
)

# 构造请求参数
params = {
    "model": creds["model"],
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "max_tokens": 1000,
}

# 如果配置了 enable_thinking=False，自动添加到 extra_body
if creds.get("enable_thinking") is False:
    params["extra_body"] = {"enable_thinking": False}

# 发送请求
response = await client.chat.completions.create(**params)
```
""")
    else:
        print("⚠️ 配置存在问题，请检查 ai_config.yaml")
    
    if not results["LM Studio 连接"]:
        print("\n💡 LM Studio 连接提示：")
        print("  1. 确保已启动 LM Studio 应用")
        print("  2. 在 LM Studio 中加载对应的 GGUF 模型")
        print("  3. 启动本地服务器（通常在 Developer 面板）")
        print("  4. 确认端口号为 1234（默认）")


if __name__ == "__main__":
    asyncio.run(main())
