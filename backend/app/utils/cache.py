"""
Redis 缓存层
提供统一的缓存接口和装饰器
"""
import json
import hashlib
import logging
from functools import wraps
from typing import Optional, Any, Callable, Dict, List, Union
from datetime import timedelta
import redis
from app.core.config import settings


logger = logging.getLogger(__name__)


class CacheError(Exception):
    """缓存操作异常"""
    pass


class RedisCache:
    """Redis 缓存封装"""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self._client: Optional[redis.Redis] = None
        self._connected = False
        # Force connection on init
        try:
            self._client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            self._client.ping()
            self._connected = True
            logger.info(f"✅ Redis 连接成功：{self.redis_url}")
        except Exception as e:
            logger.error(f"❌ Redis 连接失败：{e}")
            self._connected = False
            raise  # Don't fallback, fail fast
    
    @property
    def client(self) -> redis.Redis:
        """获取 Redis 客户端（懒加载）"""
        if self._client is None:
            try:
                self._client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
                self._client.ping()
                self._connected = True
                logger.info("✅ Redis 连接成功")
            except Exception as e:
                logger.warning(f"⚠️  Redis 连接失败：{e}，缓存功能将不可用")
                self._connected = False
                # 返回一个 mock 客户端
                self._client = redis.Redis.from_url(
                    "redis://localhost:6379",
                    decode_responses=True,
                    socket_connect_timeout=1,
                    socket_timeout=1,
                )
        return self._client
    
    def _check_connection(self) -> bool:
        """检查连接状态"""
        if not self._connected:
            try:
                self.client.ping()
                self._connected = True
            except Exception:
                return False
        return self._connected
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        # 确保连接（强制访问 client 属性以触发连接）
        try:
            client = self.client
            if not self._connected:
                # 尝试 ping 确认连接
                if not client.ping():
                    return None
        except Exception:
            return None
        
        try:
            value = client.get(key)
            if value is None:
                return None
            
            # 尝试 JSON 解码
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Cache GET error for key {key}: {e}")
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        expire: Optional[Union[int, timedelta]] = None,
    ) -> bool:
        """设置缓存"""
        # 确保连接
        try:
            client = self.client
            if not self._connected:
                if not client.ping():
                    return False
        except Exception:
            return False
        
        try:
            # 序列化值
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            # 设置过期时间
            if expire is None:
                client.set(key, value)
            elif isinstance(expire, timedelta):
                client.set(key, value, ex=int(expire.total_seconds()))
            else:
                client.set(key, value, ex=expire)
            
            return True
        except Exception as e:
            logger.error(f"Cache SET error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        if not self._check_connection():
            return False
        
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache DELETE error for key {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """批量删除匹配模式的缓存"""
        if not self._check_connection():
            return 0
        
        try:
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache DELETE_PATTERN error for pattern {pattern}: {e}")
            return 0
    
    def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        if not self._check_connection():
            return False
        
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            logger.error(f"Cache EXISTS error for key {key}: {e}")
            return False
    
    def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """自增计数"""
        if not self._check_connection():
            return None
        
        try:
            return self.client.incr(key, amount)
        except Exception as e:
            logger.error(f"Cache INCR error for key {key}: {e}")
            return None
    
    def decr(self, key: str, amount: int = 1) -> Optional[int]:
        """自减计数"""
        if not self._check_connection():
            return None
        
        try:
            return self.client.decr(key, amount)
        except Exception as e:
            logger.error(f"Cache DECR error for key {key}: {e}")
            return None
    
    def hget(self, name: str, key: str) -> Optional[Any]:
        """获取哈希字段"""
        if not self._check_connection():
            return None
        
        try:
            value = self.client.hget(name, key)
            if value is None:
                return None
            
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Cache HGET error: {e}")
            return None
    
    def hset(self, name: str, key: str, value: Any) -> bool:
        """设置哈希字段"""
        if not self._check_connection():
            return False
        
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            self.client.hset(name, key, value)
            return True
        except Exception as e:
            logger.error(f"Cache HSET error: {e}")
            return False
    
    def hgetall(self, name: str) -> Dict[str, Any]:
        """获取整个哈希"""
        if not self._check_connection():
            return {}
        
        try:
            data = self.client.hgetall(name)
            result = {}
            for k, v in data.items():
                try:
                    result[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    result[k] = v
            return result
        except Exception as e:
            logger.error(f"Cache HGETALL error: {e}")
            return {}
    
    def lpush(self, name: str, *values: Any) -> bool:
        """列表左推"""
        if not self._check_connection():
            return False
        
        try:
            serialized = [
                json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                for v in values
            ]
            self.client.lpush(name, *serialized)
            return True
        except Exception as e:
            logger.error(f"Cache LPUSH error: {e}")
            return False
    
    def rpop(self, name: str) -> Optional[Any]:
        """列表右弹"""
        if not self._check_connection():
            return None
        
        try:
            value = self.client.rpop(name)
            if value is None:
                return None
            
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Cache RPOP error: {e}")
            return None
    
    def llen(self, name: str) -> int:
        """获取列表长度"""
        if not self._check_connection():
            return 0
        
        try:
            return self.client.llen(name)
        except Exception as e:
            logger.error(f"Cache LLEN error: {e}")
            return 0


def cache(
    key_prefix: str = "",
    expire: int = 300,
    key_builder: Optional[Callable[..., str]] = None,
):
    """
    缓存装饰器
    
    Args:
        key_prefix: 缓存键前缀
        expire: 过期时间（秒）
        key_builder: 自定义键构建函数
    
    Example:
        @cache(key_prefix="user", expire=600)
        def get_user(user_id: int):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            cache_client = RedisCache()
            
            # 构建缓存键
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # 默认：使用函数名 + 参数哈希
                func_name = func.__name__
                param_str = f"{args}:{sorted(kwargs.items())}"
                param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
                cache_key = f"{key_prefix}:{func_name}:{param_hash}"
            
            # 尝试从缓存获取
            cached_value = cache_client.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return cached_value
            
            # 执行函数
            logger.debug(f"Cache MISS: {cache_key}, executing function...")
            result = func(*args, **kwargs)
            
            # 写入缓存
            if result is not None:
                cache_client.set(cache_key, result, expire=expire)
            
            return result
        
        return wrapper
    return decorator


def invalidate_cache(pattern: str):
    """
    缓存失效装饰器（用于更新/删除操作）
    
    Example:
        @invalidate_cache("user:*")
        def update_user(user_id: int, data: dict):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            result = func(*args, **kwargs)
            
            # 执行后使缓存失效
            cache_client = RedisCache()
            cache_client.delete_pattern(pattern)
            logger.info(f"Invalidated cache pattern: {pattern}")
            
            return result
        
        return wrapper
    return decorator


# 全局缓存实例
cache_client = RedisCache()


def get_cache() -> RedisCache:
    """获取缓存客户端"""
    return cache_client


# 常用缓存键前缀
class CacheKeys:
    """缓存键常量"""
    # 用户相关
    USER = "user"
    USER_SESSION = "user:session"
    USER_PERMISSIONS = "user:perms"
    
    # 交易对相关
    SYMBOL = "symbol"
    SYMBOL_PRICE = "symbol:price"
    SYMBOL_KLINE = "symbol:kline"
    
    # 策略相关
    STRATEGY = "strategy"
    STRATEGY_SIGNAL = "strategy:signal"
    
    # 订单相关
    ORDER = "order"
    ORDER_STATUS = "order:status"
    
    # 账户相关
    ACCOUNT = "account"
    ACCOUNT_BALANCE = "account:balance"
    ACCOUNT_POSITION = "account:position"
    
    # 系统相关
    SYSTEM_CONFIG = "system:config"
    SYSTEM_STATUS = "system:status"
    
    # 限流相关
    RATE_LIMIT = "ratelimit"
    
    @classmethod
    def make_key(cls, prefix: str, *parts: str) -> str:
        """构建缓存键"""
        return f"{prefix}:{':'.join(str(p) for p in parts)}"
