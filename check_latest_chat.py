import sqlite3
import sys
from datetime import datetime

db_path = r"e:\python project\tingfengbot\data\bot_data.db"

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 查询最近的聊天记录
    cursor.execute(
        """
        SELECT group_id, msg, timestamp
        FROM chat_history
        WHERE group_id = 472765283
        ORDER BY timestamp DESC
        LIMIT 100
    """
    )

    rows = cursor.fetchall()

    print("=" * 100)
    print("最近100条聊天记录（群472765283）")
    print("=" * 100)

    # 反转顺序，从最早到最新
    for idx, row in enumerate(reversed(rows)):
        group_id, msg, timestamp = row
        # 提取时间部分
        if timestamp:
            time_str = timestamp.split(" ")[1] if " " in timestamp else timestamp
            time_str = time_str.split(".")[0]  # 去掉毫秒
        else:
            time_str = "??"

        # 检查是否是self的消息
        if msg.startswith("self:") or msg.startswith("听风:"):
            print(f"【{idx+1:3d} BOT】{time_str} | {msg}")
        else:
            print(f"      {idx+1:3d}     {time_str} | {msg}")

    print("=" * 100)

    # 特别标记：查找bot的回复
    cursor.execute(
        """
        SELECT msg, timestamp
        FROM chat_history
        WHERE group_id = 472765283
        AND (msg LIKE 'self:%' OR msg LIKE '听风:%')
        ORDER BY timestamp DESC
        LIMIT 20
    """
    )

    bot_replies = cursor.fetchall()
    print("\n\n最近20条bot回复：")
    print("=" * 100)
    for idx, (msg, timestamp) in enumerate(reversed(bot_replies)):
        if timestamp:
            time_str = timestamp.split(" ")[1] if " " in timestamp else timestamp
            time_str = time_str.split(".")[0]
        else:
            time_str = "??"
        # 去掉self:前缀
        clean_msg = msg.replace("self:", "").replace("听风:", "").strip()
        print(f"{idx+1:2d}. [{time_str}] {clean_msg}")

    conn.close()

except Exception as e:
    print(f"错误: {e}", file=sys.stderr)
    import traceback

    traceback.print_exc()
