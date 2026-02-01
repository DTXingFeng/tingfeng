from functools import wraps
from typing import Callable, Optional, Any
import asyncio
from .logger import get_logger

logger = get_logger(__name__)

class BotError(Exception):
    """机器人基础异常"""
    pass

class APIError(BotError):
    """API 调用异常"""
    def __init__(self, message: str, status_code: int = None, response: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response

class DatabaseError(BotError):
    """数据库操作异常"""
    pass

class ConfigError(BotError):
    """配置异常"""
    pass

class ValidationError(BotError):
    """数据验证异常"""
    pass

def handle_errors(
    default_return: Any = None,
    log_level: str = "ERROR",
    reraise: bool = False,
    error_types: tuple = (Exception,)
):
    """
    错误处理装饰器
    
    Args:
        default_return: 发生异常时的默认返回值
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        reraise: 是否重新抛出异常
        error_types: 要捕获的异常类型
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except error_types as e:
                log_func = getattr(logger, log_level.lower(), logger.error)
                log_func(f"Function '{func.__name__}' failed: {type(e).__name__}: {str(e)}")
                
                if reraise:
                    raise
                
                return default_return
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except error_types as e:
                log_func = getattr(logger, log_level.lower(), logger.error)
                log_func(f"Function '{func.__name__}' failed: {type(e).__name__}: {str(e)}")
                
                if reraise:
                    raise
                
                return default_return
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    重试装饰器
    
    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 退避系数
        exceptions: 需要重试的异常类型
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Function '{func.__name__}' attempt {attempt + 1}/{max_attempts} failed: {str(e)}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"Function '{func.__name__}' failed after {max_attempts} attempts")
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            import time
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Function '{func.__name__}' attempt {attempt + 1}/{max_attempts} failed: {str(e)}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"Function '{func.__name__}' failed after {max_attempts} attempts")
            
            raise last_exception
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator
