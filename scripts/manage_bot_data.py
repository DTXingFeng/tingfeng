"""
Bot数据管理工具
用于管理bot的黑话、好感度等数据
使用方式: python scripts/manage_bot_data.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.db_manager import db_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BotDataManager:
    """Bot数据管理器"""

    def __init__(self):
        self.running = True

    def print_menu(self):
        """打印主菜单"""
        print("\n" + "=" * 50)
        print("           Bot数据管理工具")
        print("=" * 50)
        print("1. 黑话管理")
        print("2. 好感度管理")
        print("3. 数据统计")
        print("4. 退出")
        print("=" * 50)

    def print_slang_menu(self):
        """打印黑话管理菜单"""
        print("\n--- 黑话管理 ---")
        print("1. 查看所有黑话")
        print("2. 添加黑话")
        print("3. 更新黑话")
        print("4. 删除黑话")
        print("5. 返回主菜单")

    def print_favorability_menu(self):
        """打印好感度管理菜单"""
        print("\n--- 好感度管理 ---")
        print("1. 查看所有用户好感度")
        print("2. 查看单个用户好感度")
        print("3. 更新用户好感度")
        print("4. 批量更新好感度")
        print("5. 返回主菜单")

    async def get_group_id(self):
        """获取群组ID"""
        while True:
            group_id = input("\n请输入群组ID: ").strip()
            if group_id.isdigit():
                return int(group_id)
            print("无效的群组ID，请输入数字")

    async def slang_management(self):
        """黑话管理"""
        while self.running:
            self.print_slang_menu()
            choice = input("\n请选择操作 (1-5): ").strip()

            if choice == "1":
                await self.view_all_slang()
            elif choice == "2":
                await self.add_slang()
            elif choice == "3":
                await self.update_slang()
            elif choice == "4":
                await self.delete_slang()
            elif choice == "5":
                break
            else:
                print("无效的选择，请重新输入")

    async def view_all_slang(self):
        """查看所有黑话"""
        try:
            group_id = await self.get_group_id()
            print("\n是否筛选阶段？")
            print("0. 全部")
            print("1. 观察中")
            print("2. 验证中")
            print("3. 已采纳")
            print("4. 已废弃")
            stage_choice = input("请选择 (0-4, 默认0): ").strip() or "0"

            stage = int(stage_choice) if stage_choice != "0" else None
            min_freq = input("最小频率 (默认0): ").strip()
            min_freq = int(min_freq) if min_freq.isdigit() else 0

            slang_list = await db_manager.get_slang_candidates(group_id=group_id, min_freq=min_freq, stage=stage)

            if not slang_list:
                print(f"\n群组 {group_id} 中没有找到符合条件的黑话")
                return

            print(f"\n找到 {len(slang_list)} 条黑话:")
            print("-" * 80)
            for i, slang in enumerate(slang_list, 1):
                stage_names = {1: "观察中", 2: "验证中", 3: "已采纳", 4: "已废弃"}
                print(f"\n{i}. {slang['phrase']}")
                print(f"   频率: {slang['frequency']}")
                print(f"   阶段: {stage_names.get(slang['stage'], '未知')}")
                if slang["definition"]:
                    print(f"   定义: {slang['definition']}")
                if slang["context_samples"]:
                    print(f"   示例: {', '.join(slang['context_samples'][:3])}")

        except Exception as e:
            logger.error(f"查看黑话失败: {e}", exc_info=True)
            print(f"错误: {e}")

    async def add_slang(self):
        """添加黑话"""
        try:
            group_id = await self.get_group_id()
            phrase = input("请输入黑话短语: ").strip()

            if not phrase:
                print("黑话短语不能为空")
                return

            print("\n可选信息 (直接回车跳过):")
            definition = input("定义: ").strip() or None

            freq_input = input("频率 (默认1): ").strip()
            frequency_delta = int(freq_input) if freq_input.isdigit() else 1

            print("\n阶段选择:")
            print("1. 观察中")
            print("2. 验证中")
            print("3. 已采纳")
            print("4. 已废弃")
            stage_input = input("请选择阶段 (1-4, 默认1): ").strip() or "1"
            stage = int(stage_input) if stage_input.isdigit() else 1

            context_input = input("上下文示例 (多个用逗号分隔): ").strip()
            context_samples = [s.strip() for s in context_input.split(",")] if context_input else None

            await db_manager.update_slang_candidate(
                group_id=group_id,
                phrase=phrase,
                delta_freq=frequency_delta,
                stage=stage,
                definition=definition,
                context_samples=context_samples,
            )

            print(f"\n✓ 黑话 '{phrase}' 添加成功！")

        except Exception as e:
            logger.error(f"添加黑话失败: {e}", exc_info=True)
            print(f"错误: {e}")

    async def update_slang(self):
        """更新黑话"""
        try:
            group_id = await self.get_group_id()
            phrase = input("请输入要更新的黑话短语: ").strip()

            if not phrase:
                print("黑话短语不能为空")
                return

            print("\n要更新的信息 (直接回车保持不变):")
            definition = input("新定义: ").strip() or None

            stage_input = input("新阶段 (1-4): ").strip()
            new_stage = int(stage_input) if stage_input.isdigit() else None

            if not definition and new_stage is None:
                print("至少需要提供一个更新项")
                return

            await db_manager.update_slang_candidate(
                group_id=group_id, phrase=phrase, stage=new_stage, definition=definition, delta_freq=0
            )

            print(f"\n✓ 黑话 '{phrase}' 更新成功！")

        except Exception as e:
            logger.error(f"更新黑话失败: {e}", exc_info=True)
            print(f"错误: {e}")

    async def delete_slang(self):
        """删除黑话"""
        try:
            group_id = await self.get_group_id()
            phrase = input("请输入要删除的黑话短语: ").strip()

            if not phrase:
                print("黑话短语不能为空")
                return

            confirm = input(f"\n确认删除黑话 '{phrase}'？(y/n): ").strip().lower()
            if confirm != "y":
                print("已取消")
                return

            async with await db_manager._get_connection() as conn:
                cursor = await conn.cursor()
                await cursor.execute(
                    "DELETE FROM slang_candidates WHERE group_id = ? AND phrase = ?", (group_id, phrase)
                )
                await conn.commit()

            print(f"\n✓ 黑话 '{phrase}' 删除成功！")

        except Exception as e:
            logger.error(f"删除黑话失败: {e}", exc_info=True)
            print(f"错误: {e}")

    async def favorability_management(self):
        """好感度管理"""
        while self.running:
            self.print_favorability_menu()
            choice = input("\n请选择操作 (1-5): ").strip()

            if choice == "1":
                await self.view_all_favorability()
            elif choice == "2":
                await self.view_user_favorability()
            elif choice == "3":
                await self.update_user_favorability()
            elif choice == "4":
                await self.batch_update_favorability()
            elif choice == "5":
                break
            else:
                print("无效的选择，请重新输入")

    async def view_all_favorability(self):
        """查看所有用户好感度"""
        try:
            group_id = await self.get_group_id()

            min_fav = input("最小好感度 (0-100, 默认0): ").strip()
            min_fav = int(min_fav) if min_fav.isdigit() else 0

            max_fav = input("最大好感度 (0-100, 默认100): ").strip()
            max_fav = int(max_fav) if max_fav.isdigit() else 100

            status_filter = input("关系状态筛选 (直接回车跳过): ").strip() or None

            async with await db_manager._get_connection() as conn:
                cursor = await conn.cursor()

                query = "SELECT user_name, favorability, status FROM user_relationships WHERE group_id = ? AND favorability BETWEEN ? AND ?"
                params = [group_id, min_fav, max_fav]

                if status_filter:
                    query += " AND status = ?"
                    params.append(status_filter)

                query += " ORDER BY favorability DESC"

                await cursor.execute(query, tuple(params))
                rows = await cursor.fetchall()

                if not rows:
                    print(f"\n群组 {group_id} 中没有找到符合条件的用户")
                    return

                print(f"\n找到 {len(rows)} 个用户:")
                print("-" * 60)
                for i, (user_name, favorability, status) in enumerate(rows, 1):
                    print(f"{i:2d}. {user_name:15s} - 好感度: {favorability:3d} ({status})")

        except Exception as e:
            logger.error(f"查看好感度失败: {e}", exc_info=True)
            print(f"错误: {e}")

    async def view_user_favorability(self):
        """查看单个用户好感度"""
        try:
            group_id = await self.get_group_id()
            user_name = input("请输入用户名: ").strip()

            if not user_name:
                print("用户名不能为空")
                return

            relationship = await db_manager.get_user_relationship(group_id, user_name)

            print(f"\n用户: {user_name}")
            print(f"好感度: {relationship['favorability']}")
            print(f"关系状态: {relationship['status']}")

        except Exception as e:
            logger.error(f"查看用户好感度失败: {e}", exc_info=True)
            print(f"错误: {e}")

    async def update_user_favorability(self):
        """更新用户好感度"""
        try:
            group_id = await self.get_group_id()
            user_name = input("请输入用户名: ").strip()

            if not user_name:
                print("用户名不能为空")
                return

            delta_input = input("好感度变化量 (正数增加，负数减少，默认0): ").strip()
            delta = int(delta_input) if delta_input.lstrip("-").isdigit() else 0

            new_status = input("新关系状态 (直接回车自动推断): ").strip() or None

            result = await db_manager.update_user_relationship(
                group_id=group_id, user_name=user_name, delta_favorability=delta, new_status=new_status
            )

            print(f"\n✓ 用户 '{user_name}' 好感度更新成功！")
            print(f"新好感度: {result['favorability']}")
            print(f"新状态: {result['status']}")

        except Exception as e:
            logger.error(f"更新好感度失败: {e}", exc_info=True)
            print(f"错误: {e}")

    async def batch_update_favorability(self):
        """批量更新好感度"""
        try:
            group_id = await self.get_group_id()

            print("\n批量更新用户好感度")
            print("格式: 用户名,变化量 (每行一个)")
            print("例如: 张三,5")
            print("输入空行结束\n")

            updates = []
            while True:
                line = input(f"第 {len(updates) + 1} 个用户: ").strip()
                if not line:
                    break

                parts = line.split(",")
                if len(parts) != 2:
                    print("格式错误，请重新输入")
                    continue

                user_name = parts[0].strip()
                delta = parts[1].strip()

                if not delta.lstrip("-").isdigit():
                    print(f"变化量必须是数字: {delta}")
                    continue

                updates.append({"user_name": user_name, "delta": int(delta)})

            if not updates:
                print("没有输入任何更新")
                return

            for update in updates:
                await db_manager.update_user_relationship(
                    group_id=group_id,
                    user_name=update["user_name"],
                    delta_favorability=update["delta"],
                )

            print(f"\n✓ 成功更新 {len(updates)} 个用户的好感度！")

        except Exception as e:
            logger.error(f"批量更新好感度失败: {e}", exc_info=True)
            print(f"错误: {e}")

    async def view_statistics(self):
        """查看数据统计"""
        try:
            group_id = await self.get_group_id()

            global_stats = await db_manager.get_db_stats()

            async with await db_manager._get_connection() as conn:
                cursor = await conn.cursor()

                await cursor.execute("SELECT COUNT(*) FROM user_relationships WHERE group_id = ?", (group_id,))
                user_count = (await cursor.fetchone())[0]

                await cursor.execute("SELECT COUNT(*) FROM slang_candidates WHERE group_id = ?", (group_id,))
                slang_count = (await cursor.fetchone())[0]

                await cursor.execute("SELECT COUNT(*) FROM user_memories WHERE group_id = ?", (group_id,))
                memory_count = (await cursor.fetchone())[0]

                await cursor.execute(
                    "SELECT AVG(favorability), MAX(favorability), MIN(favorability) FROM user_relationships WHERE group_id = ?",
                    (group_id,),
                )
                avg_fav, max_fav, min_fav = await cursor.fetchone()

            print("\n" + "=" * 50)
            print(f"群组 {group_id} 数据统计")
            print("=" * 50)
            print(f"\n群组数据:")
            print(f"  用户数: {user_count}")
            print(f"  黑话数: {slang_count}")
            print(f"  记忆数: {memory_count}")
            print(f"  平均好感度: {round(avg_fav, 2) if avg_fav else 0}")
            print(f"  最高好感度: {max_fav if max_fav else 0}")
            print(f"  最低好感度: {min_fav if min_fav else 0}")

            print(f"\n全局数据:")
            for key, value in global_stats.items():
                print(f"  {key}: {value}")

        except Exception as e:
            logger.error(f"查看数据统计失败: {e}", exc_info=True)
            print(f"错误: {e}")

    async def run(self):
        """运行主程序"""
        while self.running:
            self.print_menu()
            choice = input("\n请选择功能 (1-4): ").strip()

            if choice == "1":
                await self.slang_management()
            elif choice == "2":
                await self.favorability_management()
            elif choice == "3":
                await self.view_statistics()
            elif choice == "4":
                print("\n再见！")
                break
            else:
                print("无效的选择，请重新输入")


async def main():
    """主函数"""
    manager = BotDataManager()
    await manager.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n程序已中断")
    except Exception as e:
        logger.error(f"程序异常: {e}", exc_info=True)
        print(f"\n程序异常: {e}")
