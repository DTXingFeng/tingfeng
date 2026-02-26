import sqlite3
from pathlib import Path


def check_db_structure():
    db_path = Path("data/bot_data.db")
    if not db_path.exists():
        print("数据库文件不存在")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=" * 60)
    print("bot_personality 表结构:")
    print("=" * 60)
    cursor.execute("PRAGMA table_info(bot_personality)")
    columns = cursor.fetchall()
    if columns:
        for row in columns:
            print(f"  - {row[1]:20s} {row[2]:15s} (默认值: {row[4]})")
    else:
        print("  表不存在！")

    print("\n" + "=" * 60)
    print("检查 last_vibe_update 列是否存在:")
    print("=" * 60)
    column_names = [row[1] for row in columns]
    if "last_vibe_update" in column_names:
        print("  ✓ last_vibe_update 列存在")
    else:
        print("  ✗ last_vibe_update 列不存在！")

    conn.close()


if __name__ == "__main__":
    check_db_structure()
