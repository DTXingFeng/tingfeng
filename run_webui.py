"""
启动 Web UI
使用方式: python run_webui.py
"""

from __future__ import annotations

import os
import sys

import uvicorn


def _ensure_project_root_on_path() -> None:
    """确保项目根目录在 sys.path 中"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def main() -> None:
    """启动 Web UI"""
    _ensure_project_root_on_path()
    uvicorn.run("src.webui.app:app", host="0.0.0.0", port=8765, reload=False)


if __name__ == "__main__":
    main()
