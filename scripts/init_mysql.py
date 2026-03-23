#!/usr/bin/env python3
"""
MySQL 数据库初始化 Python 脚本
"""
import pymysql
import sys
import os

print("="*60)
print("🗄️  MySQL 数据库初始化")
print("="*60)

# 配置
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_DB = "crypto_quant"
DB_USER = "cryptoquant"
DB_PASSWORD = "cryptoquant2026"
SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "..", "database", "schema.sql")

print(f"\n📋 配置信息:")
print(f"   主机：{MYSQL_HOST}:{MYSQL_PORT}")
print(f"   数据库：{MYSQL_DB}")
print(f"   用户：{DB_USER}")

# 步骤 1: 连接 MySQL
print("\n📌 步骤 1: 连接 MySQL 服务器...")
try:
    # 尝试无密码连接 (本地 socket)
    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
        )
        print("✅ MySQL 连接成功 (无密码)")
    except pymysql.Error:
        # 尝试读取 .my.cnf 或 socket 认证
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            read_default_file='~/.my.cnf',
        )
        print("✅ MySQL 连接成功 (~/.my.cnf)")
        
except Exception as e:
    print(f"❌ MySQL 连接失败：{e}")
    print(f"\n💡 请使用以下命令手动初始化:")
    print(f"   mysql -u root -p < {SCHEMA_FILE}")
    sys.exit(1)

cursor = conn.cursor()

# 步骤 2: 创建数据库
print("\n📌 步骤 2: 创建数据库...")
try:
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    print(f"✅ 数据库 {MYSQL_DB} 创建成功")
except Exception as e:
    print(f"⚠️  数据库创建可能已存在：{e}")

# 步骤 3: 创建用户
print("\n📌 步骤 3: 创建用户...")
try:
    # 删除旧用户 (如果存在)
    cursor.execute(f"DROP USER IF EXISTS '{DB_USER}'@'localhost'")
    
    # 创建新用户
    cursor.execute(f"CREATE USER '{DB_USER}'@'localhost' IDENTIFIED BY '{DB_PASSWORD}'")
    print(f"✅ 用户 {DB_USER} 创建成功")
except Exception as e:
    print(f"❌ 用户创建失败：{e}")

# 步骤 4: 授权
print("\n📌 步骤 4: 授权...")
try:
    cursor.execute(f"GRANT ALL PRIVILEGES ON {MYSQL_DB}.* TO '{DB_USER}'@'localhost'")
    cursor.execute("FLUSH PRIVILEGES")
    print(f"✅ 用户 {DB_USER} 已授权")
except Exception as e:
    print(f"❌ 授权失败：{e}")

# 步骤 5: 导入表结构
print("\n📌 步骤 5: 导入表结构...")
if os.path.exists(SCHEMA_FILE):
    try:
        # 切换到新数据库
        cursor.execute(f"USE {MYSQL_DB}")
        
        # 读取并执行 SQL 文件
        with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # 分割 SQL 语句 (按分号)
        statements = sql_script.split(';')
        
        executed = 0
        for statement in statements:
            statement = statement.strip()
            if statement and not statement.startswith('--'):
                try:
                    cursor.execute(statement)
                    executed += 1
                except Exception as e:
                    # 忽略已存在表的错误
                    if 'already exists' not in str(e).lower():
                        print(f"⚠️  执行 SQL 失败：{e}")
        
        conn.commit()
        print(f"✅ 表结构导入成功 (执行 {executed} 条语句)")
        
    except Exception as e:
        print(f"❌ 表结构导入失败：{e}")
else:
    print(f"⚠️  Schema 文件不存在：{SCHEMA_FILE}")

# 步骤 6: 验证
print("\n📌 步骤 6: 验证...")
try:
    cursor.execute(f"USE {MYSQL_DB}")
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    print(f"✅ 数据库 {MYSQL_DB} 中有 {len(tables)} 张表")
    
    if tables:
        print(f"   表列表：{', '.join([t[0] for t in tables[:5]])}{'...' if len(tables) > 5 else ''}")
except Exception as e:
    print(f"❌ 验证失败：{e}")

# 步骤 7: 测试新用户连接
print("\n📌 步骤 7: 测试新用户连接...")
try:
    test_conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=MYSQL_DB,
    )
    test_cursor = test_conn.cursor()
    test_cursor.execute("SELECT VERSION()")
    version = test_cursor.fetchone()[0]
    print(f"✅ 新用户连接成功 - MySQL {version}")
    test_conn.close()
except Exception as e:
    print(f"❌ 新用户连接失败：{e}")

# 清理
cursor.close()
conn.close()

print("\n" + "="*60)
print("🎉 MySQL 数据库初始化完成！")
print("="*60)

print(f"\n📝 连接信息:")
print(f"   主机：{MYSQL_HOST}:{MYSQL_PORT}")
print(f"   数据库：{MYSQL_DB}")
print(f"   用户：{DB_USER}")
print(f"   密码：{DB_PASSWORD}")

print(f"\n📝 SQLAlchemy URL:")
print(f"   mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}")

print(f"\n📝 .env 配置:")
print(f"   DATABASE_URL=mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}")

print(f"\n📝 下一步:")
print(f"   1. cp .env.mysql .env")
print(f"   2. python3 scripts/test_mysql_connection.py")
print(f"   3. cd backend && python3 -m uvicorn app.main:app --reload")
