"""
测试：在项目中使用 chat_template_kwargs 关闭思维链

这个脚本展示了如何在项目中修改 API 调用以关闭思维链
"""

import asyncio
from openai import AsyncOpenAI
import sys
import os

sys.path.append(os.getcwd())

from src.config.ai_config import ai_config_manager


async def call_ai_with_thinking_control(
    model_alias: str,
    messages: list,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    disable_thinking: bool = True,
) -> dict:
    """
    调用 AI 模型，支持控制思维链

    Args:
        model_alias: 模型别名
        messages: 消息列表
        temperature: 温度参数
        max_tokens: 最大 token 数
        disable_thinking: 是否关闭思维链

    Returns:
        包含 content 和 thinking 的字典
    """
    creds = ai_config_manager.get_model_credentials(model_alias)
    if not creds:
        return {"success": False, "error": f"无法获取模型 {model_alias} 的凭据"}

    client = AsyncOpenAI(
        api_key=creds["api_key"],
        base_url=creds["base_url"],
        timeout=60.0
    )

    try:
        # 构建请求参数
        request_params = {
            "model": creds["model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # 如果需要关闭思维链，添加 chat_template_kwargs
        if disable_thinking:
            request_params["extra_body"] = {
                "chat_template_kwargs": {
                    "enable_thinking": False,
                    "clear_thinking": True
                }
            }

        response = await client.chat.completions.create(**request_params)

        # 提取思考过程和最终回复
        reasoning = response.choices[0].message.reasoning_content if hasattr(response.choices[0].message, 'reasoning_content') else None
        content = response.choices[0].message.content

        return {
            "success": True,
            "content": content,
            "thinking": reasoning,
            "has_thinking": reasoning is not None,
            "model": creds["model"],
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def demo_usage():
    """演示如何使用关闭思维链的功能"""
    print("=" * 60)
    print("在项目中关闭思维链 - 使用示例")
    print("=" * 60)

    model_alias = "yunduodsv32"

    # 示例 1：关闭思维链
    print("\n【示例 1】关闭思维链")
    result1 = await call_ai_with_thinking_control(
        model_alias=model_alias,
        messages=[
            {"role": "user", "content": "你好，请介绍一下自己"}
        ],
        disable_thinking=True  # 关闭思维链
    )

    if result1["success"]:
        print(f"✅ 调用成功")
        print(f"模型: {result1['model']}")
        print(f"思考过程: {'存在' if result1['has_thinking'] else '不存在'} ✅")
        print(f"回复: {result1['content']}")
    else:
        print(f"❌ 调用失败: {result1.get('error')}")

    # 示例 2：保留思维链
    print("\n" + "-" * 60)
    print("\n【示例 2】保留思维链（对比）")
    result2 = await call_ai_with_thinking_control(
        model_alias=model_alias,
        messages=[
            {"role": "user", "content": "你好，请介绍一下自己"}
        ],
        disable_thinking=False  # 保留思维链
    )

    if result2["success"]:
        print(f"✅ 调用成功")
        print(f"思考过程: {'存在 (' + str(len(result2['thinking'])) + ' 字符)' if result2['has_thinking'] else '不存在'}")
        if result2['has_thinking']:
            print(f"思考内容预览: {result2['thinking'][:100]}...")
        print(f"回复: {result2['content']}")

    # 示例 3：添加 system 提示词
    print("\n" + "-" * 60)
    print("\n【示例 3】关闭思维链 + 自定义 system 提示")
    result3 = await call_ai_with_thinking_control(
        model_alias=model_alias,
        messages=[
            {
                "role": "system",
                "content": "你是一个友好的 AI 助手，名叫听风。请简洁地回答用户问题。"
            },
            {"role": "user", "content": "你叫什么名字？"}
        ],
        disable_thinking=True
    )

    if result3["success"]:
        print(f"✅ 调用成功")
        print(f"思考过程: {'存在' if result3['has_thinking'] else '不存在'} ✅")
        print(f"回复: {result3['content']}")


async def test_real_world_scenario():
    """测试真实场景：机器人回复"""
    print("\n" + "=" * 60)
    print("真实场景测试：机器人回复")
    print("=" * 60)

    model_alias = "yunduodsv32"

    # 模拟群聊消息
    user_message = "今天天气真好啊"
    group_context = "这是一个友好的聊天群"

    result = await call_ai_with_thinking_control(
        model_alias=model_alias,
        messages=[
            {
                "role": "system",
                "content": f"你是听风机器人，在{group_context}中。请用轻松友好的语气回复，不要展示思考过程。"
            },
            {"role": "user", "content": user_message}
        ],
        temperature=0.8,
        disable_thinking=True
    )

    if result["success"]:
        print(f"\n用户: {user_message}")
        print(f"听风: {result['content']}")
        print(f"\n✅ 无思考过程，直接回复！")
    else:
        print(f"❌ 失败: {result.get('error')}")


async def main():
    await demo_usage()
    await test_real_world_scenario()

    print("\n" + "=" * 60)
    print("集成指南")
    print("=" * 60)
    print("要在项目中使用关闭思维链功能：")
    print()
    print("1. 修改 src/utils/api_helper.py 的 call_ai_with_timeout 函数")
    print("   添加 disable_thinking 参数")
    print()
    print("2. 在调用 API 时传递 extra_body:")
    print("   ```python")
    print("   extra_body={")
    print("     'chat_template_kwargs': {")
    print("       'enable_thinking': False,")
    print("       'clear_thinking': True")
    print("     }")
    print("   }")
    print("   ```")
    print()
    print("3. 或者在需要的地方直接调用:")
    print("   from scripts.test_api_with_thinking_control import call_ai_with_thinking_control")
    print("   result = await call_ai_with_thinking_control(..., disable_thinking=True)")
    print()
    print("4. 关于英伟达问题：")
    print("   模型自称 'GLM, Z.ai 训练'，不是英伟达")
    print("   如需修改，添加 system 消息覆盖默认提示词")


if __name__ == "__main__":
    asyncio.run(main())
