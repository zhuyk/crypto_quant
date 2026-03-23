#!/bin/bash

# CryptoQuant 项目初始化脚本

set -e

echo "🚀 CryptoQuant 项目初始化"
echo "================================"

# 进入项目目录
cd "$(dirname "$0")/.."

# 1. 创建 .env 文件
echo "📝 创建环境配置文件..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✅ .env 文件已创建，请修改配置"
else
    echo "⚠️  .env 文件已存在，跳过"
fi

# 2. 创建日志目录
echo "📁 创建日志目录..."
mkdir -p logs
echo "✅ 日志目录已创建"

# 3. 创建配置目录
echo "📁 创建配置目录..."
mkdir -p config
echo "✅ 配置目录已创建"

# 4. 检查 Docker
echo "🐳 检查 Docker 环境..."
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    echo "✅ Docker 环境正常"
else
    echo "❌ 请安装 Docker 和 Docker Compose"
    exit 1
fi

# 5. 检查 Python
echo "🐍 检查 Python 环境..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo "✅ Python $PYTHON_VERSION"
else
    echo "❌ 请安装 Python 3.10+"
    exit 1
fi

# 6. 检查 Node.js
echo "📦 检查 Node.js 环境..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "✅ $NODE_VERSION"
else
    echo "⚠️  Node.js 未安装 (前端开发需要)"
fi

# 7. 启动数据库
echo "💾 启动数据库服务..."
cd docker
docker-compose up -d mysql redis
echo "✅ 数据库服务已启动"

# 8. 等待数据库就绪
echo "⏳ 等待数据库就绪..."
sleep 5

# 9. 初始化数据库
echo "📊 初始化数据库..."
# 这里可以添加数据库初始化命令

echo ""
echo "================================"
echo "✅ 项目初始化完成！"
echo ""
echo "下一步:"
echo "1. 修改 .env 文件中的配置"
echo "2. 安装后端依赖：cd backend && pip install -r requirements.txt"
echo "3. 安装前端依赖：cd frontend && npm install"
echo "4. 启动开发服务：docker-compose up -d"
echo ""
echo "📚 文档：docs/changelog.md"
echo "🎯 设计：../crypto_quant_system_design.md"
