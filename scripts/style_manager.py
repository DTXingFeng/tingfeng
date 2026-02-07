"""
Bot 风格管理工具
用于管理 bot 学习到的说话风格模式
使用方式: python scripts/style_manager.py
"""

import asyncio
import sys
from pathlib import Path
import sqlite3

sys.path.insert(0, str(Path(__file__).parent.parent))


class StyleManager:
    """Bot 风格管理器 - 交互式 CLI 工具"""

    def __init__(self, db_path: str = "data/bot_data.db"):
        self.db_path = db_path
        self.running = True

    def print_menu(self):
        """打印主菜单"""
        print("\n" + "=" * 60)
        print("                  Bot 风格管理工具")
        print("=" * 60)
        print("1. 查看风格模式")
        print("2. 搜索风格模式")
        print("3. 添加风格模式")
        print("4. 编辑风格模式")
        print("5. 删除风格模式")
        print("6. 批量操作")
        print("7. 数据统计")
        print("8. 清空所有风格 (危险!)")
        print("0. 退出")
        print("=" * 60)

    def print_view_menu(self):
        """打印查看菜单"""
        print("\n--- 查看风格模式 ---")
        print("1. 查看指定群组的所有风格")
        print("2. 查看权重最高的风格")
        print("3. 查看权重最低的风格")
        print("4. 按情境筛选")
        print("5. 返回主菜单")

    def list_all_groups(self):
        """列出所有群组"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT DISTINCT group_id 
                   FROM style_patterns 
                   ORDER BY group_id"""
            )
            return [row[0] for row in cursor.fetchall()]

    def get_group_id(self, allow_all=True):
        """
        获取群组 ID - 通过列表选择
        
        Args:
            allow_all: 是否允许选择"所有群组"
        """
        groups = self.list_all_groups()
        
        if not groups:
            print("\n没有找到任何群组")
            return None
        
        print("\n" + "=" * 50)
        print("请选择群组:")
        print("=" * 50)
        
        for i, group_id in enumerate(groups, 1):
            print(f"{i}. 群组 {group_id}")
        
        if allow_all:
            print(f"0. 所有群组")
        
        while True:
            choice = input(f"\n请输入选项 (0-{len(groups)}): ").strip()
            
            if allow_all and choice == "0":
                return None
            
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(groups):
                    return groups[idx]
            
            print(f"无效的选项，请输入 0-{len(groups)}")

    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def view_styles(self):
        """查看风格模式"""
        while self.running:
            self.print_view_menu()
            choice = input("\n请选择操作 (1-5): ").strip()

            if choice == "1":
                self.view_all_styles()
            elif choice == "2":
                self.view_top_styles()
            elif choice == "3":
                self.view_bottom_styles()
            elif choice == "4":
                self.view_by_context()
            elif choice == "5":
                break
            else:
                print("无效的选择，请重新输入")

    def view_all_styles(self):
        """查看所有风格"""
        try:
            group_id = self.get_group_id()

            with self.get_connection() as conn:
                cursor = conn.cursor()

                if group_id:
                    cursor.execute(
                        """SELECT id, context, style_desc, weight, updated_at 
                           FROM style_patterns 
                           WHERE group_id = ? 
                           ORDER BY weight DESC""",
                        (group_id,)
                    )
                else:
                    cursor.execute(
                        """SELECT group_id, id, context, style_desc, weight, updated_at 
                           FROM style_patterns 
                           ORDER BY group_id, weight DESC"""
                    )

                rows = cursor.fetchall()

                if not rows:
                    print(f"\n没有找到风格模式")
                    return

                print(f"\n找到 {len(rows)} 条风格模式:")
                print("-" * 80)

                current_group = None
                for row in rows:
                    if group_id is None:
                        if current_group != row["group_id"]:
                            current_group = row["group_id"]
                            print(f"\n>>> 群组 {current_group} <<<")
                    
                    style_id = row["id"]
                    context = row["context"][:30] + "..." if len(row["context"]) > 30 else row["context"]
                    style = row["style_desc"][:40] + "..." if len(row["style_desc"]) > 40 else row["style_desc"]
                    weight = row["weight"]
                    
                    print(f"  [{style_id:3d}] {context:30s} | {style:40s} | 权重:{weight:2d}")

        except Exception as e:
            print(f"错误: {e}")

    def view_top_styles(self):
        """查看权重最高的风格"""
        try:
            group_id = self.get_group_id()
            limit = input("\n显示前几条？(默认10): ").strip()
            limit = int(limit) if limit.isdigit() else 10

            with self.get_connection() as conn:
                cursor = conn.cursor()

                if group_id:
                    cursor.execute(
                        """SELECT id, context, style_desc, weight 
                           FROM style_patterns 
                           WHERE group_id = ? 
                           ORDER BY weight DESC 
                           LIMIT ?""",
                        (group_id, limit)
                    )
                else:
                    cursor.execute(
                        """SELECT group_id, id, context, style_desc, weight 
                           FROM style_patterns 
                           ORDER BY weight DESC 
                           LIMIT ?""",
                        (limit,)
                    )

                rows = cursor.fetchall()

                if not rows:
                    print(f"\n没有找到风格模式")
                    return

                print(f"\n权重最高的 {len(rows)} 条风格模式:")
                print("-" * 80)

                for i, row in enumerate(rows, 1):
                    if group_id is None:
                        print(f"\n{i}. [群{row['group_id']}]")
                    else:
                        print(f"\n{i}.")
                    print(f"   ID: {row['id']}")
                    print(f"   情境: {row['context']}")
                    print(f"   风格: {row['style_desc']}")
                    print(f"   权重: {row['weight']}")

        except Exception as e:
            print(f"错误: {e}")

    def view_bottom_styles(self):
        """查看权重最低的风格"""
        try:
            group_id = self.get_group_id()
            limit = input("\n显示前几条？(默认10): ").strip()
            limit = int(limit) if limit.isdigit() else 10

            with self.get_connection() as conn:
                cursor = conn.cursor()

                if group_id:
                    cursor.execute(
                        """SELECT id, context, style_desc, weight 
                           FROM style_patterns 
                           WHERE group_id = ? 
                           ORDER BY weight ASC 
                           LIMIT ?""",
                        (group_id, limit)
                    )
                else:
                    cursor.execute(
                        """SELECT group_id, id, context, style_desc, weight 
                           FROM style_patterns 
                           ORDER BY weight ASC 
                           LIMIT ?""",
                        (limit,)
                    )

                rows = cursor.fetchall()

                if not rows:
                    print(f"\n没有找到风格模式")
                    return

                print(f"\n权重最低的 {len(rows)} 条风格模式:")
                print("-" * 80)

                for i, row in enumerate(rows, 1):
                    if group_id is None:
                        print(f"\n{i}. [群{row['group_id']}]")
                    else:
                        print(f"\n{i}.")
                    print(f"   ID: {row['id']}")
                    print(f"   情境: {row['context']}")
                    print(f"   风格: {row['style_desc']}")
                    print(f"   权重: {row['weight']}")

        except Exception as e:
            print(f"错误: {e}")

    def view_by_context(self):
        """按情境筛选"""
        try:
            keyword = input("\n请输入情境关键词: ").strip()
            if not keyword:
                print("关键词不能为空")
                return

            group_id = self.get_group_id()

            with self.get_connection() as conn:
                cursor = conn.cursor()

                if group_id:
                    cursor.execute(
                        """SELECT id, context, style_desc, weight 
                           FROM style_patterns 
                           WHERE group_id = ? AND context LIKE ? 
                           ORDER BY weight DESC""",
                        (group_id, f"%{keyword}%")
                    )
                else:
                    cursor.execute(
                        """SELECT group_id, id, context, style_desc, weight 
                           FROM style_patterns 
                           WHERE context LIKE ? 
                           ORDER BY weight DESC""",
                        (f"%{keyword}%",)
                    )

                rows = cursor.fetchall()

                if not rows:
                    print(f"\n没有找到包含 '{keyword}' 的风格模式")
                    return

                print(f"\n找到 {len(rows)} 条包含 '{keyword}' 的风格模式:")
                print("-" * 80)

                for i, row in enumerate(rows, 1):
                    if group_id is None:
                        print(f"\n{i}. [群{row['group_id']}]")
                    else:
                        print(f"\n{i}.")
                    print(f"   ID: {row['id']}")
                    print(f"   情境: {row['context']}")
                    print(f"   风格: {row['style_desc']}")
                    print(f"   权重: {row['weight']}")

        except Exception as e:
            print(f"错误: {e}")

    def search_styles(self):
        """搜索风格模式"""
        try:
            print("\n--- 搜索风格模式 ---")
            keyword = input("请输入搜索关键词 (情境或风格描述): ").strip()
            if not keyword:
                print("关键词不能为空")
                return

            group_id = self.get_group_id()

            with self.get_connection() as conn:
                cursor = conn.cursor()

                if group_id:
                    cursor.execute(
                        """SELECT id, context, style_desc, weight 
                           FROM style_patterns 
                           WHERE group_id = ? AND (context LIKE ? OR style_desc LIKE ?) 
                           ORDER BY weight DESC""",
                        (group_id, f"%{keyword}%", f"%{keyword}%")
                    )
                else:
                    cursor.execute(
                        """SELECT group_id, id, context, style_desc, weight 
                           FROM style_patterns 
                           WHERE context LIKE ? OR style_desc LIKE ? 
                           ORDER BY weight DESC""",
                        (f"%{keyword}%", f"%{keyword}%")
                    )

                rows = cursor.fetchall()

                if not rows:
                    print(f"\n没有找到包含 '{keyword}' 的风格模式")
                    return

                print(f"\n找到 {len(rows)} 条包含 '{keyword}' 的风格模式:")
                print("-" * 80)

                for i, row in enumerate(rows, 1):
                    if group_id is None:
                        print(f"\n{i}. [群{row['group_id']}]")
                    else:
                        print(f"\n{i}.")
                    print(f"   ID: {row['id']}")
                    print(f"   情境: {row['context']}")
                    print(f"   风格: {row['style_desc']}")
                    print(f"   权重: {row['weight']}")

        except Exception as e:
            print(f"错误: {e}")

    def add_style(self):
        """添加风格模式"""
        try:
            print("\n--- 添加风格模式 ---")
            group_id = self.get_group_id()
            if group_id is None:
                print("必须指定群组 ID")
                return

            context = input("情境 (例如: 讨论二次元): ").strip()
            if not context:
                print("情境不能为空")
                return

            style_desc = input("风格描述 (例如: 使用大量的抽象黑话): ").strip()
            if not style_desc:
                print("风格描述不能为空")
                return

            weight_input = input("初始权重 (默认1): ").strip()
            weight = int(weight_input) if weight_input.isdigit() else 1

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO style_patterns (group_id, context, style_desc, weight)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(group_id, context, style_desc) DO UPDATE SET
                       weight = weight + ?""",
                    (group_id, context, style_desc, weight, weight)
                )
                conn.commit()

            print(f"\n✓ 风格模式添加成功！")
            print(f"   情境: {context}")
            print(f"   风格: {style_desc}")

        except Exception as e:
            print(f"错误: {e}")

    def edit_style(self):
        """编辑风格模式"""
        try:
            print("\n--- 编辑风格模式 ---")
            style_id = input("请输入要编辑的风格 ID: ").strip()
            if not style_id.isdigit():
                print("无效的 ID")
                return

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT group_id, context, style_desc, weight 
                       FROM style_patterns 
                       WHERE id = ?""",
                    (int(style_id),)
                )
                row = cursor.fetchone()

                if not row:
                    print(f"没有找到 ID 为 {style_id} 的风格模式")
                    return

                print(f"\n当前风格模式:")
                print(f"   群组: {row['group_id']}")
                print(f"   情境: {row['context']}")
                print(f"   风格: {row['style_desc']}")
                print(f"   权重: {row['weight']}")

                print("\n要修改的内容 (直接回车保持不变):")

                new_context = input(f"新情境 (当前: {row['context']}): ").strip() or None
                new_style = input(f"新风格描述 (当前: {row['style_desc']}): ").strip() or None
                new_weight = input(f"新权重 (当前: {row['weight']}): ").strip()
                new_weight = int(new_weight) if new_weight.isdigit() else None

                if not any([new_context, new_style, new_weight is not None]):
                    print("至少需要修改一项")
                    return

                if new_context:
                    cursor.execute(
                        """UPDATE style_patterns 
                           SET context = ? 
                           WHERE id = ?""",
                        (new_context, int(style_id))
                    )
                
                if new_style:
                    cursor.execute(
                        """UPDATE style_patterns 
                           SET style_desc = ? 
                           WHERE id = ?""",
                        (new_style, int(style_id))
                    )
                
                if new_weight is not None:
                    cursor.execute(
                        """UPDATE style_patterns 
                           SET weight = ? 
                           WHERE id = ?""",
                        (new_weight, int(style_id))
                    )

                conn.commit()

            print(f"\n✓ 风格模式更新成功！")

        except Exception as e:
            print(f"错误: {e}")

    def delete_style(self):
        """删除风格模式"""
        try:
            print("\n--- 删除风格模式 ---")
            style_id = input("请输入要删除的风格 ID: ").strip()
            if not style_id.isdigit():
                print("无效的 ID")
                return

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT context, style_desc FROM style_patterns WHERE id = ?""",
                    (int(style_id),)
                )
                row = cursor.fetchone()

                if not row:
                    print(f"没有找到 ID 为 {style_id} 的风格模式")
                    return

                print(f"\n将要删除的风格模式:")
                print(f"   情境: {row['context']}")
                print(f"   风格: {row['style_desc']}")

                confirm = input("\n确认删除？(yes/no): ").strip().lower()
                if confirm not in ['yes', 'y']:
                    print("已取消")
                    return

                cursor.execute("DELETE FROM style_patterns WHERE id = ?", (int(style_id),))
                conn.commit()

            print(f"\n✓ 风格模式删除成功！")

        except Exception as e:
            print(f"错误: {e}")

    def batch_operations(self):
        """批量操作"""
        print("\n--- 批量操作 ---")
        print("1. 批量删除 (按情境)")
        print("2. 批量删除 (按权重)")
        print("3. 批量修改权重")
        print("4. 返回主菜单")

        choice = input("\n请选择操作 (1-4): ").strip()

        if choice == "1":
            self.batch_delete_by_context()
        elif choice == "2":
            self.batch_delete_by_weight()
        elif choice == "3":
            self.batch_update_weight()
        elif choice == "4":
            return
        else:
            print("无效的选择")

    def batch_delete_by_context(self):
        """按情境批量删除"""
        try:
            keyword = input("\n请输入情境关键词 (匹配包含此关键词的所有风格): ").strip()
            if not keyword:
                print("关键词不能为空")
                return

            group_id = self.get_group_id()

            with self.get_connection() as conn:
                cursor = conn.cursor()

                if group_id:
                    cursor.execute(
                        """SELECT COUNT(*) FROM style_patterns 
                           WHERE group_id = ? AND context LIKE ?""",
                        (group_id, f"%{keyword}%")
                    )
                else:
                    cursor.execute(
                        """SELECT COUNT(*) FROM style_patterns 
                           WHERE context LIKE ?""",
                        (f"%{keyword}%",)
                    )

                count = cursor.fetchone()[0]

                if count == 0:
                    print(f"没有找到包含 '{keyword}' 的风格模式")
                    return

                print(f"\n将删除 {count} 条包含 '{keyword}' 的风格模式")
                confirm = input("\n确认删除？(yes/no): ").strip().lower()
                if confirm not in ['yes', 'y']:
                    print("已取消")
                    return

                if group_id:
                    cursor.execute(
                        """DELETE FROM style_patterns 
                           WHERE group_id = ? AND context LIKE ?""",
                        (group_id, f"%{keyword}%")
                    )
                else:
                    cursor.execute(
                        """DELETE FROM style_patterns 
                           WHERE context LIKE ?""",
                        (f"%{keyword}%",)
                    )

                conn.commit()

            print(f"\n✓ 成功删除 {count} 条风格模式！")

        except Exception as e:
            print(f"错误: {e}")

    def batch_delete_by_weight(self):
        """按权重批量删除"""
        try:
            print("\n删除权重低于指定值的风格模式")
            max_weight = input("请输入最大权重 (删除小于此权重的所有风格): ").strip()
            if not max_weight.isdigit():
                print("无效的权重值")
                return

            group_id = self.get_group_id()

            with self.get_connection() as conn:
                cursor = conn.cursor()

                if group_id:
                    cursor.execute(
                        """SELECT COUNT(*) FROM style_patterns 
                           WHERE group_id = ? AND weight < ?""",
                        (group_id, int(max_weight))
                    )
                else:
                    cursor.execute(
                        """SELECT COUNT(*) FROM style_patterns 
                           WHERE weight < ?""",
                        (int(max_weight),)
                    )

                count = cursor.fetchone()[0]

                if count == 0:
                    print(f"没有找到权重小于 {max_weight} 的风格模式")
                    return

                print(f"\n将删除 {count} 条权重小于 {max_weight} 的风格模式")
                confirm = input("\n确认删除？(yes/no): ").strip().lower()
                if confirm not in ['yes', 'y']:
                    print("已取消")
                    return

                if group_id:
                    cursor.execute(
                        """DELETE FROM style_patterns 
                           WHERE group_id = ? AND weight < ?""",
                        (group_id, int(max_weight))
                    )
                else:
                    cursor.execute(
                        """DELETE FROM style_patterns 
                           WHERE weight < ?""",
                        (int(max_weight),)
                    )

                conn.commit()

            print(f"\n✓ 成功删除 {count} 条风格模式！")

        except Exception as e:
            print(f"错误: {e}")

    def batch_update_weight(self):
        """批量修改权重"""
        try:
            group_id = self.get_group_id(allow_all=False)
            if group_id is None:
                print("没有可用的群组")
                return

            print("\n批量修改权重")
            print("1. 增加所有风格的权重")
            print("2. 减少所有风格的权重")
            print("3. 重置所有风格的权重")

            choice = input("\n请选择操作 (1-3): ").strip()

            if choice == "1":
                delta = input("增加权重 (例如: 1): ").strip()
                if not delta.isdigit():
                    print("无效的权重值")
                    return
                
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """UPDATE style_patterns 
                           SET weight = weight + ? 
                           WHERE group_id = ?""",
                        (int(delta), group_id)
                    )
                    conn.commit()
                
                print(f"\n✓ 成功增加权重！")

            elif choice == "2":
                delta = input("减少权重 (例如: 1): ").strip()
                if not delta.isdigit():
                    print("无效的权重值")
                    return
                
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """UPDATE style_patterns 
                           SET weight = MAX(1, weight - ?) 
                           WHERE group_id = ?""",
                        (int(delta), group_id)
                    )
                    conn.commit()
                
                print(f"\n✓ 成功减少权重！")

            elif choice == "3":
                new_weight = input("新权重值 (例如: 1): ").strip()
                if not new_weight.isdigit():
                    print("无效的权重值")
                    return
                
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """UPDATE style_patterns 
                           SET weight = ? 
                           WHERE group_id = ?""",
                        (int(new_weight), group_id)
                    )
                    conn.commit()
                
                print(f"\n✓ 成功重置权重！")

            else:
                print("无效的选择")

        except Exception as e:
            print(f"错误: {e}")

    def view_statistics(self):
        """查看数据统计"""
        try:
            group_id = self.get_group_id()

            with self.get_connection() as conn:
                cursor = conn.cursor()

                if group_id:
                    cursor.execute(
                        """SELECT COUNT(*), AVG(weight), MAX(weight), MIN(weight)
                           FROM style_patterns 
                           WHERE group_id = ?""",
                        (group_id,)
                    )
                else:
                    cursor.execute(
                        """SELECT COUNT(*), AVG(weight), MAX(weight), MIN(weight)
                           FROM style_patterns"""
                    )

                row = cursor.fetchone()

                print("\n" + "=" * 50)
                if group_id:
                    print(f"群组 {group_id} 风格模式统计")
                else:
                    print("全局风格模式统计")
                print("=" * 50)
                print(f"\n风格模式总数: {row[0]}")
                print(f"平均权重: {round(row[1], 2) if row[1] else 0}")
                print(f"最高权重: {row[2]}")
                print(f"最低权重: {row[3]}")

                if group_id:
                    cursor.execute(
                        """SELECT context, COUNT(*) as cnt 
                           FROM style_patterns 
                           WHERE group_id = ? 
                           GROUP BY context 
                           ORDER BY cnt DESC 
                           LIMIT 5""",
                        (group_id,)
                    )
                else:
                    cursor.execute(
                        """SELECT context, COUNT(*) as cnt 
                           FROM style_patterns 
                           GROUP BY context 
                           ORDER BY cnt DESC 
                           LIMIT 5"""
                    )

                rows = cursor.fetchall()

                if rows:
                    print(f"\n最常见的情境:")
                    for row in rows:
                        print(f"  - {row[0]}: {row[1]} 条")

        except Exception as e:
            print(f"错误: {e}")

    def clear_all_styles(self):
        """清空所有风格模式"""
        try:
            print("\n" + "!" * 60)
            print("警告：此操作将删除所有风格模式，且不可恢复！")
            print("!" * 60)

            group_id = self.get_group_id()

            if group_id:
                confirm = input(f"\n确认清空群组 {group_id} 的所有风格模式？(输入 'YES' 确认): ").strip()
            else:
                confirm = input("\n确认清空所有群组的所有风格模式？(输入 'YES' 确认): ").strip()

            if confirm != "YES":
                print("已取消")
                return

            with self.get_connection() as conn:
                cursor = conn.cursor()

                if group_id:
                    cursor.execute(
                        """SELECT COUNT(*) FROM style_patterns WHERE group_id = ?""",
                        (group_id,)
                    )
                    count = cursor.fetchone()[0]

                    cursor.execute(
                        """DELETE FROM style_patterns WHERE group_id = ?""",
                        (group_id,)
                    )
                else:
                    cursor.execute("""SELECT COUNT(*) FROM style_patterns""")
                    count = cursor.fetchone()[0]

                    cursor.execute("""DELETE FROM style_patterns""")

                conn.commit()

            print(f"\n✓ 成功清空 {count} 条风格模式！")

        except Exception as e:
            print(f"错误: {e}")

    def run(self):
        """运行主程序"""
        while self.running:
            self.print_menu()
            choice = input("\n请选择功能 (0-8): ").strip()

            if choice == "1":
                self.view_styles()
            elif choice == "2":
                self.search_styles()
            elif choice == "3":
                self.add_style()
            elif choice == "4":
                self.edit_style()
            elif choice == "5":
                self.delete_style()
            elif choice == "6":
                self.batch_operations()
            elif choice == "7":
                self.view_statistics()
            elif choice == "8":
                self.clear_all_styles()
            elif choice == "0":
                print("\n再见！")
                break
            else:
                print("无效的选择，请重新输入")


def main():
    """主函数"""
    print("""
    ╔════════════════════════════════════════════════╗
    ║       Bot 风格管理工具 v1.0                    ║
    ║                                                ║
    ║  管理 bot 学习到的说话风格模式                ║
    ╚════════════════════════════════════════════════╝
    """)

    manager = StyleManager()
    
    try:
        manager.run()
    except KeyboardInterrupt:
        print("\n\n程序已中断")
    except Exception as e:
        print(f"\n程序异常: {e}")


if __name__ == "__main__":
    main()
