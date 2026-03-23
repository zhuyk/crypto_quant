#!/bin/bash
# CryptoQuant 开发环境启动脚本

set -e

echo "🚀 CryptoQuant 开发环境启动"
echo "================================"

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js 未安装，请先安装 Node.js 18+"
    exit 1
fi

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装，请先安装 Python 3.10+"
    exit 1
fi

echo "✅ 环境检查通过"

# 启动 Docker 服务
echo ""
echo "📦 启动 Docker 服务..."
cd "$(dirname "$0")/.."
docker-compose up -d mysql redis

# 等待 MySQL 启动
echo "⏳ 等待 MySQL 启动..."
sleep 5

# 初始化数据库
echo ""
echo "🗄️  初始化数据库..."
# docker exec -i cryptoquant-mysql mysql -uroot -pcryptoquant2026 < database/schema.sql

# 安装后端依赖
echo ""
echo "🐍 安装后端依赖..."
cd backend
pip3 install -r requirements-test.txt

# 安装前端依赖
echo ""
echo "📦 安装前端依赖..."
cd ../frontend
npm install

echo ""
echo "✅ 环境准备完成!"
echo ""
echo "📋 下一步:"
echo "1. 启动后端：cd backend && python3 -m uvicorn app.main:app --reload"
echo "2. 启动前端：cd frontend && npm run dev"
echo ""
echo "🌐 访问地址:"
echo "  - 前端：http://localhost:3000"
echo "  - 后端 API: http://localhost:8000"
echo "  - API 文档：http://localhost:8000/docs"
