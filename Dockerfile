FROM python:3.11-slim

LABEL maintainer="your.email@example.com"
LABEL description="TingFengBot - 智能聊天机器人"

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY pyproject.toml ./
COPY requirements.txt ./

# 安装 Python 依赖（使用国内源）
RUN pip install --upgrade pip && \
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目文件
COPY src/ ./src/
COPY bot.py ./
COPY config.yaml.example ./config.yaml
COPY ai_config.yaml.example ./ai_config.yaml

# 创建必要的目录
RUN mkdir -p /app/data /app/logs /app/stickers

# 设置权限
RUN chmod +x /app

# 暴露端口
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('localhost', 8080)); s.close()" || exit 1

# 运行应用
CMD ["python", "bot.py"]
