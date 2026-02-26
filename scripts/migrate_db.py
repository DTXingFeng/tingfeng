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

        # 1. 检查并添加 chat_history.is_processed 列
        cursor.execute("PRAGMA table_info(chat_history)")
        columns = [row[1] for row in cursor.fetchall()]

        if "is_processed" not in columns:
            print("正在为 chat_history 表添加 is_processed 列...")
            cursor.execute("ALTER TABLE chat_history ADD COLUMN is_processed INTEGER DEFAULT 0")
            conn.commit()
            print("✓ chat_history.is_processed 列添加成功！")
        else:
            print("○ chat_history.is_processed 列已存在，跳过。")

        # 2. 检查并添加 bot_personality.last_vibe_update 列
        cursor.execute("PRAGMA table_info(bot_personality)")
        personality_columns = [row[1] for row in cursor.fetchall()]

        if "last_vibe_update" not in personality_columns:
            print("正在为 bot_personality 表添加 last_vibe_update 列...")
            cursor.execute("ALTER TABLE bot_personality ADD COLUMN last_vibe_update DATETIME")
            conn.commit()
            print("✓ bot_personality.last_vibe_update 列添加成功！")
        else:
            print("○ bot_personality.last_vibe_update 列已存在，跳过。")

        conn.close()
        print("\n数据库迁移完成！")

    except Exception as e:
        print(f"迁移失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    migrate_db()
