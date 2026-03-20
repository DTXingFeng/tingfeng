"""
LM Studio 服务器状态检查

帮助诊断 LM Studio 服务器的配置问题
"""

import subprocess
import json


def check_lm_studio_process():
    """检查 LM Studio 进程"""
    print("=" * 70)
    print("检查 1: LM Studio 进程状态")
    print("=" * 70)
    
    try:
        # 检查 LM Studio.exe 进程
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq LM Studio.exe'],
            capture_output=True,
            text=True
        )
        
        if 'LM Studio.exe' in result.stdout:
            print("✅ LM Studio 正在运行")
            
            # 提取 PID
            for line in result.stdout.split('\n'):
                if 'LM Studio.exe' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            pid = int(parts[1])
                            print(f"   PID: {pid}")
                            
                            # 检查该 PID 监听的端口
                            print("\n检查端口监听状态...")
                            netstat_result = subprocess.run(
                                ['netstat', '-ano', '|', 'findstr', str(pid)],
                                shell=True,
                                capture_output=True,
                                text=True
                            )
                            
                            print(f"   监听的端口:")
                            for line in netstat_result.stdout.split('\n'):
                                if 'LISTENING' in line and str(pid) in line:
                                    parts = line.split()
                                    if len(parts) >= 3:
                                        addr = parts[1]
                                        if ':' in addr:
                                            port = addr.split(':')[-1]
                                            print(f"     - 端口 {port}")
                        except:
                            pass
        else:
            print("❌ LM Studio 未运行")
            print("\n请启动 LM Studio 应用")
    except Exception as e:
        print(f"❌ 检查失败: {e}")


def check_port_1234():
    """检查端口 1234 的状态"""
    print("\n" + "=" * 70)
    print("检查 2: 端口 1234 状态")
    print("=" * 70)
    
    try:
        result = subprocess.run(
            ['netstat', '-ano', '|', 'findstr', ':1234'],
            shell=True,
            capture_output=True,
            text=True
        )
        
        if ':1234' in result.stdout:
            print("✅ 端口 1234 正在监听")
            print("\n详细信息:")
            for line in result.stdout.split('\n'):
                if ':1234' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        local_addr = parts[1]
                        pid = parts[-1]
                        print(f"  地址: {local_addr}")
                        print(f"  PID: {pid}")
        else:
            print("❌ 端口 1234 未监听")
            print("\n请在 LM Studio 中启动服务器:")
            print("  1. 打开 LM Studio")
            print("  2. 在右侧找到 'Server' 或 'Developer' 面板")
            print("  3. 点击 'Start Server'")
    except Exception as e:
        print(f"❌ 检查失败: {e}")


def test_raw_http_response():
    """测试原始 HTTP 响应"""
    print("\n" + "=" * 70)
    print("检查 3: 原始 HTTP 响应")
    print("=" * 70)
    
    try:
        import socket
        
        print("连接到 localhost:1234...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect(('127.0.0.1', 1234))
        print("✅ 连接成功")
        
        # 发送 HTTP 请求
        request = b"GET /v1/models HTTP/1.1\r\nHost: localhost\r\n\r\n"
        print(f"\n发送请求: {request[:50]}...")
        sock.sendall(request)
        
        # 接收响应
        response = sock.recv(4096)
        sock.close()
        
        print(f"\n接收到 {len(response)} 字节")
        
        if response:
            print(f"\n响应内容:")
            try:
                # 尝试解码
                text = response.decode('utf-8', errors='replace')
                print(text)
                
                # 分析响应格式
                if text.startswith('HTTP/'):
                    print("\n✅ 标准 HTTP 响应")
                elif text.startswith('=T'):
                    print("\n⚠️ 非标准响应格式（发现 '=T' 前缀）")
                    print("   这可能是 LM Studio 的编码问题")
                else:
                    print(f"\n⚠️ 未知格式")
            except:
                print(f"无法解码为文本")
                print(f"十六进制: {response[:100].hex()}")
        
    except socket.timeout:
        print("❌ 连接超时")
    except Exception as e:
        print(f"❌ 错误: {e}")


def print_troubleshooting_guide():
    """打印故障排除指南"""
    print("\n" + "=" * 70)
    print("LM Studio 故障排除指南")
    print("=" * 70)
    
    print("\n📋 在 LM Studio 中检查以下设置:")
    print("-" * 70)
    
    print("\n1️⃣ 确认服务器已启动")
    print("   - 在 LM Studio 右侧找到 'Server' 或 'Developer' 标签")
    print("   - 检查 'Start Server' 按钮是否已激活")
    print("   - 应该显示 'Stop Server' 按钮（表示服务器正在运行）")
    
    print("\n2️⃣ 检查服务器配置")
    print("   - Port: 1234（或自定义端口）")
    print("   - Host: 127.0.0.1（localhost）")
    print("   - 查看是否有 'CORS' 或 'Access Control' 设置")
    
    print("\n3️⃣ 检查模型状态")
    print("   - 确认模型已加载")
    print("   - 在 LM Studio 主界面应该能看到模型名称")
    print("   - 首次加载模型可能需要几分钟")
    
    print("\n4️⃣ 查看服务器日志（如果有）")
    print("   - 在 Server 面板中查看是否有错误信息")
    print("   - 检查是否显示 'Server running' 等状态")
    
    print("\n" + "=" * 70)
    print("常见问题")
    print("=" * 70)
    
    print("\n❌ 问题: 服务器返回 'Invalid json' 错误")
    print("解决:")
    print("  1. 在 LM Studio 中停止服务器")
    print("  2. 等待 5 秒钟")
    print("  3. 重新启动服务器")
    print("  4. 如果问题持续，重启 LM Studio 应用")
    
    print("\n❌ 问题: 连接超时")
    print("解决:")
    print("  1. 检查模型是否还在加载中")
    print("  2. 查看 LM Studio 界面是否有加载进度")
    print("  3. 尝试使用更小的模型")
    
    print("\n❌ 问题: 端口被占用")
    print("解决:")
    print("  1. 在 LM Studio 中改用其他端口（如 1235）")
    print("  2. 修改 ai_config.yaml 中的 base_url")
    print("  3. 例如: http://localhost:1235/v1")


def main():
    print("=" * 70)
    print("LM Studio 服务器诊断工具")
    print("=" * 70)
    
    # 运行检查
    check_lm_studio_process()
    check_port_1234()
    test_raw_http_response()
    
    # 显示故障排除指南
    print_troubleshooting_guide()
    
    print("\n" + "=" * 70)
    print("下一步")
    print("=" * 70)
    print("\n1. 根据上面的检查结果，在 LM Studio 中进行相应调整")
    print("2. 修复后，运行以下命令测试:")
    print("   python scripts/test_lm_studio_api.py")
    print("3. 如果成功，enable_thinking=false 配置将自动生效")


if __name__ == "__main__":
    main()
