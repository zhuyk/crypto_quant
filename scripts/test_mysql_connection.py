#!/usr/bin/env python3
"""
MySQL 数据库连接测试脚本
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.core.config import settings
from app.core.database import engine
from sqlalchemy import text

print("="*60)
print("🔌 MySQL 数据库连接测试")
print("="*60)

print(f"\n📋 配置信息:")
print(f"   DATABASE_URL: {settings.DATABASE_URL[:50]}...")
print(f"   POOL_SIZE: {settings.DATABASE_POOL_SIZE}")
print(f"   MAX_OVERFLOW: {settings.DATABASE_MAX_OVERFLOW}")

print("\n📌 测试连接...")

try:
    # 测试连接
    with engine.connect() as conn:
        # 执行简单查询
        result = conn.execute(text("SELECT 1"))
        row = result.fetchone()
        
        if row and row[0] == 1:
            print("✅ 数据库连接成功！")
        
        # 获取数据库信息
        if settings.DATABASE_URL.startswith("mysql"):
            result = conn.execute(text("SELECT VERSION()"))
            version = result.fetchone()[0]
            print(f"   MySQL 版本：{version}")
            
            result = conn.execute(text("SELECT DATABASE()"))
            db_name = result.fetchone()[0]
            print(f"   当前数据库：{db_name}")
            
            result = conn.execute(text("SELECT USER()"))
            user_info = result.fetchone()[0]
            print(f"   用户：{user_info}")
            
            # 获取表数量
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE()
            """))
            table_count = result.fetchone()[0]
            print(f"   表数量：{table_count}")
        
        elif settings.DATABASE_URL.startswith("sqlite"):
            print("   数据库类型：SQLite")
            
            # 获取表数量
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM sqlite_master 
                WHERE type='table'
            """))
            table_count = result.fetchone()[0]
            print(f"   表数量：{table_count}")
        
        # 测试连接池
        print(f"\n📌 测试连接池...")
        connections = []
        for i in range(min(5, settings.DATABASE_POOL_SIZE)):
            conn = engine.connect()
            connections.append(conn)
            print(f"   ✅ 连接 {i+1} 成功")
        
        # 关闭连接
        for conn in connections:
            conn.close()
        
        print(f"\n✅ 连接池测试通过 - 大小：{settings.DATABASE_POOL_SIZE}")
    
    print("\n" + "="*60)
    print("🎉 数据库连接测试全部通过！")
    print("="*60)
    
    print(f"\n📝 下一步:")
    print(f"   1. 运行数据迁移脚本 (如果是从 SQLite 迁移)")
    print(f"   2. 重启后端服务")
    print(f"   3. 验证 API 功能")
    
    sys.exit(0)

except Exception as e:
    print(f"\n❌ 连接测试失败：{e}")
    print(f"\n💡 可能的解决方案:")
    
    if "Access denied" in str(e):
        print(f"   1. 检查用户名密码是否正确")
        print(f"   2. 运行数据库初始化脚本")
    elif "Can't connect" in str(e) or "Connection refused" in str(e):
        print(f"   1. 确保 MySQL 服务已启动")
        print(f"   2. 检查主机名和端口是否正确")
    elif "Unknown database" in str(e):
        print(f"   1. 运行数据库初始化脚本创建数据库")
        print(f"   2. 命令：cd database && ./init_mysql.sh")
    else:
        print(f"   1. 检查 .env 配置文件")
        print(f"   2. 查看完整错误信息")
    
    import traceback
    traceback.print_exc()
    sys.exit(1)
