"""
异常处理模块
自定义异常类和统一错误响应

提供:
- CryptoQuantException 基类及子类层次
- 错误/成功响应格式化工具
- 重试装饰器
"""
from __future__ import annotations

from typing import Optional, Any, Dict, Tuple, Type
from fastapi import HTTPException, status

__all__ = [
    # 基类
    "CryptoQuantException",
    # 4xx 客户端错误
    "ValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "RateLimitError",
    "ConflictError",
    # 5xx 服务端错误
    "DatabaseError",
    "CacheError",
    "ExternalAPIError",
    "TradingError",
    "InsufficientFundsError",
    "OrderError",
    "StrategyError",
    "ConfigurationError",
    # 工具函数
    "handle_exception",
    "error_response",
    "success_response",
    "ok",
    "ok_list",
    "fail",
    "created",
    "deleted",
    "retry_on_exception",
]


class CryptoQuantException(Exception):
    """基础异常类"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "UNKNOWN_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


# ============================================
# 客户端错误 (4xx)
# ============================================

class ValidationError(CryptoQuantException):
    """参数验证错误"""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class AuthenticationError(CryptoQuantException):
    """认证失败"""
    
    def __init__(self, message: str = "认证失败"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class AuthorizationError(CryptoQuantException):
    """授权失败"""
    
    def __init__(self, message: str = "无权访问"):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class NotFoundError(CryptoQuantException):
    """资源不存在"""
    
    def __init__(self, resource: str, resource_id: Optional[str] = None):
        message = f"{resource}不存在"
        if resource_id:
            message += f": {resource_id}"
        
        super().__init__(
            message=message,
            error_code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "resource_id": resource_id},
        )


class RateLimitError(CryptoQuantException):
    """限流错误"""
    
    def __init__(
        self,
        message: str = "请求过于频繁",
        retry_after: Optional[float] = None,
    ):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after": retry_after},
        )


class ConflictError(CryptoQuantException):
    """资源冲突"""
    
    def __init__(self, message: str = "资源冲突"):
        super().__init__(
            message=message,
            error_code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
        )


# ============================================
# 服务端错误 (5xx)
# ============================================

class DatabaseError(CryptoQuantException):
    """数据库错误"""
    
    def __init__(
        self,
        message: str = "数据库操作失败",
        details: Optional[Dict] = None,
    ):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class CacheError(CryptoQuantException):
    """缓存错误"""
    
    def __init__(
        self,
        message: str = "缓存操作失败",
        details: Optional[Dict] = None,
    ):
        super().__init__(
            message=message,
            error_code="CACHE_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class ExternalAPIError(CryptoQuantException):
    """外部 API 错误（如 Binance）"""
    
    def __init__(
        self,
        message: str = "外部服务调用失败",
        service: Optional[str] = None,
        details: Optional[Dict] = None,
    ):
        super().__init__(
            message=message,
            error_code="EXTERNAL_API_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={"service": service, **(details or {})},
        )


class TradingError(CryptoQuantException):
    """交易错误"""
    
    def __init__(
        self,
        message: str = "交易操作失败",
        error_code: str = "TRADING_ERROR",
        details: Optional[Dict] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class InsufficientFundsError(TradingError):
    """资金不足"""
    
    def __init__(
        self,
        message: str = "资金不足",
        details: Optional[Dict] = None,
    ):
        super().__init__(
            message=message,
            error_code="INSUFFICIENT_FUNDS",
            details=details,
        )


class OrderError(TradingError):
    """订单错误"""
    
    def __init__(
        self,
        message: str = "订单操作失败",
        error_code: str = "ORDER_ERROR",
        details: Optional[Dict] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
        )


class StrategyError(CryptoQuantException):
    """策略错误"""
    
    def __init__(
        self,
        message: str = "策略执行失败",
        details: Optional[Dict] = None,
    ):
        super().__init__(
            message=message,
            error_code="STRATEGY_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class ConfigurationError(CryptoQuantException):
    """配置错误"""
    
    def __init__(
        self,
        message: str = "配置错误",
        details: Optional[Dict] = None,
    ):
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


# ============================================
# 异常处理器
# ============================================

def handle_exception(exc: Exception) -> CryptoQuantException:
    """
    将普通异常转换为 CryptoQuantException
    
    Args:
        exc: 原始异常
    
    Returns:
        转换后的异常
    """
    # 已经是自定义异常，直接返回
    if isinstance(exc, CryptoQuantException):
        return exc
    
    # 数据库相关异常
    exc_name = type(exc).__name__
    if "SQL" in exc_name or "Database" in exc_name:
        return DatabaseError(
            message=f"数据库错误：{str(exc)}",
            details={"original_error": exc_name},
        )
    
    # 连接相关异常
    if "Connection" in exc_name or "Timeout" in exc_name:
        return ExternalAPIError(
            message=f"连接错误：{str(exc)}",
            details={"original_error": exc_name},
        )
    
    # 默认返回通用错误
    return CryptoQuantException(
        message=str(exc),
        error_code="INTERNAL_ERROR",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


# ============================================
# 标准响应格式 (代理到 responses 模块)
# ============================================

from app.core.responses import (
    success_response,
    error_response,
    ok,
    ok_list,
    fail,
    created,
    deleted,
)


# ============================================
# 重试装饰器
# ============================================

import functools
import time
from typing import Tuple, Type


def retry_on_exception(
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    logger_func=None,
):
    """
    重试装饰器
    
    Args:
        exceptions: 需要重试的异常类型
        max_retries: 最大重试次数
        delay: 初始延迟 (秒)
        backoff: 延迟倍数
        logger_func: 日志记录函数
    
    Example:
        @retry_on_exception(exceptions=(ConnectionError,), max_retries=3)
        def fetch_data():
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        break
                    
                    if logger_func:
                        logger_func(
                            f"Retry {attempt + 1}/{max_retries} after {current_delay:.2f}s - {str(e)}"
                        )
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            # 所有重试失败，抛出最后一次异常
            if last_exception:
                raise last_exception
            
            return None
        
        return wrapper
    return decorator
