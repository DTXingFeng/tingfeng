# 使用国内代理镜像源（解决无法连接 Docker Hub 的问题）
FROM docker.m.daocloud.io/library/python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置时区为北京时间
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装系统级依赖
# chromadb 可能需要编译环境，sqlite3-dev 用于数据库支持
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制项目代码
COPY . .

# 暴露端口（如果你在 .env 里改了端口，这里也要改）
EXPOSE 8080

# 运行启动脚本
CMD ["python", "bot.py"]
