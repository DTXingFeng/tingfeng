"""
用户数据迁移脚本：将用户数据从基于 user_name 迁移到基于 user_id

迁移步骤：
1. 备份现有数据库
2. 为每个表添加 user_id 列（如果不存在）
3. 使用 user_mapping 表的数据填充 user_id
4. 合并同一 user_id 的多条记录（处理改名情况）
5. 修改主键约束为 (group_id, user_id)
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime


def backup_database(db_path: str) -> str:
    """备份数据库"""
    db_path_obj = Path(db_path)
    backup_path = db_path_obj.parent / f"{db_path_obj.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{db_path_obj.suffix}"
    shutil.copy2(db_path, backup_path)
    print(f"✅ 数据库已备份到: {backup_path}")
    return str(backup_path)


def migrate_table(conn, table_name: str, has_primary_key: bool = True):
    """
    迁移单个表
    
    Args:
        conn: 数据库连接
        table_name: 表名
        has_primary_key: 是否有复合主键 (group_id, user_name)
    """
    cursor = conn.cursor()
    
    print(f"\n{'='*60}")
    print(f"开始迁移表: {table_name}")
    print(f"{'='*60}")
    
    # 1. 检查表结构
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    print(f"当前列: {column_names}")
    
    # 2. 检查是否已有 user_id 列
    if "user_id" in column_names:
        print(f"⚠️  表 {table_name} 已有 user_id 列，跳过添加")
    else:
        # 添加 user_id 列
        try:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN user_id INTEGER")
            print(f"✅ 已添加 user_id 列到表 {table_name}")
        except Exception as e:
            print(f"❌ 添加 user_id 列失败: {e}")
            return False
    
    # 3. 从 user_mapping 获取 user_id 并更新
    try:
        # 查询当前表中所有唯一的 (group_id, user_name) 组合
        cursor.execute(f"SELECT DISTINCT group_id, user_name FROM {table_name} WHERE user_name IS NOT NULL")
        unique_users = cursor.fetchall()
        
        updated_count = 0
        not_found_count = 0
        
        for group_id, user_name in unique_users:
            # 从 user_mapping 查找对应的 user_id
            cursor.execute(
                "SELECT user_id FROM user_mapping WHERE group_id = ? AND user_name = ?",
                (group_id, user_name)
            )
            result = cursor.fetchone()
            
            if result and result[0]:
                # 更新 user_id
                cursor.execute(
                    f"UPDATE {table_name} SET user_id = ? WHERE group_id = ? AND user_name = ?",
                    (result[0], group_id, user_name)
                )
                updated_count += cursor.rowcount
            else:
                not_found_count += 1
                print(f"⚠️  未找到 user_id: group_id={group_id}, user_name={user_name}")
        
        conn.commit()
        print(f"✅ 已更新 {updated_count} 条记录的 user_id")
        if not_found_count > 0:
            print(f"⚠️  {not_found_count} 条记录未找到对应的 user_id")
    
    except Exception as e:
        print(f"❌ 更新 user_id 失败: {e}")
        conn.rollback()
        return False
    
    # 4. 如果是主键表，需要重建表以修改主键
    if has_primary_key:
        print(f"\n开始重建表 {table_name} 以修改主键...")
        
        try:
            # 获取表的所有列名
            cursor.execute(f"PRAGMA table_info({table_name})")
            all_columns = [col[1] for col in cursor.fetchall()]
            
            # 创建新表
            new_table_name = f"{table_name}_new"
            create_sql = f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'"
            cursor.execute(create_sql)
            original_sql = cursor.fetchone()[0]
            
            # 修改 SQL：将表名改为新表名，主键改为 (group_id, user_id)
            new_sql = original_sql.replace(
                f"CREATE TABLE {table_name}",
                f"CREATE TABLE {new_table_name}"
            )
            
            # 替换主键定义
            if "PRIMARY KEY (group_id, user_name)" in new_sql:
                new_sql = new_sql.replace(
                    "PRIMARY KEY (group_id, user_name)",
                    "PRIMARY KEY (group_id, user_id)"
                )
            elif "PRIMARY KEY (group_id, user_name, " in new_sql:
                # 处理有三个字段的 PRIMARY KEY（如 user_memories 的可能情况）
                new_sql = new_sql.replace(
                    "PRIMARY KEY (group_id, user_name, ",
                    "PRIMARY KEY (group_id, user_id, "
                )
            
            print(f"新表 SQL: {new_sql[:200]}...")
            cursor.execute(new_sql)
            
            # 复制数据，根据 user_id 去重（保留最新的记录）
            if "updated_at" in all_columns or "created_at" in all_columns:
                time_field = "updated_at" if "updated_at" in all_columns else "created_at"
                copy_sql = f"""
                    INSERT INTO {new_table_name} 
                    SELECT * FROM {table_name} t1
                    WHERE rowid = (
                        SELECT max(rowid) FROM {table_name} t2
                        WHERE t2.group_id = t1.group_id 
                          AND t2.user_id = t1.user_id
                          AND t2.user_id IS NOT NULL
                    )
                    UNION
                    SELECT * FROM {table_name} t1
                    WHERE user_id IS NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM {table_name} t2
                          WHERE t2.group_id = t1.group_id
                            AND t2.user_id IS NOT NULL
                            AND t2.user_name = t1.user_name
                      )
                """
            else:
                # 如果没有时间字段，保留第一条
                copy_sql = f"""
                    INSERT INTO {new_table_name}
                    SELECT * FROM {table_name} t1
                    WHERE rowid = (
                        SELECT min(rowid) FROM {table_name} t2
                        WHERE t2.group_id = t1.group_id 
                          AND t2.user_id = t1.user_id
                          AND t2.user_id IS NOT NULL
                    )
                    UNION
                    SELECT * FROM {table_name} t1
                    WHERE user_id IS NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM {table_name} t2
                          WHERE t2.group_id = t1.group_id
                            AND t2.user_id IS NOT NULL
                            AND t2.user_name = t1.user_name
                      )
                """
            
            cursor.execute(copy_sql)
            
            # 检查复制的数据量
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            old_count = cursor.fetchone()[0]
            cursor.execute(f"SELECT COUNT(*) FROM {new_table_name}")
            new_count = cursor.fetchone()[0]
            
            print(f"✅ 数据复制: {old_count} -> {new_count} 条记录")
            
            # 删除旧表，重命名新表
            cursor.execute(f"DROP TABLE {table_name}")
            cursor.execute(f"ALTER TABLE {new_table_name} RENAME TO {table_name}")
            
            conn.commit()
            print(f"✅ 表 {table_name} 主键已更新为 (group_id, user_id)")
        
        except Exception as e:
            print(f"❌ 重建表失败: {e}")
            conn.rollback()
            return False
    
    return True


def merge_duplicate_users(conn):
    """
    合并同一 user_id 的重复记录（好感度和关系状态）
    
    对于同一个 user_id，可能有多条记录（因为改名），需要：
    - 好感度：取平均值或最大值
    - 状态：取最新的状态
    """
    cursor = conn.cursor()
    
    print(f"\n{'='*60}")
    print("开始合并重复用户数据")
    print(f"{'='*60}")
    
    # 处理 user_relationships 表
    try:
        # 查找重复的 user_id
        cursor.execute("""
            SELECT group_id, user_id, COUNT(*) as cnt
            FROM user_relationships
            WHERE user_id IS NOT NULL
            GROUP BY group_id, user_id
            HAVING cnt > 1
        """)
        duplicates = cursor.fetchall()
        
        if duplicates:
            print(f"发现 {len(duplicates)} 组重复用户数据，正在合并...")
            
            for group_id, user_id, count in duplicates:
                # 获取该用户的所有记录，按时间排序
                cursor.execute("""
                    SELECT user_name, favorability, status, updated_at
                    FROM user_relationships
                    WHERE group_id = ? AND user_id = ?
                    ORDER BY updated_at DESC
                """, (group_id, user_id))
                
                records = cursor.fetchall()
                
                # 策略：
                # - 好感度：取最大值（避免降低好感度）
                # - 状态：取最新记录的状态
                # - 保留最新的 user_name
                
                max_favorability = max(r[1] for r in records)
                latest_status = records[0][2]
                latest_name = records[0][0]
                
                print(f"  合并 user_id={user_id}, group_id={group_id}: {count}条记录 -> 好感度={max_favorability}, 状态={latest_status}")
                
                # 删除所有旧记录
                cursor.execute(
                    "DELETE FROM user_relationships WHERE group_id = ? AND user_id = ?",
                    (group_id, user_id)
                )
                
                # 插入合并后的记录
                cursor.execute(
                    """
                    INSERT INTO user_relationships (group_id, user_id, user_name, favorability, status, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (group_id, user_id, latest_name, max_favorability, latest_status)
                )
            
            conn.commit()
            print(f"✅ 已合并 {len(duplicates)} 组重复用户数据")
        else:
            print("✅ 未发现重复用户数据")
    
    except Exception as e:
        print(f"❌ 合并数据失败: {e}")
        conn.rollback()


def main():
    """主迁移函数"""
    db_path = "data/bot_data.db"
    
    print(f"{'='*60}")
    print("开始用户数据迁移：user_name -> user_id")
    print(f"{'='*60}")
    print(f"数据库路径: {db_path}")
    
    # 备份数据库
    backup_path = backup_database(db_path)
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    
    try:
        # 迁移各个表
        tables_to_migrate = [
            ("user_relationships", True),  # (表名, 是否有主键)
            ("user_profiles", True),
            ("user_memories", False),  # user_memories 没有 user_name 主键，但有 user_name 列
        ]
        
        for table_name, has_pk in tables_to_migrate:
            success = migrate_table(conn, table_name, has_pk)
            if not success:
                print(f"\n❌ 迁移表 {table_name} 失败，回滚所有更改")
                conn.close()
                print(f"\n可以使用备份恢复: {backup_path}")
                return
        
        # 合并重复用户数据
        merge_duplicate_users(conn)
        
        # 显示迁移结果
        print(f"\n{'='*60}")
        print("迁移完成！数据统计：")
        print(f"{'='*60}")
        
        cursor = conn.cursor()
        
        # user_relationships 统计
        cursor.execute("SELECT COUNT(*) FROM user_relationships WHERE user_id IS NOT NULL")
        rel_count = cursor.fetchone()[0]
        print(f"✅ user_relationships: {rel_count} 条记录已关联 user_id")
        
        # user_profiles 统计
        cursor.execute("SELECT COUNT(*) FROM user_profiles WHERE user_id IS NOT NULL")
        prof_count = cursor.fetchone()[0]
        print(f"✅ user_profiles: {prof_count} 条记录已关联 user_id")
        
        # user_memories 统计
        cursor.execute("SELECT COUNT(*) FROM user_memories WHERE user_id IS NOT NULL")
        mem_count = cursor.fetchone()[0]
        print(f"✅ user_memories: {mem_count} 条记录已关联 user_id")
        
        # 显示重复用户合并情况
        cursor.execute("""
            SELECT user_name, user_id, group_id, favorability, status
            FROM user_relationships
            ORDER BY favorability DESC
            LIMIT 10
        """)
        top_users = cursor.fetchall()
        
        print(f"\n好感度最高的用户:")
        for user_name, user_id, group_id, favorability, status in top_users:
            print(f"  {user_name}(QQ:{user_id}) - 好感度: {favorability} ({status})")
        
        print(f"\n{'='*60}")
        print("✅ 迁移成功完成！")
        print(f"{'='*60}")
        print(f"备份文件: {backup_path}")
        print(f"如遇问题，可以使用备份恢复数据库")
    
    except Exception as e:
        print(f"\n❌ 迁移过程出错: {e}")
        print(f"可以使用备份恢复: {backup_path}")
    
    finally:
        conn.close()


if __name__ == "__main__":
    main()
