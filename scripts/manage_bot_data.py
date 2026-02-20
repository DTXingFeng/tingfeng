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
        print("5. 批量操作")
        print("6. 快速清理")
        print("7. 返回主菜单")

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
            choice = input("\n请选择操作 (1-7): ").strip()

            if choice == "1":
                await self.view_all_slang()
            elif choice == "2":
                await self.add_slang()
            elif choice == "3":
                await self.update_slang()
            elif choice == "4":
                await self.delete_slang()
            elif choice == "5":
                await self.slang_batch_operations()
            elif choice == "6":
                await self.quick_clean_slang()
            elif choice == "7":
                break
            else:
                print("无效的选择，请重新输入")

    async def view_all_slang(self):
        """查看所有黑话"""
        try:
            group_id = await self.get_group_id()
            print("\n显示模式：")
            print("1. 简洁列表（只显示黑话和频率）")
            print("2. 详细信息（显示定义和示例）")
            print("3. 统计概览")
            view_choice = input("请选择 (1-3, 默认1): ").strip() or "1"

            if view_choice == "3":
                await self.view_slang_statistics(group_id)
                return

            stage = None
            min_freq = 0

            if view_choice in ["1", "2"]:
                print("\n是否筛选阶段？")
                print("0. 全部")
                print("1. 观察中")
                print("2. 验证中")
                print("3. 已采纳")
                print("4. 已废弃")
                stage_choice = input("请选择 (0-4, 默认0): ").strip() or "0"
                stage = int(stage_choice) if stage_choice != "0" else None

                min_freq_input = input("最小频率 (默认0): ").strip()
                min_freq = int(min_freq_input) if min_freq_input.isdigit() else 0

            slang_list = await db_manager.get_slang_candidates(group_id=group_id, min_freq=min_freq, stage=stage)

            if not slang_list:
                print(f"\n群组 {group_id} 中没有找到符合条件的黑话")
                return

            stage_names = {1: "观察中", 2: "验证中", 3: "已采纳", 4: "已废弃"}

            if view_choice == "1":
                print(f"\n找到 {len(slang_list)} 条黑话:")
                print("-" * 60)
                for i, slang in enumerate(slang_list, 1):
                    stage_tag = stage_names.get(slang["stage"], "未知")
                    print(f"{i:3d}. [{stage_tag}] 频率{slang['frequency']:3d} - {slang['phrase']}")

            elif view_choice == "2":
                print(f"\n找到 {len(slang_list)} 条黑话:")
                print("-" * 80)
                for i, slang in enumerate(slang_list, 1):
                    print(f"\n{i}. {slang['phrase']}")
                    print(f"   频率: {slang['frequency']}")
                    print(f"   阶段: {stage_names.get(slang['stage'], '未知')}")
                    if slang["definition"]:
                        def_text = (
                            slang["definition"][:50] + "..." if len(slang["definition"]) > 50 else slang["definition"]
                        )
                        print(f"   定义: {def_text}")
                    if slang["context_samples"]:
                        print(f"   示例数: {len(slang['context_samples'])}")

        except Exception as e:
            logger.error(f"查看黑话失败: {e}", exc_info=True)
            print(f"错误: {e}")

    async def view_slang_statistics(self, group_id: int):
        """查看黑话统计概览"""
        try:
            async with await db_manager._get_connection() as conn:
                cursor = await conn.cursor()

                await cursor.execute("SELECT COUNT(*) FROM slang_candidates WHERE group_id = ?", (group_id,))
                total = (await cursor.fetchone())[0]

                if total == 0:
                    print(f"\n群组 {group_id} 没有黑话数据")
                    return

                stage_names = {1: "观察中", 2: "验证中", 3: "已采纳", 4: "已废弃"}

                print("\n" + "=" * 50)
                print(f"       群组 {group_id} 黑话统计")
                print("=" * 50)

                for stage in [1, 2, 3, 4]:
                    await cursor.execute(
                        "SELECT COUNT(*) FROM slang_candidates WHERE group_id = ? AND stage = ?", (group_id, stage)
                    )
                    count = (await cursor.fetchone())[0]
                    print(f"  {stage_names[stage]}: {count} 条")

                await cursor.execute(
                    "SELECT AVG(frequency), MAX(frequency), MIN(frequency) FROM slang_candidates WHERE group_id = ?",
                    (group_id,),
                )
                avg_freq, max_freq, min_freq = await cursor.fetchone()

                print(f"\n  平均频率: {round(avg_freq, 1) if avg_freq else 0}")
                print(f"  最高频率: {max_freq if max_freq else 0}")
                print(f"  最低频率: {min_freq if min_freq else 0}")

                await cursor.execute(
                    "SELECT phrase, frequency FROM slang_candidates WHERE group_id = ? ORDER BY frequency DESC LIMIT 5",
                    (group_id,),
                )
                top_slangs = await cursor.fetchall()

                if top_slangs:
                    print(f"\n  频率最高的 5 个黑话:")
                    for i, (phrase, freq) in enumerate(top_slangs, 1):
                        print(f"    {i}. {phrase} (频率: {freq})")

                print("=" * 50)

        except Exception as e:
            logger.error(f"查看统计失败: {e}", exc_info=True)
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

    async def slang_batch_operations(self):
        """批量操作黑话"""
        while self.running:
            print("\n--- 批量操作 ---")
            print("1. 批量删除低频黑话")
            print("2. 批量删除指定阶段黑话")
            print("3. 批量调整阶段")
            print("4. 批量调整频率")
            print("5. 返回")
            choice = input("\n请选择操作 (1-5): ").strip()

            if choice == "1":
                await self.batch_delete_by_frequency()
            elif choice == "2":
                await self.batch_delete_by_stage()
            elif choice == "3":
                await self.batch_update_stage()
            elif choice == "4":
                await self.batch_update_frequency()
            elif choice == "5":
                break
            else:
                print("无效的选择，请重新输入")

    async def batch_delete_by_frequency(self):
        """批量删除低频黑话"""
        try:
            group_id = await self.get_group_id()

            print("\n批量删除低频黑话")
            min_freq = input("删除频率低于多少的黑话？(默认5): ").strip()
            min_freq = int(min_freq) if min_freq.isdigit() else 5

            print(f"\n即将删除频率 < {min_freq} 的所有黑话")

            async with await db_manager._get_connection() as conn:
                cursor = await conn.cursor()

                await cursor.execute(
                    "SELECT COUNT(*) FROM slang_candidates WHERE group_id = ? AND frequency < ?", (group_id, min_freq)
                )
                count = (await cursor.fetchone())[0]

                if count == 0:
                    print(f"\n没有找到频率 < {min_freq} 的黑话")
                    return

                print(f"将删除 {count} 条黑话")
                confirm = input("\n确认删除？(y/n): ").strip().lower()
                if confirm != "y":
                    print("已取消")
                    return

                await cursor.execute(
                    "DELETE FROM slang_candidates WHERE group_id = ? AND frequency < ?", (group_id, min_freq)
                )
                await conn.commit()

            print(f"\n✓ 成功删除 {count} 条低频黑话！")

        except Exception as e:
            logger.error(f"批量删除失败: {e}", exc_info=True)
            print(f"错误: {e}")

    async def batch_delete_by_stage(self):
        """批量删除指定阶段黑话"""
        try:
            group_id = await self.get_group_id()

            print("\n批量删除指定阶段黑话")
            print("1. 观察中 (stage=1)")
            print("2. 验证中 (stage=2)")
            print("3. 已采纳 (stage=3)")
            print("4. 已废弃 (stage=4)")
            stage_input = input("请选择要删除的阶段 (1-4): ").strip()

            if not stage_input.isdigit() or int(stage_input) < 1 or int(stage_input) > 4:
                print("无效的阶段")
                return

            stage = int(stage_input)
            stage_names = {1: "观察中", 2: "验证中", 3: "已采纳", 4: "已废弃"}

            async with await db_manager._get_connection() as conn:
                cursor = await conn.cursor()

                await cursor.execute(
                    "SELECT COUNT(*) FROM slang_candidates WHERE group_id = ? AND stage = ?", (group_id, stage)
                )
                count = (await cursor.fetchone())[0]

                if count == 0:
                    print(f"\n没有找到阶段为 '{stage_names[stage]}' 的黑话")
                    return

                print(f"\n将删除 {count} 条 '{stage_names[stage]}' 的黑话")
                confirm = input("\n确认删除？(y/n): ").strip().lower()
                if confirm != "y":
                    print("已取消")
                    return

                await cursor.execute("DELETE FROM slang_candidates WHERE group_id = ? AND stage = ?", (group_id, stage))
                await conn.commit()

            print(f"\n✓ 成功删除 {count} 条 '{stage_names[stage]}' 的黑话！")

        except Exception as e:
            logger.error(f"批量删除失败: {e}", exc_info=True)
            print(f"错误: {e}")

    async def batch_update_stage(self):
        """批量调整黑话阶段"""
        try:
            group_id = await self.get_group_id()

            print("\n批量调整黑话阶段")
            print("源阶段:")
            source_input = input("从哪个阶段？(1-4, 直接回车跳过): ").strip()
            source_stage = int(source_input) if source_input.isdigit() else None

            print("\n目标阶段:")
            print("1. 观察中 (stage=1)")
            print("2. 验证中 (stage=2)")
            print("3. 已采纳 (stage=3)")
            print("4. 已废弃 (stage=4)")
            target_input = input("调整到哪个阶段？(1-4): ").strip()

            if not target_input.isdigit() or int(target_input) < 1 or int(target_input) > 4:
                print("无效的阶段")
                return

            target_stage = int(target_input)

            async with await db_manager._get_connection() as conn:
                cursor = await conn.cursor()

                if source_stage:
                    await cursor.execute(
                        "SELECT COUNT(*) FROM slang_candidates WHERE group_id = ? AND stage = ?",
                        (group_id, source_stage),
                    )
                    count = (await cursor.fetchone())[0]

                    if count == 0:
                        print(f"\n没有找到符合条件的黑话")
                        return

                    print(f"\n将 {count} 条黑话从阶段 {source_stage} 调整到阶段 {target_stage}")
                    confirm = input("\n确认调整？(y/n): ").strip().lower()
                    if confirm != "y":
                        print("已取消")
                        return

                    await cursor.execute(
                        "UPDATE slang_candidates SET stage = ? WHERE group_id = ? AND stage = ?",
                        (target_stage, group_id, source_stage),
                    )
                else:
                    await cursor.execute("SELECT COUNT(*) FROM slang_candidates WHERE group_id = ?", (group_id,))
                    count = (await cursor.fetchone())[0]

                    if count == 0:
                        print(f"\n没有找到符合条件的黑话")
                        return

                    print(f"\n将群组 {group_id} 的所有 {count} 条黑话调整到阶段 {target_stage}")
                    confirm = input("\n确认调整？(y/n): ").strip().lower()
                    if confirm != "y":
                        print("已取消")
                        return

                    await cursor.execute(
                        "UPDATE slang_candidates SET stage = ? WHERE group_id = ?", (target_stage, group_id)
                    )

                await conn.commit()

            print(f"\n✓ 成功调整黑话阶段！")

        except Exception as e:
            logger.error(f"批量调整失败: {e}", exc_info=True)
            print(f"错误: {e}")

    async def batch_update_frequency(self):
        """批量调整黑话频率"""
        try:
            group_id = await self.get_group_id()

            print("\n批量调整黑话频率")
            print("1. 增加频率")
            print("2. 减少频率")
            print("3. 重置频率")
            choice = input("请选择操作 (1-3): ").strip()

            if choice == "1":
                delta = input("增加多少频率？(例如: 5): ").strip()
                if not delta.isdigit():
                    print("无效的频率值")
                    return
                delta = int(delta)

                async with await db_manager._get_connection() as conn:
                    cursor = await conn.cursor()
                    await cursor.execute(
                        "UPDATE slang_candidates SET frequency = frequency + ? WHERE group_id = ?", (delta, group_id)
                    )
                    await conn.commit()

                print(f"\n✓ 所有黑话频率增加 {delta}！")

            elif choice == "2":
                delta = input("减少多少频率？(例如: 5): ").strip()
                if not delta.isdigit():
                    print("无效的频率值")
                    return
                delta = int(delta)

                async with await db_manager._get_connection() as conn:
                    cursor = await conn.cursor()
                    await cursor.execute(
                        "UPDATE slang_candidates SET frequency = MAX(0, frequency - ?) WHERE group_id = ?",
                        (delta, group_id),
                    )
                    await conn.commit()

                print(f"\n✓ 所有黑话频率减少 {delta}！")

            elif choice == "3":
                new_freq = input("重置为多少频率？(例如: 1): ").strip()
                if not new_freq.isdigit():
                    print("无效的频率值")
                    return
                new_freq = int(new_freq)

                async with await db_manager._get_connection() as conn:
                    cursor = await conn.cursor()
                    await cursor.execute(
                        "UPDATE slang_candidates SET frequency = ? WHERE group_id = ?", (new_freq, group_id)
                    )
                    await conn.commit()

                print(f"\n✓ 所有黑话频率重置为 {new_freq}！")

            else:
                print("无效的选择")

        except Exception as e:
            logger.error(f"批量调整失败: {e}", exc_info=True)
            print(f"错误: {e}")

    async def quick_clean_slang(self):
        """快速清理黑话 - 智能清理低质量黑话"""
        try:
            group_id = await self.get_group_id()

            print("\n" + "=" * 50)
            print("           快速清理黑话")
            print("=" * 50)
            print("\n将智能清理以下类型的黑话:")
            print("  1. 频率 < 5 的低频黑话")
            print("  2. 阶段为 '观察中' (stage=1) 的黑话")
            print("  3. 定义少于 15 字的黑话")
            print("  4. 定义包含模糊词的黑话")
            print("\n建议定期使用此功能清理垃圾黑话")
            print("=" * 50)

            confirm = input("\n确认开始清理？(y/n): ").strip().lower()
            if confirm != "y":
                print("已取消")
                return

            async with await db_manager._get_connection() as conn:
                cursor = await conn.cursor()

                total_deleted = 0

                # 1. 删除频率 < 5 的黑话
                await cursor.execute(
                    "SELECT COUNT(*) FROM slang_candidates WHERE group_id = ? AND frequency < 5", (group_id,)
                )
                count = (await cursor.fetchone())[0]
                if count > 0:
                    await cursor.execute(
                        "DELETE FROM slang_candidates WHERE group_id = ? AND frequency < 5", (group_id,)
                    )
                    print(f"\n✓ 删除频率 < 5 的黑话: {count} 条")
                    total_deleted += count

                # 2. 删除观察中的黑话（stage=1）
                await cursor.execute(
                    "SELECT COUNT(*) FROM slang_candidates WHERE group_id = ? AND stage = 1", (group_id,)
                )
                count = (await cursor.fetchone())[0]
                if count > 0:
                    await cursor.execute("DELETE FROM slang_candidates WHERE group_id = ? AND stage = 1", (group_id,))
                    print(f"✓ 删除观察中的黑话: {count} 条")
                    total_deleted += count

                # 3. 删除定义少于 15 字的黑话
                await cursor.execute(
                    "SELECT COUNT(*) FROM slang_candidates WHERE group_id = ? AND LENGTH(definition) < 15", (group_id,)
                )
                count = (await cursor.fetchone())[0]
                if count > 0:
                    await cursor.execute(
                        "DELETE FROM slang_candidates WHERE group_id = ? AND LENGTH(definition) < 15", (group_id,)
                    )
                    print(f"✓ 删除定义少于 15 字的黑话: {count} 条")
                    total_deleted += count

                # 4. 删除定义包含模糊词的黑话
                uncertain_keywords = ["可能", "或许", "应该", "需要结合", "具体含义", "未知", "不清楚", "猜测", "大概"]
                for keyword in uncertain_keywords:
                    await cursor.execute(
                        "DELETE FROM slang_candidates WHERE group_id = ? AND definition LIKE ?",
                        (group_id, f"%{keyword}%"),
                    )
                    count = cursor.rowcount
                    if count > 0:
                        print(f"✓ 删除包含 '{keyword}' 的黑话: {count} 条")
                        total_deleted += count

                await conn.commit()

            print(f"\n" + "=" * 50)
            print(f"清理完成！共删除 {total_deleted} 条黑话")
            print("=" * 50)

        except Exception as e:
            logger.error(f"快速清理失败: {e}", exc_info=True)
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
