"""
测试不同端口和配置的 LM Studio 连接
"""

import asyncio
import socket
import sys
import os

sys.path.append(os.getcwd())


async def check_port(port: int, host: str = "127.0.0.1") -> dict:
    """检查端口是否可访问"""
    result = {
        "port": port,
        "listening": False,
        "http": False,
        "info": ""
    }
    
    # 检查端口是否在监听
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect((host, port))
            result["listening"] = True
            result["info"] = f"端口 {port} 正在监听"
    except Exception as e:
        result["info"] = f"端口 {port} 未监听: {e}"
        return result
    
    # 尝试发送 HTTP 请求
    try:
        import aiohttp
        url = f"http://{host}:{port}/v1/models"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as response:
                result["http"] = True
                result["info"] = f"端口 {port} HTTP 正常 (状态: {response.status})"
    except asyncio.TimeoutError:
        result["info"] = f"端口 {port} 监听中但 HTTP 超时"
    except Exception as e:
        result["info"] = f"端口 {port} 监听中但 HTTP 错误: {type(e).__name__}"
    
    return result


async def main():
    print("=" * 70)
    print("检查 LM Studio 可能的端口")
    print("=" * 70)
    
    # 常见的 LM Studio 端口
    ports_to_check = [1234, 1235, 8080, 8000, 5000, 3000]
    
    print(f"\n检查端口: {ports_to_check}")
    print("-" * 70)
    
    tasks = [check_port(port) for port in ports_to_check]
    results = await asyncio.gather(*tasks)
    
    # 显示结果
    for result in results:
        status = "✅" if result["listening"] and result["http"] else "⚠️" if result["listening"] else "❌"
        print(f"{status} {result}")
    
    # 找到可用的端口
    available_ports = [r for r in results if r["listening"] and r["http"]]
    
    print("\n" + "=" * 70)
    print("结果分析")
    print("=" * 70)
    
    if available_ports:
        print(f"✅ 找到 {len(available_ports)} 个可用端口:")
        for r in available_ports:
            print(f"   - 端口 {r['port']}")
        
        # 如果找到的不是 1234，提示修改配置
        if any(r["port"] != 1234 for r in available_ports):
            print(f"\n💡 建议:")
            print(f"   当前配置使用端口 1234，但可能实际端口不同。")
            print(f"   请在 LM Studio 中确认端口号，或在 ai_config.yaml 中修改 base_url")
    else:
        print(f"❌ 没有找到可用的 HTTP 端口")
        print(f"\n💡 请在 LM Studio 中：")
        print(f"   1. 打开右侧的 'Server' 或 'Developer' 面板")
        print(f"   2. 确认 'Start Server' 按钮已激活")
        print(f"   3. 查看显示的端口号")
        print(f"   4. 如果未启动，点击启动服务器")


if __name__ == "__main__":
    asyncio.run(main())
