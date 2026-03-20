"""
使用原始 socket 测试 LM Studio 服务器响应
"""

import socket
import sys
import time


def test_raw_socket(host: str = "127.0.0.1", port: int = 1234):
    """使用原始 socket 测试连接"""
    print("=" * 70)
    print(f"测试连接到 {host}:{port}")
    print("=" * 70)
    
    try:
        # 创建 socket
        print("\n1. 创建 socket 连接...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        print(f"2. 连接到 {host}:{port}...")
        sock.connect((host, port))
        print("   ✅ 连接成功")
        
        # 发送 HTTP 请求
        http_request = b"GET /v1/models HTTP/1.1\r\nHost: localhost\r\n\r\n"
        print(f"\n3. 发送 HTTP 请求:")
        print(f"   {http_request.decode('ascii', errors='ignore')[:100]}...")
        sock.sendall(http_request)
        
        # 接收响应
        print(f"\n4. 接收响应...")
        response = b""
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
                print(f"   接收到 {len(chunk)} 字节")
                
                # 只接收前几次数据，避免死循环
                if len(response) > 10000:
                    print(f"   已接收超过 10KB，停止接收")
                    break
        except socket.timeout:
            print(f"   接收超时（已接收 {len(response)} 字节）")
        
        sock.close()
        
        # 分析响应
        print(f"\n5. 分析响应:")
        print(f"   总字节数: {len(response)}")
        
        if response:
            # 尝试显示前 500 字节
            print(f"\n   前 500 字节内容:")
            try:
                preview = response[:500]
                # 尝试解码为文本
                text_preview = preview.decode('utf-8', errors='replace')
                for line in text_preview.split('\n')[:20]:
                    print(f"   {line}")
            except:
                print(f"   (无法解码为文本)")
                print(f"   十六进制预览: {preview[:100].hex()}")
        else:
            print(f"   ⚠️ 服务器没有返回任何数据")
            print(f"\n   可能原因:")
            print(f"   1. LM Studio 服务器未完全启动")
            print(f"   2. 服务器正在加载模型")
            print(f"   3. 服务器不是 HTTP 服务器")
        
        return response
        
    except socket.timeout:
        print(f"❌ 连接超时")
        return None
    except ConnectionRefusedError:
        print(f"❌ 连接被拒绝")
        print(f"\n💡 请确保:")
        print(f"   1. LM Studio 正在运行")
        print(f"   2. 服务器已启动")
        return None
    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")
        return None


def main():
    print("\n" + "=" * 70)
    print("LM Studio 原始 Socket 测试")
    print("=" * 70)
    
    response = test_raw_socket("127.0.0.1", 1234)
    
    print("\n" + "=" * 70)
    print("诊断建议")
    print("=" * 70)
    
    if response and len(response) > 0:
        print("✅ 服务器有响应")
        print("\n但如果响应不是有效的 HTTP 格式，可能是因为:")
        print("  1. LM Studio 服务器配置问题")
        print("  2. 服务器正在启动或加载模型")
        print("  3. 端口被其他应用占用")
    elif response is not None and len(response) == 0:
        print("⚠️ 服务器连接成功但没有返回数据")
        print("\n这通常意味着:")
        print("  1. LM Studio 服务器正在启动中")
        print("  2. 首次使用需要加载模型（可能需要几分钟）")
        print("  3. 在 LM Studio 中检查是否显示 'Loading model' 或类似状态")
        print("\n建议:")
        print("  - 等待模型加载完成后再试")
        print("  - 在 LM Studio 中查看模型加载进度")
        print("  - 尝试使用更小的模型")
    else:
        print("❌ 无法连接到服务器")
        print("\n请检查:")
        print("  1. LM Studio 应用是否已启动")
        print("  2. 在 LM Studio 右侧找到 'Server' 或 'Developer' 面板")
        print("  3. 点击 'Start Server' 按钮启动服务器")
        print("  4. 确认没有防火墙阻止连接")


if __name__ == "__main__":
    main()
