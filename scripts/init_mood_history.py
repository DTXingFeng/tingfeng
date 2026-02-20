import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.db_manager import db_manager


async def main():
    print("正在初始化数据库...")
    await db_manager._ensure_init()
    print("数据库初始化完成！mood_history 表已创建。")


if __name__ == "__main__":
    asyncio.run(main())
