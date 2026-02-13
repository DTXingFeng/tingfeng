import asyncio
from openai import AsyncOpenAI
import yaml
from pathlib import Path


async def test_vlm_models():
    # 读取配置
    config_path = Path("ai_config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    api_key = config_data["platforms"]["siliconflow_official"]["api_key"]
    base_url = config_data["platforms"]["siliconflow_official"]["base_url"]

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    # 测试不同的候选模型名称
    candidate_models = [
        "Qwen/Qwen2-VL-7B-Instruct",
        "Qwen/Qwen2-VL-72B-Instruct",
        "deepseek-ai/deepseek-vl2-tiny",
        "Pro/Qwen/Qwen2-VL-7B-Instruct",
        "vendor/qwen/qwen2-vl-7b-instruct",
    ]

    test_image_url = "https://sf-maas-uat-prod.oss-cn-shanghai.aliyuncs.com/dog.png"

    for model in candidate_models:
        print(f"\n正在测试模型: {model} ...")
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "一张图描述这张图"},
                            {
                                "type": "image_url",
                                "image_url": {"url": test_image_url},
                            },
                        ],
                    }
                ],
                max_tokens=50,
            )
            print(f"✅ 成功! 回复: {response.choices[0].message.content}")
            print(f"最终确认可用模型名: {model}")
            return model
        except Exception as e:
            print(f"❌ 失败: {str(e)}")

    return None


if __name__ == "__main__":
    asyncio.run(test_vlm_models())
