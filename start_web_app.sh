#!/bin/bash
# TADF数据抽取系统 - Flask Web应用启动脚本

echo "=========================================="
echo "TADF数据抽取系统 - Web应用"
echo "=========================================="
echo ""

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到python3"
    exit 1
fi

# 检查是否安装了flask
if ! python3 -c "import flask" 2>/dev/null; then
    echo "⚠️  警告: flask未安装，正在安装..."
    pip install flask flask-cors pillow requests
fi

# 检查DECIMER服务是否运行
echo "检查DECIMER服务..."
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "⚠️  警告: DECIMER服务未运行 (http://localhost:8000)"
    echo "   请先启动DECIMER服务:"
    echo "   python server.py"
    echo "   或运行: bash start_decimer_server.sh"
    echo ""
    read -p "是否继续启动Web应用? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 启动Flask应用
echo "🚀 启动Flask Web应用..."
echo "   应用地址: http://localhost:5000"
echo "   按 Ctrl+C 停止服务"
echo ""

cd "$(dirname "$0")"
python3 web_app.py

