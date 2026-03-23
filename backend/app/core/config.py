"""
应用配置
"""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """应用配置"""
    
    # 基础配置
    APP_NAME: str = "CryptoQuant"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # 数据库用户配置（用于 Docker 初始化）
    DB_ROOT_PASSWORD: str = ""
    DB_USER: str = "cryptoquant"
    DB_PASSWORD: str = "cryptoquant2026"
    
    # 数据库配置
    # 使用 SQLite 作为开发数据库（Docker 不可用时）
    DATABASE_URL: str = "sqlite:///./crypto_quant_dev.db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    
    # Redis 配置
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_DB: int = 0
    
    # 安全配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天
    
    # CORS 配置（开发环境允许所有来源）
    CORS_ORIGINS: List[str] = ["*"]
    
    # Binance 配置
    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""
    BINANCE_TESTNET: bool = True
    
    # 代理配置
    PROXY_URL: str = ""
    
    # Celery 配置
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/cryptoquant.log"
    
    # 交易配置
    DEFAULT_INITIAL_CAPITAL: float = 100000.0
    MAX_POSITION_RATIO: float = 0.8
    MAX_DAILY_LOSS: float = 0.05
    MAX_DRAWDOWN: float = 0.20
    
    # 数据采集配置
    DATA_COLLECTOR_INTERVAL: int = 60  # 秒
    DEFAULT_SYMBOLS: List[str] = [
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "SOLUSDT",
        "XRPUSDT",
    ]
    DEFAULT_TIMEFRAMES: List[str] = [
        "1m",
        "5m",
        "15m",
        "1h",
        "4h",
        "1d",
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# 创建全局配置实例
settings = Settings()
