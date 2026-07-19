#!/bin/bash
# 心随乐动 - Railway 部署启动脚本
# 此脚本会被 Procfile 调用

set -e  # 发生错误时立即退出

echo "=== 心随乐动后端服务 ==="
echo "当前目录: $(pwd)"

# 切换到 backend 目录
cd "$(dirname "$0")/backend"
echo "工作目录: $(pwd)"

# 确保缓存目录存在
mkdir -p cache
echo "缓存目录: $(pwd)/cache"

echo "Python 版本: $(python --version 2>&1)"
echo "启动 Flask 服务..."
python app.py
