"""
限流模块
基于令牌桶算法的 API 限流
"""
import time
import random
import logging
import secrets
from functools import wraps
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from app.utils.cache import get_cache, CacheKeys


logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    """限流结果"""
    allowed: bool
    remaining: int
    reset_at: float
    retry_after: Optional[float] = None


class TokenBucket:
    """
    令牌桶限流器
    
    适用于 API 请求限流
    """
    
    def __init__(
        self,
        rate: float,  # 令牌生成速率（个/秒）
        capacity: int,  # 桶容量（最大令牌数）
        cache_client=None,
    ):
        """
        Args:
            rate: 令牌生成速率
            capacity: 桶容量
            cache_client: Redis 缓存客户端
        """
        self.rate = rate
        self.capacity = capacity
        self.cache = cache_client or get_cache()
    
    def _get_bucket_key(self, identifier: str) -> str:
        """生成桶键"""
        return f"{CacheKeys.RATE_LIMIT}:bucket:{identifier}"
    
    def _get_timestamp_key(self, identifier: str) -> str:
        """生成时间戳键"""
        return f"{CacheKeys.RATE_LIMIT}:timestamp:{identifier}"
    
    def consume(
        self,
        identifier: str,
        tokens: int = 1,
    ) -> RateLimitResult:
        """
        消费令牌
        
        Args:
            identifier: 限流标识（如 user_id, ip 等）
            tokens: 需要消费的令牌数
        
        Returns:
            限流结果
        """
        now = time.time()
        bucket_key = self._get_bucket_key(identifier)
        timestamp_key = self._get_timestamp_key(identifier)
        
        # 获取当前状态
        last_update = float(self.cache.get(timestamp_key) or 0)
        current_tokens = float(self.cache.get(bucket_key) or self.capacity)
        
        # 计算新增令牌
        elapsed = now - last_update
        new_tokens = elapsed * self.rate
        current_tokens = min(self.capacity, current_tokens + new_tokens)
        
        # 检查是否有足够令牌
        if current_tokens >= tokens:
            # 消费令牌
            current_tokens -= tokens
            self.cache.set(bucket_key, current_tokens, expire=3600)
            self.cache.set(timestamp_key, now, expire=3600)
            
            remaining = int(current_tokens)
            reset_at = now + (self.capacity - current_tokens) / self.rate
            
            return RateLimitResult(
                allowed=True,
                remaining=remaining,
                reset_at=reset_at,
            )
        else:
            # 令牌不足
            self.cache.set(bucket_key, current_tokens, expire=3600)
            self.cache.set(timestamp_key, now, expire=3600)
            
            # 计算需要等待的时间
            tokens_needed = tokens - current_tokens
            retry_after = tokens_needed / self.rate
            reset_at = now + retry_after
            
            return RateLimitResult(
                allowed=False,
                remaining=int(current_tokens),
                reset_at=reset_at,
                retry_after=retry_after,
            )
    
    def get_status(self, identifier: str) -> Dict:
        """获取限流状态"""
        now = time.time()
        bucket_key = self._get_bucket_key(identifier)
        timestamp_key = self._get_timestamp_key(identifier)
        
        current_tokens = float(self.cache.get(bucket_key) or self.capacity)
        last_update = float(self.cache.get(timestamp_key) or now)
        
        # 计算当前令牌数
        elapsed = now - last_update
        current_tokens = min(self.capacity, current_tokens + elapsed * self.rate)
        
        return {
            "tokens": int(current_tokens),
            "capacity": self.capacity,
            "rate": self.rate,
            "refill_time": (self.capacity - current_tokens) / self.rate,
        }
    
    def reset(self, identifier: str):
        """重置限流桶"""
        bucket_key = self._get_bucket_key(identifier)
        timestamp_key = self._get_timestamp_key(identifier)
        self.cache.delete(bucket_key)
        self.cache.delete(timestamp_key)


class SlidingWindowCounter:
    """
    滑动窗口计数器限流器
    
    更精确的限流，但内存消耗稍大
    """
    
    def __init__(
        self,
        max_requests: int,
        window_seconds: int,
        cache_client=None,
    ):
        """
        Args:
            max_requests: 窗口内最大请求数
            window_seconds: 窗口大小（秒）
            cache_client: Redis 缓存客户端
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.cache = cache_client or get_cache()
    
    def _get_key(self, identifier: str) -> str:
        """生成键"""
        return f"{CacheKeys.RATE_LIMIT}:window:{identifier}"
    
    def allow(self, identifier: str) -> RateLimitResult:
        """
        检查是否允许请求
        
        Args:
            identifier: 限流标识
        
        Returns:
            限流结果
        """
        now = time.time()
        key = self._get_key(identifier)
        window_start = now - self.window_seconds
        
        # 获取当前窗口内的请求
        requests = self.cache.client.zrangebyscore(
            key,
            window_start,
            now,
            start=0,
            num=self.max_requests,
        )
        
        current_count = len(requests)
        
        if current_count < self.max_requests:
            # 允许请求，记录时间戳
            self.cache.client.zadd(key, {f"{now}:{secrets.token_hex(8)}": now})
            self.cache.client.expire(key, self.window_seconds + 1)
            
            remaining = self.max_requests - current_count - 1
            reset_at = now + self.window_seconds
            
            return RateLimitResult(
                allowed=True,
                remaining=remaining,
                reset_at=reset_at,
            )
        else:
            # 限流
            # 获取最早请求的时间
            oldest = self.cache.client.zrange(key, 0, 0, withscores=True)
            if oldest:
                retry_after = oldest[0][1] + self.window_seconds - now
            else:
                retry_after = self.window_seconds
            
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=now + retry_after,
                retry_after=retry_after,
            )


class RateLimiter:
    """
    统一限流器
    
    提供多种限流策略
    """
    
    # 预定义的限流配置（测试阶段放宽）
    CONFIGS = {
        "default": {"rate": 100, "capacity": 200},  # 默认：100 次/秒
        "api": {"rate": 50, "capacity": 100},  # API：50 次/秒
        "login": {"rate": 1, "capacity": 20},  # 登录：60 次/分钟
        "trade": {"rate": 20, "capacity": 50},  # 交易：20 次/秒
        "backtest": {"rate": 5, "capacity": 10},  # 回测：5 次/秒
    }
    
    def __init__(self):
        self._buckets: Dict[str, TokenBucket] = {}
        
        # 初始化预定义桶
        for name, config in self.CONFIGS.items():
            self._buckets[name] = TokenBucket(
                rate=config["rate"],
                capacity=config["capacity"],
            )
    
    def get_bucket(self, name: str = "default") -> TokenBucket:
        """获取限流桶"""
        if name not in self._buckets:
            logger.warning(f"Unknown rate limit bucket: {name}, using default")
            return self._buckets["default"]
        return self._buckets[name]
    
    def check(
        self,
        identifier: str,
        bucket_name: str = "default",
        tokens: int = 1,
    ) -> RateLimitResult:
        """
        检查限流
        
        Args:
            identifier: 限流标识
            bucket_name: 桶名称
            tokens: 需要消费的令牌数
        
        Returns:
            限流结果
        """
        bucket = self.get_bucket(bucket_name)
        return bucket.consume(identifier, tokens)
    
    def check_login(self, identifier: str) -> RateLimitResult:
        """检查登录限流"""
        return self.check(identifier, "login")
    
    def check_trade(self, identifier: str) -> RateLimitResult:
        """检查交易限流"""
        return self.check(identifier, "trade")
    
    def check_backtest(self, identifier: str) -> RateLimitResult:
        """检查回测限流"""
        return self.check(identifier, "backtest")


# 全局限流器实例
rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """获取限流器"""
    return rate_limiter


# 限流装饰器
def rate_limit(
    bucket_name: str = "default",
    identifier_arg: Optional[str] = None,
):
    """
    限流装饰器（支持同步和异步函数）
    
    Args:
        bucket_name: 限流桶名称
        identifier_arg: 用于标识的参数名（默认使用第一个参数）
    
    Example:
        @rate_limit(bucket_name="login", identifier_arg="username")
        async def login(username: str, password: str):
            ...
    """
    import asyncio
    from inspect import iscoroutinefunction
    
    def decorator(func):
        if iscoroutinefunction(func):
            # 异步函数版本
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                limiter = get_rate_limiter()
                
                # 获取标识符
                if identifier_arg and identifier_arg in kwargs:
                    identifier = kwargs[identifier_arg]
                elif args:
                    identifier = args[0]
                else:
                    identifier = "unknown"
                
                # 检查限流
                result = limiter.check(identifier, bucket_name)
                
                if not result.allowed:
                    from fastapi import HTTPException
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "error": "rate_limit_exceeded",
                            "message": "请求过于频繁，请稍后再试",
                            "retry_after": result.retry_after,
                            "reset_at": result.reset_at,
                        },
                        headers={
                            "X-RateLimit-Remaining": str(result.remaining),
                            "X-RateLimit-Reset": str(int(result.reset_at)),
                            "Retry-After": str(int(result.retry_after or 1)),
                        },
                    )
                
                return await func(*args, **kwargs)
            
            return async_wrapper
        else:
            # 同步函数版本
            @wraps(func)
            def wrapper(*args, **kwargs):
                limiter = get_rate_limiter()
                
                # 获取标识符
                if identifier_arg and identifier_arg in kwargs:
                    identifier = kwargs[identifier_arg]
                elif args:
                    identifier = args[0]
                else:
                    identifier = "unknown"
                
                # 检查限流
                result = limiter.check(identifier, bucket_name)
                
                if not result.allowed:
                    from fastapi import HTTPException
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "error": "rate_limit_exceeded",
                            "message": "请求过于频繁，请稍后再试",
                            "retry_after": result.retry_after,
                            "reset_at": result.reset_at,
                        },
                        headers={
                            "X-RateLimit-Remaining": str(result.remaining),
                            "X-RateLimit-Reset": str(int(result.reset_at)),
                            "Retry-After": str(int(result.retry_after or 1)),
                        },
                    )
                
                return func(*args, **kwargs)
            
            return wrapper
    return decorator
