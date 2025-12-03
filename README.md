听风（Tingfeng）是一个基于大模型的智能群聊机器人（bot）。它能够理解群聊中的文本、图片等混合消息，进行智能回复、摘要、解析与识别，并以可扩展的方式接入不同平台的模型。

主要特性
- 群消息接入：基于 Shiro 框架监听群消息，支持 CQ 码标准解析
- 混合消息处理：文本与图片同条消息解析，不丢失顺序与结构
- 图片识别准备：对图片段结构化提取，便于接入视觉语言（VL）模型
- 回复/转发解析：提取回复 id、转发 id，方便溯源与展开
- 持久化存储：使用 SQLite + MyBatis-Plus 保存群聊天记录
- 模型管理：外置 `config/llm.yaml` 管理多平台模型、别名与功能路由，首次启动自动生成

技术栈
- Spring Boot 3
- MyBatis-Plus（数据访问）、SQLite（本地数据库）
- Shiro（消息接入）
- OkHttp、JSON（HTTP 与数据构造）

快速开始
- 配置 Shiro WS 地址于 `src/main/resources/application.yaml`
- 首次启动自动生成 `config/llm.yaml`，可按需修改，不随代码仓库提交
- 运行：`./gradlew.bat bootRun`

消息与CQ码
- 解析器将消息拆分为段：文本段与 CQ 段（如 `image`、`at`、`reply`、`forward`）
- 提供便捷提取方法：获取所有文本、图片信息、回复 id、转发 id 等
- 严格校验参数格式，避免将手动输入的伪 CQ 文本误判为 CQ 段

模型配置
- 文件：`config/llm.yaml`（支持通过环境变量 `LLM_CONFIG_PATH` 指定路径）
- 每个模型具备唯一 `alias`，程序只用别名即可解析出完整调用参数（`base_url + url`、`model name`、`apiKey`）
- 提供 `llm.routing` 将功能映射到模型别名，方便按场景切换模型

数据表
- 表：`group_message`
- 字段：`id`、`group_id`、`sender_qq`、`sender_nickname`、`content`、`send_time`

目标
- 成为开箱即用、可扩展的群聊智能助手，支持多模型、多场景处理，保持代码与配置分离，便于在不同环境部署与演进。
