#!/bin/bash
# DECIMER服务启动脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 启动服务
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   正在启动DECIMER服务...${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 选择启动方式
if command -v gunicorn &> /dev/null; then
    echo "检测到gunicorn，使用多进程模式..."
    echo "启动命令: gunicorn -w 2 -b $HOST:$PORT server:app"
    echo ""
    gunicorn -w 2 -b $HOST:$PORT server:app
else
    echo "使用Flask开发服务器（单进程）"
    echo "生产环境建议安装gunicorn: pip install gunicorn"
    echo ""
    python3 server.py
fi

