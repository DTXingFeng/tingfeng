# 项目架构文档

## 概述

TingFengBot 是一个基于 NoneBot2 框架和 OneBot V11 协议的深度智能化聊天机器人。它采用模块化设计，集成了多种 AI 技术，包括大语言模型（LLM）、向量数据库、知识图谱等，实现了智能对话、记忆管理、性格演化等功能。

## 系统架构

### 核心组件

```
TingFengBot/
├── bot.py                    # 应用入口
├── src/
│   ├── aimodel/              # AI 模型模块
│   │   ├── decision/         # 决策系统
│   │   │   └── decide.py     # 回复决策
│   │   ├── reply/            # 回复生成
│   │   │   ├── chat.py       # 聊天回复
│   │   │   └── personality.py # 性格管理
│   │   ├── memory/           # 记忆系统
│   │   │   ├── embeddings.py # 向量化
│   │   │   ├── vector_db.py  # 向量数据库
│   │   │   └── consolidation.py # 记忆固化
│   │   └── image_processing/ # 图像处理
│   │       └── vlm.py        # 视觉语言模型
│   ├── config/               # 配置管理
│   │   ├── config.py         # 基础配置
│   │   └── ai_config.py      # AI 配置
│   ├── plugins/              # NoneBot 插件
│   │   └── group_handler.py  # 群消息处理
│   └── utils/                # 工具模块
│       ├── db_manager.py     # 数据库管理
│       ├── message_processor.py # 消息处理
│       ├── context_manager.py # 上下文管理
│       ├── logger.py         # 日志系统
│       ├── error_handler.py  # 错误处理
│       ├── performance_monitor.py # 性能监控
│       └── security.py       # 安全模块
└── requirements.txt          # 依赖列表
```

## 核心模块详解

### 1. 消息处理流程

```
用户消息 → GroupHandler → MessageProcessor → DecisionSystem
                                                ↓
                                         [是否回复?]
                                                ↓
                                  ┌─────────────┴─────────────┐
                                  ↓                           ↓
                              [是]                         [否]
                                  ↓                           ↓
                             ReplyGenerator              丢弃/记录
                                  ↓
                          PersonalityManager
                                  ↓
                          MemoryRetrieval
                                  ↓
                          ContextBuilding
                                  ↓
                          LLM Response
                                  ↓
                          Sticker Selection
                                  ↓
                          发送回复
```

### 2. 决策系统 (Decision System)

**文件**: `src/aimodel/decision/decide.py`

**功能**:
- 判断是否应该回复消息
- 计算消息兴趣度
- 评估情绪影响
- 防止过度回复

**关键方法**:
```python
async def should_i_reply(
    group_id: int,
    msg: str,
    is_at_me: bool,
    recent_history: List[str]
) -> Dict[str, Any]
```

**决策因素**:
- 是否 @ 机器人
- 消息与机器人的相关性
- 群组活跃度
- 最近回复频率
- 消息内容质量

### 3. 回复生成系统 (Reply System)

**文件**: `src/aimodel/reply/chat.py`

**功能**:
- 生成智能回复
- 检索相关记忆
- 应用性格风格
- 选择表情包

**关键方法**:
```python
async def get_chat_reply(
    group_id: int,
    user_msg: str,
    user_name: str,
    role: str,
    mood: float
) -> Dict[str, str]
```

**处理流程**:
1. 检索相关历史记忆（向量搜索）
2. 构建上下文提示词
3. 调用 LLM 生成回复
4. 应用性格风格调整
5. 选择合适的表情包

### 4. 记忆系统 (Memory System)

#### 4.1 短期记忆

**文件**: `src/utils/db_manager.py`

**存储**:
- 聊天历史记录
- 用户关系
- 表情包映射
- 当前心情状态

#### 4.2 长期记忆

**文件**: `src/aimodel/memory/vector_db.py`

**技术**: ChromaDB 向量数据库

**存储内容**:
- 对话摘要
- 事实记忆
- 知识三元组
- 用户偏好

**检索机制**:
```python
async def search_memories(
    group_id: int,
    query: str,
    k: int = 10
) -> List[Dict]
```

#### 4.3 记忆固化

**文件**: `src/aimodel/memory/consolidation.py`

**触发条件**:
- 未处理消息累积超过 50 条

**处理流程**:
1. 获取未处理的聊天记录
2. 使用 LLM 提取关键信息
3. 分解为可检索的记忆碎片
4. 存入向量数据库
5. 标记原始消息为已处理

### 5. 性格管理系统 (Personality System)

**文件**: `src/aimodel/reply/personality.py`

**功能模块**:

#### 5.1 性格演化
- 根据用户互动调整性格参数
- 更新用户好感度
- 演化群组氛围

#### 5.2 作息管理
- 生成每日作息表
- 根据作息调整回复频率

#### 5.3 风格模仿
- 学习群组语言风格
- 提取常用表达模式
- 应用风格权重

#### 5.4 黑话挖掘
- 识别群组特有词汇
- 提炼黑话定义
- 在对话中使用黑话

### 6. 上下文管理 (Context Management)

**文件**: `src/utils/context_manager.py`

**功能**:
- 管理 Token 使用
- 动态选择模型
- 记录模型使用情况

**模型选择策略**:
- 简单任务使用轻量模型
- 复杂任务使用高能力模型
- 根据上下文长度选择模型

### 7. 数据库设计

#### 7.1 关系型数据库 (SQLite)

**表结构**:

| 表名 | 用途 |
|------|------|
| `chat_history` | 聊天记录 |
| `user_mapping` | 用户ID映射 |
| `user_memories` | 用户记忆 |
| `stickers` | 表情包库 |
| `user_relationships` | 用户关系 |
| `style_patterns` | 语言风格 |
| `slang_candidates` | 黑话候选 |
| `knowledge_triplets` | 知识三元组 |
| `personality_state` | 性格状态 |

#### 7.2 向量数据库 (ChromaDB)

**集合**: 按群组 ID 分隔

**元数据**:
- 类型（碎片/用户记忆/事实）
- 时间戳
- 相关用户

### 8. 性能监控

**文件**: `src/utils/performance_monitor.py`

**监控指标**:
- 函数执行时间
- API 调用延迟
- 错误率
- 并发数
- 内存使用

**限流机制**:
- 并发限制器 (`ConcurrencyLimiter`)
- 速率限制器 (`RateLimiter`)

### 9. 日志系统

**文件**: `src/utils/logger.py`

**日志级别**:
- DEBUG: 调试信息
- INFO: 一般信息
- WARNING: 警告
- ERROR: 错误

**日志输出**:
- 控制台（彩色）
- 文件（按日期分割）
- 按级别分类存储

### 10. 安全模块

**文件**: `src/utils/security.py`

**安全措施**:
- 输入验证
- 敏感词过滤
- 用户黑名单
- 可疑行为检测
- 速率限制

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.9+ | 主要开发语言 |
| NoneBot2 | 2.4+ | 聊天机器人框架 |
| OpenAI API | - | LLM 服务 |
| ChromaDB | 0.5+ | 向量数据库 |
| SQLite | 3.x | 关系数据库 |
| Loguru | 0.7+ | 日志系统 |
| Pydantic | 2.x | 数据验证 |
| PyYAML | 6.x | 配置解析 |

## 数据流

### 消息处理数据流

```
[用户消息]
    ↓
[预处理] → 消息清洗 → 文本分段 → 图像识别
    ↓
[决策] → 特征提取 → 模型推理 → [是否回复?]
    ↓
[生成] → 记忆检索 → 上下文构建 → LLM 调用
    ↓
[后处理] → 风格应用 → 表情包选择 → 发送
    ↓
[学习] → 记忆存储 → 性格演化 → 关系更新
```

### 记忆管理数据流

```
[原始消息]
    ↓
[短期存储] → SQLite (chat_history)
    ↓
[触发检查] → 未处理 > 50?
    ↓
[固化处理] → LLM 提取 → 碎片分解
    ↓
[向量化] → Embedding API
    ↓
[长期存储] → ChromaDB
    ↓
[标记完成] → 更新 SQLite
```

## 配置管理

### AI 配置 (ai_config.yaml)

```yaml
models:
  model_list:
    - alias: "轻量模型"
      model_id: "gpt-4o-mini"
      max_tokens: 4096
      supports_vision: false
      use_reasoning: false
      reasoning_model_id: null
    - alias: "主模型"
      model_id: "gpt-4o"
      max_tokens: 128000
      supports_vision: true
      use_reasoning: false
      reasoning_model_id: null
```

### 机器人配置 (config.yaml)

```yaml
bot:
  name: "听风"
  role: "AI助手"
  mood: 0.5
  stickers_dir: "stickers"
```

## 性能优化

### 已实现的优化

1. **数据库索引**
   - 为高频查询字段添加索引
   - 复合索引优化多条件查询

2. **并发控制**
   - 信号量限制并发数
   - 速率限制防止过载

3. **异步处理**
   - 背景任务异步执行
   - 不阻塞主消息处理

4. **批量操作**
   - 批量向量计算
   - 批量数据库写入

5. **缓存机制**
   - 向量缓存（可扩展）
   - 上下文缓存

### 可扩展的优化

1. Redis 缓存层
2. 消息队列（如 Celery）
3. 分布式向量数据库
4. 数据库读写分离

## 部署架构

### 单机部署

```
┌─────────────────────────────┐
│      TingFengBot            │
│  ┌──────────────────────┐  │
│  │   NoneBot2 Core      │  │
│  ├──────────────────────┤  │
│  │   AI Models          │  │
│  ├──────────────────────┤  │
│  │   Memory System      │  │
│  ├──────────────────────┤  │
│  │   SQLite + ChromaDB  │  │
│  └──────────────────────┘  │
└─────────────────────────────┘
```

### 分布式部署（建议）

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Bot 1     │     │   Bot 2     │     │   Bot N     │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                  ┌────────┴────────┐
                  │  Message Queue  │
                  └────────┬────────┘
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐
│  Vector DB  │    │  Redis      │    │  PostgreSQL │
│  (ChromaDB) │    │  Cache      │    │  Database   │
└─────────────┘    └─────────────┘    └─────────────┘
```

## 扩展点

### 1. 自定义回复策略

位置: `src/aimodel/reply/chat.py`

可以通过继承或修改 `get_chat_reply` 函数实现自定义回复策略。

### 2. 自定义决策逻辑

位置: `src/aimodel/decision/decide.py`

修改 `should_i_reply` 函数实现自定义决策规则。

### 3. 自定义记忆检索

位置: `src/aimodel/memory/vector_db.py`

修改 `search_memories` 函数实现自定义检索策略。

### 4. 自定义性格模块

位置: `src/aimodel/reply/personality.py`

可以添加新的性格特征和行为模式。

## 测试策略

### 单元测试

- 测试核心逻辑函数
- Mock 外部依赖
- 覆盖率目标: 80%+

### 集成测试

- 测试模块间交互
- 使用测试数据库
- 模拟真实消息流

### 端到端测试

- 完整的消息处理流程
- 性能测试
- 压力测试

## 监控和告警

### 监控指标

- 消息处理延迟
- API 调用成功率
- 数据库查询性能
- 内存/CPU 使用率
- 错误率

### 告警条件

- API 失败率 > 5%
- 平均响应时间 > 5s
- 错误率 > 1%
- 内存使用 > 90%

## 故障排查

### 常见问题

1. **回复延迟高**
   - 检查 API 响应时间
   - 检查数据库查询性能
   - 检查并发限制

2. **回复质量差**
   - 检查上下文长度
   - 检查记忆相关性
   - 检查模型选择

3. **内存占用高**
   - 检查向量数据库大小
   - 检查缓存使用
   - 运行数据库清理

4. **数据库查询慢**
   - 检查索引是否创建
   - 运行 VACUUM 优化
   - 清理旧数据

## 开发指南

### 添加新功能

1. 确定功能所属模块
2. 在对应目录创建文件
3. 实现核心逻辑
4. 添加错误处理和日志
5. 编写单元测试
6. 更新文档

### 代码规范

- 使用 `black` 格式化代码
- 使用 `ruff` 检查代码质量
- 使用 `mypy` 进行类型检查
- 编写清晰的文档字符串
- 遵循 PEP 8 规范

### 贡献流程

1. Fork 项目
2. 创建特性分支
3. 提交变更
4. 推送到分支
5. 创建 Pull Request

## 许可证

MIT License
