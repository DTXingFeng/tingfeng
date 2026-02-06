import asyncio
from typing import List, Dict, Any, Callable, Optional
from collections import deque
from nonebot import logger


class AsyncVectorQueue:
    def __init__(self, max_workers: int = 2):
        self._queue = deque()
        self._max_workers = max_workers
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition()

    async def _worker(self, worker_id: int):
        while True:
            async with self._condition:
                await self._condition.wait_for(lambda: len(self._queue) > 0 or not self._running)

                if not self._running and len(self._queue) == 0:
                    break

                if len(self._queue) == 0:
                    continue

                task_data = self._queue.popleft()

            try:
                func, args, kwargs = task_data
                await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"向量队列任务执行失败 (worker {worker_id}): {e}", exc_info=True)

    async def start(self):
        async with self._lock:
            if self._running:
                return

            self._running = True
            self._workers = [asyncio.create_task(self._worker(i)) for i in range(self._max_workers)]
            logger.info(f"向量队列已启动，worker 数量: {self._max_workers}")

    async def stop(self):
        async with self._lock:
            if not self._running:
                return

            self._running = False

        async with self._condition:
            self._condition.notify_all()

        await asyncio.gather(*self._workers, return_exceptions=True)
        logger.info("向量队列已停止")

    async def submit(self, func: Callable, *args, **kwargs):
        async with self._condition:
            self._queue.append((func, args, kwargs))
            self._condition.notify()


_global_queue: Optional[AsyncVectorQueue] = None


def get_vector_queue() -> AsyncVectorQueue:
    global _global_queue
    if _global_queue is None:
        _global_queue = AsyncVectorQueue(max_workers=2)
    return _global_queue
