#!/usr/bin/env python3
"""
MySQL 快速配置脚本 (简化版)
创建配置文件和测试连接
"""
import os
import sys

print("="*60)
print("🗄️  MySQL 快速配置")
print("="*60)

# 配置
DB_USER = "cryptoquant"
DB_PASSWORD = "cryptoquant2026"
DB_NAME = "crypto_quant"
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306

print(f"""
📋 配置信息:
   主机：{MYSQL_HOST}:{MYSQL_PORT}
   数据库：{DB_NAME}
   用户：{DB_USER}
   密码：{DB_PASSWORD}
""")

# 步骤 1: 创建/更新 .env 文件
print("📌 步骤 1: 配置环境变量...")

env_content = f"""# CryptoQuant MySQL 环境配置
# 自动生成 - {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# ============================================
# 基础配置
# ============================================
ENVIRONMENT=development
DEBUG=True
SECRET_KEY=your-super-secret-key-change-this-in-production

# ============================================
# MySQL 数据库配置
# ============================================
DB_ROOT_PASSWORD=cryptoquant2026
DB_USER={DB_USER}
DB_PASSWORD={DB_PASSWORD}

# MySQL 连接字符串
DATABASE_URL=mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{DB_NAME}

# 数据库连接池配置
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40

# ============================================
# Redis 配置
# ============================================
REDIS_URL=redis://localhost:6379
REDIS_DB=0

# ============================================
# Binance 配置
# ============================================
BINANCE_TESTNET=True
BINANCE_API_KEY=your-testnet-api-key
BINANCE_API_SECRET=your-testnet-api-secret

# ============================================
# CORS 配置
# ============================================
CORS_ORIGINS=["http://localhost:3000","http://localhost:8080"]

# ============================================
# 日志配置
# ============================================
LOG_LEVEL=INFO
LOG_FILE=logs/cryptoquant.log

# ============================================
# 交易配置
# ============================================
DEFAULT_INITIAL_CAPITAL=100000
MAX_POSITION_RATIO=0.8
MAX_DAILY_LOSS=0.05
MAX_DRAWDOWN=0.20
"""

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
with open(env_path, 'w', encoding='utf-8') as f:
    f.write(env_content)

print(f"✅ 配置文件已更新：{env_path}")

# 步骤 2: 提供手动初始化命令
print("\n📌 步骤 2: 手动初始化 MySQL 数据库...")
print("\n💡 请执行以下命令初始化数据库:\n")
print(f"""   # 登录 MySQL
   mysql -u root -p
   
   # 创建数据库
   CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   
   # 创建用户
   CREATE USER IF NOT EXISTS '{DB_USER}'@'localhost' IDENTIFIED BY '{DB_PASSWORD}';
   
   # 授权
   GRANT ALL PRIVILEGES ON {DB_NAME}.* TO '{DB_USER}'@'localhost';
   FLUSH PRIVILEGES;
   
   # 导入表结构
   USE {DB_NAME};
   SOURCE /Users/zhuyukun/.openclaw/workspace/crypto_quant/database/schema.sql;
   
   # 验证
   SHOW TABLES;
   exit;
""")

# 步骤 3: 测试连接 (如果数据库已初始化)
print("\n📌 步骤 3: 测试连接...")
print("\n💡 数据库初始化后，运行以下命令测试:\n")
print(f"   cd /Users/zhuyukun/.openclaw/workspace/crypto_quant/scripts")
print(f"   python3 test_mysql_connection.py")

print("\n" + "="*60)
print("📝 配置完成！")
print("="*60)

print(f"\n📝 下一步:")
print(f"   1. 执行上述 MySQL 命令初始化数据库")
print(f"   2. 运行：python3 test_mysql_connection.py")
print(f"   3. 重启后端服务")
