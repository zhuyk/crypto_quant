#!/bin/bash
# MySQL 数据库初始化脚本

echo "============================================================"
echo "🗄️  MySQL 数据库初始化"
echo "============================================================"

# 配置
MYSQL_HOST="localhost"
MYSQL_PORT="3306"
MYSQL_ROOT_PASSWORD=""  # 留空则提示输入
DB_NAME="crypto_quant"
DB_USER="cryptoquant"
DB_PASSWORD="cryptoquant2026"

echo ""
echo "📋 配置信息:"
echo "   主机：${MYSQL_HOST}:${MYSQL_PORT}"
echo "   数据库：${DB_NAME}"
echo "   用户：${DB_USER}"
echo ""

# 检查 MySQL 是否运行
echo "📌 步骤 1: 检查 MySQL 服务..."
if ! command -v mysql &> /dev/null; then
    echo "❌ MySQL 客户端未安装"
    echo ""
    echo "💡 安装方法:"
    echo "   macOS:  brew install mysql"
    echo "   Ubuntu: sudo apt-get install mysql-client"
    echo "   CentOS: sudo yum install mysql"
    exit 1
fi

# 检查 MySQL 连接
echo "📌 步骤 2: 测试 MySQL 连接..."
if [ -z "$MYSQL_ROOT_PASSWORD" ]; then
    # 无密码或 socket 认证
    if ! mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -e "SELECT 1" &> /dev/null; then
        echo "❌ 无法连接到 MySQL 服务器"
        echo ""
        echo "💡 请检查:"
        echo "   1. MySQL 服务是否启动"
        echo "   2. 主机名和端口是否正确"
        echo "   3. 防火墙设置"
        exit 1
    fi
    MYSQL_CMD="mysql -h $MYSQL_HOST -P $MYSQL_PORT"
else
    # 密码认证
    if ! mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u root -p"$MYSQL_ROOT_PASSWORD" -e "SELECT 1" &> /dev/null; then
        echo "❌ 无法连接到 MySQL 服务器 (密码认证失败)"
        exit 1
    fi
    MYSQL_CMD="mysql -h $MYSQL_HOST -P $MYSQL_PORT -u root -p$MYSQL_ROOT_PASSWORD"
fi

echo "✅ MySQL 连接成功"

# 创建数据库
echo ""
echo "📌 步骤 3: 创建数据库..."
$MYSQL_CMD -e "CREATE DATABASE IF NOT EXISTS $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
echo "✅ 数据库 ${DB_NAME} 创建成功"

# 创建用户并授权
echo ""
echo "📌 步骤 4: 创建用户并授权..."
$MYSQL_CMD -e "CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';"
$MYSQL_CMD -e "GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';"
$MYSQL_CMD -e "FLUSH PRIVILEGES;"
echo "✅ 用户 ${DB_USER} 创建并授权成功"

# 导入表结构
echo ""
echo "📌 步骤 5: 导入表结构..."
if [ -f "schema.sql" ]; then
    $MYSQL_CMD < schema.sql
    echo "✅ 表结构导入成功"
else
    echo "⚠️  schema.sql 文件不存在，跳过表结构导入"
    echo "💡 请确保在 database/ 目录下运行此脚本"
fi

# 验证
echo ""
echo "📌 步骤 6: 验证..."
TABLE_COUNT=$($MYSQL_CMD -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${DB_NAME}';" 2>/dev/null)
echo "✅ 数据库 ${DB_NAME} 中有 ${TABLE_COUNT} 张表"

echo ""
echo "============================================================"
echo "🎉 MySQL 数据库初始化完成！"
echo "============================================================"
echo ""
echo "📝 连接信息:"
echo "   主机：${MYSQL_HOST}:${MYSQL_PORT}"
echo "   数据库：${DB_NAME}"
echo "   用户：${DB_USER}"
echo "   密码：${DB_PASSWORD}"
echo ""
echo "📝 连接字符串:"
echo "   mysql -h ${MYSQL_HOST} -P ${MYSQL_PORT} -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME}"
echo ""
echo "📝 SQLAlchemy URL:"
echo "   mysql+pymysql://${DB_USER}:${DB_PASSWORD}@${MYSQL_HOST}:${MYSQL_PORT}/${DB_NAME}"
echo ""
echo "📝 .env 配置:"
echo "   DATABASE_URL=mysql+pymysql://${DB_USER}:${DB_PASSWORD}@${MYSQL_HOST}:${MYSQL_PORT}/${DB_NAME}"
echo ""
