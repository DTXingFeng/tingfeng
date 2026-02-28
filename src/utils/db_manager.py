import aiosqlite
import datetime
import json
import re
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any


class DBManager:
    def __init__(self, db_path: str = "data/bot_data.db"):
        self.db_path = Path(db_path)
        self._init_done = False

    @staticmethod
    def _merge_impressions(old_impression: str, new_impression: str) -> str:
        """
        智能合并印象

        支持的操作标记：
        - "+新内容" - 添加新特征
        - "-要删除的内容" - 删除不再适用的特征
        - "~旧内容|新内容" - 更新现有特征
        - 无标记 - 智能合并（去重、相似内容合并）

        Args:
            old_impression: 旧的印象
            new_impression: 新的印象

        Returns:
            合并后的印象
        """
        if not old_impression:
            return new_impression
        if not new_impression:
            return old_impression

        # 解析旧印象为特征列表
        old_features = [f.strip() for f in old_impression.split("，") if f.strip()]
        new_features = [f.strip() for f in new_impression.split("，") if f.strip()]

        # 处理新印象中的操作标记
        features_to_add = []
        features_to_remove = set()
        features_to_update = {}
        features_to_merge = []

        for feature in new_features:
            if feature.startswith("+"):
                # 添加操作
                add_content = feature[1:].strip()
                if add_content:
                    features_to_add.append(add_content)
            elif feature.startswith("-"):
                # 删除操作
                remove_content = feature[1:].strip()
                if remove_content:
                    features_to_remove.add(remove_content)
            elif feature.startswith("~"):
                # 更新操作
                update_content = feature[1:].strip()
                if "|" in update_content:
                    old, new = update_content.split("|", 1)
                    features_to_update[old.strip()] = new.strip()
            else:
                # 普通内容，需要智能合并
                features_to_merge.append(feature)

        # 构建最终特征列表
        final_features = []

        # 添加未被删除的旧特征
        for old_feature in old_features:
            # 检查是否需要删除（完全匹配或包含）
            should_remove = False
            for remove_pattern in features_to_remove:
                if remove_pattern in old_feature or old_feature == remove_pattern:
                    should_remove = True
                    break

            if not should_remove:
                # 检查是否需要更新
                updated = False
                for old_pattern, new_value in features_to_update.items():
                    if old_pattern in old_feature:
                        final_features.append(new_value)
                        updated = True
                        break

                if not updated:
                    final_features.append(old_feature)

        # 处理需要智能合并的新特征
        for merge_feature in features_to_merge:
            # 检查是否与现有特征重复或相似
            is_duplicate = False
            for existing in final_features:
                # 完全相同
                if merge_feature == existing:
                    is_duplicate = True
                    break
                # 包含关系（短字符串包含在长字符串中）
                if len(merge_feature) > 2 and len(existing) > 2:
                    if merge_feature in existing or existing in merge_feature:
                        is_duplicate = True
                        break

            if not is_duplicate:
                final_features.append(merge_feature)

        # 添加明确要添加的特征
        for add_feature in features_to_add:
            if add_feature not in final_features:
                final_features.append(add_feature)

        # 去重并合并
        seen = set()
        unique_features = []
        for f in final_features:
            if f not in seen:
                seen.add(f)
                unique_features.append(f)

        return "，".join(unique_features) if unique_features else old_impression

    async def _ensure_init(self):
        """确保数据库已初始化（懒加载）"""
        if not self._init_done:
            await self._init_db()
            self._init_done = True

    async def _get_connection(self):
        """获取数据库连接"""
        await self._ensure_init()
        return aiosqlite.connect(self.db_path)

    async def _init_db(self):
        """初始化数据库表结构"""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_mapping (
                        group_id INTEGER,
                        user_name TEXT,
                        user_id INTEGER,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (group_id, user_name)
                    )
                """
                )

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chat_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id INTEGER,
                        msg TEXT,
                        message_id INTEGER,
                        is_processed INTEGER DEFAULT 0,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # 为已存在的表添加 message_id 字段（如果不存在）
                try:
                    await cursor.execute("ALTER TABLE chat_history ADD COLUMN message_id INTEGER")
                except aiosqlite.OperationalError:
                    pass

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        group_id INTEGER,
                        user_id INTEGER,
                        user_name TEXT,
                        impression TEXT,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (group_id, user_id)
                    )
                """
                )

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_impression_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id INTEGER,
                        user_id INTEGER,
                        user_name TEXT,
                        impression TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS stickers (
                        file_hash TEXT PRIMARY KEY,
                        description TEXT,
                        tag TEXT,
                        file_id TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id INTEGER,
                        user_id INTEGER,
                        user_name TEXT,
                        content TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bot_moods (
                        group_id INTEGER PRIMARY KEY,
                        mood_value INTEGER DEFAULT 50,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS mood_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id INTEGER,
                        mood_delta INTEGER,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bot_personality (
                        group_id INTEGER PRIMARY KEY,
                        traits TEXT,
                        recent_thoughts TEXT,
                        style_vibe TEXT,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        last_vibe_update DATETIME
                    )
                """
                )

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_relationships (
                        group_id INTEGER,
                        user_id INTEGER,
                        user_name TEXT,
                        favorability INTEGER DEFAULT 50,
                        status TEXT DEFAULT '陌生人',
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (group_id, user_id)
                    )
                """
                )

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bot_schedules (
                        group_id INTEGER,
                        date TEXT,
                        schedule_json TEXT,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (group_id, date)
                    )
                """
                )

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS style_patterns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id INTEGER,
                        context TEXT,
                        style_desc TEXT,
                        weight INTEGER DEFAULT 1,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(group_id, context, style_desc)
                    )
                """
                )

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS slang_candidates (
                        group_id INTEGER,
                        phrase TEXT,
                        frequency INTEGER DEFAULT 1,
                        stage INTEGER DEFAULT 1,
                        definition TEXT,
                        context_samples TEXT,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (group_id, phrase)
                    )
                """
                )

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS knowledge_triplets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id INTEGER,
                        subject TEXT,
                        predicate TEXT,
                        object TEXT,
                        confidence REAL DEFAULT 1.0,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(group_id, subject, predicate, object)
                    )
                """
                )

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bot_reply_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id INTEGER,
                        triggered_by_user TEXT,
                        is_at_bot INTEGER DEFAULT 0,
                        interest_score REAL DEFAULT 0,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS mute_reflections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id INTEGER,
                        ban_reason TEXT,
                        trigger_context TEXT,
                        reflection_thought TEXT,
                        lesson_learned TEXT,
                        operator_id INTEGER,
                        duration_seconds INTEGER,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                await cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_chat_history_group_time ON chat_history(group_id, timestamp)"
                )
                await cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_chat_history_group_processed ON chat_history(group_id, is_processed, timestamp)"
                )
                await cursor.execute("CREATE INDEX IF NOT EXISTS idx_stickers_tag ON stickers(tag)")
                await cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_user_memories_group_user_time ON user_memories(group_id, user_name, created_at)"
                )
                await cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_user_relationships_favorability ON user_relationships(favorability)"
                )
                await cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_style_patterns_weight ON style_patterns(weight DESC)"
                )
                await cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_slang_candidates_query ON slang_candidates(group_id, stage, frequency)"
                )
                await cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_knowledge_triplets_confidence ON knowledge_triplets(confidence DESC)"
                )
                await cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_knowledge_triplets_subject ON knowledge_triplets(subject)"
                )
                await cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_bot_reply_history_group_time ON bot_reply_history(group_id, timestamp DESC)"
                )
                await cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_bot_reply_history_active ON bot_reply_history(group_id, is_at_bot, timestamp DESC)"
                )
                await cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mute_reflections_group_time ON mute_reflections(group_id, timestamp DESC)"
                )
                await cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mood_history_group_time ON mood_history(group_id, timestamp DESC)"
                )
                await cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_user_impression_history_user_time ON user_impression_history(user_id, created_at DESC)"
                )

                await conn.commit()
        except Exception as e:
            print(f"数据库初始化失败: {e}")
            raise

    async def add_chat_log(self, group_id: int, msg: str, message_id: Optional[int] = None):
        """添加一条聊天记录
        
        Args:
            group_id: 群组ID
            msg: 消息内容
            message_id: QQ消息ID（用于引用回复）
        """
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            if message_id is not None:
                await cursor.execute(
                    "INSERT INTO chat_history (group_id, msg, message_id) VALUES (?, ?, ?)",
                    (group_id, msg, message_id)
                )
            else:
                await cursor.execute("INSERT INTO chat_history (group_id, msg) VALUES (?, ?)", (group_id, msg))
            await conn.commit()

    async def get_chat_log(self, group_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """获取指定群组最近的聊天记录
        
        Returns:
            包含 message, message_id 的字典列表
        """
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                "SELECT msg, message_id FROM chat_history WHERE group_id = ? ORDER BY timestamp DESC LIMIT ?",
                (group_id, limit)
            )
            rows = await cursor.fetchall()
            messages = [
                {"message": row[0], "message_id": row[1]}
                for row in rows
            ]
            messages.reverse()
            return messages

    async def get_chat_log_before(
        self, group_id: int, limit: int = 10, before_timestamp: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取指定群组在指定时间之前的聊天记录（用于并发安全的回复生成）
        
        Returns:
            包含 message, message_id 的字典列表
        """
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            if before_timestamp:
                await cursor.execute(
                    "SELECT msg, message_id FROM chat_history WHERE group_id = ? AND timestamp < ? ORDER BY timestamp DESC LIMIT ?",
                    (group_id, before_timestamp, limit),
                )
            else:
                await cursor.execute(
                    "SELECT msg, message_id FROM chat_history WHERE group_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (group_id, limit)
                )
            rows = await cursor.fetchall()
            messages = [
                {"message": row[0], "message_id": row[1]}
                for row in rows
            ]
            messages.reverse()
            return messages

    async def get_new_message_count_since(self, group_id: int, since_timestamp: str) -> int:
        """获取自指定时间以来的新消息数量"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                "SELECT COUNT(*) FROM chat_history WHERE group_id = ? AND timestamp > ?",
                (group_id, since_timestamp),
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_last_vibe_update_time(self, group_id: int) -> Optional[str]:
        """获取上次群氛围更新时间"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute("SELECT last_vibe_update FROM bot_personality WHERE group_id = ?", (group_id,))
            row = await cursor.fetchone()
            return row[0] if row else None

    async def should_update_vibe(self, group_id: int, min_messages: int = 100) -> tuple[bool, int, Optional[str]]:
        """
        判断是否应该更新群氛围

        Returns:
            (should_update, message_count, last_update_time)
            - should_update: 是否应该更新
            - message_count: 自上次更新以来的消息数量
            - last_update_time: 上次更新时间
        """
        last_update_time = await self.get_last_vibe_update_time(group_id)

        if not last_update_time:
            # 从未更新过，应该更新
            return True, 0, None

        # 计算自上次更新以来的新消息数量
        new_msg_count = await self.get_new_message_count_since(group_id, last_update_time)

        should_update = new_msg_count >= min_messages
        return should_update, new_msg_count, last_update_time

    async def get_unprocessed_logs(self, group_id: int, limit: int = 50) -> List[Tuple[int, str]]:
        """获取未处理过的原始记录"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                "SELECT id, msg FROM chat_history WHERE group_id = ? AND is_processed = 0 ORDER BY timestamp ASC LIMIT ?",
                (group_id, limit),
            )
            rows = await cursor.fetchall()
            return [(row[0], row[1]) for row in rows]

    async def mark_as_processed(self, msg_ids: List[int]):
        """标记消息为已处理"""
        if not msg_ids:
            return
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.executemany(
                "UPDATE chat_history SET is_processed = 1 WHERE id = ?", [(mid,) for mid in msg_ids]
            )
            await conn.commit()

    async def update_user_impression(self, group_id: int, user_id: int, user_name: str, impression: str):
        """更新对某个用户的印象（智能合并 + 保留历史记录）"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()

            # 先查询是否已有旧印象
            await cursor.execute(
                "SELECT impression FROM user_profiles WHERE group_id = ? AND user_id = ?", (group_id, user_id)
            )
            row = await cursor.fetchone()

            # 智能合并新印象与旧印象
            if row and row[0]:
                old_impression = row[0]
                merged_impression = self._merge_impressions(old_impression, impression)

                # 只有当合并后的印象确实发生变化时才保存历史
                if merged_impression != old_impression:
                    await cursor.execute(
                        """
                        INSERT INTO user_impression_history (group_id, user_id, user_name, impression, created_at)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (group_id, user_id, user_name, old_impression),
                    )

                final_impression = merged_impression
            else:
                # 没有旧印象，直接使用新印象
                final_impression = impression

            # 更新当前印象
            await cursor.execute(
                """
                INSERT INTO user_profiles (group_id, user_id, user_name, impression, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(group_id, user_id) DO UPDATE SET
                user_name = excluded.user_name,
                impression = excluded.impression,
                updated_at = CURRENT_TIMESTAMP
            """,
                (group_id, user_id, user_name, final_impression),
            )
            await conn.commit()

    async def replace_user_impression(self, group_id: int, user_id: int, user_name: str, impression: str):
        """
        强制替换用户印象（不进行智能合并）
        仅在需要完全重置印象时使用
        """
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()

            # 查询旧印象
            await cursor.execute(
                "SELECT impression FROM user_profiles WHERE group_id = ? AND user_id = ?", (group_id, user_id)
            )
            row = await cursor.fetchone()

            # 如果存在旧印象且与新印象不同，保存到历史
            if row and row[0] and row[0] != impression:
                await cursor.execute(
                    """
                    INSERT INTO user_impression_history (group_id, user_id, user_name, impression, created_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (group_id, user_id, user_name, row[0]),
                )

            # 直接替换印象
            await cursor.execute(
                """
                INSERT INTO user_profiles (group_id, user_id, user_name, impression, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(group_id, user_id) DO UPDATE SET
                user_name = excluded.user_name,
                impression = excluded.impression,
                updated_at = CURRENT_TIMESTAMP
            """,
                (group_id, user_id, user_name, impression),
            )
            await conn.commit()

    async def get_user_impression(self, group_id: int, user_id: int) -> Optional[str]:
        """获取对某个用户的整体印象"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                "SELECT impression FROM user_profiles WHERE group_id = ? AND user_id = ?", (group_id, user_id)
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def get_user_impression_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """获取某个用户的印象历史记录（跨群查询）"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                """
                SELECT group_id, user_name, impression, created_at 
                FROM user_impression_history 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
                """,
                (user_id, limit),
            )
            rows = await cursor.fetchall()
            return [
                {"group_id": row[0], "user_name": row[1], "impression": row[2], "created_at": row[3]} for row in rows
            ]

    async def list_impression_history(
        self,
        group_id: Optional[int] = None,
        user_id: Optional[int] = None,
        keyword: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """获取印象历史列表（支持分页、关键词搜索）"""
        query = "SELECT id, group_id, user_id, user_name, impression, created_at FROM user_impression_history WHERE 1=1"
        params: List[Any] = []

        if group_id is not None:
            query += " AND group_id = ?"
            params.append(group_id)
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)
        if keyword:
            query += " AND (impression LIKE ? OR user_name LIKE ?)"
            like_keyword = f"%{keyword}%"
            params.extend([like_keyword, like_keyword])

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(query, tuple(params))
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "group_id": row[1],
                    "user_id": row[2],
                    "user_name": row[3],
                    "impression": row[4],
                    "created_at": row[5],
                }
                for row in rows
            ]

    async def add_user_specific_memory(self, group_id: int, user_id: int, user_name: str, content: str):
        """为特定用户增加一条具体记忆点"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                "SELECT id FROM user_memories WHERE group_id = ? AND user_id = ? AND content = ?",
                (group_id, user_id, content),
            )
            if await cursor.fetchone():
                return

            await cursor.execute(
                "INSERT INTO user_memories (group_id, user_id, user_name, content) VALUES (?, ?, ?, ?)",
                (group_id, user_id, user_name, content),
            )
            await conn.commit()

    async def get_user_specific_memories(self, group_id: int, user_id: int, limit: int = 5) -> List[str]:
        """获取特定用户的多个记忆点"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                "SELECT content FROM user_memories WHERE group_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT ?",
                (group_id, user_id, limit),
            )
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def list_user_memories(
        self,
        group_id: int,
        user_id: Optional[int] = None,
        keyword: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """获取用户记忆列表"""
        query = "SELECT id, user_id, user_name, content, created_at FROM user_memories WHERE group_id = ?"
        params: List[Any] = [group_id]
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)
        if keyword:
            query += " AND content LIKE ?"
            params.append(f"%{keyword}%")
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(query, tuple(params))
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "user_id": row[1],
                    "user_name": row[2],
                    "content": row[3],
                    "created_at": row[4],
                }
                for row in rows
            ]

    async def delete_user_memory(self, memory_id: int) -> int:
        """删除指定记忆"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute("DELETE FROM user_memories WHERE id = ?", (memory_id,))
            await conn.commit()
            return cursor.rowcount

    async def get_sticker_cache(self, file_hash: str) -> Optional[Dict[str, str]]:
        """根据哈希获取表情包缓存"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute("SELECT description, tag, file_id FROM stickers WHERE file_hash = ?", (file_hash,))
            row = await cursor.fetchone()
            if row:
                return {"description": row[0], "tag": row[1], "file_id": row[2]}
            return None

    async def update_user_id_map(self, group_id: int, user_name: str, user_id: int):
        """更新用户名到 ID 的映射"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                """
                INSERT INTO user_mapping (group_id, user_name, user_id, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(group_id, user_name) DO UPDATE SET
                user_id = excluded.user_id,
                updated_at = CURRENT_TIMESTAMP
            """,
                (group_id, user_name, user_id),
            )
            await conn.commit()

    async def get_user_id_by_name(self, group_id: int, user_name: str) -> Optional[int]:
        """根据用户名查找 ID"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                "SELECT user_id FROM user_mapping WHERE group_id = ? AND user_name = ?", (group_id, user_name)
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def save_sticker_cache(self, file_hash: str, description: str, tag: str, file_id: Optional[str] = None):
        """保存表情包缓存"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                """
                INSERT INTO stickers (file_hash, description, tag, file_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(file_hash) DO UPDATE SET
                description = excluded.description,
                tag = excluded.tag,
                file_id = COALESCE(excluded.file_id, stickers.file_id)
            """,
                (file_hash, description, tag, file_id),
            )
            await conn.commit()

    async def get_stickers_by_tag(self, tag: str) -> List[Dict[str, str]]:
        """根据标签获取所有表情包"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute("SELECT file_id, description FROM stickers WHERE tag = ?", (tag,))
            rows = await cursor.fetchall()
            return [{"file_id": row[0], "description": row[1]} for row in rows]

    async def clear_all_stickers(self) -> int:
        """清空所有表情包缓存"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute("SELECT COUNT(*) FROM stickers")
            row = await cursor.fetchone()
            count = row[0] if row else 0
            await cursor.execute("DELETE FROM stickers")
            await conn.commit()
            return count

    async def get_mood(self, group_id: int) -> int:
        """获取群聊对应的心情值"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute("SELECT mood_value FROM bot_moods WHERE group_id = ?", (group_id,))
            row = await cursor.fetchone()
            if row:
                return row[0]
            await cursor.execute("INSERT INTO bot_moods (group_id, mood_value) VALUES (?, 50)", (group_id,))
            await conn.commit()
            return 50

    async def get_all_group_moods(self) -> List[Tuple[int, int]]:
        """获取所有记录了心情值的群组"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute("SELECT group_id, mood_value FROM bot_moods")
            rows = await cursor.fetchall()
            return [(row[0], row[1]) for row in rows]

    async def get_recent_mood_changes(self, group_id: int, count: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的心情变化记录

        Args:
            group_id: 群组ID
            count: 获取记录数量

        Returns:
            心情变化记录列表，包含 mood_delta 和 timestamp
        """
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                """
                SELECT mood_delta, timestamp FROM mood_history 
                WHERE group_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (group_id, count),
            )
            rows = await cursor.fetchall()
            return [{"mood_delta": row[0], "timestamp": row[1]} for row in rows] if rows else []

    async def has_recent_negative_feedback(self, group_id: int, threshold: int = -5, recent_count: int = 5) -> bool:
        """
        检测最近是否有明显的负面反馈

        Args:
            group_id: 群组ID
            threshold: 负面阈值（默认-5，即单次影响超过-5分视为负面）
            recent_count: 检查最近的N条记录

        Returns:
            True 表示最近有负面反馈，False 表示没有
        """
        changes = await self.get_recent_mood_changes(group_id, count=recent_count)

        # 检查是否有超过阈值的负面记录
        negative_count = sum(1 for change in changes if change["mood_delta"] < threshold)

        # 如果最近N条记录中有超过1/3是负面，或者有一次严重负面（<-10），返回True
        severe_negative = any(change["mood_delta"] < -10 for change in changes)

        return severe_negative or negative_count >= (recent_count // 3)

    async def update_mood(self, group_id: int, delta: int) -> int:
        """更新心情值 (增加或减少)"""
        current_mood = await self.get_mood(group_id)
        new_mood = max(0, min(100, current_mood + delta))
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                """
                UPDATE bot_moods SET mood_value = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE group_id = ?
            """,
                (new_mood, group_id),
            )
            await cursor.execute(
                """
                INSERT INTO mood_history (group_id, mood_delta)
                VALUES (?, ?)
                """,
                (group_id, delta),
            )
            await conn.commit()
        return new_mood

    async def get_personality_state(self, group_id: int) -> Dict[str, Any]:
        """获取人格状态"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                "SELECT traits, recent_thoughts, style_vibe FROM bot_personality WHERE group_id = ?", (group_id,)
            )
            row = await cursor.fetchone()
            if row:
                return {"traits": json.loads(row[0]) if row[0] else {}, "recent_thoughts": row[1], "style_vibe": row[2]}
            return {"traits": {}, "recent_thoughts": "", "style_vibe": ""}

    async def get_all_groups(self) -> List[int]:
        """获取所有已激活人格状态的群组 ID"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute("SELECT group_id FROM bot_personality")
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def update_personality_state(
        self, group_id: int, traits: Optional[Dict] = None, thoughts: Optional[str] = None, vibe: Optional[str] = None
    ):
        """更新人格状态"""
        state = await self.get_personality_state(group_id)

        new_traits = json.dumps(traits if traits is not None else state["traits"])
        new_thoughts = thoughts if thoughts is not None else state["recent_thoughts"]
        new_vibe = vibe if vibe is not None else state["style_vibe"]

        async with await self._get_connection() as conn:
            cursor = await conn.cursor()

            # 如果更新了 style_vibe，同时更新 last_vibe_update
            if vibe is not None:
                await cursor.execute(
                    """
                    INSERT INTO bot_personality (group_id, traits, recent_thoughts, style_vibe, updated_at, last_vibe_update)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT(group_id) DO UPDATE SET
                    traits = excluded.traits,
                    recent_thoughts = excluded.recent_thoughts,
                    style_vibe = excluded.style_vibe,
                    updated_at = CURRENT_TIMESTAMP,
                    last_vibe_update = CURRENT_TIMESTAMP
                """,
                    (group_id, new_traits, new_thoughts, new_vibe),
                )
            else:
                await cursor.execute(
                    """
                    INSERT INTO bot_personality (group_id, traits, recent_thoughts, style_vibe, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(group_id) DO UPDATE SET
                    traits = excluded.traits,
                    recent_thoughts = excluded.recent_thoughts,
                    style_vibe = excluded.style_vibe,
                    updated_at = CURRENT_TIMESTAMP
                """,
                    (group_id, new_traits, new_thoughts, new_vibe),
                )
            await conn.commit()

    async def get_user_relationship(self, group_id: int, user_id: int) -> Dict[str, Any]:
        """获取用户关系数据"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                "SELECT favorability, status FROM user_relationships WHERE group_id = ? AND user_id = ?",
                (group_id, user_id),
            )
            row = await cursor.fetchone()
            if row:
                return {"favorability": row[0], "status": row[1]}
            return {"favorability": 50, "status": "陌生人"}

    async def update_user_relationship(
        self,
        group_id: int,
        user_id: int,
        user_name: str,
        delta_favorability: int = 0,
        new_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """更新用户好感度和关系状态"""
        current = await self.get_user_relationship(group_id, user_id)
        new_fav = max(0, min(100, current["favorability"] + delta_favorability))

        if new_status is None:
            if new_fav <= 10:
                new_status = "死对头"
            elif new_fav <= 30:
                new_status = "厌恶"
            elif new_fav <= 55:
                new_status = "陌生人"
            elif new_fav <= 75:
                new_status = "朋友"
            else:
                new_status = "死党"

        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                """
                INSERT INTO user_relationships (group_id, user_id, user_name, favorability, status, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(group_id, user_id) DO UPDATE SET
                user_name = excluded.user_name,
                favorability = ?,
                status = ?,
                updated_at = CURRENT_TIMESTAMP
                """,
                (group_id, user_id, user_name, new_fav, new_status, new_fav, new_status),
            )
            await conn.commit()
        return {"favorability": new_fav, "status": new_status}

    async def get_bot_schedule(self, group_id: int, date_str: str) -> List[Dict]:
        """获取指定日期的作息表"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                "SELECT schedule_json FROM bot_schedules WHERE group_id = ? AND date = ?", (group_id, date_str)
            )
            row = await cursor.fetchone()
            if row:
                return json.loads(row[0])
            return []

    async def update_bot_schedule(self, group_id: int, date_str: str, schedule: List[Dict]):
        """更新作息表"""
        schedule_json = json.dumps(schedule, ensure_ascii=False)
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                """
                INSERT INTO bot_schedules (group_id, date, schedule_json, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(group_id, date) DO UPDATE SET
                schedule_json = excluded.schedule_json,
                updated_at = CURRENT_TIMESTAMP
            """,
                (group_id, date_str, schedule_json),
            )
            await conn.commit()

    async def add_style_pattern(self, group_id: int, context: str, style_desc: str):
        """记录或更新风格模式"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                """
                INSERT INTO style_patterns (group_id, context, style_desc, weight, updated_at)
                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(group_id, context, style_desc) DO UPDATE SET
                weight = weight + 1,
                updated_at = CURRENT_TIMESTAMP
            """,
                (group_id, context, style_desc),
            )
            await conn.commit()

    async def get_style_patterns(self, group_id: int, limit: int = 20) -> List[Dict]:
        """获取权重最高的风格模式"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                "SELECT context, style_desc, weight FROM style_patterns WHERE group_id = ? ORDER BY weight DESC LIMIT ?",
                (group_id, limit),
            )
            rows = await cursor.fetchall()
            return [{"context": row[0], "style_desc": row[1], "weight": row[2]} for row in rows]

    async def update_slang_candidate(
        self,
        group_id: int,
        phrase: str,
        delta_freq: int = 1,
        stage: Optional[int] = None,
        definition: Optional[str] = None,
        context_samples: Optional[List[str]] = None,
    ):
        """更新黑话候选词状态"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                "SELECT frequency, stage, definition, context_samples FROM slang_candidates WHERE group_id = ? AND phrase = ?",
                (group_id, phrase),
            )
            row = await cursor.fetchone()

            if row:
                new_freq = row[0] + delta_freq
                new_stage = stage if stage is not None else row[1]
                new_def = definition if definition is not None else row[2]

                existing_samples = json.loads(row[3] or "[]")
                if context_samples:
                    existing_samples.extend(context_samples)
                    existing_samples = list(set(existing_samples))[-10:]
                new_samples = json.dumps(existing_samples, ensure_ascii=False)

                await cursor.execute(
                    """
                    UPDATE slang_candidates SET 
                    frequency = ?, stage = ?, definition = ?, context_samples = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE group_id = ? AND phrase = ?
                """,
                    (new_freq, new_stage, new_def, new_samples, group_id, phrase),
                )
            else:
                new_samples = json.dumps(context_samples or [], ensure_ascii=False)
                await cursor.execute(
                    """
                    INSERT INTO slang_candidates (group_id, phrase, frequency, stage, definition, context_samples)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (group_id, phrase, delta_freq, stage or 1, definition, new_samples),
                )
            await conn.commit()

    async def get_slang_candidates(self, group_id: int, min_freq: int = 0, stage: Optional[int] = None) -> List[Dict]:
        """获取黑话候选词"""
        query = "SELECT phrase, frequency, stage, definition, context_samples FROM slang_candidates WHERE group_id = ? AND frequency >= ?"
        params = [group_id, min_freq]
        if stage is not None:
            query += " AND stage = ?"
            params.append(stage)

        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(query, tuple(params))
            rows = await cursor.fetchall()
            return [
                {
                    "phrase": row[0],
                    "frequency": row[1],
                    "stage": row[2],
                    "definition": row[3],
                    "context_samples": json.loads(row[4] or "[]"),
                }
                for row in rows
            ]

    async def list_slang_candidates(
        self,
        group_id: int,
        stage: Optional[int] = None,
        min_freq: int = 0,
        keyword: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """获取黑话候选词列表"""
        query = (
            "SELECT phrase, frequency, stage, definition, context_samples, updated_at "
            "FROM slang_candidates WHERE group_id = ? AND frequency >= ?"
        )
        params: List[Any] = [group_id, min_freq]
        if stage is not None:
            query += " AND stage = ?"
            params.append(stage)
        if keyword:
            query += " AND (phrase LIKE ? OR definition LIKE ?)"
            like_keyword = f"%{keyword}%"
            params.extend([like_keyword, like_keyword])
        query += " ORDER BY frequency DESC, updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(query, tuple(params))
            rows = await cursor.fetchall()
            return [
                {
                    "phrase": row[0],
                    "frequency": row[1],
                    "stage": row[2],
                    "definition": row[3],
                    "context_samples": json.loads(row[4] or "[]"),
                    "updated_at": row[5],
                }
                for row in rows
            ]

    async def delete_slang_candidate(self, group_id: int, phrase: str) -> int:
        """删除黑话候选词"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute("DELETE FROM slang_candidates WHERE group_id = ? AND phrase = ?", (group_id, phrase))
            await conn.commit()
            return cursor.rowcount

    async def list_style_patterns(
        self,
        group_id: int,
        keyword: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """获取风格模式列表"""
        query = "SELECT id, context, style_desc, weight, updated_at FROM style_patterns WHERE group_id = ?"
        params: List[Any] = [group_id]
        if keyword:
            query += " AND (context LIKE ? OR style_desc LIKE ?)"
            like_keyword = f"%{keyword}%"
            params.extend([like_keyword, like_keyword])
        query += " ORDER BY weight DESC, updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(query, tuple(params))
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "context": row[1],
                    "style_desc": row[2],
                    "weight": row[3],
                    "updated_at": row[4],
                }
                for row in rows
            ]

    async def delete_style_pattern_by_id(self, style_id: int) -> int:
        """删除风格模式"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute("DELETE FROM style_patterns WHERE id = ?", (style_id,))
            await conn.commit()
            return cursor.rowcount

    async def add_knowledge_triplet(
        self, group_id: int, subject: str, predicate: str, obj: str, confidence: float = 1.0
    ):
        """添加知识三元组"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                """
                INSERT INTO knowledge_triplets (group_id, subject, predicate, object, confidence, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(group_id, subject, predicate, object) DO UPDATE SET
                confidence = (confidence + excluded.confidence) / 2.0,
                updated_at = CURRENT_TIMESTAMP
            """,
                (group_id, subject, predicate, obj, confidence),
            )
            await conn.commit()

    async def get_knowledge_triplets(
        self, group_id: int, subject: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """查询知识三元组"""
        query = "SELECT subject, predicate, object, confidence FROM knowledge_triplets WHERE group_id = ?"
        params: List[Any] = [group_id]
        if subject:
            query += " AND subject = ?"
            params.append(subject)
        query += " ORDER BY confidence DESC LIMIT ?"
        params.append(limit)

        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(query, tuple(params))
            rows = await cursor.fetchall()
            return [{"subject": row[0], "predicate": row[1], "object": row[2], "confidence": row[3]} for row in rows]

    async def delete_knowledge_triplet(
        self,
        group_id: int,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        obj: Optional[str] = None,
    ) -> int:
        """
        删除知识三元组

        Args:
            group_id: 群组 ID
            subject: 主体（可选，不指定则删除该群所有）
            predicate: 谓词（可选）
            obj: 客体（可选）

        Returns:
            删除的记录数
        """
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()

            conditions = ["group_id = ?"]
            params: List[Any] = [group_id]

            if subject:
                conditions.append("subject = ?")
                params.append(subject)
            if predicate:
                conditions.append("predicate = ?")
                params.append(predicate)
            if obj:
                conditions.append("object = ?")
                params.append(obj)

            query = f"DELETE FROM knowledge_triplets WHERE {' AND '.join(conditions)}"
            await cursor.execute(query, tuple(params))
            deleted_count = cursor.rowcount
            await conn.commit()

            return deleted_count

    async def delete_style_pattern(
        self, group_id: int, context: Optional[str] = None, style_desc: Optional[str] = None
    ) -> int:
        """
        删除风格模式

        Args:
            group_id: 群组 ID
            context: 情境（可选）
            style_desc: 风格描述（可选）

        Returns:
            删除的记录数
        """
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()

            conditions = ["group_id = ?"]
            params: List[Any] = [group_id]

            if context:
                conditions.append("context = ?")
                params.append(context)
            if style_desc:
                conditions.append("style_desc = ?")
                params.append(style_desc)

            query = f"DELETE FROM style_patterns WHERE {' AND '.join(conditions)}"
            await cursor.execute(query, tuple(params))
            deleted_count = cursor.rowcount
            await conn.commit()

            return deleted_count

    async def merge_style_patterns(
        self, group_id: int, old_patterns: List[Dict], new_context: str, new_style_desc: str
    ) -> bool:
        """
        合并多个风格模式为一个

        Args:
            group_id: 群组 ID
            old_patterns: 要合并的旧模式列表 [{"context": "...", "style_desc": "..."}]
            new_context: 新的情境描述
            new_style_desc: 新的风格描述

        Returns:
            是否成功
        """
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()

            try:
                total_weight = 0
                for pattern in old_patterns:
                    await cursor.execute(
                        "SELECT weight FROM style_patterns WHERE group_id = ? AND context = ? AND style_desc = ?",
                        (group_id, pattern["context"], pattern["style_desc"]),
                    )
                    row = await cursor.fetchone()
                    if row:
                        total_weight += row[0]

                    await cursor.execute(
                        "DELETE FROM style_patterns WHERE group_id = ? AND context = ? AND style_desc = ?",
                        (group_id, pattern["context"], pattern["style_desc"]),
                    )

                await cursor.execute(
                    """
                    INSERT INTO style_patterns (group_id, context, style_desc, weight, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(group_id, context, style_desc) DO UPDATE SET
                    weight = weight + ?,
                    updated_at = CURRENT_TIMESTAMP
                    """,
                    (group_id, new_context, new_style_desc, total_weight, total_weight),
                )

                await conn.commit()
                return True
            except Exception:
                await conn.rollback()
                return False

    async def get_all_names_for_user(self, group_id: int, user_name: str) -> List[str]:
        """获取用户在所有群组中的名字（通过 QQ 号关联）"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()

            await cursor.execute(
                "SELECT user_id FROM user_mapping WHERE group_id = ? AND user_name = ?", (group_id, user_name)
            )
            row = await cursor.fetchone()

            if row and row[0]:
                user_id = row[0]
                await cursor.execute("SELECT DISTINCT user_name FROM user_mapping WHERE user_id = ?", (user_id,))
                rows = await cursor.fetchall()
                return [r[0] for r in rows]

            return [user_name]

    async def get_user_impression_cross_group(self, group_id: int, user_id: int) -> Optional[str]:
        """获取用户印象（跨群查询）"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()

            await cursor.execute(
                "SELECT impression FROM user_profiles WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)
            )

            rows = await cursor.fetchall()
            rows_list = list(rows)
            if rows_list:
                return rows_list[0][0] if rows_list[0] else None

            return None

    async def get_user_specific_memories_cross_group(self, group_id: int, user_id: int, limit: int = 5) -> List[str]:
        """获取用户具体记忆（跨群查询）"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()

            await cursor.execute(
                "SELECT content FROM user_memories WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            )

            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def get_user_relationship_cross_group(self, group_id: int, user_id: int) -> Dict[str, Any]:
        """获取用户关系（跨群查询）"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()

            await cursor.execute("SELECT favorability, status FROM user_relationships WHERE user_id = ?", (user_id,))

            rows = await cursor.fetchall()
            rows_list = list(rows)
            if rows_list:
                from collections import Counter

                avg_fav = int(sum(r[0] for r in rows_list) / len(rows_list))

                status_counter = Counter(r[1] for r in rows_list)
                most_common_status = status_counter.most_common(1)[0][0]

                return {"favorability": avg_fav, "status": most_common_status}

            return {"favorability": 50, "status": "陌生人"}

    async def get_db_stats(self) -> Dict[str, int]:
        """获取数据库统计信息"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            stats = {}

            tables = [
                "chat_history",
                "user_memories",
                "stickers",
                "style_patterns",
                "slang_candidates",
                "knowledge_triplets",
            ]
            for table in tables:
                await cursor.execute(f"SELECT COUNT(*) FROM {table}")
                result = await cursor.fetchone()
                stats[table] = result[0] if result else 0

            return stats

    async def cleanup_old_data(self, days: int = 30) -> Dict[str, int]:
        """清理旧数据以释放空间"""
        from datetime import datetime, timedelta

        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        deleted_counts = {}

        async with await self._get_connection() as conn:
            cursor = await conn.cursor()

            try:
                await cursor.execute(f"DELETE FROM chat_history WHERE timestamp < '{cutoff_date}' AND is_processed = 1")
                deleted_counts["chat_history"] = cursor.rowcount

                await cursor.execute(f"DELETE FROM user_memories WHERE created_at < '{cutoff_date}'")
                deleted_counts["user_memories"] = cursor.rowcount

                await cursor.execute(f"DELETE FROM style_patterns WHERE updated_at < '{cutoff_date}' AND weight < 5")
                deleted_counts["style_patterns"] = cursor.rowcount

                await cursor.execute(
                    f"DELETE FROM slang_candidates WHERE updated_at < '{cutoff_date}' AND stage < 3 AND frequency < 5"
                )
                deleted_counts["slang_candidates"] = cursor.rowcount

                await conn.commit()
            except Exception as e:
                await conn.rollback()
                raise e

        return deleted_counts

    async def record_bot_reply(
        self, group_id: int, triggered_by: str, is_at_bot: bool = False, interest_score: float = 0
    ):
        """记录 bot 的一次回复行为"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                """
                INSERT INTO bot_reply_history (group_id, triggered_by_user, is_at_bot, interest_score)
                VALUES (?, ?, ?, ?)
                """,
                (group_id, triggered_by, 1 if is_at_bot else 0, interest_score),
            )
            await conn.commit()

    async def get_recent_reply_count(self, group_id: int, minutes: int = 10, only_active: bool = True) -> int:
        """
        获取指定时间内的回复次数

        Args:
            group_id: 群组ID
            minutes: 统计时间范围（分钟）
            only_active: 是否只统计主动发言（True=不包含被艾特的回复，False=包含所有回复）
        """
        from datetime import datetime, timedelta

        cutoff_time = (datetime.now() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()

            if only_active:
                # 只统计主动发言（非艾特）
                await cursor.execute(
                    """
                    SELECT COUNT(*) FROM bot_reply_history 
                    WHERE group_id = ? AND timestamp >= ? AND is_at_bot = 0
                    """,
                    (group_id, cutoff_time),
                )
            else:
                # 统计所有回复
                await cursor.execute(
                    """
                    SELECT COUNT(*) FROM bot_reply_history 
                    WHERE group_id = ? AND timestamp >= ?
                    """,
                    (group_id, cutoff_time),
                )

            result = await cursor.fetchone()
            return result[0] if result else 0

    async def get_last_reply_time(self, group_id: int, only_active: bool = True) -> Optional[datetime.datetime]:
        """
        获取最后一次回复的时间

        Args:
            group_id: 群组ID
            only_active: 是否只查询主动发言（True=不包含被艾特的回复，False=包含所有回复）
        """
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()

            if only_active:
                # 只查询主动发言
                await cursor.execute(
                    """
                    SELECT timestamp FROM bot_reply_history 
                    WHERE group_id = ? AND is_at_bot = 0
                    ORDER BY timestamp DESC LIMIT 1
                    """,
                    (group_id,),
                )
            else:
                # 查询所有回复
                await cursor.execute(
                    """
                    SELECT timestamp FROM bot_reply_history 
                    WHERE group_id = ? 
                    ORDER BY timestamp DESC LIMIT 1
                    """,
                    (group_id,),
                )

            result = await cursor.fetchone()
            if result:
                from datetime import datetime

                return datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
            return None

    async def cleanup_old_reply_history(self, days: int = 7):
        """清理旧的回复历史记录"""
        from datetime import datetime, timedelta

        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute("DELETE FROM bot_reply_history WHERE timestamp < ?", (cutoff_date,))
            await conn.commit()

    async def vacuum_database(self):
        """执行数据库优化，回收空间"""
        async with await self._get_connection() as conn:
            await conn.execute("VACUUM")
            await conn.commit()

    async def save_mute_reflection(
        self,
        group_id: int,
        ban_reason: str,
        trigger_context: str,
        reflection_thought: str,
        lesson_learned: str,
        operator_id: int,
        duration_seconds: int,
    ):
        """保存禁言反思记录"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                """
                INSERT INTO mute_reflections 
                (group_id, ban_reason, trigger_context, reflection_thought, lesson_learned, operator_id, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    group_id,
                    ban_reason,
                    trigger_context,
                    reflection_thought,
                    lesson_learned,
                    operator_id,
                    duration_seconds,
                ),
            )
            await conn.commit()

    async def get_mute_reflections(self, group_id: int, limit: int = 10) -> List[Dict]:
        """获取禁言反思记录"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                """
                SELECT ban_reason, reflection_thought, lesson_learned, operator_id, duration_seconds, timestamp
                FROM mute_reflections
                WHERE group_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (group_id, limit),
            )
            rows = await cursor.fetchall()
            return [
                {
                    "ban_reason": row[0],
                    "reflection_thought": row[1],
                    "lesson_learned": row[2],
                    "operator_id": row[3],
                    "duration_seconds": row[4],
                    "timestamp": row[5],
                }
                for row in rows
            ]


db_manager = DBManager()
