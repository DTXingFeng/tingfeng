import sqlite3
from pathlib import Path

db_path = Path("data/bot_data.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = [row[0] for row in cursor.fetchall()]
print("数据库表列表:")
for table in sorted(tables):
    print(f"  - {table}")

if "mood_history" in tables:
    print("\nmood_history 表已存在！")
    cursor.execute("PRAGMA table_info(mood_history)")
    columns = cursor.fetchall()
    print("mood_history 表结构:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
else:
    print("\nmood_history 表不存在！")

conn.close()
