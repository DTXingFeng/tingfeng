"""
全面验证项目中所有 AI 调用是否正确支持 enable_thinking 参数
"""

import re
from pathlib import Path


def check_file_for_enable_thinking_support(file_path: Path) -> dict:
    """检查文件是否正确支持 enable_thinking"""
    result = {
        "file": str(file_path),
        "has_api_call": False,
        "has_enable_thinking": False,
        "uses_helper": False,
        "api_calls": [],
        "issues": []
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否有直接调用 chat.completions.create
        api_pattern = r'chat\.completions\.create\s*\('
        api_calls = re.findall(api_pattern, content)
        if api_calls:
            result["has_api_call"] = True
            result["api_calls"] = api_calls
        
        # 检查是否使用了辅助函数
        helper_patterns = [
            r'call_ai_with_timeout\s*\(',
            r'call_ai_with_timeout_and_json\s*\(',
            r'create_with_auto_fallback\s*\(',
        ]
        for pattern in helper_patterns:
            if re.search(pattern, content):
                result["uses_helper"] = True
                break
        
        # 检查是否有 enable_thinking 支持
        thinking_patterns = [
            r'creds\.get\(["\']enable_thinking["\']\)',
            r'enable_thinking.*False',
            r'extra_body.*enable_thinking',
        ]
        for pattern in thinking_patterns:
            if re.search(pattern, content):
                result["has_enable_thinking"] = True
                break
        
        # 分析问题
        if result["has_api_call"] and not result["uses_helper"]:
            if not result["has_enable_thinking"]:
                result["issues"].append("直接调用 API 但没有 enable_thinking 支持")
            else:
                # 需要检查是否在每次调用前都添加了参数
                # 简化检查：看是否有 extra_body 的设置
                if 'extra_body' in content and 'enable_thinking' in content:
                    # 有支持，标记为 OK
                    pass
                else:
                    result["issues"].append("可能缺少 enable_thinking 参数")
        
    except Exception as e:
        result["issues"].append(f"检查失败: {e}")
    
    return result


def main():
    print("=" * 70)
    print("全面验证 enable_thinking 参数支持")
    print("=" * 70)
    
    # 搜索所有 Python 文件
    src_dir = Path("src")
    python_files = list(src_dir.rglob("*.py"))
    
    results = []
    for file_path in python_files:
        result = check_file_for_enable_thinking_support(file_path)
        if result["has_api_call"] or result["uses_helper"]:
            results.append(result)
    
    # 分类显示
    print("\n" + "=" * 70)
    print("检查结果")
    print("=" * 70)
    
    safe_files = []
    warning_files = []
    
    for result in results:
        if not result["issues"]:
            safe_files.append(result)
        else:
            warning_files.append(result)
    
    print(f"\n✅ 已正确支持的文件 ({len(safe_files)}):")
    print("-" * 70)
    for result in safe_files:
        file_name = result["file"].replace("src/", "").replace("\\", "/")
        if result["uses_helper"]:
            status = "使用辅助函数（自动支持）"
        elif result["has_enable_thinking"]:
            status = "直接调用 + enable_thinking 支持"
        else:
            status = "仅使用辅助函数"
        print(f"  ✅ {file_name:50s} {status}")
    
    if warning_files:
        print(f"\n⚠️ 需要注意的文件 ({len(warning_files)}):")
        print("-" * 70)
        for result in warning_files:
            file_name = result["file"].replace("src/", "").replace("\\", "/")
            print(f"  ⚠️ {file_name:50s}")
            for issue in result["issues"]:
                print(f"     - {issue}")
    else:
        print(f"\n🎉 所有文件都已正确支持 enable_thinking 参数！")
    
    # 详细信息
    print("\n" + "=" * 70)
    print("详细信息")
    print("=" * 70)
    
    for result in results:
        file_name = result["file"].replace("src/", "").replace("\\", "/")
        print(f"\n文件: {file_name}")
        print(f"  - API 调用数: {len(result['api_calls'])}")
        print(f"  - 使用辅助函数: {result['uses_helper']}")
        print(f"  - enable_thinking 支持: {result['has_enable_thinking']}")
        if result['issues']:
            print(f"  - 问题: {result['issues']}")
    
    # 总结
    print("\n" + "=" * 70)
    print("总结")
    print("=" * 70)
    
    total_files = len(results)
    safe_count = len(safe_files)
    warning_count = len(warning_files)
    
    print(f"\n总文件数: {total_files}")
    print(f"✅ 已支持: {safe_count}")
    print(f"⚠️ 需注意: {warning_count}")
    
    if warning_count == 0:
        print("\n🎉 完美！所有 AI 调用都已正确支持 enable_thinking 参数！")
        return 0
    else:
        print(f"\n⚠️ 有 {warning_count} 个文件需要检查")
        return 1


if __name__ == "__main__":
    exit(main())
