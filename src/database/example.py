"""
数据库包使用示例

使用方法：
1. 直接使用 db 执行 SQL
2. 继承 BaseRepository 创建自定义 Repository
"""

from src.database import db, BaseRepository


class UserRepository(BaseRepository):
    table_name = "users"


db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")


id = UserRepository.insert({"name": "张三", "email": "zhangsan@example.com"})
user = UserRepository.get_by_id(id)
users = UserRepository.find_many("name LIKE ?", ("张%",), limit=10)
count = UserRepository.count()
UserRepository.update(id, {"name": "张三更新"})
UserRepository.delete(id)
