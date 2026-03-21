import sqlite3
import threading
from pathlib import Path
from typing import Optional
from contextlib import contextmanager


class DatabaseConnection:
    _instance: Optional['DatabaseConnection'] = None
    _lock = threading.Lock()
    
    def __init__(self, db_path: str = "data.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._ensure_database_dir()
    
    def _ensure_database_dir(self):
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
    
    def get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                isolation_level=None
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    @contextmanager
    def transaction(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor
    
    def execute_many(self, sql: str, params_list: list) -> sqlite3.Cursor:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.executemany(sql, params_list)
        return cursor
    
    def fetchone(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        cursor = self.execute(sql, params)
        return cursor.fetchone()
    
    def fetchall(self, sql: str, params: tuple = ()) -> list:
        cursor = self.execute(sql, params)
        return cursor.fetchall()
    
    def close(self):
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
    
    @classmethod
    def get_instance(cls, db_path: str = "data.db") -> 'DatabaseConnection':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(db_path)
        return cls._instance


db = DatabaseConnection.get_instance()
