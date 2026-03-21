from typing import Optional, Any
from .connection import db


class BaseRepository:
    table_name: str = ""
    
    @classmethod
    def insert(cls, data: dict) -> int:
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        sql = f"INSERT INTO {cls.table_name} ({columns}) VALUES ({placeholders})"
        cursor = db.execute(sql, tuple(data.values()))
        return cursor.lastrowid
    
    @classmethod
    def update(cls, id: int, data: dict) -> bool:
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        sql = f"UPDATE {cls.table_name} SET {set_clause} WHERE id = ?"
        cursor = db.execute(sql, tuple(data.values()) + (id,))
        return cursor.rowcount > 0
    
    @classmethod
    def delete(cls, id: int) -> bool:
        sql = f"DELETE FROM {cls.table_name} WHERE id = ?"
        cursor = db.execute(sql, (id,))
        return cursor.rowcount > 0
    
    @classmethod
    def get_by_id(cls, id: int) -> Optional[dict]:
        sql = f"SELECT * FROM {cls.table_name} WHERE id = ?"
        row = db.fetchone(sql, (id,))
        return dict(row) if row else None
    
    @classmethod
    def get_all(cls, limit: int = 100, offset: int = 0) -> list:
        sql = f"SELECT * FROM {cls.table_name} LIMIT ? OFFSET ?"
        rows = db.fetchall(sql, (limit, offset))
        return [dict(row) for row in rows]
    
    @classmethod
    def find_one(cls, where: str, params: tuple = ()) -> Optional[dict]:
        sql = f"SELECT * FROM {cls.table_name} WHERE {where}"
        row = db.fetchone(sql, params)
        return dict(row) if row else None
    
    @classmethod
    def find_many(cls, where: str = "1=1", params: tuple = (), limit: int = 100, offset: int = 0) -> list:
        sql = f"SELECT * FROM {cls.table_name} WHERE {where} LIMIT ? OFFSET ?"
        rows = db.fetchall(sql, params + (limit, offset))
        return [dict(row) for row in rows]
    
    @classmethod
    def count(cls, where: str = "1=1", params: tuple = ()) -> int:
        sql = f"SELECT COUNT(*) as cnt FROM {cls.table_name} WHERE {where}"
        row = db.fetchone(sql, params)
        return row['cnt'] if row else 0
    
    @classmethod
    def raw_execute(cls, sql: str, params: tuple = ()) -> list:
        rows = db.fetchall(sql, params)
        return [dict(row) if row else None for row in rows]
