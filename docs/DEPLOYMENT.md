# 部署指南

## 目录

- [本地部署](#本地部署)
- [Docker 部署](#docker-部署)
- [Docker Compose 部署](#docker-compose-部署)
- [环境变量配置](#环境变量配置)
- [数据库维护](#数据库维护)
- [监控和日志](#监控和日志)
- [故障排查](#故障排查)

## 本地部署

### 前置要求

- Python 3.9 或更高版本
- pip
- Git（可选）

### 安装步骤

1. **克隆项目**
   ```bash
   git clone https://github.com/yourusername/tingfengbot.git
   cd tingfengbot
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **安装依赖**
   ```bash
   # 使用国内源
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

4. **配置机器人人设**
   ```bash
   # 复制并编辑 config.yaml
   cp config.yaml.example config.yaml
   # 编辑 config.yaml，设置机器人人设和行为
   ```

5. **配置 AI 模型**
   ```bash
   # 复制并编辑 ai_config.yaml
   cp ai_config.yaml.example ai_config.yaml
   # 编辑 ai_config.yaml，填入你的 API Key
   ```

6. **配置环境变量**
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，填入实际配置
   ```

7. **配置 OneBot V11**
   1. 安装 go-cqhttp 或 NapCat
   2. 配置 OneBot V11 正向 WebSocket 服务器
   3. 在 `.env` 中设置：
      ```
      ONEBOT_WS_URLS=["ws://your-cqhttp-host:8080"]
      ONEBOT_ACCESS_TOKEN=your-access-token
      ```

8. **运行机器人**
   ```bash
   python bot.py
   ```

### Docker 部署

### 前置要求

- Docker 20.10 或更高版本
- Docker Compose 2.0 或更高版本（可选）

### 构建镜像

```bash
docker build -t tingfengbot:latest .
```

### 运行容器

```bash
docker run -d \
  --name tingfengbot \
  -p 8080:8080 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -v $(pwd)/ai_config.yaml:/app/ai_config.yaml \
  -v $(pwd)/stickers:/app/stickers \
  --env-file .env \
  tingfengbot:latest
```

### 查看日志

```bash
docker logs -f tingfengbot
```

### 停止容器

```bash
docker stop tingfengbot
docker rm tingfengbot
```

## Docker Compose 部署（推荐）

### 快速开始

1. **准备配置文件**
   ```bash
   cp .env.example .env
   # 编辑 .env 文件
   ```

2. **启动服务**
   ```bash
   docker-compose up -d
   ```

3. **查看状态**
   ```bash
   docker-compose ps
   ```

4. **查看日志**
   ```bash
   docker-compose logs -f
   ```

5. **停止服务**
   ```bash
   docker-compose down
   ```

### 高级配置

#### 资源限制

编辑 `docker-compose.yml` 中的 `deploy.resources` 部分：

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'      # 最大 CPU 核心数
      memory: 2G       # 最大内存
    reservations:
      cpus: '0.5'      # 保留 CPU 核心数
      memory: 512M     # 保留内存
```

#### 数据持久化

数据会自动持久化到以下卷：
- `./data` - 数据库文件
- `./logs` - 日志文件
- `./config.yaml` - 机器人人设配置
- `./ai_config.yaml` - AI模型配置
- `./stickers` - 表情包文件

#### 网络配置

默认使用 bridge 网络。如果需要连接其他容器，可以自定义网络：

```yaml
networks:
  tingfengbot-network:
    external: true  # 使用已存在的外部网络
```

#### 自动重启

默认设置为 `restart: unless-stopped`，容器会在崩溃时自动重启。

### 更新部署

```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker-compose up -d --build

# 或者分步执行
docker-compose stop
docker-compose build
docker-compose up -d
```

### 备份和恢复

#### 备份

```bash
# 创建备份目录
mkdir -p backup

# 备份数据
tar -czf backup/data_$(date +%Y%m%d).tar.gz data/
tar -czf backup/logs_$(date +%Y%m%d).tar.gz logs/
tar -czf backup/config_$(date +%Y%m%d).tar.gz config.yaml ai_config.yaml
```

#### 恢复

```bash
# 停止服务
docker-compose down

# 恢复数据
tar -xzf backup/data_YYYYMMDD.tar.gz
tar -xzf backup/logs_YYYYMMDD.tar.gz
tar -xzf backup/config_YYYYMMDD.tar.gz

# 重启服务
docker-compose up -d
```

## 环境变量配置

### 必需配置

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `ONEBOT_WS_URLS` | OneBot WebSocket 地址列表（JSON 数组） | `["ws://localhost:8080"]` |

### 可选配置

#### NoneBot 配置

```bash
DRIVER=~websockets                        # 驱动类型
HOST=0.0.0.0                             # 监听地址
PORT=8080                                # 监听端口
LOG_LEVEL=INFO                           # 日志级别
```

#### OneBot 配置

```bash
ONEBOT_ACCESS_TOKEN=your-access-token      # OneBot 访问令牌（可选）
```

#### Docker 配置

```bash
TZ=Asia/Shanghai                         # 时区
```

## 数据库维护

### 查看数据库统计

在 Python REPL 中执行：

```python
from src.utils.db_manager import db_manager

stats = db_manager.get_db_stats()
print(stats)
```

### 清理旧数据

```python
from src.utils.db_manager import db_manager

# 清理 30 天前的数据
deleted = db_manager.cleanup_old_data(days=30)
print(deleted)
```

### 优化数据库

```python
from src.utils.db_manager import db_manager

# 执行 VACUUM 优化
db_manager.vacuum_database()
```

### 定期清理任务

可以使用 cron 或 systemd 定时器定期清理：

#### Cron 示例

```bash
# 每天凌晨 3 点清理 30 天前的数据
0 3 * * * cd /app && python -c "from src.utils.db_manager import db_manager; db_manager.cleanup_old_data(days=30)" >> /app/logs/cleanup.log 2>&1

# 每周日凌晨 4 点优化数据库
0 4 * * 0 cd /app && python -c "from src.utils.db_manager import db_manager; db_manager.vacuum_database()" >> /app/logs/vacuum.log 2>&1
```

#### 在 Docker Compose 中添加定时任务

编辑 `docker-compose.yml`，添加 cron 服务：

```yaml
services:
  cron:
    image: tingfengbot:latest
    command: >
      sh -c "echo '0 3 * * * cd /app && python -c \"from src.utils.db_manager import db_manager; db_manager.cleanup_old_data(days=30)\"' | crontab - && crond -f"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
```

## 监控和日志

### 查看日志

#### 本地部署

```bash
# 查看所有日志
tail -f logs/*.log

# 查看错误日志
tail -f logs/error_*.log

# 查看信息日志
tail -f logs/info_*.log
```

#### Docker 部署

```bash
# 实时查看容器日志
docker logs -f tingfengbot

# 查看最近 100 行日志
docker logs --tail 100 tingfengbot

# 查看错误日志
docker logs tingfengbot | grep ERROR
```

#### Docker Compose 部署

```bash
docker-compose logs -f
```

### 性能监控

在 Python REPL 中执行：

```python
from src.utils.performance_monitor import performance_monitor

# 查看所有性能统计
performance_monitor.log_summary()

# 查看特定操作的统计
stats = performance_monitor.get_stats("consolidate_memories")
print(stats)

# 查看性能摘要
summary = performance_monitor.get_summary()
print(summary)
```

### 健康检查

Docker 容器会自动进行健康检查：

```bash
# 查看容器健康状态
docker inspect tingfengbot --format='{{.State.Health.Status}}'

# 查看健康检查日志
docker inspect tingfengbot --format='{{json .State.Health}}' | jq
```

### 集成监控系统

#### Prometheus + Grafana

创建 `prometheus.yml`：

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'tingfengbot'
    static_configs:
      - targets: ['tingfengbot:8080']
```

在 `docker-compose.yml` 中添加：

```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - 9090:9090
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    ports:
      - 3000:3000
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana
    restart: unless-stopped

volumes:
  grafana-data:
```

## 故障排查

### 常见问题

#### 1. 机器人无法启动

**症状**：容器启动后立即退出

**排查步骤**：
```bash
# 查看容器日志
docker logs tingfengbot

# 检查配置文件
docker exec tingfengbot cat .env
docker exec tingfengbot cat /app/config.yaml
docker exec tingfengbot cat /app/ai_config.yaml

# 检查文件权限
docker exec tingfengbot ls -la /app
```

**可能原因**：
- `.env` 文件配置错误
- `config.yaml` 或 `ai_config.yaml` 文件缺失或格式错误
- AI API Key 无效
- 文件权限问题

#### 2. 无法连接到 OneBot

**症状**：日志显示 WebSocket 连接失败

**排查步骤**：
```bash
# 检查 OneBot 是否运行
# 检查 ONEBOT_WS_URL 配置
# 测试 WebSocket 连接
wscat -c ws://your-onebot-host:8080
```

**解决方案**：
- 确保 OneBot 服务正在运行
- 检查防火墙设置
- 验证 `ONEBOT_WS_URL` 和 `ONEBOT_ACCESS_TOKEN` 配置

#### 3. API 调用失败

**症状**：日志显示 AI API 错误

**排查步骤**：
```bash
# 检查 AI 配置
docker exec tingfengbot cat /app/ai_config.yaml

# 查看容器日志中的详细错误信息
docker logs tingfengbot | grep -i error
```

**解决方案**：
- 检查 `ai_config.yaml` 中的 API Key 是否正确
- 检查 API 平台是否可用
- 检查 API 配额是否充足
- 检查 `base_url` 配置是否正确

#### 4. 内存占用过高

**症状**：容器内存使用率超过 90%

**排查步骤**：
```bash
# 查看容器资源使用
docker stats tingfengbot

# 检查数据库大小
docker exec tingfengbot ls -lh /app/data/

# 查看向量数据库大小
docker exec tingfengbot du -sh /app/data/chroma
```

**解决方案**：
- 清理旧数据：`db_manager.cleanup_old_data()`
- 优化数据库：`db_manager.vacuum_database()`
- 增加内存限制
- 减少并发任务数：`MAX_CONCURRENT_TASKS`

#### 5. 数据库查询慢

**症状**：消息处理延迟高

**排查步骤**：
```python
# 检查索引是否创建
docker exec tingfengbot python -c "
from src.utils.db_manager import db_manager
import sqlite3
conn = sqlite3.connect('/app/data/tingfengbot.db')
cursor = conn.cursor()
cursor.execute(\"SELECT name FROM sqlite_master WHERE type='index'\")
print(cursor.fetchall())
conn.close()
"
```

**解决方案**：
- 确保已创建数据库索引
- 运行 `VACUUM` 优化
- 清理旧数据
- 考虑迁移到 PostgreSQL

#### 6. 日志文件过大

**症状**：磁盘空间不足

**解决方案**：
```bash
# 清理旧日志
find /app/logs -name "*.log" -mtime +30 -delete

# 或使用 logrotate
```

### 调试模式

启用调试日志：

```bash
# 编辑 .env
LOG_LEVEL=DEBUG

# 重启服务
docker-compose restart
```

### 重置配置

如果配置错误导致无法启动，可以重置：

```bash
# 停止服务
docker-compose down

# 删除配置（谨慎操作！）
rm -f .env
rm -rf data/

# 重新配置
cp .env.example .env
# 编辑 .env

# 重启服务
docker-compose up -d
```

## 安全建议

1. **保护敏感信息**
   - 不要将 `.env` 文件提交到 Git
   - 使用密钥管理服务（如 Vault）
   - 定期轮换 API 密钥

2. **网络安全**
   - 不要在公网暴露 OneBot 端口
   - 使用防火墙限制访问
   - 启用 TLS/SSL

3. **访问控制**
   - 配置超级用户列表
   - 使用强密码
   - 启用速率限制

4. **定期备份**
   - 备份数据库文件
   - 备份配置文件
   - 备份向量数据库

5. **监控告警**
   - 设置 CPU/内存告警
   - 设置错误率告警
   - 定期检查日志

## 性能优化

1. **使用更快的存储**
   - 使用 SSD 而不是 HDD
   - 考虑使用 Redis 缓存

2. **优化数据库**
   - 创建适当的索引
   - 定期执行 VACUUM
   - 考虑迁移到 PostgreSQL

3. **调整并发配置**
   - 根据硬件调整 `MAX_CONCURRENT_TASKS`
   - 调整 `MAX_CONSOLIDATION_CONCURRENT`

4. **使用 CDN**
   - 为表情包使用 CDN
   - 为静态资源使用 CDN

## 更新和维护

### 更新依赖

```bash
# 本地部署
pip install --upgrade -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# Docker 部署
docker-compose down
docker build -t tingfengbot:latest .
docker-compose up -d
```

### 数据迁移

如果需要迁移数据到新版本：

```bash
# 停止服务
docker-compose down

# 备份数据
cp -r data data.backup
cp -r logs logs.backup

# 更新代码
git pull

# 重新构建
docker-compose up -d --build

# 验证运行正常后删除备份
# rm -rf data.backup logs.backup
```

## 支持

- 文档：[docs/](./)
- 问题反馈：[GitHub Issues](https://github.com/yourusername/tingfengbot/issues)
- 讨论：[GitHub Discussions](https://github.com/yourusername/tingfengbot/discussions)
