"""
数据库迁移脚本：添加缺失的 last_vibe_update 字段

执行方式：
    python scripts/migrate_add_missing_columns.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.db_manager import db_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def migrate():
    """执行数据库迁移"""
    try:
        # 确保数据库已初始化
        await db_manager._ensure_init()

        async with await db_manager._get_connection() as conn:
            cursor = await conn.cursor()

            # 检查 last_vibe_update 字段是否存在
            await cursor.execute("PRAGMA table_info(bot_personality)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

            if "last_vibe_update" not in column_names:
                logger.info("检测到缺失 last_vibe_update 字段，正在添加...")
                await cursor.execute("ALTER TABLE bot_personality ADD COLUMN last_vibe_update DATETIME")
                logger.success("成功添加 last_vibe_update 字段")
            else:
                logger.info("last_vibe_update 字段已存在，跳过")

            await conn.commit()

        logger.success("数据库迁移完成")
        return True

    except Exception as e:
        logger.error(f"数据库迁移失败: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(migrate())
    sys.exit(0 if success else 1)
