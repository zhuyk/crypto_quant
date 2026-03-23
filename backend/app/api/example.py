"""
示例 API 端点
演示重试、缓存、限流等功能的最佳实践
"""
import time
import random
import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from app.utils import (
    retry,
    exchange_retry_handler,
    get_cache,
    CacheKeys,
    rate_limit,
    get_rate_limiter,
)
from app.core.exceptions import (
    ExternalAPIError,
    NotFoundError,
    ValidationError,
    success_response,
)
from app.monitoring import get_metrics


logger = logging.getLogger(__name__)
router = APIRouter()
metrics = get_metrics()


# ============================================
# 示例：带重试的 API 调用
# ============================================

@router.get("/example/slow-api")
@rate_limit(bucket_name="api", identifier_arg="symbol")
async def example_slow_api(
    symbol: str = Query(..., description="交易对，如 BTCUSDT"),
    fail_rate: float = Query(0.3, description="模拟失败率 0-1"),
):
    """
    示例：带重试的外部 API 调用
    
    模拟调用 Binance API，可能失败，自动重试
    """
    cache = get_cache()
    cache_key = CacheKeys.make_key(CacheKeys.SYMBOL_PRICE, symbol)
    
    # 1. 先尝试从缓存获取
    cached_data = cache.get(cache_key)
    if cached_data:
        logger.info(f"Cache HIT for {symbol}")
        return success_response(
            data=cached_data,
            message="从缓存获取",
        )
    
    # 2. 缓存未命中，调用外部 API（带重试）
    def fetch_price():
        """模拟外部 API 调用"""
        if random.random() < fail_rate:
            raise ConnectionError(f"Simulated network error for {symbol}")
        
        # 模拟延迟
        time.sleep(0.1)
        
        return {
            "symbol": symbol,
            "price": round(random.uniform(20000, 70000), 2),
            "timestamp": int(time.time() * 1000),
        }
    
    try:
        # 使用重试处理器执行
        data = exchange_retry_handler.execute(
            fetch_price,
            exceptions=(ConnectionError,),
        )
        
        # 3. 写入缓存（5 分钟过期）
        cache.set(cache_key, data, expire=300)
        
        return success_response(
            data=data,
            message="从外部 API 获取",
        )
    
    except Exception as e:
        logger.error(f"Failed to fetch price for {symbol}: {e}")
        raise ExternalAPIError(
            message=f"获取 {symbol} 价格失败",
            service="binance",
            details={"symbol": symbol, "error": str(e)},
        )


# ============================================
# 示例：带熔断器的 API
# ============================================

from app.utils.retry import CircuitBreaker, CircuitBreakerError

# 全局熔断器实例
external_api_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30.0,
    logger=logger,
)


@router.get("/example/circuit-breaker")
async def example_circuit_breaker(
    fail: bool = Query(False, description="是否模拟失败"),
):
    """
    示例：熔断器模式
    
    当失败次数达到阈值时自动熔断，防止雪崩
    """
    def call_external_service():
        if fail:
            raise ConnectionError("Service unavailable")
        return {"status": "healthy", "data": "test"}
    
    try:
        result = external_api_breaker.call(call_external_service)
        
        return success_response(
            data=result,
            message="服务正常",
        )
    
    except CircuitBreakerError as e:
        # 熔断状态
        return success_response(
            data={
                "status": "circuit_open",
                "message": "服务已熔断，请稍后重试",
            },
            message="熔断器保护触发",
        )
    
    except Exception as e:
        raise ExternalAPIError(
            message="外部服务调用失败",
            service="example",
            details={"error": str(e)},
        )


# ============================================
# 示例：批量操作（带限流）
# ============================================

@router.get("/example/batch")
@rate_limit(bucket_name="backtest", identifier_arg="user_id")
async def example_batch_operation(
    symbols: List[str] = Query(..., description="交易对列表"),
    user_id: Optional[str] = Query(None, description="用户 ID"),
):
    """
    示例：批量操作
    
    对多个交易对进行操作，使用更严格的限流
    """
    if len(symbols) > 10:
        raise ValidationError(
            message="最多同时查询 10 个交易对",
            details={"max_allowed": 10, "requested": len(symbols)},
        )
    
    cache = get_cache()
    results = []
    
    for symbol in symbols:
        # 模拟处理
        price_data = {
            "symbol": symbol,
            "price": round(random.uniform(20000, 70000), 2),
        }
        results.append(price_data)
        
        # 记录指标
        metrics.record_strategy_signal(
            strategy="example",
            symbol=symbol,
            signal_type="query",
        )
    
    return success_response(
        data={
            "count": len(results),
            "results": results,
        },
        message=f"成功查询 {len(results)} 个交易对",
    )


# ============================================
# 示例：异步任务（带状态跟踪）
# ============================================

@router.post("/example/async-task")
@rate_limit(bucket_name="backtest", identifier_arg="task_name")
async def example_async_task(
    task_name: str = Query(..., description="任务名称"),
    duration: int = Query(5, description="模拟耗时（秒）"),
):
    """
    示例：异步任务
    
    模拟耗时操作，返回任务 ID 供后续查询
    """
    cache = get_cache()
    task_id = f"task_{int(time.time() * 1000)}"
    task_key = CacheKeys.make_key("task", task_id)
    
    # 创建任务状态
    task_status = {
        "task_id": task_id,
        "task_name": task_name,
        "status": "running",
        "progress": 0,
        "created_at": time.time(),
    }
    
    # 保存任务状态（10 分钟过期）
    cache.set(task_key, task_status, expire=600)
    
    # 模拟异步处理（实际应该用 Celery）
    # 这里为了演示直接同步执行
    time.sleep(min(duration, 3))  # 最多等待 3 秒
    
    # 更新状态
    task_status["status"] = "completed"
    task_status["progress"] = 100
    task_status["completed_at"] = time.time()
    cache.set(task_key, task_status, expire=600)
    
    return success_response(
        data={
            "task_id": task_id,
            "status": "completed",
            "result": f"Task {task_name} completed",
        },
        message="任务执行完成",
    )


@router.get("/example/task-status/{task_id}")
async def example_task_status(task_id: str):
    """
    查询异步任务状态
    """
    cache = get_cache()
    task_key = CacheKeys.make_key("task", task_id)
    
    task_status = cache.get(task_key)
    
    if not task_status:
        raise NotFoundError("task", task_id)
    
    return success_response(
        data=task_status,
        message="任务状态查询成功",
    )


# ============================================
# 示例：限流测试端点
# ============================================

@router.get("/example/rate-limit-test")
async def example_rate_limit_test():
    """
    示例：限流测试
    
    快速调用此端点可以触发限流
    """
    limiter = get_rate_limiter()
    
    # 获取限流状态
    status = limiter._buckets["default"].get_status("test_user")
    
    return success_response(
        data={
            "message": "请求成功",
            "rate_limit_status": status,
            "tip": "快速刷新此端点可以触发限流",
        },
        message="限流测试端点",
    )
