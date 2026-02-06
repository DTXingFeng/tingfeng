import chromadb
from chromadb.config import Settings
from pathlib import Path
from typing import List, Dict, Any, Optional
import time
import asyncio
import threading
import shutil
from concurrent.futures import ThreadPoolExecutor


class VectorDB:
    def __init__(self, db_path: str = "data/vector_db"):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        self.collection_prefix = "group_memory_"
        self._collection_cache = {}
        self._client = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vector_db")
        
        self._init_client()

    def _init_client(self):
        from nonebot import logger
        
        max_retries = 2
        for attempt in range(max_retries):
            try:
                self._client = chromadb.PersistentClient(
                    path=str(self.db_path),
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
                logger.info(f"向量数据库初始化成功 (路径: {self.db_path})")
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"向量数据库初始化失败，尝试修复... (尝试 {attempt + 1}/{max_retries})")
                    self._repair_database()
                else:
                    logger.error(f"向量数据库初始化失败，已重试 {max_retries} 次: {e}")
                    self._client = None

    def _repair_database(self):
        from nonebot import logger
        try:
            backup_path = self.db_path.parent / f"vector_db_backup_{int(time.time())}"
            logger.warning(f"正在备份现有向量数据库到: {backup_path}")
            
            if self.db_path.exists():
                shutil.move(str(self.db_path), str(backup_path))
            
            self.db_path.mkdir(parents=True, exist_ok=True)
            logger.info("向量数据库已重置，将创建新的数据库文件")
        except Exception as e:
            logger.error(f"修复向量数据库失败: {e}")

    def _get_collection(self, group_id: int):
        if not self._client:
            return None
            
        if group_id not in self._collection_cache:
            collection_name = f"{self.collection_prefix}{group_id}"
            try:
                self._collection_cache[group_id] = self._client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                from nonebot import logger
                logger.error(f"获取向量集合失败: {e}")
                return None
        return self._collection_cache[group_id]

    def _sync_add_memory(self, group_id: int, text: str, vector: List[float], metadata: Dict[str, Any] = None):
        if not self._client:
            return
            
        try:
            collection = self._get_collection(group_id)
            if not collection:
                return
                
            doc_id = str(int(time.time() * 1000000))
            
            final_metadata = metadata or {}
            if "timestamp" not in final_metadata:
                final_metadata["timestamp"] = int(time.time())

            collection.add(
                ids=[doc_id],
                embeddings=[vector],
                documents=[text],
                metadatas=[final_metadata]
            )
        except Exception as e:
            from nonebot import logger
            logger.debug(f"向量数据库添加失败 (非致命): {e}")

    def _sync_query_memory(self, group_id: int, vector: List[float], n_results: int = 3) -> List[str]:
        if not self._client:
            return []
            
        try:
            collection = self._get_collection(group_id)
            if not collection:
                return []
            
            count = collection.count()
            if count == 0:
                return []

            results = collection.query(
                query_embeddings=[vector],
                n_results=min(n_results, count)
            )

            return results["documents"][0] if results["documents"] else []
        except Exception as e:
            from nonebot import logger
            logger.debug(f"向量数据库查询失败 (非致命): {e}")
            return []

    def _sync_clear_collection(self, group_id: int):
        if not self._client:
            return
            
        try:
            collection = self._get_collection(group_id)
            if not collection:
                return
                
            count = collection.count()
            if count > 0:
                collection.delete(where={})
                from nonebot import logger
                logger.info(f"已清空群 {group_id} 的向量集合")
        except Exception as e:
            from nonebot import logger
            logger.error(f"清空向量集合失败: {e}")

    def _sync_get_count(self, group_id: int) -> int:
        if not self._client:
            return 0
            
        try:
            collection = self._get_collection(group_id)
            if not collection:
                return 0
            return collection.count()
        except Exception:
            return 0

    async def add_memory(self, group_id: int, text: str, vector: List[float], metadata: Dict[str, Any] = None):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, self._sync_add_memory, group_id, text, vector, metadata)

    async def query_memory(self, group_id: int, vector: List[float], n_results: int = 3) -> List[str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self._sync_query_memory, group_id, vector, n_results)

    async def clear_collection(self, group_id: int):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, self._sync_clear_collection, group_id)

    async def get_collection_count(self, group_id: int) -> int:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self._sync_get_count, group_id)


vector_db = VectorDB()
