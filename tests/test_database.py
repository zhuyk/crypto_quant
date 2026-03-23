#!/usr/bin/env python3
"""
数据库连接测试脚本
"""
import sys
from pathlib import Path
from dotenv import load_dotenv
import os

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# 加载环境变量
load_dotenv(Path(__file__).parent.parent / ".env")

def test_env():
    """测试环境变量加载"""
    print("\n" + "="*60)
    print("测试：环境变量加载")
    print("="*60)
    
    env_vars = {
        "ENVIRONMENT": os.getenv("ENVIRONMENT"),
        "DEBUG": os.getenv("DEBUG"),
        "DATABASE_URL": os.getenv("DATABASE_URL"),
        "REDIS_URL": os.getenv("REDIS_URL"),
        "BINANCE_TESTNET": os.getenv("BINANCE_TESTNET"),
    }
    
    for key, value in env_vars.items():
        status = "✅" if value else "❌"
        display_value = value[:50] + "..." if value and len(value) > 50 else value
        print(f"{status} {key}: {display_value}")
    
    return all(env_vars.values())


def test_database_schema():
    """测试数据库 Schema 文件"""
    print("\n" + "="*60)
    print("测试：数据库 Schema 文件")
    print("="*60)
    
    schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
    
    if not schema_path.exists():
        print("❌ Schema 文件不存在")
        return False
    
    with open(schema_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 检查关键表
    tables = [
        "users",
        "strategies",
        "backtest_runs",
        "trades",
        "positions",
        "klines",
    ]
    
    for table in tables:
        if f"CREATE TABLE IF NOT EXISTS {table}" in content or f"CREATE TABLE {table} (" in content:
            print(f"✅ 表 {table} 已定义")
        else:
            print(f"❌ 表 {table} 未定义")
    
    print(f"\n📊 Schema 文件大小：{len(content)} 字节")
    return True


def test_database_connection():
    """测试数据库连接（需要 Docker 运行）"""
    print("\n" + "="*60)
    print("测试：数据库连接")
    print("="*60)
    
    try:
        from sqlalchemy import create_engine, text
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "app"))
        from core.config import settings
        
        print(f"📡 尝试连接：{settings.DATABASE_URL[:50]}...")
        
        # 使用 pymysql 作为 MySQL 驱动
        engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"charset": "utf8mb4"}
        )
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ 数据库连接成功")
            
            # 尝试获取版本
            result = conn.execute(text("SELECT VERSION()"))
            version = result.fetchone()[0]
            print(f"📊 MySQL 版本：{version}")
            
        return True
        
    except ImportError as e:
        print(f"⚠️  模块导入失败：{e}")
        print("\n💡 提示：需要安装完整依赖")
        print("   运行：pip install pymysql cryptography")
        return False
    except Exception as e:
        error_msg = str(e)
        if "Connection" in error_msg or "refused" in error_msg.lower() or "can't connect" in error_msg.lower():
            print(f"❌ 数据库连接失败：无法连接到 MySQL 服务")
            print("\n💡 提示：请先启动 Docker 容器")
            print("   运行：docker-compose up -d mysql")
        else:
            print(f"❌ 数据库连接失败：{e}")
        return False


def test_redis_connection():
    """测试 Redis 连接（需要 Docker 运行）"""
    print("\n" + "="*60)
    print("测试：Redis 连接")
    print("="*60)
    
    try:
        import redis
        from core.config import settings
        
        print(f"📡 尝试连接：{settings.REDIS_URL}")
        
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        
        print("✅ Redis 连接成功")
        return True
        
    except Exception as e:
        print(f"❌ Redis 连接失败：{e}")
        print("\n💡 提示：请先启动 Docker 容器")
        print("   运行：docker-compose up -d redis")
        return False


def main():
    """运行所有测试"""
    print("\n" + "🚀"*30)
    print(" CryptoQuant 数据库连接测试")
    print("🚀"*30)
    
    results = {
        "环境变量": test_env(),
        "Schema 文件": test_database_schema(),
        "数据库连接": test_database_connection(),
        "Redis 连接": test_redis_connection(),
    }
    
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for test, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 所有测试通过！")
    else:
        print("\n⚠️  部分测试失败，请检查配置")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
