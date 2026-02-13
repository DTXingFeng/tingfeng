import sqlite3
from pathlib import Path


def migrate_db():
    db_path = Path("data/bot_data.db")
    if not db_path.exists():
        print("数据库文件不存在，无需迁移。")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查 is_processed 列是否存在
        cursor.execute("PRAGMA table_info(chat_history)")
        columns = [row[1] for row in cursor.fetchall()]

        if "is_processed" not in columns:
            print("正在为 chat_history 表添加 is_processed 列...")
            cursor.execute("ALTER TABLE chat_history ADD COLUMN is_processed INTEGER DEFAULT 0")
            conn.commit()
            print("迁移成功！")
        else:
            print("is_processed 列已存在，无需迁移。")

        conn.close()
    except Exception as e:
        print(f"迁移失败: {e}")


if __name__ == "__main__":
    migrate_db()
