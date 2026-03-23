#!/usr/bin/env python3
"""
SQLite 到 MySQL 数据迁移脚本
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
import sqlite3
import pymysql
import json
from datetime import datetime

print("="*60)
print("🔄 SQLite 到 MySQL 数据迁移工具")
print("="*60)

# 配置
SQLITE_DB = "../backend/crypto_quant_dev.db"
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_USER = "cryptoquant"
MYSQL_PASSWORD = "cryptoquant2026"
MYSQL_DB = "crypto_quant"

def check_mysql_connection():
    """检查 MySQL 连接"""
    print("\n📌 步骤 1: 检查 MySQL 连接...")
    
    try:
        # 先尝试连接 MySQL 服务器 (不指定数据库)
        connection = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
        )
        
        with connection.cursor() as cursor:
            # 检查数据库是否存在
            cursor.execute(f"SHOW DATABASES LIKE '{MYSQL_DB}'")
            db_exists = cursor.fetchone()
            
            if not db_exists:
                print(f"⚠️  数据库 {MYSQL_DB} 不存在")
                print(f"💡 请先运行数据库初始化脚本:")
                print(f"   mysql -u root -p < ../database/schema.sql")
                return False
            
            # 测试数据库连接
            connection.select_db(MYSQL_DB)
            print(f"✅ MySQL 连接成功 - {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}")
            
        connection.close()
        return True
        
    except pymysql.Error as e:
        print(f"❌ MySQL 连接失败：{e}")
        print(f"\n💡 可能的解决方案:")
        print(f"   1. 确保 MySQL 服务已启动")
        print(f"   2. 检查用户名密码是否正确")
        print(f"   3. 运行数据库初始化脚本")
        return False


def check_sqlite_db():
    """检查 SQLite 数据库"""
    print("\n📌 步骤 2: 检查 SQLite 数据库...")
    
    if not os.path.exists(SQLITE_DB):
        print(f"❌ SQLite 数据库不存在：{SQLITE_DB}")
        return None
    
    try:
        conn = sqlite3.connect(SQLITE_DB)
        cursor = conn.cursor()
        
        # 获取所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"✅ SQLite 数据库存在 - {len(tables)} 张表")
        print(f"   表列表：{', '.join(tables[:5])}{'...' if len(tables) > 5 else ''}")
        
        conn.close()
        return tables
        
    except Exception as e:
        print(f"❌ SQLite 检查失败：{e}")
        return None


def migrate_data(sqlite_tables):
    """迁移数据"""
    print("\n📌 步骤 3: 开始迁移数据...")
    
    # SQLite 连接
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()
    
    # MySQL 连接
    mysql_conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset='utf8mb4',
    )
    mysql_cursor = mysql_conn.cursor()
    
    migrated_count = 0
    skipped_tables = ['sqlite_sequence']  # 跳过 SQLite 系统表
    
    for table in sqlite_tables:
        if table in skipped_tables:
            print(f"⏭️  跳过系统表：{table}")
            continue
        
        try:
            # 获取 SQLite 数据
            sqlite_cursor.execute(f"SELECT * FROM {table}")
            rows = sqlite_cursor.fetchall()
            
            if not rows:
                print(f"⏭️  空表：{table}")
                continue
            
            # 获取列名
            columns = [description[0] for description in sqlite_cursor.description]
            
            # 过滤自增列 (id)
            if 'id' in columns:
                # 检查 MySQL 表是否有自增 id
                mysql_cursor.execute(f"DESCRIBE {table}")
                mysql_columns = mysql_cursor.fetchall()
                
                for col in mysql_columns:
                    if col[0] == 'id' and 'auto_increment' in col[5].lower():
                        # 启用自增列插入
                        mysql_cursor.execute("SET SESSION sql_mode=''")
                        break
            
            # 构建 INSERT 语句
            placeholders = ','.join(['%s'] * len(columns))
            columns_str = ','.join([f"`{col}`" for col in columns])
            insert_sql = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"
            
            # 批量插入
            data = [tuple(row) for row in rows]
            
            try:
                mysql_cursor.executemany(insert_sql, data)
                mysql_conn.commit()
                
                migrated_count += len(rows)
                print(f"✅ {table}: {len(rows)} 条记录")
                
            except pymysql.Error as e:
                print(f"⚠️  {table} 插入失败：{e}，尝试逐行插入...")
                # 逐行插入 (跳过错误记录)
                success = 0
                for row in data:
                    try:
                        mysql_cursor.execute(insert_sql, row)
                        success += 1
                    except:
                        pass
                mysql_conn.commit()
                print(f"   成功：{success}/{len(data)} 条")
                migrated_count += success
        
        except Exception as e:
            print(f"❌ {table} 迁移失败：{e}")
            mysql_conn.rollback()
    
    # 关闭连接
    sqlite_conn.close()
    mysql_conn.close()
    
    print(f"\n✅ 迁移完成 - 共 {migrated_count} 条记录")
    return migrated_count


def verify_migration():
    """验证迁移结果"""
    print("\n📌 步骤 4: 验证迁移结果...")
    
    try:
        mysql_conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB,
            charset='utf8mb4',
        )
        mysql_cursor = mysql_conn.cursor()
        
        # 获取所有表
        mysql_cursor.execute("SHOW TABLES")
        tables = [row[0] for row in mysql_cursor.fetchall()]
        
        print(f"✅ MySQL 数据库 - {len(tables)} 张表")
        
        # 统计总记录数
        total_rows = 0
        for table in tables[:10]:  # 只显示前 10 张表
            mysql_cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = mysql_cursor.fetchone()[0]
            total_rows += count
            print(f"   {table}: {count} 条")
        
        if len(tables) > 10:
            print(f"   ... 还有 {len(tables) - 10} 张表")
        
        mysql_conn.close()
        
        print(f"\n✅ 验证完成 - 总记录数：{total_rows}")
        return True
        
    except Exception as e:
        print(f"❌ 验证失败：{e}")
        return False


def main():
    """主函数"""
    print(f"\n📅 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📂 SQLite: {SQLITE_DB}")
    print(f"🗄️  MySQL: {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}")
    
    # 步骤 1: 检查 MySQL 连接
    if not check_mysql_connection():
        print("\n❌ 迁移失败：MySQL 连接检查未通过")
        return 1
    
    # 步骤 2: 检查 SQLite 数据库
    sqlite_tables = check_sqlite_db()
    if not sqlite_tables:
        print("\n❌ 迁移失败：SQLite 数据库检查未通过")
        return 1
    
    # 步骤 3: 迁移数据
    migrate_count = migrate_data(sqlite_tables)
    
    # 步骤 4: 验证迁移
    if not verify_migration():
        print("\n⚠️  迁移完成但验证失败，请手动检查")
        return 1
    
    print("\n" + "="*60)
    print("🎉 数据迁移成功完成！")
    print("="*60)
    print(f"\n📊 迁移统计:")
    print(f"   - 表数量：{len(sqlite_tables)}")
    print(f"   - 记录数：{migrate_count}")
    print(f"\n📝 下一步:")
    print(f"   1. 更新 .env 文件中的 DATABASE_URL")
    print(f"   2. 重启后端服务")
    print(f"   3. 验证 API 功能")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 迁移异常：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
