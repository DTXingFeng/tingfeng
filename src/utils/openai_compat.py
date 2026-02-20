"""
OpenAI API 平台兼容性处理工具

提供统一的 API 调用接口，自动处理不同平台的兼容性问题
"""

import json
from typing import Dict, Any, Optional
from openai import AsyncOpenAI, BadRequestError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OpenAICompat:
    """
    OpenAI API 兼容性包装器

    功能：
    - 自动检测平台是否支持 response_format 参数
    - 自动重试不支持的参数
    - 缓存检测结果以提升性能
    """

    def __init__(self):
        self._platform_capabilities: Dict[str, Dict[str, bool]] = {}

    def _get_platform_key(self, base_url: str, model: str) -> str:
        """生成平台唯一标识"""
        return f"{base_url}#{model}"

    def _is_response_format_error(self, error: Exception) -> bool:
        """
        检查错误是否由 response_format 参数引起

        Args:
            error: API 调用异常

        Returns:
            bool: 是否为 response_format 相关错误
        """
        error_str = str(error).lower()
        error_body = ""

        # 尝试提取错误体
        if hasattr(error, "body") and error.body:
            if isinstance(error.body, dict):
                error_body = json.dumps(error.body).lower()
            elif isinstance(error.body, str):
                error_body = error.body.lower()

        combined_text = error_str + error_body

        # 检查常见的错误指示
        indicators = [
            "response_format",
            "response format",
            "parameter",
            "参数非法",
            "invalid parameter",
            "unsupported parameter",
        ]

        # 检查错误码
        status_code = None
        if hasattr(error, "status_code"):
            status_code = error.status_code
        elif hasattr(error, "status"):
            status_code = error.status
        elif hasattr(error, "code"):
            status_code = error.code

        # 如果错误码是 400 且包含相关关键词
        if status_code == 400:
            return any(indicator in combined_text for indicator in indicators)

        return False

    async def create_with_auto_fallback(
        self,
        client: AsyncOpenAI,
        model: str,
        messages: list,
        base_url: str,
        use_response_format: bool = True,
        stream: bool = False,
        **kwargs,
    ):
        """
        带有自动降级的 chat.completions.create 调用

        Args:
            client: AsyncOpenAI 客户端
            model: 模型名称
            messages: 消息列表
            base_url: API base_url（用于缓存）
            use_response_format: 是否尝试使用 response_format
            stream: 是否使用流式响应
            **kwargs: 其他传递给 API 的参数

        Returns:
            API 响应对象（streaming 或 non-streaming）
        """
        platform_key = self._get_platform_key(base_url, model)

        # 检查缓存：如果已知不支持，直接跳过
        if platform_key in self._platform_capabilities:
            if not self._platform_capabilities[platform_key].get("supports_response_format", True):
                use_response_format = False

        # 首次尝试：尝试带 response_format 调用（如果请求）
        if use_response_format:
            try:
                request_params = {
                    "model": model,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                    "stream": stream,
                    **kwargs,
                }
                response = await client.chat.completions.create(**request_params)

                # 成功：缓存平台支持信息
                self._platform_capabilities[platform_key] = {"supports_response_format": True}
                return response

            except (BadRequestError, Exception) as e:
                # 检查是否为 response_format 相关错误
                if self._is_response_format_error(e):
                    logger.debug(f"平台 {platform_key} 不支持 response_format，自动降级")
                    # 缓存不支持信息
                    self._platform_capabilities[platform_key] = {"supports_response_format": False}
                else:
                    # 其他错误，直接抛出
                    raise

        # 降级尝试：不带 response_format
        request_params = {"model": model, "messages": messages, "stream": stream, **kwargs}
        response = await client.chat.completions.create(**request_params)

        return response

    def should_try_response_format(self, base_url: str, model: str) -> bool:
        """
        检查是否应该尝试使用 response_format（基于缓存）

        Args:
            base_url: API base_url
            model: 模型名称

        Returns:
            bool: 是否应该尝试
        """
        platform_key = self._get_platform_key(base_url, model)
        if platform_key in self._platform_capabilities:
            return self._platform_capabilities[platform_key].get("supports_response_format", True)
        return True  # 未知平台，默认尝试


# 全局单例
openai_compat = OpenAICompat()
