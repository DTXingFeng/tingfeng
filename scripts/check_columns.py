import sqlite3
from pathlib import Path

db_path = Path("data/bot_data.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(chat_history)")
columns = cursor.fetchall()

print("chat_history 表结构:")
for col in columns:
    print(f"  {col[1]:<15} {col[2]:<10} DEFAULT: {col[4]}")

conn.close()
