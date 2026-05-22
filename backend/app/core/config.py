"""
应用配置 - 基于 Pydantic Settings

特性:
- 环境变量自动加载 (.env 文件)
- 类型验证和转换
- 配置分组（数据库/安全/交易/数据采集）
- 自定义验证器
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator
from typing import List, Optional
from pathlib import Path


class Settings(BaseSettings):
    """
    应用配置
    
    所有配置项可通过环境变量或 .env 文件覆盖。
    字段名即环境变量名（大写）。
    """
    
    # ==================== 基础配置 ====================
    APP_NAME: str = "CryptoQuant"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # ==================== 数据库配置 ====================
    # Docker 初始化用
    DB_ROOT_PASSWORD: str = ""
    DB_USER: str = "cryptoquant"
    DB_PASSWORD: str = "cryptoquant2026"
    
    # 连接 URL（SQLite / MySQL）
    DATABASE_URL: str = "sqlite:///./crypto_quant_dev.db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_RECYCLE: int = 3600  # 秒
    
    # ==================== Redis 配置 ====================
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_DB: int = 0
    
    # ==================== 安全配置 ====================
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    
    # ==================== 交易所配置 ====================
    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""
    BINANCE_TESTNET: bool = True
    
    # 代理（用于访问交易所 API）
    PROXY_URL: str = ""
    
    # ==================== Celery 配置 ====================
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    
    # ==================== 日志配置 ====================
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/cryptoquant.log"
    
    # ==================== 交易风控配置 ====================
    DEFAULT_INITIAL_CAPITAL: float = 100000.0
    MAX_POSITION_RATIO: float = 0.8
    MAX_DAILY_LOSS: float = 0.05
    MAX_DRAWDOWN: float = 0.20
    
    # ==================== 数据采集配置 ====================
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

    # ==================== 验证器 ====================

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """确保日志级别合法"""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"无效日志级别: {v}，允许: {valid_levels}")
        return v

    @field_validator("MAX_POSITION_RATIO")
    @classmethod
    def validate_position_ratio(cls, v: float) -> float:
        """仓位比例必须在 0-1 之间"""
        if not 0 < v <= 1.0:
            raise ValueError(f"MAX_POSITION_RATIO 必须在 (0, 1] 之间，当前: {v}")
        return v

    @field_validator("MAX_DAILY_LOSS", "MAX_DRAWDOWN")
    @classmethod
    def validate_loss_limits(cls, v: float) -> float:
        """亏损限制必须在 0-1 之间"""
        if not 0 < v < 1.0:
            raise ValueError(f"亏损限制必须在 (0, 1) 之间，当前: {v}")
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """检查数据库 URL 格式"""
        if not v:
            raise ValueError("DATABASE_URL 不能为空")
        supported_prefixes = ("sqlite", "mysql", "postgresql")
        if not any(v.startswith(p) for p in supported_prefixes):
            raise ValueError(f"DATABASE_URL 前缀必须是 {supported_prefixes} 之一")
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str, info) -> str:
        """生产环境必须修改 SECRET_KEY"""
        # info.data 包含已解析的字段
        # 注: 此处无法可靠获取 ENVIRONMENT，仅做警告级别的检查
        if v == "your-secret-key-change-in-production":
            import warnings
            warnings.warn(
                "SECRET_KEY 使用默认值，请在生产环境中修改！",
                UserWarning,
                stacklevel=2,
            )
        return v

    # ==================== 便捷属性 ====================

    @property
    def is_production(self) -> bool:
        """是否生产环境"""
        return self.ENVIRONMENT in ("production", "prod")

    @property
    def is_development(self) -> bool:
        """是否开发环境"""
        return self.ENVIRONMENT in ("development", "dev")

    @property
    def is_sqlite(self) -> bool:
        """是否使用 SQLite"""
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def is_mysql(self) -> bool:
        """是否使用 MySQL"""
        return self.DATABASE_URL.startswith("mysql")

    @property
    def db_host(self) -> Optional[str]:
        """提取数据库主机（仅 MySQL）"""
        if "@" in self.DATABASE_URL:
            return self.DATABASE_URL.split("@")[-1].split("/")[0]
        return None

    class Config:
        env_file = ".env"
        case_sensitive = True


# 创建全局配置实例
settings = Settings()
