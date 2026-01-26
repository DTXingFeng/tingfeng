import asyncio
import sys
import os

# 将 src 目录添加到路径
sys.path.append(os.path.join(os.getcwd()))

from src.aimodel.image_processing.vlm import get_vlm_description
from src.config.ai_config import ai_config

async def main():
    # 使用一张公开的测试图片 (百度 Logo)
    test_url = "https://www.baidu.com/img/PCtm_d9c8750bed0b3c7d089fa7d55720d6cf.png"
    
    print(f"=== 图像识别功能测试 ===")
    print(f"当前使用的模型别名: {ai_config.image_model}")
    print(f"正在请求识别 URL: {test_url}")
    print("等待 AI 响应中...\n")
    
    try:
        result = await get_vlm_description(test_url)
        print("--- 识别结果 ---")
        print(result)
        print("----------------")
    except Exception as e:
        print(f"测试执行过程中发生崩溃: {e}")

if __name__ == "__main__":
    asyncio.run(main())
