from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Optional
import asyncio


class TimedCache(OrderedDict):
    """带时间过期的缓存字典，自动清理过期条目"""

    def __init__(self, ttl_seconds: int = 3600, max_size: int = 1000):
        """
        初始化缓存

        Args:
            ttl_seconds: 条目存活时间（秒），默认 1 小时
            max_size: 最大缓存条目数，默认 1000
        """
        super().__init__()
        self.ttl = ttl_seconds
        self.max_size = max_size
        self._lock = asyncio.Lock()

    async def get(self, key: Any, default: Any = None) -> Any:
        """获取缓存值，如果过期则删除并返回默认值"""
        async with self._lock:
            if key not in self:
                return default

            value, timestamp = self[key]

            if datetime.now() - timestamp > timedelta(seconds=self.ttl):
                del self[key]
                return default

            return value

    async def set(self, key: Any, value: Any):
        """设置缓存值"""
        async with self._lock:
            self._cleanup()

            self[key] = (value, datetime.now())

            if len(self) > self.max_size:
                self.popitem(last=False)

    async def delete(self, key: Any):
        """删除指定键"""
        async with self._lock:
            if key in self:
                del self[key]

    async def clear(self):
        """清空所有缓存"""
        async with self._lock:
            super().clear()

    async def cleanup(self):
        """手动清理过期条目"""
        async with self._lock:
            self._cleanup()

    def _cleanup(self):
        """内部清理方法（不加锁）"""
        now = datetime.now()
        expired_keys = [k for k, (_, timestamp) in self.items() if now - timestamp > timedelta(seconds=self.ttl)]
        for k in expired_keys:
            del self[k]

    def __setitem__(self, key: Any, value: Any):
        """支持字典式赋值（直接设置）"""
        if isinstance(value, tuple) and len(value) == 2 and isinstance(value[1], datetime):
            super().__setitem__(key, value)
        else:
            super().__setitem__(key, (value, datetime.now()))
            self._cleanup()

            if len(self) > self.max_size:
                self.popitem(last=False)

    def __getitem__(self, key: Any) -> Any:
        """支持字典式获取（直接获取，不检查过期）"""
        value, timestamp = super().__getitem__(key)
        return value

    def __contains__(self, key: Any) -> bool:
        """支持 in 操作符"""
        if key in super():
            value, timestamp = super().__getitem__(key)
            if datetime.now() - timestamp <= timedelta(seconds=self.ttl):
                return True
            del self[key]
        return False


class GroupContextManager:
    """群组上下文管理器，专门用于管理群聊消息上下文"""

    def __init__(self, ttl_seconds: int = 300):
        """
        初始化群组上下文管理器

        Args:
            ttl_seconds: 上下文保留时间（秒），默认 5 分钟
        """
        self.contexts = TimedCache(ttl_seconds=ttl_seconds, max_size=100)

    async def set_context(self, group_id: int, context: dict):
        """设置群组上下文"""
        await self.contexts.set(group_id, context)

    async def get_context(self, group_id: int) -> Optional[dict]:
        """获取群组上下文"""
        return await self.contexts.get(group_id)

    async def clear_context(self, group_id: int):
        """清除群组上下文"""
        await self.contexts.delete(group_id)

    async def cleanup(self):
        """清理过期上下文"""
        await self.contexts.cleanup()

    def __len__(self):
        """返回当前缓存的上下文数量"""
        return len([k for k in self.contexts.keys()])


class DecisionStateTracker:
    """决策状态追踪器，用于管理决策冷却期"""

    def __init__(self):
        self.last_decision_times = TimedCache(ttl_seconds=86400, max_size=1000)
        self.pending_decisions = TimedCache(ttl_seconds=300, max_size=500)
        self.deciding_groups = set()
        self._lock = asyncio.Lock()

    async def get_last_decision_time(self, group_id: int) -> float:
        """获取最后决策时间"""
        result = await self.last_decision_times.get(group_id, 0)
        return result if isinstance(result, (int, float)) else 0

    async def set_last_decision_time(self, group_id: int, timestamp: float):
        """设置最后决策时间"""
        await self.last_decision_times.set(group_id, timestamp)

    async def is_pending(self, group_id: int) -> bool:
        """检查是否有待处理的决策"""
        result = await self.pending_decisions.get(group_id, False)
        return bool(result)

    async def set_pending(self, group_id: int, pending: bool):
        """设置待处理状态"""
        await self.pending_decisions.set(group_id, pending)

    async def start_decision(self, group_id: int) -> bool:
        """开始决策（返回是否成功）"""
        async with self._lock:
            if group_id in self.deciding_groups:
                return False
            self.deciding_groups.add(group_id)
            return True

    async def end_decision(self, group_id: int):
        """结束决策"""
        async with self._lock:
            self.deciding_groups.discard(group_id)

    async def cleanup(self):
        """清理过期状态"""
        await self.last_decision_times.cleanup()
        await self.pending_decisions.cleanup()
