#!/bin/bash
# TADF数据抽取系统 - Streamlit应用启动脚本

echo "=========================================="
echo "TADF数据抽取系统 - Web应用"
echo "=========================================="
echo ""

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到python3"
    exit 1
fi

# 检查是否安装了streamlit
if ! python3 -c "import streamlit" 2>/dev/null; then
    echo "⚠️  警告: streamlit未安装，正在安装..."
    pip install streamlit pillow pandas
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

# 启动Streamlit应用
echo "🚀 启动Streamlit应用..."
echo "   应用将在浏览器中自动打开"
echo "   如果未自动打开，请访问: http://localhost:8501"
echo ""

streamlit run app.py --server.port 8501 --server.address localhost

