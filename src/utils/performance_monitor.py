import time
import asyncio
from typing import Dict, Optional, Callable
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta
from .logger import get_logger

logger = get_logger(__name__)

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics: Dict[str, Dict] = defaultdict(lambda: {
            "count": 0,
            "total_time": 0.0,
            "min_time": float('inf'),
            "max_time": 0.0,
            "errors": 0,
            "last_error_time": None
        })
        self.start_time = time.time()
    
    def record(self, name: str, duration: float, success: bool = True):
        """
        记录性能指标
        
        Args:
            name: 操作名称
            duration: 执行时间（秒）
            success: 是否成功
        """
        metrics = self.metrics[name]
        metrics["count"] += 1
        metrics["total_time"] += duration
        metrics["min_time"] = min(metrics["min_time"], duration)
        metrics["max_time"] = max(metrics["max_time"], duration)
        
        if not success:
            metrics["errors"] += 1
            metrics["last_error_time"] = datetime.now()
    
    def get_stats(self, name: str) -> Optional[Dict]:
        """获取指定操作的统计信息"""
        if name not in self.metrics:
            return None
        
        metrics = self.metrics[name]
        count = metrics["count"]
        if count == 0:
            return None
        
        return {
            "name": name,
            "count": count,
            "avg_time": metrics["total_time"] / count,
            "min_time": metrics["min_time"],
            "max_time": metrics["max_time"],
            "total_time": metrics["total_time"],
            "errors": metrics["errors"],
            "error_rate": metrics["errors"] / count if count > 0 else 0,
            "last_error_time": metrics["last_error_time"]
        }
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """获取所有统计信息"""
        return {name: self.get_stats(name) for name in self.metrics.keys()}
    
    def get_summary(self) -> Dict:
        """获取性能摘要"""
        uptime = time.time() - self.start_time
        total_calls = sum(m["count"] for m in self.metrics.values())
        total_errors = sum(m["errors"] for m in self.metrics.values())
        
        return {
            "uptime_seconds": uptime,
            "uptime_formatted": str(timedelta(seconds=int(uptime))),
            "total_operations": total_calls,
            "total_errors": total_errors,
            "overall_error_rate": total_errors / total_calls if total_calls > 0 else 0,
            "operations_per_second": total_calls / uptime if uptime > 0 else 0
        }
    
    def reset(self, name: Optional[str] = None):
        """
        重置指标
        
        Args:
            name: 要重置的操作名称，如果为 None 则重置所有
        """
        if name:
            if name in self.metrics:
                del self.metrics[name]
        else:
            self.metrics.clear()
            self.start_time = time.time()
    
    def log_summary(self):
        """打印性能摘要到日志"""
        summary = self.get_summary()
        logger.info("=" * 60)
        logger.info("性能监控摘要")
        logger.info(f"运行时间: {summary['uptime_formatted']}")
        logger.info(f"总操作数: {summary['total_operations']}")
        logger.info(f"总错误数: {summary['total_errors']}")
        logger.info(f"错误率: {summary['overall_error_rate']:.2%}")
        logger.info(f"操作/秒: {summary['operations_per_second']:.2f}")
        logger.info("=" * 60)
        
        for name, stats in self.get_all_stats().items():
            if stats:
                logger.info(
                    f"{name}: 调用={stats['count']} "
                    f"平均={stats['avg_time']:.3f}s "
                    f"最小={stats['min_time']:.3f}s "
                    f"最大={stats['max_time']:.3f}s "
                    f"错误率={stats['error_rate']:.2%}"
                )

# 全局单例
performance_monitor = PerformanceMonitor()

def monitor_performance(name: Optional[str] = None):
    """
    性能监控装饰器
    
    Args:
        name: 操作名称，默认使用函数名
    """
    def decorator(func: Callable):
        op_name = name or func.__name__
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            success = True
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start
                performance_monitor.record(op_name, duration, success)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            success = True
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start
                performance_monitor.record(op_name, duration, success)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

class RateLimiter:
    """速率限制器"""
    
    def __init__(self, max_calls: int, time_window: float):
        """
        初始化速率限制器
        
        Args:
            max_calls: 时间窗口内的最大调用次数
            time_window: 时间窗口（秒）
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls: list = []
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """
        尝试获取调用许可
        
        Returns:
            是否成功获取许可
        """
        async with self._lock:
            now = time.time()
            # 移除超出时间窗口的调用记录
            self.calls = [t for t in self.calls if now - t < self.time_window]
            
            if len(self.calls) < self.max_calls:
                self.calls.append(now)
                return True
            return False
    
    async def wait_for_slot(self):
        """等待获取调用许可"""
        while not await self.acquire():
            wait_time = self.time_window / self.max_calls
            await asyncio.sleep(wait_time)
    
    def get_remaining_calls(self) -> int:
        """获取剩余调用次数"""
        now = time.time()
        self.calls = [t for t in self.calls if now - t < self.time_window]
        return max(0, self.max_calls - len(self.calls))

class ConcurrencyLimiter:
    """并发限制器"""
    
    def __init__(self, max_concurrent: int):
        """
        初始化并发限制器
        
        Args:
            max_concurrent: 最大并发数
        """
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
        self.current_concurrent = 0
        self._lock = asyncio.Lock()
    
    async def __aenter__(self):
        await self.semaphore.acquire()
        async with self._lock:
            self.current_concurrent += 1
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with self._lock:
            self.current_concurrent -= 1
        self.semaphore.release()
    
    def get_current_usage(self) -> int:
        """获取当前并发数"""
        return self.current_concurrent
    
    def get_available_slots(self) -> int:
        """获取可用槽位"""
        return self.max_concurrent - self.current_concurrent

def limit_concurrency(max_concurrent: int):
    """
    并发限制装饰器
    
    Args:
        max_concurrent: 最大并发数
    """
    limiter = ConcurrencyLimiter(max_concurrent)
    
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            async with limiter:
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 同步函数无法使用 asyncio.Semaphore，直接执行
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator
