# MCP (Model Context Protocol) 工具包

为听风 bot 提供可扩展的工具调用能力。

## 📁 目录结构

```
src/mcp/
├── __init__.py          # 包入口
├── base_tool.py         # 工具基类
├── registry.py          # 工具注册中心（单例）
├── loader.py           # 工具加载器
├── tools/              # 工具实现目录
│   ├── __init__.py
│   ├── memory.py        # 记忆相关工具
│   ├── user.py          # 用户相关工具
│   ├── knowledge.py      # 知识图谱工具
│   └── utility.py       # 实用工具
└── README.md           # 本文档
```

## 🛠️ 已实现的工具

### 记忆工具
- **memory_search**: 搜索长期记忆（向量数据库）
- **get_user_memories**: 获取用户的具体记忆
- **add_memory**: 主动添加记忆

### 用户工具
- **get_user_profile**: 获取用户完整画像
- **get_creator_info**: 获取创造者信息
- **update_relationship**: 更新关系状态

### 知识工具
- **knowledge_query**: 查询知识图谱
- **get_creator_knowledge**: 查询创造者相关知识
- **add_knowledge**: 添加知识三元组

### 实用工具
- **get_current_time**: 获取当前时间
- **is_within_schedule**: 检查作息表状态
- **format_text**: 文本格式化
- **count_words**: 字数统计

## 🚀 快速开始

### 1. 自动加载（推荐）

工具会在 bot 启动时自动加载：

```python
# bot.py 中已配置
@driver.on_startup
async def load_mcp_tools():
    from src.mcp.loader import load_all_tools
    await load_all_tools()
```

### 2. 手动注册工具

如果你想添加自定义工具：

```python
from src.mcp.base_tool import BaseTool
from src.mcp.registry import tool_registry

class MyCustomTool(BaseTool):
    name = "my_tool"
    description = "我的自定义工具"
    parameters = {
        "input": {
            "type": "string",
            "description": "输入内容",
            "required": True
        }
    }
    
    async def execute(self, input: str) -> dict:
        return {
            "result": f"处理了: {input}",
            "success": True
        }

# 注册工具
tool_registry.register(MyCustomTool())
```

### 3. 调用工具

```python
from src.mcp.registry import tool_registry

# 直接调用
result = await tool_registry.execute("get_current_time")
if result["success"]:
    print(f"当前时间: {result['data']['datetime']}")
```

## 📊 工具定义格式

每个工具必须实现以下属性和方法：

```python
class MyTool(BaseTool):
    # 工具名称（必须）
    name: str = "tool_name"
    
    # 工具描述（必须）
    description: str = "工具的用途说明"
    
    # 参数定义（必须）
    parameters: Dict[str, Any] = {
        "param1": {
            "type": "string|integer|boolean",
            "description": "参数说明",
            "required": True|False
        }
    }
    
    # 执行方法（必须，异步）
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        返回格式：
        {
            "success": bool,
            "data": Any,
            "error": Optional[str]
        }
        """
        pass
```

## 🔌 与 OpenAI Function Calling 集成

工具注册后会自动转换为 OpenAI function calling 格式：

```python
from src.mcp.registry import tool_registry

# 获取所有工具定义
functions = tool_registry.get_all_definitions()

# 在调用 LLM 时传入
response = await client.chat.completions.create(
    model=creds["model"],
    messages=messages,
    functions=functions,
    function_call="auto"
)
```

## ⚙️ 配置

复制 `mcp_config.yaml.example` 到 `mcp_config.yaml` 并根据需要调整配置。

## 🧪 测试

运行工具加载测试：

```bash
python src/mcp/loader.py
```

这会：
- 加载所有工具
- 显示工具摘要
- 测试工具调用

## 🔒 安全注意事项

1. **敏感操作**：`add_memory`、`add_knowledge` 等工具应谨慎使用
2. **参数验证**：所有参数都会被严格验证
3. **错误处理**：所有工具调用都有异常捕获
4. **日志记录**：建议开启日志记录所有工具调用

## 💡 扩展建议

### 添加新工具的最佳实践

1. **命名规范**：使用 `verb_noun` 格式（如 `get_user_profile`）
2. **描述清晰**：描述要说明工具的用途、参数含义、返回格式
3. **异步优先**：所有耗时操作都应该用 `async`
4. **错误处理**：返回统一格式的错误信息
5. **日志记录**：使用 `logger` 记录关键操作

### 工具分类

建议按功能分类组织：

- `memory_*`: 记忆相关
- `user_*`: 用户相关
- `knowledge_*`: 知识相关
- `emotion_*`: 情感分析
- `utility_*`: 实用工具
- `control_*`: 控制类

## 📝 许可证

与听风 bot 项目保持一致。
