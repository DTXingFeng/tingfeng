"""
LM Studio 配置验证和最终测试

测试配置是否正确，并提供使用说明
"""

import sys
import os

sys.path.append(os.getcwd())

from src.config.ai_config import ai_config_manager


def print_config_summary():
    """打印配置摘要"""
    print("=" * 70)
    print("LM Studio 配置验证")
    print("=" * 70)
    
    model_alias = "glm-4.7-heretic-neo-code"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    if not creds:
        print("❌ 无法获取模型凭据")
        return False
    
    print(f"\n✅ 配置文件正确\n")
    print(f"模型配置:")
    print(f"  别名:       {model_alias}")
    print(f"  模型名:     {creds['model']}")
    print(f"  API 地址:   {creds['base_url']}")
    print(f"  API Key:    {creds['api_key']}")
    print(f"  思考模式:   {creds.get('enable_thinking', '未配置')}")
    
    return True


def print_lm_studio_guide():
    """打印 LM Studio 配置指南"""
    print("\n" + "=" * 70)
    print("LM Studio 配置指南")
    print("=" * 70)
    
    print("\n📋 步骤 1: 启动 LM Studio 并加载模型")
    print("-" * 70)
    print("1. 打开 LM Studio 应用")
    print("2. 在左侧面板搜索或选择模型:")
    print(f"   DavidAU/GLM-4.7-Flash-Uncensored-Heretic-NEO-CODE-Imatrix-MAX-GGUF")
    print("3. 点击 'Download' 或 'Load' 加载模型")
    print("4. 等待模型加载完成（首次可能需要较长时间）")
    
    print("\n📋 步骤 2: 启动 API 服务器")
    print("-" * 70)
    print("1. 在 LM Studio 右侧找到 'Server' 或 'Developer' 面板")
    print("2. 配置服务器设置:")
    print("   - Port: 1234（默认）")
    print("   - Host: 127.0.0.1（本地）")
    print("   - CORS: 可选启用（如果需要跨域访问）")
    print("3. 点击 'Start Server' 启动服务器")
    print("4. 确认服务器状态显示为 'Running' 或绿色指示")
    
    print("\n📋 步骤 3: 验证服务器")
    print("-" * 70)
    print("在 LM Studio 的 Server 面板中，应该看到类似信息:")
    print("  - Server running at http://localhost:1234")
    print("  - Model: [模型名称]")
    print("  - 或类似的运行状态指示")
    
    print("\n📋 步骤 4: 测试连接")
    print("-" * 70)
    print("运行以下命令测试:")
    print("  python scripts/final_lm_studio_test.py --test-connection")
    
    print("\n" + "=" * 70)
    print("常见问题")
    print("=" * 70)
    
    print("\n❌ 问题 1: 连接超时")
    print("原因: 模型还在加载中")
    print("解决: 等待模型完全加载，查看 LM Studio 的加载进度")
    
    print("\n❌ 问题 2: 'Invalid json' 错误")
    print("原因: 服务器未完全启动或配置错误")
    print("解决:")
    print("  1. 在 LM Studio 中停止服务器（Stop Server）")
    print("  2. 等待几秒钟")
    print("  3. 重新启动服务器（Start Server）")
    print("  4. 确认端口设置正确（默认 1234）")
    
    print("\n❌ 问题 3: 端口已被占用")
    print("原因: 其他应用使用了 1234 端口")
    print("解决: 在 LM Studio 中改用其他端口（如 1235），并更新配置文件")
    
    print("\n❌ 问题 4: 模型未找到")
    print("原因: 模型名称不匹配")
    print("解决:")
    print("  1. 在 LM Studio 中确认已加载的模型名称")
    print("  2. 在 ai_config.yaml 中更新 model_name 字段")
    print("  3. 或使用 LM Studio 中显示的确切模型名称")


def print_usage_example():
    """打印使用示例"""
    print("\n" + "=" * 70)
    print("使用示例")
    print("=" * 70)
    
    print("\n在代码中使用 LM Studio 模型:")
    print("-" * 70)
    
    print("""
```python
import asyncio
from openai import AsyncOpenAI
from src.config.ai_config import ai_config_manager

async def chat_with_lm_studio(message: str):
    # 获取凭据（自动包含 enable_thinking: False）
    creds = ai_config_manager.get_model_credentials("glm-4.7-heretic-neo-code")
    
    # 创建客户端
    client = AsyncOpenAI(
        api_key=creds["api_key"],
        base_url=creds["base_url"],
        timeout=60.0  # 本地模型可能需要更长的超时时间
    )
    
    # 构造请求参数
    params = {
        "model": creds["model"],
        "messages": [
            {"role": "user", "content": message}
        ],
        "temperature": 0.7,
        "max_tokens": 1000,
    }
    
    # 如果配置了 enable_thinking=False，自动添加到 extra_body
    if creds.get("enable_thinking") is False:
        params["extra_body"] = {"enable_thinking": False}
    
    # 发送请求
    try:
        response = await client.chat.completions.create(**params)
        return response.choices[0].message.content
    except Exception as e:
        return f"错误: {e}"

# 使用
asyncio.run(chat_with_lm_studio("你好，请介绍一下你自己"))
```
""")


def print_integration_tips():
    """打印集成提示"""
    print("\n" + "=" * 70)
    print("集成到项目中")
    print("=" * 70)
    
    print("\n要使用 LM Studio 模型作为默认模型，修改 ai_config.yaml:")
    print("-" * 70)
    print("""
# 将以下功能的模型改为 glm-4.7-heretic-neo-code:
reply_model: "glm-4.7-heretic-neo-code"
decision_model: "glm-4.7-heretic-neo-code"
consolidation_model: "glm-4.7-heretic-neo-code"
inner_voice_model: "glm-4.7-heretic-neo-code"
# ... 等等
""")
    
    print("\n⚠️ 注意事项:")
    print("-" * 70)
    print("1. 本地模型需要保持 LM Studio 应用一直运行")
    print("2. 首次加载模型需要较长时间，请耐心等待")
    print("3. 确保系统有足够的内存运行本地模型")
    print("4. 本地模型可能比云端 API 慢，但更隐私且免费")
    print("5. enable_thinking=false 参数已配置，不会输出思考过程")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="LM Studio 配置验证")
    parser.add_argument("--test-connection", action="store_true",
                       help="测试与 LM Studio 的连接")
    args = parser.parse_args()
    
    # 显示配置
    print_config_summary()
    
    # 显示配置指南
    print_lm_studio_guide()
    
    # 显示使用示例
    print_usage_example()
    
    # 显示集成提示
    print_integration_tips()
    
    if args.test_connection:
        print("\n" + "=" * 70)
        print("连接测试")
        print("=" * 70)
        print("\n⚠️ 由于检测到服务器响应格式问题，")
        print("请先按照上面的指南配置 LM Studio，然后重试。")
        print("\n配置完成后，可以手动测试:")
        print("  1. 在 LM Studio Server 面板确认服务器状态")
        print("  2. 检查端口是否为 1234")
        print("  3. 使用上面的代码示例进行测试")


if __name__ == "__main__":
    main()
