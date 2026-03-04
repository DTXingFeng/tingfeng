"""
重试装饰器：用于处理不稳定的网络和 API 调用
"""

import asyncio
import functools
from typing import Callable, TypeVar, Any, Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def retry_on_timeout(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    backoff_factor: float = 2.0,
    timeout_errors: tuple = (TimeoutError, asyncio.TimeoutError),
) -> Callable:
    """
    重试装饰器，专门处理超时错误

    Args:
        max_retries: 最大重试次数（默认3次）
        base_delay: 基础延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        backoff_factor: 退避因子，每次重试延迟时间乘以此因子
        timeout_errors: 视为超时错误的异常类型

    Returns:
        装饰后的函数
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            delay = base_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except timeout_errors as e:
                    last_exception = e

                    if attempt < max_retries:
                        logger.warning(
                            f"{func.__name__} 超时 (尝试 {attempt + 1}/{max_retries + 1})，" f"{delay:.1f}秒后重试..."
                        )
                        await asyncio.sleep(min(delay, max_delay))
                        delay *= backoff_factor
                    else:
                        logger.error(f"{func.__name__} 达到最大重试次数 ({max_retries})，仍然失败")

            raise last_exception

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            delay = base_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except timeout_errors as e:
                    last_exception = e

                    if attempt < max_retries:
                        logger.warning(
                            f"{func.__name__} 超时 (尝试 {attempt + 1}/{max_retries + 1})，" f"{delay:.1f}秒后重试..."
                        )
                        time.sleep(min(delay, max_delay))
                        delay *= backoff_factor
                    else:
                        logger.error(f"{func.__name__} 达到最大重试次数 ({max_retries})，仍然失败")

            raise last_exception

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def retry_on_api_error(
    max_retries: int = 2,
    ignored_errors: Optional[tuple] = None,
) -> Callable:
    """
    重试装饰器，处理 API 错误

    Args:
        max_retries: 最大重试次数（默认2次）
        ignored_errors: 忽略的错误类型，这些错误不会重试

    Returns:
        装饰后的函数
    """
    if ignored_errors is None:
        ignored_errors = ()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if isinstance(e, ignored_errors):
                        logger.error(f"{func.__name__} 遇到忽略的错误: {e}")
                        raise

                    if attempt < max_retries:
                        logger.warning(
                            f"{func.__name__} 出错 (尝试 {attempt + 1}/{max_retries + 1}): {e}，" f"重试中..."
                        )
                        await asyncio.sleep(1)
                    else:
                        logger.error(f"{func.__name__} 达到最大重试次数 ({max_retries})，仍然失败: {e}")

            raise last_exception

        return wrapper

    return decorator
