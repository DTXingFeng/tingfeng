import aiosqlite
import datetime
import json
from pathlib import Path
from typing import List, Tuple, Optional, Dict


class DBManager:
    def __init__(self, db_path: str = "data/bot_data.db"):
        self.db_path = Path(db_path)
        self._init_done = False

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
                        is_processed INTEGER DEFAULT 0,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

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
                    CREATE TABLE IF NOT EXISTS bot_personality (
                        group_id INTEGER PRIMARY KEY,
                        traits TEXT,
                        recent_thoughts TEXT,
                        style_vibe TEXT,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
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

                await conn.commit()
        except Exception as e:
            print(f"数据库初始化失败: {e}")
            raise

    async def add_chat_log(self, group_id: int, msg: str):
        """添加一条聊天记录"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute("INSERT INTO chat_history (group_id, msg) VALUES (?, ?)", (group_id, msg))
            await conn.commit()

    async def get_chat_log(self, group_id: int, limit: int = 10) -> List[str]:
        """获取指定群组最近的聊天记录"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                "SELECT msg FROM chat_history WHERE group_id = ? ORDER BY timestamp DESC LIMIT ?", (group_id, limit)
            )
            rows = await cursor.fetchall()
            messages = [row[0] for row in rows]
            messages.reverse()
            return messages

    async def get_unprocessed_logs(self, group_id: int, limit: int = 50) -> List[Tuple[int, str]]:
        """获取未处理过的原始记录"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                "SELECT id, msg FROM chat_history WHERE group_id = ? AND is_processed = 0 ORDER BY timestamp ASC LIMIT ?",
                (group_id, limit),
            )
            return await cursor.fetchall()

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
        """更新对某个用户的印象"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
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

    async def save_sticker_cache(self, file_hash: str, description: str, tag: str, file_id: str = None):
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
            count = (await cursor.fetchone())[0]
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
            return await cursor.fetchall()

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
            await conn.commit()
        return new_mood

    async def get_personality_state(self, group_id: int) -> Dict[str, any]:
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
        self, group_id: int, traits: Dict = None, thoughts: str = None, vibe: str = None
    ):
        """更新人格状态"""
        state = await self.get_personality_state(group_id)

        new_traits = json.dumps(traits if traits is not None else state["traits"])
        new_thoughts = thoughts if thoughts is not None else state["recent_thoughts"]
        new_vibe = vibe if vibe is not None else state["style_vibe"]

        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
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

    async def get_user_relationship(self, group_id: int, user_id: int) -> Dict[str, any]:
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
        self, group_id: int, user_id: int, user_name: str, delta_favorability: int = 0, new_status: str = None
    ) -> Dict[str, any]:
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
                favorability = excluded.favorability,
                status = excluded.status,
                updated_at = CURRENT_TIMESTAMP
            """,
                (group_id, user_id, user_name, new_fav, new_status),
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
        stage: int = None,
        definition: str = None,
        context_samples: List[str] = None,
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

    async def get_slang_candidates(self, group_id: int, min_freq: int = 0, stage: int = None) -> List[Dict]:
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

    async def get_knowledge_triplets(self, group_id: int, subject: str = None, limit: int = 50) -> List[Dict]:
        """查询知识三元组"""
        query = "SELECT subject, predicate, object, confidence FROM knowledge_triplets WHERE group_id = ?"
        params = [group_id]
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
                "SELECT impression FROM user_profiles WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,)
            )

            rows = await cursor.fetchall()
            if rows:
                return rows[0][0] if rows[0] else None

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

    async def get_user_relationship_cross_group(self, group_id: int, user_id: int) -> Dict[str, any]:
        """获取用户关系（跨群查询）"""
        async with await self._get_connection() as conn:
            cursor = await conn.cursor()
            
            await cursor.execute(
                "SELECT favorability, status FROM user_relationships WHERE user_id = ?", (user_id,)
            )

            rows = await cursor.fetchall()
            if rows:
                from collections import Counter

                avg_fav = int(sum(r[0] for r in rows) / len(rows))

                status_counter = Counter(r[1] for r in rows)
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
                stats[table] = result[0]

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

    async def record_bot_reply(self, group_id: int, triggered_by: str, is_at_bot: bool = False, interest_score: float = 0):
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

    async def get_last_reply_time(self, group_id: int, only_active: bool = True) -> Optional[datetime]:
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


db_manager = DBManager()
