import asyncio
import sys
import os

# 将项目根目录添加到 python 路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.db_manager import db_manager
from src.aimodel.reply.personality import personality_manager


async def main():
    print("🚀 开始为所有群组重新生成碎片化作息表...")

    groups = await db_manager.get_all_groups()
    if not groups:
        print("⚠️ 数据库中没有找到任何已激活的群组。")
        return

    for group_id in groups:
        print(f"\n[群组: {group_id}] 正在生成...")
        schedule = await personality_manager.generate_daily_schedule(group_id)
        if schedule:
            print(f"✅ 生成成功！共 {len(schedule)} 个时间段。")
        else:
            print(f"❌ 生成失败。")

    print("\n✨ 所有作息表已刷新。你可以运行 python scripts/inspect_schedule.py 查看结果。")


if __name__ == "__main__":
    asyncio.run(main())
