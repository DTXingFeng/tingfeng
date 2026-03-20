"""
检查 OpenAI SDK 实际发送的 URL
"""

import asyncio
from openai import AsyncOpenAI
import sys
import os

sys.path.append(os.getcwd())

from src.config.ai_config import ai_config_manager


async def check_url_with_different_configs():
    """测试不同的 base_url 配置"""
    
    model_alias = "glm-4.7-heretic-neo-code"
    creds = ai_config_manager.get_model_credentials(model_alias)
    
    print("=" * 70)
    print("测试不同的 base_url 配置")
    print("=" * 70)
    
    # 测试配置
    test_configs = [
        ("http://localhost:1234/v1", "当前配置（包含 /v1）"),
        ("http://localhost:1234", "不包含 /v1"),
    ]
    
    for base_url, description in test_configs:
        print(f"\n{'='*70}")
        print(f"配置: {description}")
        print(f"base_url: {base_url}")
        print(f"{'='*70}")
        
        try:
            client = AsyncOpenAI(
                api_key=creds["api_key"],
                base_url=base_url,
                timeout=10.0
            )
            
            # 测试 /v1/models 端点
            print(f"\n尝试调用 client.models.list()...")
            print(f"实际请求 URL 应该是: {base_url}/models" if base_url.endswith("/v1") else f"实际请求 URL 应该是: {base_url}/v1/models")
            
            models = await client.models.list()
            
            print(f"✅ 成功！")
            print(f"\n可用模型:")
            for model in models.data[:5]:  # 只显示前5个
                print(f"  - {model.id}")
            
            print(f"\n✅ 这个配置正确: {base_url}")
            return base_url  # 返回第一个成功的配置
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 失败: {type(e).__name__}")
            
            # 尝试从错误中提取实际 URL
            if "http" in error_msg:
                import re
                urls = re.findall(r'https?://[^\s]+', error_msg)
                if urls:
                    print(f"实际请求的 URL: {urls[0]}")
            else:
                print(f"错误信息: {error_msg[:200]}")
    
    return None


async def test_with_raw_http(base_url: str):
    """使用原始 HTTP 请求测试"""
    print(f"\n{'='*70}")
    print(f"原始 HTTP 请求测试")
    print(f"{'='*70}")
    
    import aiohttp
    
    # 尝试不同的路径
    test_paths = [
        "/v1/models",
        "/models",
        "/",
    ]
    
    for path in test_paths:
        url = f"http://localhost:1234{path}"
        print(f"\n尝试: {url}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    print(f"✅ 状态码: {response.status}")
                    text = await response.text()
                    print(f"响应预览: {text[:200]}")
                    
                    if response.status == 200:
                        print(f"✅ 可用的 URL: {url}")
                        return url
        except Exception as e:
            print(f"❌ 失败: {type(e).__name__}")
    
    return None


async def main():
    print("=" * 70)
    print("LM Studio URL 诊断")
    print("=" * 70)
    
    # 方法 1: 测试不同的 base_url 配置
    correct_base_url = await check_url_with_different_configs()
    
    if correct_base_url:
        print(f"\n{'='*70}")
        print(f"✅ 找到正确的配置")
        print(f"{'='*70}")
        print(f"\n正确的 base_url 应该是:")
        print(f"  {correct_base_url}")
        
        print(f"\n如果与当前配置不同，请修改 ai_config.yaml:")
        print(f"  lm_studio_local:")
        print(f"    base_url: \"{correct_base_url}\"")
    else:
        print(f"\n{'='*70}")
        print(f"❌ 未能找到可用的配置")
        print(f"{'='*70}")
        
        # 方法 2: 尝试原始 HTTP 请求
        print(f"\n尝试原始 HTTP 请求...")
        working_url = await test_with_raw_http("http://localhost:1234")
        
        if working_url:
            print(f"\n✅ 找到可用的 URL: {working_url}")
        else:
            print(f"\n❌ LM Studio 服务器可能未正确启动")


if __name__ == "__main__":
    asyncio.run(main())
