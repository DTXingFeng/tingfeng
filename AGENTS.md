# TingFengBot 代理编码指南（精简版）

本文件用于指导在此仓库工作的智能代理。内容基于当前项目约定，重点包括构建/检查/测试命令，以及统一的代码风格与工程习惯。

## 目录

- 项目概述
- 构建/检查/测试命令
- 代码风格与约定
- 项目结构速览
- 开发注意事项
- 提交前检查

## 项目概述

- 框架：NoneBot2 / OneBot V11
- 语言：Python 3.9+
- AI 接口：OpenAI SDK（兼容 DeepSeek、SiliconFlow 等）
- 数据库：SQLite + ChromaDB
- 配置：Pydantic + YAML
- 并发：asyncio

## 构建/检查/测试命令

```bash
# 安装依赖
pip install -r requirements.txt

# 安装开发依赖
pip install -e ".[dev]"

# 代码格式化
black .

# 代码检查
ruff check .

# 类型检查
mypy src/

# 运行全部测试
pytest

# 运行单个测试文件
pytest tests/test_example.py

# 运行单个测试函数
pytest tests/test_example.py::test_specific_function

# 运行带覆盖率的测试
pytest --cov=src --cov-report=term-missing

# 仅运行特定标记
pytest -m unit
pytest -m integration
pytest -m "not slow"
```

### 数据库与启动

```bash
# 数据库迁移
python scripts/migrate_db.py

# 初始化数据库
python -c "from src.utils.init_memory import initialize_all_groups; import asyncio; asyncio.run(initialize_all_groups())"

# 启动机器人
python bot.py
```

## 代码风格与约定

### 语言与注释

- 代码注释、文档字符串、UI 文本、用户提示全部使用中文
- 文档字符串使用三重双引号 `"""`

### 导入顺序

1. 标准库
2. 第三方库
3. 本地导入（以 `src` 起始）

```python
# 标准库
import os
from typing import Any, Dict, Optional

# 第三方库
import nonebot
from pydantic import BaseModel

# 本地导入
from src.config.config import bot_config
from src.utils.logger import get_logger
```

### 格式化与样式

- 行长度：120 字符
- 缩进：4 空格
- 字符串引号：优先双引号
- 代码格式化：`black .`
- 代码检查：`ruff check .`

### 类型提示

- **所有函数都必须包含类型提示**
- 异步函数返回类型要显式标注
- 常用类型请从 `typing` 导入

```python
from typing import Any, Dict, Optional

async def get_chat_reply(
    group_id: int,
    user_name: str,
    current_msg: str,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """获取 AI 回复逻辑"""
    ...
```

### 命名规范

- 类名：`PascalCase`
- 函数/变量：`snake_case`
- 常量：`UPPER_SNAKE_CASE`
- 私有成员：前缀 `_`
- 异步函数：使用 `async def`，命名仍为 `snake_case`

### 错误处理

- 优先使用 `src.utils.error_handler` 中的自定义异常
- I/O 或外部调用必须捕获并记录异常
- 日志使用 `src.utils.logger.get_logger`

```python
from src.utils.error_handler import handle_errors
from src.utils.logger import get_logger

logger = get_logger(__name__)

@handle_errors(default_return={"error": "处理失败"}, log_level="ERROR")
async def process_message(msg: str) -> Dict[str, Any]:
    """处理消息"""
    ...
```

### 异步与 I/O

- 所有 I/O 必须异步
- 必须避免在异步函数中执行阻塞调用
- 必要时使用线程池包装阻塞操作

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

def blocking_operation() -> None:
    ...

async def async_wrapper() -> None:
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, blocking_operation)
```

### 配置与数据库

- 配置使用 Pydantic 模型
- 全局配置从 `src.config.config` / `src.config.ai_config` 获取
- 数据库操作通过 `src.utils.db_manager`

```python
from src.config.config import bot_config
from src.utils.db_manager import db_manager

bot_name = bot_config.bot_name
await db_manager.save_chat_log(group_id, user_name, message)
```

### 测试约定

- 测试文件：`tests/test_*.py` 或 `tests/*_test.py`
- 测试类：`Test` 前缀
- 测试函数：`test_` 前缀
- 使用 `pytest` + `pytest-asyncio`

```python
import pytest

@pytest.mark.asyncio
async def test_my_function() -> None:
    ...
```

## 项目结构速览

```
src/
├── aimodel/          # 决策、记忆、回复
├── mcp/              # MCP 工具系统
├── config/           # 配置管理
├── plugins/          # NoneBot 插件
└── utils/            # 数据库、日志、错误处理
```

## 开发注意事项

- 中文项目：注释与用户提示必须中文
- 异常必须记录日志
- 所有函数必须有类型提示
- I/O 操作必须异步
- 提交前务必格式化与检查

## 提交前检查

- `black .`
- `ruff check .`
- `mypy src/`
- `pytest`
