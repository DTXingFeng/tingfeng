# TingFengBot (听风)

一个基于 NoneBot2 和 OneBot V11 协议的深度智能化聊天机器人。它不仅能聊天，还具备“察言观色”的决策能力、长短期记忆系统以及智能表情包互动功能。

> [!IMPORTANT]
> 本项目在开发过程中，大量参考了 [MaiBot (麦麦)](https://github.com/Mai-with-u/MaiBot) 的设计思路，特别是在拟人化社交、差异化人际关系、动态人格演化以及“去 AI 化”表达等方面深受启发。在此向原作者表示诚挚的敬意。

## ✨ 核心特性

- 🧠 **智能决策系统 (Decision Making)**：
  - 不再仅仅依赖艾特或随机概率。
  - 使用小模型（如 Qwen-7B）实时分析对话语境，判断用户是否在接话或话题是否符合人设兴趣，实现自然插话。
  - 具备**决策冷却机制**，避免在活跃群聊中过度打扰。

- 🎭 **差异化人际关系 (Social System)**：
  - **好感度进化**：根据聊天内容动态调整对每个用户的“好感度”与“关系状态”。
  - **见人说人话**：根据关系等级（死对头、陌生人、朋友、死党）自动切换不同的交互态度与行为准则。
  - **权限识别**：能够精准识别唯一的“创造者”，表现出特殊的依赖与损友性格。

- 💤 **AI 作息与碎片化生存 (Life System)**：
  - **资源分配表**：AI 每天根据人设自动规划作息，仅在特定的“水群时间”主动发言。
  - **唤醒关注**：被强制唤醒后会进入 5 分钟关注期，保证对话连贯。
  - **极致碎片化**：发言窗口短促且随机，有效降低打扰感，增强幽灵般的真实感。

- 📚 **深度进化学习 (Learning Engine)**：
  - **实时模仿**：情境化捕捉群友表达风格，提取 (情境, 风格) 键值对进行权重化模仿。
  - **渐进式黑话挖掘**：三阶段差分推理，自动识别、定义并掌握群内特有黑话。
  - **知识图谱沉淀**：从对话中提取 (主体-谓语-客体) 三元组，实现结构化记忆。
  - **梦境代理 (Dream Agent)**：后台自动复盘，进行记忆的合并、精炼与噪声清理。

- 🖼️ **智能视觉与表情包 (VLM & Sticker)**：
  - **看图识梗**：集成 Qwen2-VL，精准识别图片内容。
  - **动图深度识别**：支持 GIF/WebP 多帧采样拼接识别，能看懂动态动作序列。
  - **表情包缓存**：通过 MD5 匹配实现秒回缓存结果。

- ✍️ **去 AI 化表达 (Expressor)**：
  - **拒绝条理性**：禁止使用“首先、其次”等逻辑词，强制随性、跳跃的发言。
  - **动态人格状态**：随机切换（慵懒、热情、高冷、傲娇、混乱）状态，模拟真实情绪波动。
  - **极致主义**：一次只聊一个话题，杜绝冗长解释，极致碎片化短句。

- 🎭 **人设高度可定制**：
  - 身份设定与核心代码完全解耦。
  - 只需修改 `config.yaml`，即可快速切换角色。

- 🛡️ **群组管理**：
  - 完善的白名单/黑名单过滤机制。

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
