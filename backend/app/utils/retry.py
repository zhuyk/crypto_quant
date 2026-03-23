"""
重试机制工具模块
为网络请求、数据库操作等提供统一的重试逻辑
"""
import time
import random
import logging
from functools import wraps
from typing import Optional, Callable, Tuple, Type, Any
from datetime import datetime


logger = logging.getLogger(__name__)


class RetryError(Exception):
    """重试失败异常"""
    
    def __init__(self, message: str, last_exception: Optional[Exception] = None, attempts: int = 0):
        super().__init__(message)
        self.last_exception = last_exception
        self.attempts = attempts


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    logger: Optional[logging.Logger] = None,
):
    """
    重试装饰器
    
    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 延迟倍率
        max_delay: 最大延迟（秒）
        jitter: 是否添加随机抖动
        exceptions: 需要重试的异常类型
        logger: 日志记录器
    
    Example:
        @retry(max_attempts=3, delay=1.0, exceptions=(ConnectionError,))
        def fetch_data():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        msg = f"Function {func.__name__} failed after {max_attempts} attempts"
                        if logger:
                            logger.error(msg, exc_info=True)
                        raise RetryError(msg, last_exception=e, attempts=attempt)
                    
                    # 计算下次延迟时间
                    sleep_time = min(current_delay, max_delay)
                    if jitter:
                        # 添加 ±25% 的随机抖动
                        sleep_time = sleep_time * (0.75 + random.random() * 0.5)
                    
                    if logger:
                        logger.warning(
                            f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {sleep_time:.2f}s..."
                        )
                    
                    time.sleep(sleep_time)
                    current_delay *= backoff
            
            # 不应该到达这里
            raise RetryError(
                f"Function {func.__name__} failed after {max_attempts} attempts",
                last_exception=last_exception,
                attempts=max_attempts,
            )
        
        return wrapper
    return decorator


class RetryHandler:
    """重试处理器（类形式）"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        max_delay: float = 60.0,
        jitter: bool = True,
        logger: Optional[logging.Logger] = None,
    ):
        self.max_attempts = max_attempts
        self.delay = delay
        self.backoff = backoff
        self.max_delay = max_delay
        self.jitter = jitter
        self.logger = logger or logging.getLogger(__name__)
    
    def execute(
        self,
        func: Callable,
        *args,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
        **kwargs,
    ) -> Any:
        """
        执行函数并重试
        
        Args:
            func: 要执行的函数
            args: 函数参数
            exceptions: 需要重试的异常类型
            kwargs: 函数关键字参数
        
        Returns:
            函数执行结果
        """
        current_delay = self.delay
        last_exception = None
        
        for attempt in range(1, self.max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                last_exception = e
                
                if attempt == self.max_attempts:
                    msg = f"Operation failed after {self.max_attempts} attempts"
                    self.logger.error(msg, exc_info=True)
                    raise RetryError(msg, last_exception=e, attempts=attempt)
                
                sleep_time = min(current_delay, self.max_delay)
                if self.jitter:
                    sleep_time = sleep_time * (0.75 + random.random() * 0.5)
                
                self.logger.warning(
                    f"Attempt {attempt}/{self.max_attempts} failed: {e}. "
                    f"Retrying in {sleep_time:.2f}s..."
                )
                
                time.sleep(sleep_time)
                current_delay *= self.backoff
        
        raise RetryError(
            f"Operation failed after {self.max_attempts} attempts",
            last_exception=last_exception,
            attempts=self.max_attempts,
        )


class CircuitBreakerError(Exception):
    """熔断器异常"""
    pass


class CircuitBreaker:
    """
    熔断器模式实现
    
    防止系统雪崩，当错误率达到阈值时自动熔断
    """
    
    CLOSED = "closed"      # 正常状态
    OPEN = "open"          # 熔断状态
    HALF_OPEN = "half_open"  # 半开状态（尝试恢复）
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Args:
            failure_threshold: 失败阈值（达到此值后熔断）
            recovery_timeout: 恢复超时（秒）
            half_open_max_calls: 半开状态允许的最大调用次数
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self.state = self.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0
        
        self.logger = logger or logging.getLogger(__name__)
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """通过熔断器执行函数"""
        if self.state == self.OPEN:
            if self._should_attempt_reset():
                self._enter_half_open()
            else:
                raise CircuitBreakerError(
                    f"Circuit breaker is OPEN. Will retry after {self.recovery_timeout}s"
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """是否应该尝试重置"""
        if self.last_failure_time is None:
            return True
        
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout
    
    def _enter_half_open(self):
        """进入半开状态"""
        self.state = self.HALF_OPEN
        self.half_open_calls = 0
        self.logger.info("Circuit breaker entered HALF_OPEN state")
    
    def _on_success(self):
        """成功调用"""
        if self.state == self.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                self._enter_closed()
        else:
            self.failure_count = 0
    
    def _on_failure(self):
        """失败调用"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == self.HALF_OPEN:
            self._enter_open()
        elif self.failure_count >= self.failure_threshold:
            self._enter_open()
    
    def _enter_open(self):
        """进入开启（熔断）状态"""
        self.state = self.OPEN
        self.logger.warning(
            f"Circuit breaker OPENED after {self.failure_count} failures"
        )
    
    def _enter_closed(self):
        """进入关闭（正常）状态"""
        self.state = self.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.logger.info("Circuit breaker CLOSED - service recovered")
    
    @property
    def is_closed(self) -> bool:
        """是否处于正常状态"""
        return self.state == self.CLOSED
    
    @property
    def is_open(self) -> bool:
        """是否处于熔断状态"""
        return self.state == self.OPEN


# 预定义的重试处理器实例
database_retry_handler = RetryHandler(
    max_attempts=3,
    delay=0.5,
    backoff=2.0,
    logger=logging.getLogger("database"),
)

api_retry_handler = RetryHandler(
    max_attempts=5,
    delay=1.0,
    backoff=2.0,
    max_delay=30.0,
    logger=logging.getLogger("api"),
)

exchange_retry_handler = RetryHandler(
    max_attempts=5,
    delay=1.0,
    backoff=2.0,
    max_delay=60.0,
    logger=logging.getLogger("exchange"),
)
