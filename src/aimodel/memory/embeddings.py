import httpx
from src.config.ai_config import ai_config, ai_config_manager
from typing import List

async def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    使用配置的 Embedding 模型生成向量
    """
    model_alias = ai_config.memory_model
    if not model_alias:
        raise ValueError("未配置 Embedding 模型 (memory_model)")
    
    creds = ai_config_manager.get_model_credentials(model_alias)
    if not creds:
        raise ValueError(f"找不到模型别名 '{model_alias}' 的配置")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{creds['base_url']}/embeddings",
            headers={
                "Authorization": f"Bearer {creds['api_key']}",
                "Content-Type": "application/json"
            },
            json={
                "model": creds["model"],
                "input": texts
            },
            timeout=30.0
        )
        
        if response.status_code != 200:
            raise Exception(f"Embedding API error: {response.text}")
            
        data = response.json()
        # SiliconFlow 的返回格式通常符合 OpenAI 标准
        embeddings = [item["embedding"] for item in data["data"]]
        return embeddings
