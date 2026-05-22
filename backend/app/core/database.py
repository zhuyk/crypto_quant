"""
数据库连接配置

支持 SQLite 和 MySQL，提供:
- 同步 Session (get_db)
- 异步兼容 Session (async_get_db) 用于 FastAPI Depends
- 连接池管理
- 重试机制
"""
from __future__ import annotations

from typing import Generator, AsyncGenerator
from contextlib import contextmanager

from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger

from app.core.config import settings


def _create_engine() -> Engine:
    """
    创建数据库引擎

    根据 DATABASE_URL 自动选择 SQLite 或 MySQL 并配置连接池。
    """
    db_url: str = settings.DATABASE_URL

    if settings.is_sqlite:
        logger.info("📊 使用 SQLite 数据库")
        return create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            echo=settings.DEBUG,
            future=True,
        )

    if settings.is_mysql or db_url.startswith("postgresql"):
        db_host = settings.db_host or "unknown"
        logger.info(f"🗄️  使用 {'MySQL' if settings.is_mysql else 'PostgreSQL'} 数据库: {db_host}")
        return create_engine(
            db_url,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_pre_ping=True,
            pool_recycle=settings.DATABASE_POOL_RECYCLE,
            echo=settings.DEBUG,
            future=True,
        )

    raise ValueError(f"不支持的数据库类型: {db_url.split(':')[0]}")


# 全局引擎和 Session 工厂
engine: Engine = _create_engine()
SessionLocal: sessionmaker[Session] = sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)

# ORM 基类
Base = declarative_base()


# ============================================================
# Session 获取
# ============================================================

@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    同步获取数据库会话（上下文管理器）

    Usage:
        with get_db() as db:
            db.query(...)
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def async_get_db() -> AsyncGenerator[Session, None]:
    """
    FastAPI 依赖注入用的异步 Session 生成器。

    内部使用同步 SQLAlchemy Session（通过 yield），
    FastAPI 会在请求结束时自动关闭。

    Usage:
        @router.get("/")
        async def endpoint(db: Session = Depends(async_get_db)):
            ...
    """
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ============================================================
# 初始化和工具函数
# ============================================================

def init_db(max_retries: int = 3, retry_delay: float = 2.0) -> None:
    """
    初始化数据库连接（带重试）

    Args:
        max_retries: 最大重试次数
        retry_delay: 重试间隔（秒）
    """
    import time

    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ 数据库连接成功")
            return
        except SQLAlchemyError as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(
                    f"数据库连接失败 (尝试 {attempt}/{max_retries}): {e}，"
                    f"{retry_delay}s 后重试..."
                )
                time.sleep(retry_delay)
                retry_delay *= 2  # 指数退避
            else:
                logger.error(f"❌ 数据库连接失败（已重试 {max_retries} 次）: {e}")

    if last_error:
        raise last_error


def create_tables() -> None:
    """创建所有 ORM 映射的表"""
    # 确保所有模型已导入
    from app.models import __all__ as _models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("✅ 数据库表创建/同步完成")


def execute_with_retry(
    func,
    *args,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    **kwargs,
):
    """
    带重试执行数据库操作

    Args:
        func: 要执行的可调用对象
        max_retries: 最大重试次数
        retry_delay: 初始延迟（秒）
    """
    import time

    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            return func(*args, **kwargs)
        except SQLAlchemyError as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(f"数据库操作失败，重试 {attempt}/{max_retries}: {e}")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise

    if last_error:
        raise last_error
