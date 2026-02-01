import sys
import os
import traceback
from pathlib import Path

# 将项目根目录加入 path
root_path = Path(__file__).parent.parent.absolute()
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

def test_imports():
    print("=== TingFengBot Import Diagnostic ===")
    print(f"Python version: {sys.version}")
    print(f"Current directory: {Path.cwd()}")
    print("-" * 40)

    modules_to_test = [
        "nonebot",
        "chromadb",
        "tiktoken",
        "openai",
        "PIL",
        "src.config.config",
        "src.utils.db_manager",
        "src.utils.logger",
        "src.plugins.group_handler"
    ]

    for module_name in modules_to_test:
        try:
            print(f"Testing import: {module_name}...", end=" ", flush=True)
            __import__(module_name)
            print("✅ SUCCESS")
        except ImportError as e:
            print(f"❌ FAILED (ImportError)")
            print(f"   Reason: {e}")
        except PermissionError as e:
            print(f"❌ FAILED (PermissionError)")
            print(f"   Reason: {e}")
            print(f"   Hint: Run 'sudo chown -R $USER:$USER {root_path}'")
        except Exception as e:
            print(f"❌ FAILED ({type(e).__name__})")
            print(f"   Reason: {e}")
            if "unable to open database file" in str(e):
                print(f"   Hint: Check permissions for the 'data' directory.")
        print("-" * 20)

    # 检查目录权限
    print("\n=== Directory Permission Check ===")
    dirs_to_check = ["data", "logs", "stickers"]
    for d in dirs_to_check:
        d_path = root_path / d
        print(f"Checking directory: {d}...", end=" ")
        if not d_path.exists():
            try:
                d_path.mkdir(parents=True, exist_ok=True)
                print("✅ Created")
            except Exception as e:
                print(f"❌ Cannot create ({e})")
        else:
            if os.access(d_path, os.W_OK):
                print("✅ Writable")
            else:
                print("❌ Not Writable")

if __name__ == "__main__":
    test_imports()
