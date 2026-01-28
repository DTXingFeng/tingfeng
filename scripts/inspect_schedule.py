import sqlite3
import json
import datetime
from pathlib import Path

def inspect_today_schedule():
    db_path = Path("data/bot_data.db")
    if not db_path.exists():
        print("❌ 数据库文件不存在。")
        return

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    print(f"\n--- 📅 听风作息表查询 ({today}) ---")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询今天的所有作息
        cursor.execute("SELECT group_id, schedule_json FROM bot_schedules WHERE date = ?", (today,))
        rows = cursor.fetchall()
        
        if not rows:
            print(f"⚠️ 今天还没有生成任何作息表。")
            print("提示：机器人收到群消息时会自动触发生成，或者等待凌晨定时任务。")
            return

        for group_id, schedule_json in rows:
            schedule = json.loads(schedule_json)
            print(f"\n[群组: {group_id}]")
            print("-" * 40)
            print(f"{'时间段':<15} | {'活动内容':<12} | {'是否发言'}")
            print("-" * 40)
            
            for item in schedule:
                time_range = f"{item.get('start')} - {item.get('end')}"
                activity = item.get('activity')
                can_chat = "✅ 是" if item.get('can_chat') else "❌ 否"
                print(f"{time_range:<15} | {activity:<12} | {can_chat}")
            
        conn.close()
    except Exception as e:
        print(f"❌ 查询出错: {e}")

if __name__ == "__main__":
    inspect_today_schedule()
