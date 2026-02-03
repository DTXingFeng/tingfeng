import sqlite3
import datetime
import json
from pathlib import Path
from typing import List, Tuple, Optional, Dict

class DBManager:
    def __init__(self, db_path: str = "data/bot_data.db"):
        self.db_path = Path(db_path)
        try:
            # 确保数据目录存在
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()
        except sqlite3.OperationalError as e:
            if "unable to open database file" in str(e):
                print(f"\n❌ ERROR: 无法打开数据库文件 '{db_path}'。")
                print(f"这通常是由于目录权限不足导致的。")
                print(f"提示: 请尝试运行 'sudo chown -R $USER:$USER {Path.cwd()}' 或 'chmod -R 755 data/'\n")
            raise e

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
            # 创建人格状态表
            # group_id: 群号
            # traits: JSON 格式的人格特征值
            # thoughts: 最近的一次内心独白
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_personality (
                    group_id INTEGER PRIMARY KEY,
                    traits TEXT,
                    recent_thoughts TEXT,
                    style_vibe TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # 创建用户关系表
            # favorability: 好感度 (0-100, 默认 50)
            # status: 关系状态 (如：陌生人、熟人、朋友、死党、死对头)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_relationships (
                    group_id INTEGER,
                    user_name TEXT,
                    favorability INTEGER DEFAULT 50,
                    status TEXT DEFAULT '陌生人',
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (group_id, user_name)
                )
            ''')
            # 创建作息表
            # group_id: 群号
            # schedule_json: 存储作息时间段的 JSON 字符串
            # date: 日期 (YYYY-MM-DD)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_schedules (
                    group_id INTEGER,
                    date TEXT,
                    schedule_json TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (group_id, date)
                )
            ''')
            
            # 创建风格模仿表 (Mimicry)
            # context: 发生的情境 (如: "被夸奖", "被骂", "讨论技术")
            # style_desc: 对应的表达风格描述
            # weight: 该风格的权重计数
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS style_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER,
                    context TEXT,
                    style_desc TEXT,
                    weight INTEGER DEFAULT 1,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(group_id, context, style_desc)
                )
            ''')
            
            # 创建黑话挖掘表 (Slang Mining)
            # stage: 挖掘阶段 (1: 盲猜, 2: 境推, 3: 判定)
            # context_samples: 出现的上下文样本 JSON
            cursor.execute('''
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
            ''')
            
            # 创建知识图谱三元组表 (Knowledge Graph)
            cursor.execute('''
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
            ''')
            
            # 创建数据库索引以提高查询性能
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_history_group_time ON chat_history(group_id, timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_history_group_processed ON chat_history(group_id, is_processed, timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_stickers_tag ON stickers(tag)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_memories_group_user_time ON user_memories(group_id, user_name, created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_relationships_favorability ON user_relationships(favorability)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_style_patterns_weight ON style_patterns(weight DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_slang_candidates_query ON slang_candidates(group_id, stage, frequency)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_knowledge_triplets_confidence ON knowledge_triplets(confidence DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_knowledge_triplets_subject ON knowledge_triplets(subject)')
            
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

    def get_personality_state(self, group_id: int) -> Dict[str, any]:
        """获取人格状态"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT traits, recent_thoughts, style_vibe FROM bot_personality WHERE group_id = ?",
                (group_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "traits": json.loads(row[0]) if row[0] else {},
                    "recent_thoughts": row[1],
                    "style_vibe": row[2]
                }
            return {"traits": {}, "recent_thoughts": "", "style_vibe": ""}

    def get_all_groups(self) -> List[int]:
        """获取所有已激活人格状态的群组 ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT group_id FROM bot_personality")
            return [row[0] for row in cursor.fetchall()]

    def update_personality_state(self, group_id: int, traits: Dict = None, thoughts: str = None, vibe: str = None):
        """更新人格状态"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 先获取现有数据
            state = self.get_personality_state(group_id)
            
            new_traits = json.dumps(traits if traits is not None else state["traits"])
            new_thoughts = thoughts if thoughts is not None else state["recent_thoughts"]
            new_vibe = vibe if vibe is not None else state["style_vibe"]
            
            cursor.execute('''
                INSERT INTO bot_personality (group_id, traits, recent_thoughts, style_vibe, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(group_id) DO UPDATE SET
                traits = excluded.traits,
                recent_thoughts = excluded.recent_thoughts,
                style_vibe = excluded.style_vibe,
                updated_at = CURRENT_TIMESTAMP
            ''', (group_id, new_traits, new_thoughts, new_vibe))
            conn.commit()

    def get_user_relationship(self, group_id: int, user_name: str) -> Dict[str, any]:
        """获取用户关系数据"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT favorability, status FROM user_relationships WHERE group_id = ? AND user_name = ?",
                (group_id, user_name)
            )
            row = cursor.fetchone()
            if row:
                return {"favorability": row[0], "status": row[1]}
            return {"favorability": 50, "status": "陌生人"}

    def update_user_relationship(self, group_id: int, user_name: str, delta_favorability: int = 0, new_status: str = None):
        """更新用户好感度和关系状态"""
        current = self.get_user_relationship(group_id, user_name)
        new_fav = max(0, min(100, current["favorability"] + delta_favorability))
        
        # 自动根据好感度更新状态（如果未指定新状态）
        if new_status is None:
            if new_fav <= 10: new_status = "死对头"
            elif new_fav <= 30: new_status = "厌恶"
            elif new_fav <= 55: new_status = "陌生人"
            elif new_fav <= 75: new_status = "朋友"
            else: new_status = "死党"
            
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_relationships (group_id, user_name, favorability, status, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(group_id, user_name) DO UPDATE SET
                favorability = excluded.favorability,
                status = excluded.status,
                updated_at = CURRENT_TIMESTAMP
            ''', (group_id, user_name, new_fav, new_status))
            conn.commit()
        return {"favorability": new_fav, "status": new_status}

    def get_bot_schedule(self, group_id: int, date_str: str) -> List[Dict]:
        """获取指定日期的作息表"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT schedule_json FROM bot_schedules WHERE group_id = ? AND date = ?",
                (group_id, date_str)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return []

    def update_bot_schedule(self, group_id: int, date_str: str, schedule: List[Dict]):
        """更新作息表"""
        schedule_json = json.dumps(schedule, ensure_ascii=False)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO bot_schedules (group_id, date, schedule_json, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(group_id, date) DO UPDATE SET
                schedule_json = excluded.schedule_json,
                updated_at = CURRENT_TIMESTAMP
            ''', (group_id, date_str, schedule_json))
            conn.commit()

    # --- 升级学习能力相关方法 ---

    def add_style_pattern(self, group_id: int, context: str, style_desc: str):
        """记录或更新风格模式"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO style_patterns (group_id, context, style_desc, weight, updated_at)
                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(group_id, context, style_desc) DO UPDATE SET
                weight = weight + 1,
                updated_at = CURRENT_TIMESTAMP
            ''', (group_id, context, style_desc))
            conn.commit()

    def get_style_patterns(self, group_id: int, limit: int = 20) -> List[Dict]:
        """获取权重最高的风格模式"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT context, style_desc, weight FROM style_patterns WHERE group_id = ? ORDER BY weight DESC LIMIT ?",
                (group_id, limit)
            )
            return [{"context": row[0], "style_desc": row[1], "weight": row[2]} for row in cursor.fetchall()]

    def update_slang_candidate(self, group_id: int, phrase: str, delta_freq: int = 1, stage: int = None, definition: str = None, context_samples: List[str] = None):
        """更新黑话候选词状态"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 获取现有数据
            cursor.execute("SELECT frequency, stage, definition, context_samples FROM slang_candidates WHERE group_id = ? AND phrase = ?", (group_id, phrase))
            row = cursor.fetchone()
            
            if row:
                new_freq = row[0] + delta_freq
                new_stage = stage if stage is not None else row[1]
                new_def = definition if definition is not None else row[2]
                
                # 合并上下文样本
                existing_samples = json.loads(row[3] or "[]")
                if context_samples:
                    existing_samples.extend(context_samples)
                    existing_samples = list(set(existing_samples))[-10:] # 最多保留10个样本
                new_samples = json.dumps(existing_samples, ensure_ascii=False)
                
                cursor.execute('''
                    UPDATE slang_candidates SET 
                    frequency = ?, stage = ?, definition = ?, context_samples = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE group_id = ? AND phrase = ?
                ''', (new_freq, new_stage, new_def, new_samples, group_id, phrase))
            else:
                new_samples = json.dumps(context_samples or [], ensure_ascii=False)
                cursor.execute('''
                    INSERT INTO slang_candidates (group_id, phrase, frequency, stage, definition, context_samples)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (group_id, phrase, delta_freq, stage or 1, definition, new_samples))
            conn.commit()

    def get_slang_candidates(self, group_id: int, min_freq: int = 0, stage: int = None) -> List[Dict]:
        """获取黑话候选词"""
        query = "SELECT phrase, frequency, stage, definition, context_samples FROM slang_candidates WHERE group_id = ? AND frequency >= ?"
        params = [group_id, min_freq]
        if stage is not None:
            query += " AND stage = ?"
            params.append(stage)
            
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            return [{
                "phrase": row[0], 
                "frequency": row[1], 
                "stage": row[2], 
                "definition": row[3], 
                "context_samples": json.loads(row[4] or "[]")
            } for row in cursor.fetchall()]

    def add_knowledge_triplet(self, group_id: int, subject: str, predicate: str, obj: str, confidence: float = 1.0):
        """添加知识三元组"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO knowledge_triplets (group_id, subject, predicate, object, confidence, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(group_id, subject, predicate, object) DO UPDATE SET
                confidence = (confidence + excluded.confidence) / 2.0,
                updated_at = CURRENT_TIMESTAMP
            ''', (group_id, subject, predicate, obj, confidence))
            conn.commit()

    def get_knowledge_triplets(self, group_id: int, subject: str = None, limit: int = 50) -> List[Dict]:
        """查询知识三元组"""
        query = "SELECT subject, predicate, object, confidence FROM knowledge_triplets WHERE group_id = ?"
        params = [group_id]
        if subject:
            query += " AND subject = ?"
            params.append(subject)
        query += " ORDER BY confidence DESC LIMIT ?"
        params.append(limit)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            return [{"subject": row[0], "predicate": row[1], "object": row[2], "confidence": row[3]} for row in cursor.fetchall()]

    # 跨群用户查询方法
    def get_all_names_for_user(self, group_id: int, user_name: str) -> List[str]:
        """
        获取用户在所有群组中的名字（通过 QQ 号关联）
        
        Args:
            group_id: 当前群组 ID
            user_name: 用户名
            
        Returns:
            该用户在所有群组中的名字列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 先获取当前用户的 QQ 号
            cursor.execute(
                "SELECT user_id FROM user_mapping WHERE group_id = ? AND user_name = ?",
                (group_id, user_name)
            )
            row = cursor.fetchone()
            
            if row and row[0]:
                # 使用 QQ 号查找所有群组中的名字
                user_id = row[0]
                cursor.execute(
                    "SELECT DISTINCT user_name FROM user_mapping WHERE user_id = ?",
                    (user_id,)
                )
                return [r[0] for r in cursor.fetchall()]
            
            # 如果没有 QQ 号，只返回当前名字
            return [user_name]

    def get_user_impression_cross_group(self, group_id: int, user_name: str) -> Optional[str]:
        """
        获取用户印象（跨群查询）
        
        通过 QQ 号关联，聚合该用户在所有群组的印象
        
        Args:
            group_id: 当前群组 ID
            user_name: 用户名
            
        Returns:
            用户印象文本（聚合后的）
        """
        all_names = self.get_all_names_for_user(group_id, user_name)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 查询该用户所有名字的印象
            placeholders = ','.join(['?' for _ in all_names])
            cursor.execute(
                f"SELECT impression FROM user_profiles WHERE user_name IN ({placeholders}) ORDER BY updated_at DESC",
                all_names
            )
            
            rows = cursor.fetchall()
            if rows:
                # 返回最新的印象
                return rows[0][0] if rows[0] else None
            
            return None

    def get_user_specific_memories_cross_group(self, group_id: int, user_name: str, limit: int = 5) -> List[str]:
        """
        获取用户具体记忆（跨群查询）
        
        通过 QQ 号关联，聚合该用户在所有群组的记忆
        
        Args:
            group_id: 当前群组 ID
            user_name: 用户名
            limit: 返回数量限制
            
        Returns:
            记忆内容列表（按时间倒序）
        """
        all_names = self.get_all_names_for_user(group_id, user_name)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 查询该用户所有名字的记忆
            placeholders = ','.join(['?' for _ in all_names])
            cursor.execute(
                f"SELECT content FROM user_memories WHERE user_name IN ({placeholders}) ORDER BY created_at DESC LIMIT ?",
                all_names + [limit]
            )
            
            return [row[0] for row in cursor.fetchall()]

    def get_user_relationship_cross_group(self, group_id: int, user_name: str) -> Dict[str, any]:
        """
        获取用户关系（跨群查询）
        
        通过 QQ 号关联，计算该用户在所有群组的平均好感度和最常见关系状态
        
        Args:
            group_id: 当前群组 ID
            user_name: 用户名
            
        Returns:
            包含 favorability 和 status 的字典
        """
        all_names = self.get_all_names_for_user(group_id, user_name)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 查询该用户所有名字的关系数据
            placeholders = ','.join(['?' for _ in all_names])
            cursor.execute(
                f"SELECT favorability, status FROM user_relationships WHERE user_name IN ({placeholders})",
                all_names
            )
            
            rows = cursor.fetchall()
            if rows:
                # 计算平均好感度
                avg_fav = int(sum(r[0] for r in rows) / len(rows))
                
                # 获取最常见的关系状态
                from collections import Counter
                status_counter = Counter(r[1] for r in rows)
                most_common_status = status_counter.most_common(1)[0][0]
                
                return {"favorability": avg_fav, "status": most_common_status}
            
            return {"favorability": 50, "status": "陌生人"}

    def get_db_stats(self) -> Dict[str, int]:
        """获取数据库统计信息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            stats = {}
            
            tables = ['chat_history', 'user_memories', 'stickers', 'style_patterns', 'slang_candidates', 'knowledge_triplets']
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
            
            return stats

    def cleanup_old_data(self, days: int = 30):
        """
        清理旧数据以释放空间
        
        Args:
            days: 保留最近多少天的数据，默认30天
        """
        from datetime import datetime, timedelta
        
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        deleted_counts = {}
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute(f"DELETE FROM chat_history WHERE timestamp < '{cutoff_date}' AND is_processed = 1")
                deleted_counts['chat_history'] = cursor.rowcount
                
                cursor.execute(f"DELETE FROM user_memories WHERE created_at < '{cutoff_date}'")
                deleted_counts['user_memories'] = cursor.rowcount
                
                cursor.execute(f"DELETE FROM style_patterns WHERE updated_at < '{cutoff_date}' AND weight < 5")
                deleted_counts['style_patterns'] = cursor.rowcount
                
                cursor.execute(f"DELETE FROM slang_candidates WHERE updated_at < '{cutoff_date}' AND stage < 3 AND frequency < 5")
                deleted_counts['slang_candidates'] = cursor.rowcount
                
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
        
        return deleted_counts

    def vacuum_database(self):
        """执行数据库优化，回收空间"""
        with self._get_connection() as conn:
            conn.execute("VACUUM")
            conn.commit()

# 全局单例
db_manager = DBManager()
