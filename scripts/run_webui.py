"""
启动 Web UI
使用方式: python scripts/run_webui.py
"""

import uvicorn


def main() -> None:
    """启动 Web UI"""
    uvicorn.run("src.webui.app:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    main()
