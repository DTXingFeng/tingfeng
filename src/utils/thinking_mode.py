"""
思考模式处理工具

提供统一的思考模式支持，兼容不同 AI 模型的思考字段
"""

import asyncio
from typing import Dict, Optional, Any, AsyncIterator
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ThinkingModeHandler:
    """
    思考模式处理器

    功能：
    - 统一处理不同模型的思考内容字段（reasoning_content、thinking_content 等）
    - 支持流式和非流式响应
    - 提供思考内容收集和最终内容提取
    - 支持多种思考模型（DeepSeek R1、OpenAI o1/o3 等）
    """

    KNOWN_THINKING_FIELDS = [
        "reasoning_content",
        "thinking_content",
        "thought",
        "thinking",
        "reasoning",
    ]

    def __init__(self, enable_thinking_log: bool = True):
        """
        初始化思考模式处理器

        Args:
            enable_thinking_log: 是否记录思考过程日志
        """
        self.enable_thinking_log = enable_thinking_log
        self._stats = {
            "total_calls": 0,
            "thinking_enabled_calls": 0,
            "thinking_chars_collected": 0,
        }

    def _extract_thinking_from_delta(self, delta: Any) -> Optional[str]:
        """
        从 chunk delta 中提取思考内容

        Args:
            delta: OpenAI 响应的 delta 对象

        Returns:
            思考内容字符串，如果没有则返回 None
        """
        if not delta:
            return None

        for field in self.KNOWN_THINKING_FIELDS:
            if hasattr(delta, field):
                content = getattr(delta, field)
                if content:
                    return content

        return None

    def _extract_content_from_delta(self, delta: Any) -> Optional[str]:
        """
        从 chunk delta 中提取最终内容

        Args:
            delta: OpenAI 响应的 delta 对象

        Returns:
            最终内容字符串，如果没有则返回 None
        """
        if not delta:
            return None

        if hasattr(delta, "content") and delta.content:
            return delta.content

        return None

    async def process_streaming_response(
        self,
        stream: AsyncIterator[ChatCompletionChunk],
        model_name: str = "unknown",
        collect_thinking: bool = True,
        chunk_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        处理流式响应，分离思考内容和最终内容

        Args:
            stream: OpenAI 流式响应迭代器
            model_name: 模型名称（用于日志）
            collect_thinking: 是否收集思考内容
            chunk_callback: 每个块到达时的回调函数

        Returns:
            包含以下字段的字典：
            - content: 最终回复内容
            - thinking: 思考过程内容（如果有）
            - has_thinking: 是否包含思考内容
            - chunk_count: 接收到的块数量
            - elapsed_time: 处理耗时（秒）
        """
        self._stats["total_calls"] += 1

        content = ""
        thinking = ""
        chunk_count = 0
        start_time = asyncio.get_event_loop().time()
        has_thinking = False

        async for chunk in stream:
            chunk_count += 1

            if chunk_callback:
                await chunk_callback(chunk)

            delta = chunk.choices[0].delta if chunk.choices else None

            if not delta:
                continue

            if collect_thinking:
                thinking_chunk = self._extract_thinking_from_delta(delta)
                if thinking_chunk:
                    thinking += thinking_chunk
                    has_thinking = True

                    if self.enable_thinking_log and chunk_count <= 5:
                        logger.debug(f"[{model_name}] 思考内容: {thinking_chunk[:50]}...")

            content_chunk = self._extract_content_from_delta(delta)
            if content_chunk:
                content += content_chunk

                if self.enable_thinking_log and chunk_count <= 5:
                    logger.debug(f"[{model_name}] 最终内容: {content_chunk[:50]}...")

        elapsed = asyncio.get_event_loop().time() - start_time

        if has_thinking:
            self._stats["thinking_enabled_calls"] += 1
            self._stats["thinking_chars_collected"] += len(thinking)

            logger.info(
                f"[{model_name}] 思考模式: "
                f"思考长度={len(thinking)}, 最终长度={len(content)}, "
                f"块数={chunk_count}, 耗时={elapsed:.1f}s"
            )

        return {
            "content": content.strip(),
            "thinking": thinking.strip(),
            "has_thinking": has_thinking,
            "chunk_count": chunk_count,
            "elapsed_time": elapsed,
        }

    def process_non_streaming_response(self, response: ChatCompletion) -> Dict[str, Any]:
        """
        处理非流式响应，提取思考内容和最终内容

        Args:
            response: OpenAI 非流式响应对象

        Returns:
            包含以下字段的字典：
            - content: 最终回复内容
            - thinking: 思考过程内容（如果有）
            - has_thinking: 是否包含思考内容
        """
        self._stats["total_calls"] += 1

        message = response.choices[0].message if response.choices else None
        if not message:
            return {
                "content": "",
                "thinking": "",
                "has_thinking": False,
            }

        content = message.content or ""
        thinking = ""

        for field in self.KNOWN_THINKING_FIELDS:
            if hasattr(message, field):
                thinking_content = getattr(message, field)
                if thinking_content:
                    thinking = thinking_content
                    break

        has_thinking = bool(thinking)

        if has_thinking:
            self._stats["thinking_enabled_calls"] += 1
            self._stats["thinking_chars_collected"] += len(thinking)

            if self.enable_thinking_log:
                logger.info(f"思考模式检测: " f"思考长度={len(thinking)}, 最终长度={len(content)}")

        return {
            "content": content.strip(),
            "thinking": thinking.strip(),
            "has_thinking": has_thinking,
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取思考模式统计信息"""
        return self._stats.copy()

    def reset_stats(self):
        """重置统计信息"""
        self._stats = {
            "total_calls": 0,
            "thinking_enabled_calls": 0,
            "thinking_chars_collected": 0,
        }


async def stream_with_thinking_mode(
    client: AsyncOpenAI,
    model: str,
    messages: list,
    base_url: str,
    max_tokens: int = 150,
    temperature: float = 0.7,
    tools: Optional[list] = None,
    tool_choice: Any = None,
    handler: Optional[ThinkingModeHandler] = None,
    enable_thinking: Optional[bool] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    使用思考模式进行流式调用的便捷函数

    Args:
        client: AsyncOpenAI 客户端
        model: 模型名称
        messages: 消息列表
        base_url: API base_url
        max_tokens: 最大 token 数
        temperature: 温度参数
        tools: MCP 工具列表（可选）
        tool_choice: 工具选择策略（可选）
        handler: 思考模式处理器（可选，默认创建新实例）
        enable_thinking: 是否启用思考模式（None=不设置，False=禁用）
        **kwargs: 其他传递给 API 的参数

    Returns:
        包含 content、thinking、tool_calls 等的字典
    """
    if handler is None:
        handler = ThinkingModeHandler()

    stream_params = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
        **kwargs,
    }

    if tools:
        stream_params["tools"] = tools
        stream_params["tool_choice"] = tool_choice or "auto"

    # 如果 enable_thinking=False，添加到 extra_body
    if enable_thinking is False:
        if "extra_body" not in stream_params:
            stream_params["extra_body"] = {}
        stream_params["extra_body"]["enable_thinking"] = False

    stream = await client.chat.completions.create(**stream_params)

    result = await handler.process_streaming_response(
        stream=stream,
        model_name=model,
        collect_thinking=True,
    )

    return result


def create_thinking_mode_handler(enable_log: bool = True) -> ThinkingModeHandler:
    """
    创建思考模式处理器实例

    Args:
        enable_log: 是否启用思考日志

    Returns:
        ThinkingModeHandler 实例
    """
    return ThinkingModeHandler(enable_thinking_log=enable_log)


thinking_handler = ThinkingModeHandler()
