# TingFengBot

一个基于 NoneBot2 和 OneBot V11 协议的智能聊天机器人，具备 AI 模型集成和插件化架构。

## 功能特性

- 🤖 支持 OneBot V11 协议，兼容多种 QQ 机器人框架
- 🧠 集成 AI 模型处理能力（视觉语言模型、决策模块等）
- 🔌 模块化插件系统，易于扩展功能
- 🛡️ 安全性设计，默认忽略私聊消息
- 📁 清晰的目录结构，便于维护和开发

## 项目结构

```
tingfengbot/
├── src/
│   ├── aimodel/          # AI 模型相关模块
│   │   ├── decision/     # 决策模块
│   │   ├── image_processing/ # 图像处理模块
│   │   ├── memory/       # 记忆模块
│   │   └── reply/        # 回复生成模块
│   ├── config/           # 配置文件
│   ├── plugins/          # 插件目录
│   └── utils/            # 工具函数
├── bot.py               # 主程序入口
├── requirements.txt     # Python 依赖
├── .env.example        # 环境变量示例
└── README.md           # 项目说明
```

## 快速开始

### 环境要求

- Python 3.8+
- pip 20.0+

### 安装步骤

1. 克隆项目到本地：
```bash
git clone <repository-url>
cd tingfengbot
```

2. 创建虚拟环境并激活：
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 配置环境变量：
```bash
cp .env.example .env
# 编辑 .env 文件，根据实际情况修改配置
```

5. 配置 AI 模型（可选）：
    - 复制 `ai_config.yaml.example` 到 `ai_config.yaml` 并配置 API 密钥
    - 复制 `config.yaml.example` 到 `config.yaml` 并调整参数

### 运行机器人

```bash
python bot.py
```

## 配置说明

### 环境变量 (.env)

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| DRIVER | 驱动类型 | ~websockets |
| HOST | 监听主机 | 127.0.0.1 |
| PORT | 监听端口 | 8080 |
| LOG_LEVEL | 日志级别 | DEBUG |
| ONEBOT_WS_URLS | OneBot WebSocket 地址 | ["ws://192.168.8.240:3001"] |

### 配置文件

- `ai_config.yaml`: AI 模型相关配置（API 密钥、模型参数等）
- `config.yaml`: 机器人行为配置（触发词、回复策略等）

**注意**：包含敏感信息的配置文件已被添加到 `.gitignore`，请勿提交到版本控制。

## 插件开发

在 `src/plugins/` 目录下创建新的 Python 文件即可开发插件。参考 `group_handler.py` 的写法。

插件基本结构：
```python
from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent

my_command = on_command("test")

@my_command.handle()
async def handle_test(event: GroupMessageEvent):
    await my_command.finish("Hello, World!")
```

## 贡献指南

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 支持与联系

如有问题或建议，请提交 Issue 或通过其他方式联系维护者。