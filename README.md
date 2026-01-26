# TingFengBot (听风)

一个基于 NoneBot2 和 OneBot V11 协议的深度智能化聊天机器人。它不仅能聊天，还具备“察言观色”的决策能力、长短期记忆系统以及智能表情包互动功能。

## ✨ 核心特性

- 🧠 **智能决策系统 (Decision Making)**：
  - 不再仅仅依赖艾特或随机概率。
  - 使用小模型（如 Qwen-7B）实时分析对话语境，判断用户是否在接话或话题是否符合人设兴趣，实现自然插话。
  - 具备**决策冷却机制**，避免在活跃群聊中过度打扰。

- 📚 **多维记忆系统 (Memory System)**：
  - **短期记忆**：基于数据库的最近对话上下文。
  - **长期记忆 (RAG)**：基于 ChromaDB 向量数据库，通过语义搜索找回很久以前的往事。
  - **用户画像与细节记忆**：自动提炼用户的性格特征（Profile）和具体事实（Specific Memories，如职业、爱好），实现“越聊越懂你”。

- 🖼️ **智能视觉与表情包 (VLM & Sticker)**：
  - **看图识梗**：集成 Qwen2-VL-72B，能够精准识别图片、梗图及表情包内容。
  - **表情包缓存**：通过图片哈希（MD5）匹配，识别过的表情包将秒回缓存结果，极大节省 API 开销。
  - **主动斗图**：AI 会根据语境主动选择合适的表情包标签，系统自动从库中匹配并发送。

- 🎭 **人设高度可定制**：
  - 身份设定与核心代码完全解耦。
  - 只需修改 `config.yaml`，即可将机器人从“二次元少女”转变为任何你想要的角色。

- 🛡️ **群组管理**：
  - 完善的白名单/黑名单过滤机制，精确控制机器人的活动范围。

## 📁 项目结构

```
tingfengbot/
├── src/
│   ├── aimodel/
│   │   ├── decision/      # 智能决策逻辑 (Reasoner/LLM)
│   │   ├── image_processing/ # VLM 图像识别与处理
│   │   ├── memory/        # 向量库、记忆固化与 Embedding
│   │   └── reply/         # 核心回复生成逻辑
│   ├── config/            # 机器人与 AI 模型配置解析
│   ├── plugins/           # NoneBot 插件 (业务核心)
│   └── utils/             # 数据库管理 (SQLite) 与消息清洗
├── data/                  # 数据库与向量库存储 (Git 忽略)
├── scripts/               # 数据库迁移、功能测试等实用脚本
├── bot.py                 # 程序入口
└── config.yaml            # 机器人行为配置
```

## 🚀 快速开始

### 1. 安装环境
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置文件
- 复制 `ai_config.yaml.example` -> `ai_config.yaml`：配置你的 OpenAI/SiliconFlow API Key。
- 复制 `config.yaml.example` -> `config.yaml`：设置机器人名字、人设及白名单群号。
- 复制 `.env.example` -> `.env`：配置 NoneBot 运行环境及 WebSocket 地址。

### 3. 初始化数据库
第一次运行前，建议运行迁移脚本确保数据库结构最新：
```bash
python scripts/migrate_db.py
```

### 4. 启动
```bash
python bot.py
```

## 🛠️ 技术栈
- **框架**: NoneBot2 / OneBot V11
- **AI 接口**: OpenAI SDK (兼容 DeepSeek, SiliconFlow 等)
- **数据库**: SQLite (关系型) / ChromaDB (向量型)
- **视觉**: PIL / Qwen2-VL

## ⚠️ 注意事项
- 本项目默认不响应私聊消息。
- 请确保你的 API Key 余额充足，建议使用硅基流动等高性价比平台。
- 包含密钥的 `*.yaml` 和 `data/` 目录已被加入 `.gitignore`，请放心开发。
