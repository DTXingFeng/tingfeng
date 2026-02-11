# TingFengBot 代理编码指南

本文档为在此代码库中工作的 AI 代理提供必要的信息。

## 项目概述

TingFengBot（听风）是一个基于 NoneBot2 和 OneBot V11 协议的深度智能化聊天机器人。它具备智能决策、差异化人际关系、长短期记忆系统和智能表情包互动功能。

## 技术栈

- **框架**: NoneBot2 / OneBot V11
- **语言**: Python 3.9+
- **AI 接口**: OpenAI SDK（兼容 DeepSeek、SiliconFlow 等）
- **数据库**: SQLite（关系型）/ ChromaDB（向量型）
- **配置管理**: Pydantic + YAML
- **异步**: asyncio

## 构建/检查/测试命令

### 基本命令

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

# 运行所有测试
pytest

# 运行单个测试文件
pytest tests/test_example.py

# 运行单个测试函数
pytest tests/test_example.py::test_specific_function

# 运行带覆盖率的测试
pytest --cov=src --cov-report=term-missing

# 运行特定标记的测试
pytest -m unit          # 仅运行单元测试
pytest -m integration   # 仅运行集成测试
pytest -m "not slow"    # 排除慢速测试
```

### 数据库迁移

```bash
# 运行数据库迁移
python scripts/migrate_db.py

# 初始化数据库
python -c "from src.utils.init_memory import initialize_all_groups; import asyncio; asyncio.run(initialize_all_groups())"
```

### 启动机器人

```bash
python bot.py
```

## 代码风格指南

### 导入顺序

遵循以下导入顺序（使用 ruff 自动排序）：

1. 标准库导入
2. 第三方库导入
3. 本地应用导入（从 `src` 开始）

```python
# 标准库
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# 第三方库
import nonebot
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

# 本地导入
from src.config.config import bot_config
from src.utils.logger import get_logger
from src.utils.error_handler import handle_errors
```

### 格式化

- **行长度**: 120 字符（由 black 和 ruff 强制执行）
- **缩进**: 4 个空格
- **字符串引号**: 优先使用双引号 `"`
- **文档字符串**: 使用三重双引号 `"""`

### 类型提示

**所有函数都必须包含类型提示**：

```python
async def get_chat_reply(
    group_id: int,
    user_name: str,
    current_msg: str,
    user_id: Optional[int] = None,
    reply_message_id: Optional[int] = None,
    bot=None,
) -> Dict[str, any]:
    """获取 AI 回复逻辑"""
    pass
```

**常用类型导入**：
```python
from typing import Dict, List, Optional, Any, Callable, Tuple
```

### 命名约定

- **类名**: `PascalCase`（例如 `BotConfig`, `BaseTool`）
- **函数和变量**: `snake_case`（例如 `get_chat_reply`, `user_name`）
- **常量**: `UPPER_SNAKE_CASE`（例如 `MAX_RETRIES`）
- **私有方法**: 以前缀 `_` 开头（例如 `_internal_method`）
- **异步函数**: 以 `async` 开头或在必要时使用 `async def`

### 文档字符串

**所有公共函数、类和方法都必须有中文文档字符串**：

```python
async def get_chat_reply(
    group_id: int,
    user_name: str,
    current_msg: str,
) -> Dict[str, any]:
    """
    获取 AI 回复逻辑
    
    Args:
        group_id: 群组 ID
        user_name: 用户名称
        current_msg: 当前消息内容
        
    Returns:
        包含回复文本和表情包 URL 的字典
    """
    pass
```

### 错误处理

**使用自定义异常类**（定义在 `src.utils.error_handler`）：

```python
from src.utils.error_handler import BotError, APIError, DatabaseError, ConfigError, ValidationError
```

**使用错误处理装饰器**：

```python
from src.utils.error_handler import handle_errors

@handle_errors(default_return={"error": "处理失败"}, log_level="ERROR")
async def process_message(msg: str) -> Dict[str, Any]:
    # 处理逻辑
    pass
```

**直接异常处理**：

```python
try:
    result = await some_operation()
except APIError as e:
    logger.error(f"API 调用失败: {e}")
    return {"error": str(e)}
except Exception as e:
    logger.error(f"未知错误: {e}", exc_info=True)
    raise
```

### 异步编程

**所有 I/O 操作都必须是异步的**：

```python
async def fetch_data() -> Dict[str, Any]:
    # 使用异步客户端
    async with AsyncClient() as client:
        response = await client.get(url)
        return response.json()
```

**避免在异步函数中使用阻塞操作** - 如果必须使用阻塞操作，在线程池中运行：

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

def blocking_operation():
    # 阻塞操作
    pass

async def async_wrapper():
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        result = await loop.run_in_executor(pool, blocking_operation)
    return result
```

### 日志

**使用统一的日志记录器**（定义在 `src.utils.logger`）：

```python
from src.utils.logger import get_logger

logger = get_logger(__name__)

logger.debug("调试信息")
logger.info("一般信息")
logger.warning("警告信息")
logger.error("错误信息")
```

### 配置管理

**使用 Pydantic 模型进行配置**：

```python
from pydantic import BaseModel, Field
from typing import Optional, List

class MyConfig(BaseModel):
    name: str = "默认值"
    enabled: bool = True
    items: List[str] = Field(default_factory=list)
```

**访问全局配置**：

```python
from src.config.config import bot_config
from src.config.ai_config import ai_config

# 使用配置
bot_name = bot_config.bot_name
model = ai_config.reply_model
```

### 数据库操作

**使用数据库管理器**（定义在 `src.utils.db_manager`）：

```python
from src.utils.db_manager import db_manager

# 异步数据库操作
await db_manager.save_chat_log(group_id, user_name, message)
logs = await db_manager.get_chat_log(group_id, limit=20)
```

### MCP 工具开发

**创建新工具**：

1. 继承 `BaseTool` 类
2. 定义 `name`, `description`, `parameters`
3. 实现 `execute` 方法
4. 在工具加载器中注册

```python
from src.mcp.base_tool import BaseTool
from typing import Dict, Any

class MyCustomTool(BaseTool):
    name = "my_tool"
    description = "我的自定义工具描述"
    parameters = {
        "input": {
            "type": "string",
            "description": "输入参数",
            "required": True
        }
    }
    
    async def execute(self, input: str) -> Dict[str, Any]:
        """执行工具逻辑"""
        result = process(input)
        return {"success": True, "data": result}
```

### 插件开发

**创建 NoneBot 插件**（放在 `src/plugins/` 目录）：

```python
import nonebot
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent

# 注册命令
matcher = on_command("hello", priority=10, block=True)

@matcher.handle()
async def handle_hello(bot: Bot, event: GroupMessageEvent):
    user_id = event.user_id
    group_id = event.group_id
    await matcher.send(f"你好，用户 {user_id}！")
```

### 测试

**测试文件命名**：
- 单元测试：`tests/test_*.py` 或 `tests/*_test.py`
- 测试类：以 `Test` 开头
- 测试函数：以 `test_` 开头

**使用 pytest 和 pytest-asyncio**：

```python
import pytest
from src.my_module import my_function

@pytest.mark.asyncio
async def test_my_function():
    result = await my_function("test_input")
    assert result == "expected_output"

@pytest.mark.unit
def test_sync_function():
    result = my_sync_function()
    assert result is not None

@pytest.mark.slow
@pytest.mark.asyncio
async def test_slow_operation():
    # 慢速测试
    pass
```

## 项目结构理解

```
src/
├── aimodel/          # AI 模型相关（决策、记忆、回复）
│   ├── decision/     # 智能决策逻辑
│   ├── image_processing/  # VLM 图像识别
│   ├── memory/       # 记忆管理（向量库、固化）
│   └── reply/        # 回复生成逻辑
├── mcp/              # MCP 工具调用系统
│   ├── tools/        # 内置工具集
│   ├── base_tool.py  # 工具基类
│   ├── registry.py   # 工具注册中心
│   └── loader.py     # 工具加载器
├── config/           # 配置管理
├── plugins/          # NoneBot 插件（业务逻辑）
└── utils/            # 工具函数（数据库、日志、错误处理）
```

## 重要注意事项

1. **使用中文**：这是一个中文项目，所有注释、文档字符串和用户提示都应使用中文
2. **异常处理**：始终使用适当的异常处理，尤其是对于 I/O 操作和 API 调用
3. **日志记录**：使用适当的日志级别，记录足够的调试信息
4. **类型提示**：所有函数都必须有类型提示
5. **异步优先**：所有 I/O 操作都应该是异步的
6. **配置验证**：使用 Pydantic 进行配置验证
7. **代码格式化**：在提交前运行 `black .` 和 `ruff check .`

## 代码提交前检查清单

- [ ] 运行 `black .` 格式化代码
- [ ] 运行 `ruff check .` 检查代码质量
- [ ] 运行 `mypy src/` 进行类型检查
- [ ] 运行 `pytest` 确保所有测试通过
- [ ] 更新相关文档字符串
- [ ] 确保所有函数都有类型提示
- [ ] 确保所有异步操作都使用 `async/await`
