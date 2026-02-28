import asyncio
import base64
import httpx
import io
import hashlib
from PIL import Image
from openai import AsyncOpenAI
from src.config.ai_config import ai_config, ai_config_manager
from src.utils.db_manager import db_manager
from src.utils.context_manager import context_manager
from src.utils.thinking_mode import thinking_handler


async def process_and_encode_image(url: str, max_size: int = 1024) -> tuple[str, str, bool]:
    """
    下载图片并返回 (base64编码, 内容哈希, 是否为动图)
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch image: {response.status_code}")

        content = response.content
        file_hash = hashlib.md5(content).hexdigest()

        # 加载图片
        img_bytes = io.BytesIO(content)
        img = Image.open(img_bytes)

        is_animated = getattr(img, "is_animated", False)

        if is_animated:
            # 动图处理：采样多帧并拼接
            frames = []
            n_frames = getattr(img, "n_frames", 1)
            # 采样 4 帧：首帧、1/3处、2/3处、末帧
            sample_indices = [0, n_frames // 3, (2 * n_frames) // 3, n_frames - 1]
            # 去重并排序
            sample_indices = sorted(list(set(sample_indices)))

            for i in sample_indices:
                img.seek(i)
                frame = img.convert("RGB")
                # 缩小单帧尺寸以防拼接后过大
                frame.thumbnail((512, 512))
                frames.append(frame)

            # 横向拼接
            total_width = sum(f.width for f in frames)
            max_height = max(f.height for f in frames)
            combined_img = Image.new("RGB", (total_width, max_height))

            x_offset = 0
            for f in frames:
                combined_img.paste(f, (x_offset, 0))
                x_offset += f.width
            img = combined_img
        else:
            # 非 RGB 格式处理
            if img.mode != "RGB":
                img = img.convert("RGB")

        # 最终缩放检查
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
        img.save(buffered, format="JPEG", quality=80)
        base64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

        return base64_str, file_hash, is_animated


async def describe_image(image_url: str, is_sticker: bool = False, file_id: str = None) -> str:
    """
    使用 VLM 模型识别图片内容。如果是表情包，会进行缓存处理。

    Args:
        image_url: 图片URL（用于下载）
        is_sticker: 是否为表情包
        file_id: OneBot的file字段（用于发送消息）
    """
    # 1. 预处理并获取哈希
    try:
        base64_image, file_hash, is_gif = await process_and_encode_image(image_url)
    except Exception as e:
        return f"图片处理失败: {str(e)}"

    # 2. 如果是表情包，检查缓存
    if is_sticker:
        cache = await db_manager.get_sticker_cache(file_hash)
        if cache:
            return f"[表情描述: {cache['description']}, 标签: {cache['tag']}]"

    # 3. 获取 AI 配置
    model_alias = ai_config.image_model
    if not model_alias:
        return "未配置图像识别模型"

    creds = ai_config_manager.get_model_credentials(model_alias)
    if not creds:
        return f"找不到模型别名 '{model_alias}' 的配置"

    client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=30.0)

    # 4. 准备提示词
    gif_hint = "（这张图片是一张动图/GIF 的多帧采样拼接图，请分析其动作序列和变化过程）" if is_gif else ""

    if is_sticker:
        prompt = (
            f"你是一个表情包专家。{gif_hint}请深度解析这张表情包并完成以下任务：\n"
            "1. **文字提取**：必须完整、准确地提取图中出现的文字内容（如果有）。\n"
            "2. **画面描述** 用一句话描述角色的动作、神情及整体画风。如果是动图，请描述其动作过程。\n"
            "3. **情感定性**：从[开心、大哭、暴躁、委屈、傲娇、得意、摸摸头、疑惑、震惊]中选一个最贴切的标签。\n"
            '输出格式：\'标签|文字:"内容", 描述:"具体画面"\'。'
        )
    else:
        prompt = f"请用中文深度描述这张图片的内容。{gif_hint}如果有文字，必须完整提取并概括其核心含义。请留意图中的主体、场景及直观感受，输出为一段 50 字以内的流畅平文本。"

    # 5. 上下文截断检查（主要针对文本提示词，虽然通常不会超限，但为了统一管理）
    optimized_prompt, prompt_tokens = context_manager.truncate_text(
        text=prompt, model_alias=model_alias, max_output_tokens=500
    )

    # 6. 发送请求
    try:
        response = await client.chat.completions.create(
            model=creds["model"],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": optimized_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                }
            ],
        )

        # 使用思考模式处理器处理响应
        response_result = thinking_handler.process_non_streaming_response(response)
        result = response_result["content"].strip()

        if response_result["has_thinking"]:
            from src.utils.logger import get_logger

            logger = get_logger(__name__)
            logger.info(f"图像识别使用思考模式: 推理长度={len(response_result['thinking'])}")

        # 6. 如果是表情包，解析并存入缓存
        if is_sticker:
            if "|" in result:
                tag, desc = result.split("|", 1)
                tag = tag.strip()
                desc = desc.strip()
                # 优先使用 file_id，如果没有则使用 url
                stored_id = file_id or image_url
                await db_manager.save_sticker_cache(file_hash, desc, tag, stored_id)
                return f"[表情描述: {desc}, 标签: {tag}]"
            else:
                # 兜底处理
                stored_id = file_id or image_url
                await db_manager.save_sticker_cache(file_hash, result, "未知", stored_id)
                return f"[表情描述: {result}]"

        return result

    except Exception as e:
        return f"图像识别出错: {str(e)}"


async def get_vlm_description(url: str, is_sticker: bool = False, file_id: str = None) -> str:
    """包装函数，供 message_processor 调用"""
    if not url:
        return "图片 URL 为空"

    description = await describe_image(url, is_sticker=is_sticker, file_id=file_id)
    return description
