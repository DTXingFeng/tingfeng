import chromadb
from chromadb.config import Settings
from pathlib import Path
from typing import List, Dict, Any, Optional
import time

class VectorDB:
    def __init__(self, db_path: str = "data/vector_db"):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        # 初始化 ChromaDB 客户端
        self.client = chromadb.PersistentClient(path=str(self.db_path))
        
        # 获取或创建集合 (按群号隔离)
        # 注意：Chroma 集合名必须是 3-63 个字符，且符合特定正则
        self.collection_prefix = "group_memory_"

    def _get_collection(self, group_id: int):
        collection_name = f"{self.collection_prefix}{group_id}"
        return self.client.get_or_create_collection(name=collection_name)

    def add_memory(self, group_id: int, text: str, vector: List[float], metadata: Dict[str, Any] = None):
        """
        向向量库添加一条记忆
        """
        collection = self._get_collection(group_id)
        
        # 使用时间戳作为 ID
        doc_id = str(int(time.time() * 1000))
        
        # 准备元数据，确保不为空（ChromaDB 要求元数据字典不能为空）
        final_metadata = metadata or {}
        if "timestamp" not in final_metadata:
            final_metadata["timestamp"] = int(time.time())
        
        collection.add(
            ids=[doc_id],
            embeddings=[vector],
            documents=[text],
            metadatas=[final_metadata]
        )

    def query_memory(self, group_id: int, vector: List[float], n_results: int = 3) -> List[str]:
        """
        根据向量查询最相关的记忆
        """
        collection = self._get_collection(group_id)
        
        # 如果集合为空，直接返回
        if collection.count() == 0:
            return []
            
        results = collection.query(
            query_embeddings=[vector],
            n_results=min(n_results, collection.count())
        )
        
        # 返回匹配到的文本列表
        return results['documents'][0] if results['documents'] else []

# 全局单例
vector_db = VectorDB()
