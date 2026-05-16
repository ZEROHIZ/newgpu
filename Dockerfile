# 使用 Python 3.10 基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装 Redis 和必要的系统工具
RUN apt-get update && apt-get install -y \
    redis-server \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建数据存储目录
RUN mkdir -p data

# 设置环境变量
ENV PYTHONPATH=/app
ENV DEFAULT_GPU_ID=0
ENV DEFAULT_GPU_INDEX=0

# 暴露端口 (FastAPI 默认 8000)
EXPOSE 8000

# 赋予启动脚本执行权限
RUN chmod +x entrypoint.sh

# 启动脚本
ENTRYPOINT ["./entrypoint.sh"]
