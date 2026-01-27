import sqlite3
import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict

class DBManager:
    def __init__(self, db_path: str = "data/bot_data.db"):
        self.db_path = Path(db_path)
        # 确保数据目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建用户ID映射表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_mapping (
                    group_id INTEGER,
                    user_name TEXT,
                    user_id INTEGER,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (group_id, user_name)
                )
            ''')
            
            # 创建聊天记录表
            # group_id: 群号
            # msg: 格式为 "名字:内容"
            # timestamp: 时间戳
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER,
                    msg TEXT,
                    is_processed INTEGER DEFAULT 0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # 创建用户印象表
            # group_id: 群号
            # user_name: 用户名
            # impression: 对该用户的印象/画像
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_profiles (
                    group_id INTEGER,
                    user_name TEXT,
                    impression TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (group_id, user_name)
                )
            ''')
            # 创建表情包缓存表
            # file_hash: 图片内容哈希，唯一标识
            # description: AI 识别出的语义描述
            # tag: 表情分类标签（如：开心、大哭、暴躁）
            # file_id: OneBot 平台的 file_id 或 URL (可选)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stickers (
                    file_hash TEXT PRIMARY KEY,
                    description TEXT,
                    tag TEXT,
                    file_id TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # 创建用户细节记忆表 (支持一个人有多个记忆点)
            # group_id: 群号
            # user_name: 用户名
            # content: 具体的记忆内容
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER,
                    user_name TEXT,
                    content TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # 创建心情表
            # group_id: 群号 (心情按群独立)
            # mood_value: 心情值，0-100 (0: 极差, 50: 平静, 100: 极好)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_moods (
                    group_id INTEGER PRIMARY KEY,
                    mood_value INTEGER DEFAULT 50,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def add_chat_log(self, group_id: int, msg: str):
        """添加一条聊天记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_history (group_id, msg) VALUES (?, ?)",
                (group_id, msg)
            )
            conn.commit()

    def get_chat_log(self, group_id: int, limit: int = 10) -> List[str]:
        """获取指定群组最近的聊天记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT msg FROM chat_history WHERE group_id = ? ORDER BY timestamp DESC LIMIT ?",
                (group_id, limit)
            )
            rows = cursor.fetchall()
            # 结果是倒序的，需要反转回正序
            messages = [row[0] for row in rows]
            messages.reverse()
            return messages

    def get_unprocessed_logs(self, group_id: int, limit: int = 50) -> List[Tuple[int, str]]:
        """获取未处理过的原始记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, msg FROM chat_history WHERE group_id = ? AND is_processed = 0 ORDER BY timestamp ASC LIMIT ?",
                (group_id, limit)
            )
            return cursor.fetchall()

    def mark_as_processed(self, msg_ids: List[int]):
        """标记消息为已处理"""
        if not msg_ids:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "UPDATE chat_history SET is_processed = 1 WHERE id = ?",
                [(mid,) for mid in msg_ids]
            )
            conn.commit()

    def update_user_impression(self, group_id: int, user_name: str, impression: str):
        """更新对某个用户的印象"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_profiles (group_id, user_name, impression, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(group_id, user_name) DO UPDATE SET
                impression = excluded.impression,
                updated_at = CURRENT_TIMESTAMP
            ''', (group_id, user_name, impression))
            conn.commit()

    def get_user_impression(self, group_id: int, user_name: str) -> Optional[str]:
        """获取对某个用户的整体印象"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT impression FROM user_profiles WHERE group_id = ? AND user_name = ?",
                (group_id, user_name)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def add_user_specific_memory(self, group_id: int, user_name: str, content: str):
        """为特定用户增加一条具体记忆点"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 简单去重：如果该用户已经有完全一样的记忆内容，就不重复添加
            cursor.execute(
                "SELECT id FROM user_memories WHERE group_id = ? AND user_name = ? AND content = ?",
                (group_id, user_name, content)
            )
            if cursor.fetchone():
                return
                
            cursor.execute(
                "INSERT INTO user_memories (group_id, user_name, content) VALUES (?, ?, ?)",
                (group_id, user_name, content)
            )
            conn.commit()

    def get_user_specific_memories(self, group_id: int, user_name: str, limit: int = 5) -> List[str]:
        """获取特定用户的多个记忆点"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content FROM user_memories WHERE group_id = ? AND user_name = ? ORDER BY created_at DESC LIMIT ?",
                (group_id, user_name, limit)
            )
            return [row[0] for row in cursor.fetchall()]

    def get_sticker_cache(self, file_hash: str) -> Optional[Dict[str, str]]:
        """根据哈希获取表情包缓存"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT description, tag, file_id FROM stickers WHERE file_hash = ?",
                (file_hash,)
            )
            row = cursor.fetchone()
            if row:
                return {"description": row[0], "tag": row[1], "file_id": row[2]}
            return None

    def update_user_id_map(self, group_id: int, user_name: str, user_id: int):
        """更新用户名到 ID 的映射"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_mapping (group_id, user_name, user_id, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(group_id, user_name) DO UPDATE SET
                user_id = excluded.user_id,
                updated_at = CURRENT_TIMESTAMP
            ''', (group_id, user_name, user_id))
            conn.commit()

    def get_user_id_by_name(self, group_id: int, user_name: str) -> Optional[int]:
        """根据用户名查找 ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id FROM user_mapping WHERE group_id = ? AND user_name = ?",
                (group_id, user_name)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def save_sticker_cache(self, file_hash: str, description: str, tag: str, file_id: str = None):
        """保存表情包缓存"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO stickers (file_hash, description, tag, file_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(file_hash) DO UPDATE SET
                description = excluded.description,
                tag = excluded.tag,
                file_id = COALESCE(excluded.file_id, stickers.file_id)
            ''', (file_hash, description, tag, file_id))
            conn.commit()

    def get_stickers_by_tag(self, tag: str) -> List[Dict[str, str]]:
        """根据标签获取所有表情包"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT file_id, description FROM stickers WHERE tag = ?",
                (tag,)
            )
            rows = cursor.fetchall()
            return [{"file_id": row[0], "description": row[1]} for row in rows]

    def get_mood(self, group_id: int) -> int:
        """获取群聊对应的心情值"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT mood_value FROM bot_moods WHERE group_id = ?", (group_id,))
            row = cursor.fetchone()
            if row:
                return row[0]
            # 如果不存在，初始化为 50
            cursor.execute("INSERT INTO bot_moods (group_id, mood_value) VALUES (?, 50)", (group_id,))
            conn.commit()
            return 50

    def get_all_group_moods(self) -> List[Tuple[int, int]]:
        """获取所有记录了心情值的群组"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT group_id, mood_value FROM bot_moods")
            return cursor.fetchall()

    def update_mood(self, group_id: int, delta: int):
        """更新心情值 (增加或减少)"""
        current_mood = self.get_mood(group_id)
        new_mood = max(0, min(100, current_mood + delta))
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE bot_moods SET mood_value = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE group_id = ?
            ''', (new_mood, group_id))
            conn.commit()
        return new_mood

# 全局单例
db_manager = DBManager()
