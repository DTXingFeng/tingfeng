"""
清空表情包缓存

表情包缓存中存储的 URL 可能会过期，导致发送失败。
使用此脚本清空缓存后，bot 会重新学习群内的表情包。
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.db_manager import db_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)

def main():
    print("=" * 60)
    print("表情包缓存清理工具")
    print("=" * 60)
    print()
    print("⚠️  警告：此操作将清空所有已学习的表情包！")
    print("清空后，bot 需要重新学习群内的表情包。")
    print()
    
    # 查询当前表情包数量
    import sqlite3
    db_path = "data/bot_data.db"
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT tag, COUNT(*) FROM stickers GROUP BY tag ORDER BY COUNT(*) DESC")
        results = cursor.fetchall()
        
        if results:
            print("当前表情包统计：")
            total = 0
            for tag, count in results:
                print(f"  - {tag}: {count} 个")
                total += count
            print(f"  总计: {total} 个")
            print()
        
        conn.close()
    
    confirm = input("确定要清空吗？(输入 'yes' 确认): ")
    
    if confirm.lower() == 'yes':
        count = db_manager.clear_all_stickers()
        logger.info(f"已清空 {count} 个表情包缓存")
        print(f"✅ 已清空 {count} 个表情包缓存")
        print()
        print("💡 提示：重启 bot 后，它会重新学习群内的表情包。")
    else:
        print("❌ 操作已取消")
    
    print()

if __name__ == "__main__":
    main()
