"""
API 中间件
限流、审计日志、请求追踪等
"""
import time
import uuid
import logging
from typing import Callable
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from app.utils.rate_limiter import get_rate_limiter
from app.core.audit_log import get_audit_logger
from app.core.exceptions import CryptoQuantException, handle_exception


logger = logging.getLogger(__name__)


async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
    """
    限流中间件
    
    根据路径和用户身份应用不同的限流策略
    """
    # 获取限流标识（优先使用用户 ID，其次使用 IP）
    user_id = request.headers.get("X-User-ID")
    client_ip = request.client.host if request.client else "unknown"
    identifier = user_id or f"ip:{client_ip}"
    
    # 根据路径选择限流桶
    path = request.url.path
    if "/login" in path or "/auth" in path:
        bucket = "login"
    elif "/trade" in path or "/order" in path:
        bucket = "trade"
    elif "/backtest" in path:
        bucket = "backtest"
    else:
        bucket = "api"
    
    limiter = get_rate_limiter()
    result = limiter.check(identifier, bucket)
    
    # 添加限流头
    headers = {
        "X-RateLimit-Remaining": str(result.remaining),
        "X-RateLimit-Reset": str(int(result.reset_at)),
    }
    
    if not result.allowed:
        logger.warning(
            f"Rate limit exceeded for {identifier} on {path}. "
            f"Retry after: {result.retry_after:.2f}s"
        )
        
        response = JSONResponse(
            status_code=429,
            content={
                "error": "rate_limit_exceeded",
                "message": "请求过于频繁，请稍后再试",
                "retry_after": result.retry_after,
            },
            headers={
                **headers,
                "Retry-After": str(int(result.retry_after or 1)),
            },
        )
        # 确保 CORS 头存在
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response
    
    # 执行请求
    response = await call_next(request)
    
    # 添加限流头到响应
    for key, value in headers.items():
        response.headers[key] = value
    
    return response


async def audit_log_middleware(request: Request, call_next: Callable) -> Response:
    """
    审计日志中间件
    
    记录所有敏感操作
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]
    
    # 添加请求 ID 到上下文
    request.state.request_id = request_id
    
    # 获取用户信息
    user_id = request.headers.get("X-User-ID")
    client_ip = request.client.host if request.client else "unknown"
    
    # 执行请求
    response = await call_next(request)
    
    # 计算耗时
    duration = time.time() - start_time
    
    # 只记录敏感操作
    sensitive_paths = ["/order", "/trade", "/strategy", "/withdraw", "/api_key"]
    is_sensitive = any(path in request.url.path for path in sensitive_paths)
    
    if is_sensitive or response.status_code >= 400:
        audit_logger = get_audit_logger()
        
        # 确定操作类型
        method = request.method
        if method == "GET":
            action = "READ"
        elif method == "POST":
            action = "CREATE"
        elif method == "PUT" or method == "PATCH":
            action = "UPDATE"
        elif method == "DELETE":
            action = "DELETE"
        else:
            action = method
        
        # 记录审计日志
        audit_logger.log(
            action=action,
            resource=request.url.path.split("/")[1] or "api",
            user_id=user_id,
            status="success" if response.status_code < 400 else "failure",
            details={
                "method": method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
                "ip_address": client_ip,
                "request_id": request_id,
            },
            ip_address=client_ip,
        )
    
    return response


async def request_tracking_middleware(request: Request, call_next: Callable) -> Response:
    """
    请求追踪中间件
    
    添加请求 ID、记录性能指标
    """
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    
    # 添加请求 ID 到上下文
    request.state.request_id = request_id
    request.state.start_time = start_time
    
    # 执行请求
    response = await call_next(request)
    
    # 添加追踪头
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = str(round((time.time() - start_time) * 1000, 2)) + "ms"
    
    # 记录请求日志
    duration = time.time() - start_time
    log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
    
    logger.log(
        log_level,
        f"{request.method} {request.url.path} - {response.status_code} - "
        f"{duration*1000:.2f}ms - req:{request_id}"
    )
    
    return response


async def error_handler_middleware(request: Request, call_next: Callable) -> Response:
    """
    错误处理中间件
    
    统一错误响应格式
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        return await call_next(request)
    except CryptoQuantException as e:
        # 自定义业务异常
        log_level = logging.WARNING if e.status_code < 500 else logging.ERROR
        logger.log(
            log_level,
            f"{e.error_code} on {request.url.path}: {e.message}"
        )
        return JSONResponse(
            status_code=e.status_code,
            content={
                **e.to_dict(),
                "request_id": request_id,
            },
        )
    except HTTPException as e:
        # FastAPI 标准 HTTP 异常
        logger.warning(
            f"HTTP {e.status_code} on {request.url.path}: {e.detail}"
        )
        return JSONResponse(
            status_code=e.status_code,
            content={
                "error": True,
                "error_code": "HTTP_ERROR",
                "status_code": e.status_code,
                "message": str(e.detail),
                "request_id": request_id,
            },
            headers=getattr(e, "headers", None),
        )
    except Exception as e:
        # 未处理的异常 - 转换为标准格式
        converted = handle_exception(e)
        logger.error(
            f"Unhandled exception on {request.url.path}: {e}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=converted.status_code,
            content={
                **converted.to_dict(),
                "request_id": request_id,
            },
        )


# 中间件注册顺序（从外到内）
MIDDLEWARE_ORDER = [
    "error_handler",      # 最外层：捕获所有错误
    "request_tracking",   # 追踪所有请求
    "rate_limit",         # 限流
    "audit_log",          # 审计日志（最内层）
]


def get_middleware(name: str):
    """获取中间件函数"""
    middlewares = {
        "error_handler": error_handler_middleware,
        "request_tracking": request_tracking_middleware,
        "rate_limit": rate_limit_middleware,
        "audit_log": audit_log_middleware,
    }
    return middlewares.get(name)
