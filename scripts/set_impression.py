import asyncio
import sys
import os

# 将 src 目录添加到路径
sys.path.append(os.path.join(os.getcwd()))

from src.utils.db_manager import db_manager

async def set_manual_impression():
    # 从之前的日志中看到的群号和用户名
    group_id = 140955192 
    user_name = "刑风_"   
    impression = "机器人最亲密、最信任的人。"

    try:
        # 调用封装好的方法，它会自动确保表已创建
        db_manager.update_user_impression(group_id, user_name, impression)
        print(f"成功通过 DBManager 设置对用户 '{user_name}' 的印象为: {impression}")
    except Exception as e:
        print(f"设置失败: {e}")

if __name__ == "__main__":
    asyncio.run(set_manual_impression())
