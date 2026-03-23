#!/usr/bin/env python3
"""
数据库初始化脚本
读取 schema.sql 并执行
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import pymysql
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <level>{message}</level>")

# 加载环境变量
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# 获取数据库配置
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_ROOT_PASSWORD", "cryptoquant2026")
DB_NAME = os.getenv("DB_NAME", "crypto_quant")


def read_schema() -> str:
    """读取 schema.sql 文件"""
    schema_path = Path(__file__).parent / "schema.sql"
    
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema 文件不存在：{schema_path}")
    
    with open(schema_path, "r", encoding="utf-8") as f:
        return f.read()


def init_database():
    """初始化数据库"""
    logger.info("🗄️  开始初始化数据库...")
    
    try:
        # 连接到 MySQL (不指定数据库)
        logger.info(f"📡 连接到 MySQL: {DB_HOST}:{DB_PORT}")
        connection = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        
        with connection.cursor() as cursor:
            # 读取 schema
            logger.info("📄 读取 schema.sql...")
            schema = read_schema()
            
            # 执行 schema
            logger.info("⚙️  执行数据库初始化...")
            
            # 分割 SQL 语句 (按分号分割，但要注意存储过程等)
            statements = schema.split(";")
            
            success_count = 0
            error_count = 0
            
            for stmt in statements:
                stmt = stmt.strip()
                if not stmt:
                    continue
                
                try:
                    cursor.execute(stmt)
                    success_count += 1
                except Exception as e:
                    error_msg = str(e)
                    if "already exists" not in error_msg.lower() and "duplicate" not in error_msg.lower():
                        logger.warning(f"⚠️  执行失败 (可能已存在): {error_msg[:100]}")
                    error_count += 1
            
            connection.commit()
            
            logger.info(f"✅ 数据库初始化完成!")
            logger.info(f"   成功：{success_count} 条语句")
            logger.info(f"   警告/跳过：{error_count} 条语句")
        
        # 验证连接
        logger.info(f"🔍 验证数据库连接...")
        with connection.cursor() as cursor:
            cursor.execute(f"USE {DB_NAME}")
            cursor.execute("SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema = %s", (DB_NAME,))
            result = cursor.fetchone()
            logger.info(f"📊 数据库表数量：{result['table_count']}")
        
        connection.close()
        
        return True
        
    except pymysql.Error as e:
        logger.error(f"❌ 数据库错误：{e}")
        return False
    except Exception as e:
        logger.error(f"❌ 初始化失败：{e}")
        return False


def main():
    """主函数"""
    logger.info("="*60)
    logger.info(" CryptoQuant 数据库初始化")
    logger.info("="*60)
    
    success = init_database()
    
    if success:
        logger.info("🎉 数据库初始化成功!")
        return 0
    else:
        logger.error("❌ 数据库初始化失败!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
