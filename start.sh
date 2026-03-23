#!/bin/bash
# CryptoQuant 快速启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "🚀 CryptoQuant 快速启动"
echo "========================================"
echo ""

# 检查 Docker 服务
echo "📦 检查 Docker 服务..."
if docker ps | grep -q crypto_quant_mysql; then
    echo "✅ MySQL 已运行"
else
    echo "⚠️  MySQL 未运行，启动中..."
    cd docker
    docker-compose up -d mysql redis
    cd ..
fi

if docker ps | grep -q crypto_quant_redis; then
    echo "✅ Redis 已运行"
else
    echo "⚠️  Redis 未运行，启动中..."
    cd docker
    docker-compose up -d redis
    cd ..
fi

echo ""

# 停止旧的后端进程
echo "🛑 停止旧的后端进程..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 2

# 启动后端
echo "🔧 启动后端服务..."
cd backend

# 检查依赖
if ! /usr/local/bin/python3.12 -c "import fastapi" 2>/dev/null; then
    echo "⚠️  安装 Python 依赖..."
    /usr/local/bin/python3.12 -m pip install --break-system-packages -q -r requirements.txt
fi

# 启动后端（后台运行）
nohup /usr/local/bin/python3.12 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "✅ 后端服务已启动 (PID: $BACKEND_PID)"

# 等待后端启动
echo "⏳ 等待后端启动..."
sleep 5

# 检查后端是否正常
for i in {1..10}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ 后端服务正常"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "❌ 后端启动失败，查看日志：logs/backend.log"
        exit 1
    fi
    echo "   尝试 $i/10..."
    sleep 2
done

cd ..

# 检查前端
echo ""
echo "🌐 检查前端服务..."
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ 前端服务已运行"
else
    echo "⚠️  前端未运行"
    echo ""
    echo "💡 启动前端命令:"
    echo "   cd frontend"
    echo "   npm run dev"
    echo ""
fi

# 显示访问信息
echo ""
echo "========================================"
echo "✨ 启动完成！"
echo "========================================"
echo ""
echo "📍 访问地址:"
echo "   前端：http://localhost:3000"
echo "   后端 API: http://localhost:8000"
echo "   API 文档：http://localhost:8000/docs"
echo ""
echo "🔑 配置交易所:"
echo "   方式 1: 访问 http://localhost:3000/exchange-keys"
echo "   方式 2: 运行 python3 scripts/quick_config.py"
echo ""
echo "📊 查看日志:"
echo "   tail -f logs/backend.log"
echo ""
echo "🛑 停止服务:"
echo "   pkill -f 'uvicorn app.main:app'"
echo ""

# 保存 PID
echo $BACKEND_PID > /tmp/crypto_quant_backend.pid

echo "========================================"
