# TingFengBot API 文档

## 目录

- [公共 API](#公共-api)
- [内部 API](#内部-api)
- [数据库 API](#数据库-api)
- [工具 API](#工具-api)

## 公共 API

### 决策系统 API

#### `should_i_reply`

判断机器人是否应该回复消息。

**函数签名**:
```python
async def should_i_reply(
    group_id: int,
    msg: str,
    is_at_me: bool,
    recent_history: List[str]
) -> Dict[str, Any]
```

**参数**:
- `group_id` (int): 群组 ID
- `msg` (str): 用户消息内容
- `is_at_me` (bool): 是否 @ 机器人
- `recent_history` (List[str]): 最近的消息历史

**返回值**:
```python
{
    "should_reply": bool,      # 是否回复
    "mood_impact": float,      # 情绪影响值 (-1.0 到 1.0)
    "interest_score": float,   # 兴趣评分 (0.0 到 1.0)
    "is_replying_to_bot": bool # 是否是回复机器人的消息
}
```

**示例**:
```python
from src.aimodel.decision.decide import should_i_reply

result = await should_i_reply(
    group_id=123456789,
    msg="你好啊",
    is_at_me=True,
    recent_history=["大家好", "天气不错"]
)

if result["should_reply"]:
    print(f"应该回复，兴趣度: {result['interest_score']}")
```

### 回复生成 API

#### `get_chat_reply`

生成聊天回复。

**函数签名**:
```python
async def get_chat_reply(
    group_id: int,
    user_msg: str,
    user_name: str,
    role: str,
    mood: float
) -> Dict[str, str]
```

**参数**:
- `group_id` (int): 群组 ID
- `user_msg` (str): 用户消息
- `user_name` (str): 用户昵称
- `role` (str): 用户角色
- `mood` (float): 当前心情值 (-1.0 到 1.0)

**返回值**:
```python
{
    "text": str,      # 回复文本
    "sticker": Optional[str]  # 表情包 URL（可选）
}
```

**示例**:
```python
from src.aimodel.reply.chat import get_chat_reply

reply = await get_chat_reply(
    group_id=123456789,
    user_msg="今天天气怎么样？",
    user_name="小明",
    role="member",
    mood=0.5
)

print(f"回复: {reply['text']}")
if reply["sticker"]:
    print(f"表情包: {reply['sticker']}")
```

### 记忆系统 API

#### `consolidate_memories`

将未处理的聊天记录固化为长期记忆。

**函数签名**:
```python
async def consolidate_memories(group_id: int) -> None
```

**参数**:
- `group_id` (int): 群组 ID

**返回值**: None

**说明**:
- 当未处理消息累积超过 50 条时触发
- 自动提取关键信息并存储到向量数据库
- 标记原始消息为已处理

**示例**:
```python
from src.aimodel.memory.consolidation import consolidate_memories

await consolidate_memories(group_id=123456789)
```

### 性格管理 API

#### `PersonalityManager`

性格管理器类，处理性格演化和行为模式。

**方法**:

##### `evolve_personality`

演化性格和用户关系。

**函数签名**:
```python
async def evolve_personality(
    self,
    group_id: int,
    user_name: str,
    user_msg: str
) -> None
```

**参数**:
- `group_id` (int): 群组 ID
- `user_name` (str): 用户昵称
- `user_msg` (str): 用户消息

**示例**:
```python
from src.aimodel.reply.personality import personality_manager

await personality_manager.evolve_personality(
    group_id=123456789,
    user_name="小明",
    user_msg="哈哈，真有意思"
)
```

##### `get_inner_thoughts`

生成内心独白。

**函数签名**:
```python
async def get_inner_thoughts(self, group_id: int, context: str) -> str
```

**参数**:
- `group_id` (int): 群组 ID
- `context` (str): 上下文

**返回值**: 内心独白文本

**示例**:
```python
thoughts = await personality_manager.get_inner_thoughts(
    group_id=123456789,
    context="今天大家聊得很开心"
)
print(f"内心独白: {thoughts}")
```

##### `get_daily_schedule`

生成每日作息表。

**函数签名**:
```python
async def get_daily_schedule(self, group_id: int) -> List[Dict]
```

**参数**:
- `group_id` (int): 群组 ID

**返回值**:
```python
[
    {
        "start": "09:00",
        "end": "10:00",
        "activity": "晨间活动"
    },
    ...
]
```

**示例**:
```python
schedule = await personality_manager.get_daily_schedule(group_id=123456789)
for item in schedule:
    print(f"{item['start']}-{item['end']}: {item['activity']}")
```

##### `capture_style_patterns`

捕获语言风格模式。

**函数签名**:
```python
async def capture_style_patterns(
    self,
    group_id: int,
    history: List[Dict]
) -> None
```

**参数**:
- `group_id` (int): 群组 ID
- `history` (List[Dict]): 聊天历史

**示例**:
```python
from src.utils.db_manager import db_manager

history = db_manager.get_chat_log(group_id=123456789, limit=20)
await personality_manager.capture_style_patterns(group_id, history)
```

##### `mine_slang`

挖掘黑话词汇。

**函数签名**:
```python
async def mine_slang(
    self,
    group_id: int,
    history: List[Dict]
) -> None
```

**参数**:
- `group_id` (int): 群组 ID
- `history` (List[Dict]): 聊天历史

**示例**:
```python
history = db_manager.get_chat_log(group_id=123456789, limit=20)
await personality_manager.mine_slang(group_id, history)
```

## 内部 API

### 向量数据库 API

#### `VectorDB`

向量数据库管理类。

**方法**:

##### `add_memory`

添加记忆到向量数据库。

**函数签名**:
```python
def add_memory(
    self,
    group_id: int,
    text: str,
    vector: List[float],
    metadata: Dict = None
) -> None
```

**参数**:
- `group_id` (int): 群组 ID
- `text` (str): 记忆文本
- `vector` (List[float]): 文本向量
- `metadata` (Dict): 元数据（可选）

**示例**:
```python
from src.aimodel.memory.vector_db import vector_db
from src.aimodel.memory.embeddings import get_embeddings

text = "小明喜欢打篮球"
vectors = await get_embeddings([text])
vector_db.add_memory(
    group_id=123456789,
    text=text,
    vector=vectors[0],
    metadata={"user": "小明", "type": "preference"}
)
```

##### `search_memories`

搜索相关记忆。

**函数签名**:
```python
async def search_memories(
    self,
    group_id: int,
    query: str,
    k: int = 10,
    filter_metadata: Dict = None
) -> List[Dict]
```

**参数**:
- `group_id` (int): 群组 ID
- `query` (str): 查询文本
- `k` (int): 返回结果数量
- `filter_metadata` (Dict): 元数据过滤条件

**返回值**:
```python
[
    {
        "text": str,
        "metadata": Dict,
        "distance": float
    },
    ...
]
```

**示例**:
```python
memories = await vector_db.search_memories(
    group_id=123456789,
    query="小明喜欢什么运动？",
    k=5
)

for mem in memories:
    print(f"{mem['text']} (距离: {mem['distance']:.2f})")
```

##### `delete_memories`

删除记忆。

**函数签名**:
```python
def delete_memories(
    self,
    group_id: int,
    filter_metadata: Dict
) -> None
```

**参数**:
- `group_id` (int): 群组 ID
- `filter_metadata` (Dict): 元数据过滤条件

**示例**:
```python
vector_db.delete_memories(
    group_id=123456789,
    filter_metadata={"user": "小明"}
)
```

### 向量化 API

#### `get_embeddings`

获取文本的向量表示。

**函数签名**:
```python
async def get_embeddings(
    texts: List[str],
    model: str = None
) -> List[List[float]]
```

**参数**:
- `texts` (List[str]): 文本列表
- `model` (str): 模型名称（可选，默认使用配置的模型）

**返回值**: 向量列表

**示例**:
```python
from src.aimodel.memory.embeddings import get_embeddings

texts = ["你好世界", "今天天气不错"]
vectors = await get_embeddings(texts)
print(f"向量维度: {len(vectors[0])}")
```

### 上下文管理 API

#### `ContextManager`

上下文和模型管理器。

**方法**:

##### `get_model`

获取模型配置。

**函数签名**:
```python
def get_model(self, alias: str) -> Dict
```

**参数**:
- `alias` (str): 模型别名

**返回值**:
```python
{
    "model_id": str,
    "max_tokens": int,
    "supports_vision": bool,
    ...
}
```

**示例**:
```python
from src.utils.context_manager import context_manager

model = context_manager.get_model("主模型")
print(f"模型ID: {model['model_id']}")
```

##### `select_model_for_task`

为任务选择合适的模型。

**函数签名**:
```python
def select_model_for_task(
    self,
    task_type: str,
    context_length: int
) -> Dict
```

**参数**:
- `task_type` (str): 任务类型（"chat", "consolidation", "personality" 等）
- `context_length` (int): 上下文长度

**返回值**: 模型配置

**示例**:
```python
model = context_manager.select_model_for_task(
    task_type="chat",
    context_length=500
)
```

##### `track_token_usage`

追踪 Token 使用情况。

**函数签名**:
```python
def track_token_usage(
    self,
    model_alias: str,
    prompt_tokens: int,
    completion_tokens: int
) -> None
```

**参数**:
- `model_alias` (str): 模型别名
- `prompt_tokens` (int): 输入 Token 数
- `completion_tokens` (int): 输出 Token 数

**示例**:
```python
context_manager.track_token_usage(
    model_alias="主模型",
    prompt_tokens=1000,
    completion_tokens=200
)
```

##### `get_token_usage`

获取 Token 使用统计。

**函数签名**:
```python
def get_token_usage(self, model_alias: str = None) -> Dict
```

**参数**:
- `model_alias` (str): 模型别名（可选）

**返回值**:
```python
{
    "total_prompt_tokens": int,
    "total_completion_tokens": int,
    "total_tokens": int,
    "estimated_cost": float
}
```

**示例**:
```python
usage = context_manager.get_token_usage("主模型")
print(f"总Token数: {usage['total_tokens']}")
```

## 数据库 API

#### `DBManager`

数据库管理器，提供所有数据库操作。

**方法**:

##### `add_chat_log`

添加聊天记录。

**函数签名**:
```python
def add_chat_log(
    self,
    group_id: int,
    msg: str
) -> int
```

**参数**:
- `group_id` (int): 群组 ID
- `msg` (str): 消息内容

**返回值**: 记录 ID

**示例**:
```python
from src.utils.db_manager import db_manager

log_id = db_manager.add_chat_log(
    group_id=123456789,
    msg="小明: 今天天气不错"
)
```

##### `get_chat_log`

获取聊天记录。

**函数签名**:
```python
def get_chat_log(
    self,
    group_id: int,
    limit: int = 50,
    offset: int = 0
) -> List[Dict]
```

**参数**:
- `group_id` (int): 群组 ID
- `limit` (int): 返回数量
- `offset` (int): 偏移量

**返回值**:
```python
[
    {
        "id": int,
        "group_id": int,
        "msg": str,
        "timestamp": str
    },
    ...
]
```

**示例**:
```python
logs = db_manager.get_chat_log(group_id=123456789, limit=10)
for log in logs:
    print(f"{log['timestamp']}: {log['msg']}")
```

##### `get_unprocessed_logs`

获取未处理的聊天记录。

**函数签名**:
```python
def get_unprocessed_logs(
    self,
    group_id: int,
    limit: int = 100
) -> List[Dict]
```

**参数**:
- `group_id` (int): 群组 ID
- `limit` (int): 返回数量

**返回值**: 聊天记录列表

**示例**:
```python
unprocessed = db_manager.get_unprocessed_logs(group_id=123456789)
print(f"未处理记录数: {len(unprocessed)}")
```

##### `mark_as_processed`

标记记录为已处理。

**函数签名**:
```python
def mark_as_processed(self, msg_ids: List[int]) -> None
```

**参数**:
- `msg_ids` (List[int]): 记录 ID 列表

**示例**:
```python
db_manager.mark_as_processed([1, 2, 3, 4, 5])
```

##### `add_user_memory`

添加用户记忆。

**函数签名**:
```python
def add_user_memory(
    self,
    group_id: int,
    user_name: str,
    memory: str
) -> None
```

**参数**:
- `group_id` (int): 群组 ID
- `user_name` (str): 用户名
- `memory` (str): 记忆内容

**示例**:
```python
db_manager.add_user_memory(
    group_id=123456789,
    user_name="小明",
    memory="喜欢打篮球"
)
```

##### `get_user_memories`

获取用户记忆。

**函数签名**:
```python
def get_user_memories(
    self,
    group_id: int,
    user_name: str = None,
    limit: int = 10
) -> List[Dict]
```

**参数**:
- `group_id` (int): 群组 ID
- `user_name` (str): 用户名（可选）
- `limit` (int): 返回数量

**返回值**: 用户记忆列表

**示例**:
```python
memories = db_manager.get_user_memories(
    group_id=123456789,
    user_name="小明",
    limit=5
)
for mem in memories:
    print(mem["memory"])
```

##### `update_favorability`

更新用户好感度。

**函数签名**:
```python
def update_favorability(
    self,
    group_id: int,
    user_name: str,
    delta: float
) -> None
```

**参数**:
- `group_id` (int): 群组 ID
- `user_name` (str): 用户名
- `delta` (float): 好感度变化值

**示例**:
```python
db_manager.update_favorability(
    group_id=123456789,
    user_name="小明",
    delta=0.1
)
```

##### `get_favorability`

获取用户好感度。

**函数签名**:
```python
def get_favorability(
    self,
    group_id: int,
    user_name: str
) -> float
```

**参数**:
- `group_id` (int): 群组 ID
- `user_name` (str): 用户名

**返回值**: 好感度值

**示例**:
```python
fav = db_manager.get_favorability(123456789, "小明")
print(f"好感度: {fav:.2f}")
```

##### `add_sticker`

添加表情包。

**函数签名**:
```python
def add_sticker(
    self,
    group_id: int,
    tag: str,
    url: str
) -> None
```

**参数**:
- `group_id` (int): 群组 ID
- `tag` (str): 标签
- `url` (str): 表情包 URL

**示例**:
```python
db_manager.add_sticker(
    group_id=123456789,
    tag="开心",
    url="http://example.com/happy.gif"
)
```

##### `get_sticker`

获取表情包。

**函数签名**:
```python
def get_sticker(self, group_id: int, tag: str) -> Optional[str]
```

**参数**:
- `group_id` (int): 群组 ID
- `tag` (str): 标签

**返回值**: 表情包 URL（如果找到）

**示例**:
```python
url = db_manager.get_sticker(123456789, "开心")
if url:
    print(f"表情包: {url}")
```

##### `get_mood`

获取当前心情值。

**函数签名**:
```python
def get_mood(self, group_id: int) -> float
```

**参数**:
- `group_id` (int): 群组 ID

**返回值**: 心情值

**示例**:
```python
mood = db_manager.get_mood(123456789)
print(f"当前心情: {mood:.2f}")
```

##### `update_mood`

更新心情值。

**函数签名**:
```python
def update_mood(self, group_id: int, delta: float) -> None
```

**参数**:
- `group_id` (int): 群组 ID
- `delta` (float): 心情变化值

**示例**:
```python
db_manager.update_mood(123456789, 0.1)
```

##### `cleanup_old_data`

清理旧数据。

**函数签名**:
```python
def cleanup_old_data(self, days: int = 30) -> Dict[str, int]
```

**参数**:
- `days` (int): 保留最近多少天的数据

**返回值**: 删除记录数统计

**示例**:
```python
stats = db_manager.cleanup_old_data(days=30)
print(f"清理统计: {stats}")
```

##### `vacuum_database`

优化数据库。

**函数签名**:
```python
def vacuum_database(self) -> None
```

**示例**:
```python
db_manager.vacuum_database()
```

## 工具 API

### 日志 API

#### `get_logger`

获取 logger 实例。

**函数签名**:
```python
def get_logger(name: str = None) -> Logger
```

**参数**:
- `name` (str): logger 名称（可选）

**返回值**: Logger 实例

**示例**:
```python
from src.utils.logger import get_logger

logger = get_logger(__name__)
logger.info("这是一条信息")
logger.error("这是一个错误")
logger.debug("这是调试信息")
```

### 性能监控 API

#### `monitor_performance`

性能监控装饰器。

**函数签名**:
```python
def monitor_performance(name: str = None)
```

**参数**:
- `name` (str): 操作名称（可选，默认使用函数名）

**示例**:
```python
from src.utils.performance_monitor import monitor_performance

@monitor_performance("my_function")
async def my_function():
    # 函数实现
    pass

# 函数执行后，性能数据会被自动记录
```

#### `PerformanceMonitor`

性能监控器类。

**方法**:

##### `get_stats`

获取指定操作的统计信息。

**函数签名**:
```python
def get_stats(self, name: str) -> Optional[Dict]
```

**示例**:
```python
from src.utils.performance_monitor import performance_monitor

stats = performance_monitor.get_stats("my_function")
if stats:
    print(f"平均执行时间: {stats['avg_time']:.3f}s")
    print(f"总调用次数: {stats['count']}")
```

##### `get_all_stats`

获取所有统计信息。

**函数签名**:
```python
def get_all_stats(self) -> Dict[str, Dict]
```

**示例**:
```python
all_stats = performance_monitor.get_all_stats()
for name, stats in all_stats.items():
    print(f"{name}: {stats}")
```

##### `log_summary`

打印性能摘要。

**函数签名**:
```python
def log_summary(self) -> None
```

**示例**:
```python
performance_monitor.log_summary()
```

### 并发控制 API

#### `ConcurrencyLimiter`

并发限制器类。

**使用方式**:

作为上下文管理器：
```python
from src.utils.performance_monitor import ConcurrencyLimiter

limiter = ConcurrencyLimiter(max_concurrent=5)

async def some_task():
    async with limiter:
        # 同时最多 5 个任务可以执行
        await do_work()
```

使用装饰器：
```python
from src.utils.performance_monitor import limit_concurrency

@limit_concurrency(max_concurrent=5)
async def some_task():
    # 同时最多 5 个任务可以执行
    await do_work()
```

#### `RateLimiter`

速率限制器类。

**方法**:

##### `acquire`

尝试获取调用许可。

**函数签名**:
```python
async def acquire(self) -> bool
```

**返回值**: 是否成功获取许可

**示例**:
```python
from src.utils.performance_monitor import RateLimiter

limiter = RateLimiter(max_calls=10, time_window=60)

if await limiter.acquire():
    # 执行操作
else:
    # 超过速率限制
    pass
```

##### `wait_for_slot`

等待获取调用许可。

**函数签名**:
```python
async def wait_for_slot(self) -> None
```

**示例**:
```python
await limiter.wait_for_slot()
# 会自动等待，直到可以执行
```

### 错误处理 API

#### `handle_errors`

错误处理装饰器。

**函数签名**:
```python
def handle_errors(
    default_return: Any = None,
    log_level: str = "ERROR",
    reraise: bool = False,
    error_types: tuple = (Exception,)
)
```

**参数**:
- `default_return`: 发生异常时的默认返回值
- `log_level`: 日志级别
- `reraise`: 是否重新抛出异常
- `error_types`: 要捕获的异常类型

**示例**:
```python
from src.utils.error_handler import handle_errors

@handle_errors(default_return=None, log_level="WARNING")
async def risky_function():
    # 可能失败的操作
    pass
```

#### `retry_on_failure`

重试装饰器。

**函数签名**:
```python
def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
)
```

**参数**:
- `max_attempts`: 最大重试次数
- `delay`: 初始延迟时间（秒）
- `backoff`: 退避系数
- `exceptions`: 需要重试的异常类型

**示例**:
```python
from src.utils.error_handler import retry_on_failure

@retry_on_failure(max_attempts=3, delay=1.0, backoff=2.0)
async def unstable_api_call():
    # 不稳定的 API 调用
    pass
```

### 安全 API

#### `InputValidator`

输入验证器类。

**方法**:

##### `validate_text`

验证文本输入。

**函数签名**:
```python
@staticmethod
def validate_text(text: str, max_length: int = 5000) -> Dict[str, Any]
```

**返回值**:
```python
{
    "valid": bool,
    "sanitized": str,
    "reason": Optional[str]
}
```

**示例**:
```python
from src.utils.security import InputValidator

result = InputValidator.validate_text("你好世界")
if result["valid"]:
    text = result["sanitized"]
    # 使用验证后的文本
else:
    print(f"验证失败: {result['reason']}")
```

##### `validate_username`

验证用户名。

**函数签名**:
```python
@staticmethod
def validate_username(username: str) -> Dict[str, Any]
```

**示例**:
```python
result = InputValidator.validate_username("小明")
username = result["sanitized"]
```

#### `SecurityMiddleware`

安全中间件类。

**方法**:

##### `is_user_blocked`

检查用户是否被阻止。

**函数签名**:
```python
def is_user_blocked(self, user_id: int) -> bool
```

**示例**:
```python
from src.utils.security import security_middleware

if security_middleware.is_user_blocked(123456):
    print("用户已被阻止")
```

##### `block_user`

阻止用户。

**函数签名**:
```python
def block_user(self, user_id: int, reason: str = "") -> None
```

**示例**:
```python
security_middleware.block_user(123456, reason="发送恶意消息")
```

##### `unblock_user`

解除用户阻止。

**函数签名**:
```python
def unblock_user(self, user_id: int) -> None
```

**示例**:
```python
security_middleware.unblock_user(123456)
```

## 错误处理

所有 API 函数都可能抛出以下异常：

- `APIError`: API 调用失败
- `DatabaseError`: 数据库操作失败
- `ConfigError`: 配置错误
- `ValidationError`: 数据验证失败

建议使用 try-except 捕获异常：

```python
from src.utils.error_handler import APIError, DatabaseError

try:
    reply = await get_chat_reply(...)
except APIError as e:
    logger.error(f"API 错误: {e}")
except DatabaseError as e:
    logger.error(f"数据库错误: {e}")
except Exception as e:
    logger.error(f"未知错误: {e}")
```

## 最佳实践

1. **使用性能监控装饰器**：为关键函数添加性能监控
2. **添加错误处理**：使用装饰器或 try-except 处理异常
3. **验证输入**：使用 InputValidator 验证用户输入
4. **记录日志**：使用 logger 记录重要操作
5. **控制并发**：使用并发限制器防止资源耗尽
6. **定期清理数据**：使用 cleanup_old_data 清理旧数据
7. **优化数据库**：定期运行 vacuum_database

## 更新日志

- v1.0.0: 初始版本
