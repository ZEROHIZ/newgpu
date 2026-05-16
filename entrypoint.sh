#!/bin/bash
# 启动 Redis 服务 (后台运行)
echo "Starting Redis server..."
redis-server --daemonize yes

# 等待 Redis 启动
until redis-cli ping >/dev/null 2>&1; do
  echo "Waiting for Redis..."
  sleep 1
done
echo "Redis is ready."

# 启动 FastAPI 应用
echo "Starting GPUREDIS API..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
