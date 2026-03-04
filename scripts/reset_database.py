"""
数据库重置脚本：删除旧数据库并创建新的数据库结构

使用方法：
    python scripts/reset_database.py

注意：
    - 此操作将永久删除所有数据，无法恢复！
    - 执行前会要求确认
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.db_manager import db_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)


def confirm_reset() -> bool:
    """确认是否要重置数据库"""
    print("\n" + "!" * 60)
    print("警告：此操作将永久删除所有数据库数据，无法恢复！")
    print("!" * 60)
    print("\n将要删除的内容：")
    print("  - 所有聊天记录")
    print("  - 用户印象和记忆")
    print("  - 群组氛围和风格模式")
    print("  - 黑话库和知识图谱")
    print("  - 所有其他数据")
    print("\n注意：新的数据库将包含修复后的完整表结构")

    confirm = input("\n确认要重置数据库？(输入 'YES' 确认): ").strip()
    return confirm == "YES"


async def reset_database():
    """重置数据库"""
    if not confirm_reset():
        print("\n已取消操作")
        return False

    try:
        db_path = db_manager.db_path

        # 检查数据库文件是否存在
        if not db_path.exists():
            print(f"\n数据库文件不存在: {db_path}")
            print("将创建新的数据库...")

        # 删除旧数据库文件
        if db_path.exists():
            print(f"\n正在删除数据库文件: {db_path}")
            db_path.unlink()
            print("✓ 数据库文件已删除")

        # 重置初始化标志，强制重新初始化
        db_manager._init_done = False

        # 重新初始化数据库（创建新表）
        print("\n正在创建新的数据库结构...")
        await db_manager._ensure_init()
        print("✓ 数据库初始化完成")

        # 验证表结构
        async with await db_manager._get_connection() as conn:
            cursor = await conn.cursor()

            await cursor.execute("PRAGMA table_info(bot_personality)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

            print("\n验证 bot_personality 表结构:")
            if "last_vibe_update" in column_names:
                print("  ✓ last_vibe_update 字段存在")
            else:
                print("  ✗ last_vibe_update 字段缺失（不应该发生）")
                return False

            print(f"\n表结构验证完成，共 {len(column_names)} 个字段")

        print("\n" + "=" * 60)
        print("数据库重置成功！")
        print("=" * 60)
        print("\n提示：")
        print("  1. 所有数据已清空，机器人将重新学习")
        print("  2. 可以通过 WebUI 或命令行工具重新添加数据")
        print("  3. 建议运行群组初始化来激活基本功能")

        return True

    except Exception as e:
        logger.error(f"数据库重置失败: {e}", exc_info=True)
        print(f"\n✗ 错误: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(reset_database())
    sys.exit(0 if success else 1)
