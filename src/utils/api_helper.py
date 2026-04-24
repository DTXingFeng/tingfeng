"""
AI API 调用辅助工具：提供统一的超时处理和错误恢复机制
"""

import asyncio
from typing import Any, Dict, Optional
from openai import AsyncOpenAI
from src.config.ai_config import ai_config_manager
from src.utils.logger import get_logger
from src.utils.retry import retry_on_timeout

logger = get_logger(__name__)


class APICallResult:
    """API 调用结果封装"""

    def __init__(
        self,
        success: bool,
        content: str = "",
        error: Optional[str] = None,
        has_thinking: bool = False,
        thinking: str = "",
    ):
        self.success = success
        self.content = content
        self.error = error
        self.has_thinking = has_thinking
        self.thinking = thinking


async def call_ai_with_timeout(
    model_alias: str,
    messages: list,
    max_retries: int = 2,
    timeout: float = 60.0,
    temperature: float = 0.7,
    use_stream: bool = False,
) -> APICallResult:
    """
    调用 AI 模型并自动处理超时和重试

    Args:
        model_alias: 模型别名
        messages: 消息列表
        max_retries: 最大重试次数
        timeout: 超时时间（秒）
        temperature: 温度参数
        use_stream: 是否使用流式响应

    Returns:
        APICallResult 对象
    """
    creds = ai_config_manager.get_model_credentials(model_alias)
    if not creds:
        return APICallResult(success=False, error=f"无法获取模型 {model_alias} 的凭据")

    @retry_on_timeout(max_retries=max_retries, base_delay=1.0, max_delay=5.0)
    async def _make_call():
        client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=timeout)

        # 构建基础请求参数
        request_params = {
            "model": creds["model"],
            "messages": messages,
            "temperature": temperature,
            "stream": use_stream,
        }

        # 自动提取配置的额外字段（如 thinking、enable_thinking）添加到 extra_body
        base_fields = ["base_url", "api_key", "model", "max_context_tokens", "enable_thinking"]
        extra_body = {}
        for key, value in creds.items():
            if key not in base_fields and value is not None:
                extra_body[key] = value
        
        # 如果配置了 enable_thinking，添加到 extra_body
        if "enable_thinking" in creds:
            extra_body["enable_thinking"] = creds["enable_thinking"]
        
        # 如果有额外字段，添加到请求中
        if extra_body:
            request_params["extra_body"] = extra_body

        if use_stream:
            response = await client.chat.completions.create(**request_params)
            return response, True
        else:
            response = await client.chat.completions.create(**request_params)
            return response, False

    try:
        response, is_stream = await _make_call()

        if is_stream:
            from src.utils.thinking_mode import thinking_handler

            stream_result = await thinking_handler.process_streaming_response(
                stream=response,
                model_name=creds["model"],
                collect_thinking=True,
            )

            return APICallResult(
                success=True,
                content=stream_result["content"],
                has_thinking=stream_result["has_thinking"],
                thinking=stream_result["thinking"],
            )
        else:
            from src.utils.thinking_mode import thinking_handler

            response_result = thinking_handler.process_non_streaming_response(response)
            return APICallResult(
                success=True,
                content=response_result["content"],
                has_thinking=response_result["has_thinking"],
                thinking=response_result["thinking"],
            )

    except Exception as e:
        error_msg = str(e)
        logger.error(f"AI 调用失败 ({model_alias}): {error_msg}")
        return APICallResult(success=False, error=error_msg)


async def call_ai_with_timeout_and_json(
    model_alias: str,
    messages: list,
    max_retries: int = 2,
    timeout: float = 60.0,
    temperature: float = 0.3,
) -> tuple[bool, Any, str]:
    """
    调用 AI 并尝试解析 JSON 结果

    Returns:
        (success, parsed_data, error_message)
    """
    import json
    from src.utils.openai_compat import openai_compat

    creds = ai_config_manager.get_model_credentials(model_alias)
    if not creds:
        return False, None, f"无法获取模型 {model_alias} 的凭据"

    @retry_on_timeout(max_retries=max_retries, base_delay=1.0, max_delay=5.0)
    async def _make_call():
        client = AsyncOpenAI(api_key=creds["api_key"], base_url=creds["base_url"], timeout=timeout)

        return await openai_compat.create_with_auto_fallback(
            client=client,
            model=creds["model"],
            messages=messages,
            base_url=creds["base_url"],
            use_response_format=True,
            stream=False,
            temperature=temperature,
            enable_thinking=creds.get("enable_thinking"),
        )

    try:
        response = await _make_call()

        from src.utils.thinking_mode import thinking_handler

        response_result = thinking_handler.process_non_streaming_response(response)
        result_text = response_result["content"]

        if not result_text or not result_text.strip():
            return False, None, "AI 返回空内容"

        result_text = result_text.strip()

        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        if not result_text:
            return False, None, "清理后内容为空"

        try:
            data = json.loads(result_text)
            return True, data, ""
        except json.JSONDecodeError as e:
            return False, None, f"JSON 解析失败: {e}"

    except Exception as e:
        error_msg = str(e)
        return False, None, error_msg
