"""
数据库连接配置
支持 SQLite 和 MySQL
"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger
from typing import Generator
from contextlib import contextmanager
from app.core.config import settings
from app.utils.retry import database_retry_handler, RetryError


def create_db_engine():
    """
    创建数据库引擎
    
    根据 DATABASE_URL 自动选择 SQLite 或 MySQL
    """
    db_url = settings.DATABASE_URL
    
    # 检测数据库类型
    if db_url.startswith("sqlite"):
        logger.info("📊 使用 SQLite 数据库")
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            echo=settings.DEBUG,
        )
    elif db_url.startswith("mysql"):
        logger.info(f"🗄️  使用 MySQL 数据库: {db_url.split('@')[-1] if '@' in db_url else 'N/A'}")
        engine = create_engine(
            db_url,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_pre_ping=True,  # 连接前 ping 测试
            pool_recycle=3600,   # 1 小时回收连接
            echo=settings.DEBUG,
        )
    else:
        raise ValueError(f"不支持的数据库类型：{db_url}")
    
    return engine


# 创建数据库引擎
engine = create_db_engine()

# 创建 Session 工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()


@contextmanager
def get_db() -> Generator:
    """
    获取数据库会话（同步版本，上下文管理器）
    
    自动处理会话关闭和异常
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        db.close()


async def async_get_db():
    """
    异步获取数据库会话
    
    在 async 路由中使用 Depends(async_get_db)，
    内部通过线程池执行同步 SQLAlchemy Session 操作。
    """
    import asyncio
    from functools import partial
    
    db = SessionLocal()
    try:
        # 将同步操作封装为线程池调用
        yield db
    except Exception as e:
        db.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        # 在线程池中执行 close，避免阻塞事件循环
        await asyncio.get_event_loop().run_in_executor(None, db.close)


def init_db():
    """
    初始化数据库（带重试）
    """
    def _test_connection():
        connection = engine.connect()
        connection.close()
        return True
    
    try:
        # 使用重试处理器执行连接测试
        database_retry_handler.execute(_test_connection, exceptions=(SQLAlchemyError,))
        logger.info("✅ 数据库连接成功")
    except SQLAlchemyError as e:
        logger.error(f"❌ 数据库连接失败：{e}")
        raise
    except Exception as e:
        logger.error(f"❌ 数据库初始化异常：{e}")
        raise


def create_tables():
    """创建所有表"""
    from app.models import user, account, strategy, symbol, order, position, trade, performance, backtest
    
    Base.metadata.create_all(bind=engine)
    logger.info("✅ 数据库表创建成功")


def execute_with_retry(func, *args, max_retries: int = 3, **kwargs):
    """
    带重试执行数据库操作
    
    Args:
        func: 要执行的函数
        args: 函数参数
        max_retries: 最大重试次数
        kwargs: 函数关键字参数
    """
    handler = database_retry_handler
    handler.max_attempts = max_retries
    return handler.execute(func, *args, exceptions=(SQLAlchemyError,), **kwargs)
