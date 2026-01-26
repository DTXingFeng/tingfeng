import asyncio
import base64
import httpx
import io
from PIL import Image
from openai import AsyncOpenAI
from src.config.ai_config import ai_config, ai_config_manager

async def process_and_encode_image(url: str, max_size: int = 1024) -> str:
    """
    从 URL 下载图片，如果长边超过 max_size 则等比缩小，并返回 base64 编码
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch image: {response.status_code}")
        
        # 加载图片
        img_bytes = io.BytesIO(response.content)
        img = Image.open(img_bytes)
        
        # 处理动图 (GIF, WebP 等)
        if getattr(img, "is_animated", False):
            # 动图通常很大且 API 不支持，我们提取第一帧
            img.seek(0)
            img = img.convert("RGB")
        
        # 处理非 RGB 格式 (RGBA, P, L 等)
        if img.mode != "RGB":
            img = img.convert("RGB")
            
        # 检查尺寸
        width, height = img.size
        if max(width, height) > max_size:
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
        # 转换回 base64
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=85)
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

async def describe_image(image_url: str) -> str:
    """
    使用 VLM 模型识别图片内容
    """
    # 1. 获取配置
    model_alias = ai_config.image_model
    if not model_alias:
        return "未配置图像识别模型"
    
    creds = ai_config_manager.get_model_credentials(model_alias)
    if not creds:
        return f"找不到模型别名 '{model_alias}' 的配置"

    # 2. 准备客户端
    client = AsyncOpenAI(
        api_key=creds["api_key"],
        base_url=creds["base_url"]
    )

    # 3. 下载并处理图片
    try:
        base64_image = await process_and_encode_image(image_url)
    except Exception as e:
        return f"图片处理失败: {str(e)}"

    # 4. 发送请求
    try:
        # 提示词要求：识别类型（梗图、游戏等），抓住群聊语境下的重点
        prompt = (
            "请用一句话描述这张图片，需重点识别其在群聊语境下的属性（如：梗图/Meme、游戏截图、生活照、网页截图等）。要求：\n"
            "1. 描述最核心的视觉信息及意图（如梗图的槽点、游戏的具体场景）。\n"
            "2. 字数控制在 60 字以内，直接输出描述。"
        )

        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                }
            ],
            max_tokens=500,
        )

        description = response.choices[0].message.content.strip()
        return description

    except Exception as e:
        return f"图像识别出错: {str(e)}"

async def get_vlm_description(url: str) -> str:
    """包装函数，供 message_processor 调用"""
    if not url:
        return "图片 URL 为空"
    
    # 在这里实现真正的识别逻辑
    description = await describe_image(url)
    return description
