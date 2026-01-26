import asyncio
import httpx
import json
from openai import AsyncOpenAI
import yaml
from pathlib import Path
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from src.config.ai_config import ai_config, ai_config_manager
from src.aimodel.memory.embeddings import get_embeddings
from src.aimodel.memory.vector_db import vector_db
from src.utils.db_manager import db_manager

async def test_embedding():
    print("--- [1/5] 测试 Embedding 模型 ---")
    try:
        texts = ["你好", "听风是谁？"]
        vectors = await get_embeddings(texts)
        if len(vectors) == 2 and len(vectors[0]) > 0:
            print("✅ Embedding 正常: 成功生成向量，维度为", len(vectors[0]))
            return True
    except Exception as e:
        print("❌ Embedding 失败:", e)
    return False

async def test_chat():
    print("\n--- [2/5] 测试 Chat 回复模型 ---")
    try:
        model_alias = ai_config.reply_model
        creds = ai_config_manager.get_model_credentials(model_alias)
        client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"])
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[{"role": "user", "content": "你好，请简单打个招呼"}],
            max_tokens=20
        )
        print("✅ Chat 正常: ", response.choices[0].message.content.strip())
        return True
    except Exception as e:
        print("❌ Chat 失败:", e)
    return False

async def test_decision():
    print("\n--- [3/5] 测试 Decision 决策模型 ---")
    try:
        model_alias = ai_config.decision_model
        creds = ai_config_manager.get_model_credentials(model_alias)
        client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"])
        # 测试 JSON 模式
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[{"role": "user", "content": "请输出一个JSON，包含'test': true字段"}],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()
        data = json.loads(content)
        if data.get("test") is True:
            print("✅ Decision 正常 (JSON 模式已开启)")
            return True
    except Exception as e:
        print("❌ Decision 失败:", e)
    return False

async def test_consolidation():
    print("\n--- [4/5] 测试 Consolidation 记忆固化模型 ---")
    try:
        model_alias = ai_config.consolidation_model
        creds = ai_config_manager.get_model_credentials(model_alias)
        client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"])
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[{"role": "user", "content": "提取事实：张三今天去爬山了。格式：'事实'"}],
            max_tokens=30
        )
        print("✅ Consolidation 正常:", response.choices[0].message.content.strip())
        return True
    except Exception as e:
        print("❌ Consolidation 失败:", e)
    return False

async def test_vlm():
    print("\n--- [5/5] 测试 VLM 图像识别模型 ---")
    try:
        model_alias = ai_config.image_model
        creds = ai_config_manager.get_model_credentials(model_alias)
        client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"])
        test_image_url = "https://sf-maas-uat-prod.oss-cn-shanghai.aliyuncs.com/dog.png"
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "图里有什么？"},
                        {"type": "image_url", "image_url": {"url": test_image_url}},
                    ],
                }
            ],
            max_tokens=30
        )
        print("✅ VLM 正常:", response.choices[0].message.content.strip())
        return True
    except Exception as e:
        print("❌ VLM 失败:", e)
    return False

async def main():
    print("=== 开始全系统 AI 功能检查 ===\n")
    results = {
        "Embedding": await test_embedding(),
        "Chat": await test_chat(),
        "Decision": await test_decision(),
        "Consolidation": await test_consolidation(),
        "VLM": await test_vlm()
    }
    
    print("\n=== 检查报告总结 ===")
    all_ok = True
    for name, ok in results.items():
        status = "🟢 正常" if ok else "🔴 异常"
        print(f"{name}: {status}")
        if not ok: all_ok = False
    
    if all_ok:
        print("\n✨ 所有 AI 功能均已就绪，系统运行正常！")
    else:
        print("\n⚠️ 部分功能存在异常，请检查配置。")

if __name__ == "__main__":
    asyncio.run(main())
