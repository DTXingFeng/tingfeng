# TingFengBot 开发指南

本文档为 AI 编码代理提供项目开发规范与指南。

## 构建与测试命令

### 代码格式化与检查
```bash
python -m black src/                    # 格式化代码
python -m ruff check src/               # 代码检查
python -m ruff check --fix src/         # 自动修复
python -m mypy src/                     # 类型检查
```

### 运行测试
```bash
pytest                                  # 所有测试
pytest tests/test_example.py            # 单个测试文件
pytest tests/test_example.py::test_func # 单个测试函数
pytest -v --cov=src --cov-report=html   # 详细输出+覆盖率
pytest -m unit                          # 仅单元测试
pytest -m "not slow"                    # 排除慢速测试
```

### 数据库迁移
```bash
python scripts/migrate_db.py
```

## 代码风格指南

### 导入顺序
```python
# 1. 标准库
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

# 2. 第三方库
import yaml
from pydantic import BaseModel, Field
from openai import AsyncOpenAI

# 3. 本地导入
from src.config.ai_config import ai_config
from src.utils.logger import get_logger
from src.utils.error_handler import handle_errors, APIError
```

### 命名约定
- **类名**: `PascalCase` (BotConfig, ConfigManager, BaseTool)
- **函数名**: `snake_case` (should_i_reply, load_config, safe_execute)
- **变量名**: `snake_case` (bot_config, model_alias, long_term_memories)
- **常量**: `UPPER_SNAKE_CASE` (MAX_TOKENS, DEFAULT_TIMEOUT)
- **私有成员**: 单下划线前缀 `_private_method`

### 类型注解
所有函数必须包含类型注解和文档字符串：

```python
async def should_i_reply(
    group_id: int,
    user_name: str,
    current_msg: str,
    is_at_me: bool = False,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """判断机器人是否应该参与当前对话"""
    pass
```

### 文档字符串
使用三引号文档字符串，说明参数和返回值：

```python
async def execute(self, **kwargs) -> Dict[str, Any]:
    """
    执行工具

    Args:
        **kwargs: 工具参数

    Returns:
        dict: {"success": bool, "data": Any, "error": Optional[str]}
    """
    pass
```

### 错误处理
使用 `try-except` 捕获异常，使用 `logger` 记录错误，优雅降级：

```python
try:
    long_term_memories = vector_db.query_memory(group_id, query_vectors[0], n_results=3)
except Exception as e:
    logger.error(f"查询记忆失败: {e}", exc_info=True)
    long_term_memories = []
```

### 异步编程
- 所有 I/O 操作使用 `async/await`
- 使用 `AsyncOpenAI` 而非同步版本
- 数据库操作使用异步方法
- 避免在异步函数中使用阻塞调用

### Pydantic 模型
使用 Pydantic 进行配置验证，使用 `Field` 设置默认值：

```python
class BotConfig(BaseModel):
    bot_name: str = "听风"
    allowed_groups: List[int] = Field(default_factory=list)
    creator_id: Optional[int] = None
```

### 代码格式
- 行长度限制：120 字符
- 使用 Black 自动格式化
- 使用 Ruff 进行代码质量检查
- 使用 MyPy 进行类型检查（非强制模式）

### 项目特定约定

**MCP 工具开发**：继承 `BaseTool`，实现 `execute` 方法，使用 `tool_registry.register()` 注册

**日志记录**：使用 `get_logger(__name__)`，错误用 `logger.error()`，一般信息用 `logger.info()`

**数据库操作**：使用 `db_manager`，使用异步方法，注意事务管理

**AI 模型调用**：使用 `ai_config_manager` 获取配置，使用 `context_manager.truncate_text()` 处理长文本

**配置管理**：敏感信息在 `.env`（不提交），配置模板用 `.example` 后缀

**测试**：测试文件在 `tests/`，使用 `pytest`，异步测试用 `pytest-asyncio`

### 禁止事项
- ⚠️ **禁止提交包含密钥的配置文件**
- ⚠️ **禁止在代码中硬编码 API Key**
- ⚠️ **禁止使用同步阻塞操作（如 time.sleep, requests）**
- ⚠️ **禁止使用裸 except（必须指定异常类型）**

## 快速参考

### 添加新功能检查清单
1. [ ] 代码符合命名约定
2. [ ] 函数有类型注解和文档字符串
3. [ ] 错误处理完善（try-except + logger）
4. [ ] 使用异步方法（如适用）
5. [ ] 运行 black、ruff、mypy 检查
6. [ ] 添加测试（如适用）

### 常见模式

**安全的异步工具执行**：
```python
logger = get_logger(__name__)
async def safe_tool_call(tool, **kwargs):
    try:
        result = await tool.safe_execute(**kwargs)
        if not result["success"]:
            logger.error(f"工具执行失败: {result['error']}")
            return None
        return result["data"]
    except Exception as e:
        logger.error(f"工具调用异常: {e}", exc_info=True)
        return None
```

**获取配置**：
```python
name = bot_config.bot_name
model = ai_config.decision_model
creds = ai_config_manager.get_model_credentials(model)
```

**日志记录**：
```python
logger = get_logger(__name__)
logger.info("普通信息")
logger.error("错误信息", exc_info=True)
```
