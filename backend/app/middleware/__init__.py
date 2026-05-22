"""
API 中间件

提供:
- rate_limit_middleware: 限流
- audit_log_middleware: 审计日志
- request_tracking_middleware: 请求追踪 + 性能指标
- error_handler_middleware: 统一错误响应
"""
from __future__ import annotations

import time
import uuid
import logging
from typing import Callable, Awaitable

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse

from app.core.exceptions import CryptoQuantException, handle_exception

logger = logging.getLogger(__name__)

# 类型别名: ASGI 中间件的 call_next 签名
CallNext = Callable[[Request], Awaitable[Response]]

__all__ = [
    "rate_limit_middleware",
    "audit_log_middleware",
    "request_tracking_middleware",
    "error_handler_middleware",
]


async def rate_limit_middleware(request: Request, call_next: CallNext) -> Response:
    """
    限流中间件

    根据路径和用户身份应用不同的限流策略。
    超限返回 429 + Retry-After 头。
    """
    # 获取限流标识
    user_id: str | None = request.headers.get("X-User-ID")
    client_ip: str = request.client.host if request.client else "unknown"
    identifier: str = user_id or f"ip:{client_ip}"

    # 路径 → 桶
    path: str = request.url.path
    if "/login" in path or "/auth" in path:
        bucket = "login"
    elif "/trade" in path or "/order" in path:
        bucket = "trade"
    elif "/backtest" in path:
        bucket = "backtest"
    else:
        bucket = "api"

    from app.utils.rate_limiter import get_rate_limiter

    limiter = get_rate_limiter()
    result = limiter.check(identifier, bucket)

    # 限流响应头
    headers: dict[str, str] = {
        "X-RateLimit-Remaining": str(result.remaining),
        "X-RateLimit-Reset": str(int(result.reset_at)),
    }

    if not result.allowed:
        logger.warning(
            f"Rate limit: {identifier} on {path} (bucket={bucket}), "
            f"retry_after={result.retry_after:.1f}s"
        )
        response = JSONResponse(
            status_code=429,
            content={
                "error": True,
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": "请求过于频繁，请稍后再试",
                "retry_after": result.retry_after,
            },
            headers={**headers, "Retry-After": str(int(result.retry_after or 1))},
        )
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    response = await call_next(request)

    for key, value in headers.items():
        response.headers[key] = value

    return response


async def audit_log_middleware(request: Request, call_next: CallNext) -> Response:
    """
    审计日志中间件

    记录敏感操作（交易/策略/密钥管理）和所有 4xx/5xx 响应。
    """
    start_time: float = time.time()
    request_id: str = getattr(request.state, "request_id", str(uuid.uuid4())[:8])

    response = await call_next(request)

    duration: float = time.time() - start_time

    # 判断是否需要审计
    sensitive_keywords = ("/order", "/trade", "/strategy", "/api-key", "/withdraw")
    is_sensitive: bool = any(kw in request.url.path for kw in sensitive_keywords)

    if is_sensitive or response.status_code >= 400:
        user_id: str | None = request.headers.get("X-User-ID")
        client_ip: str = request.client.host if request.client else "unknown"

        # 映射 HTTP 方法 → 操作类型
        action_map = {"GET": "READ", "POST": "CREATE", "PUT": "UPDATE", "PATCH": "UPDATE", "DELETE": "DELETE"}
        action: str = action_map.get(request.method, request.method)

        from app.core.audit_log import get_audit_logger

        audit_logger = get_audit_logger()
        audit_logger.log(
            action=action,
            resource=request.url.path.split("/")[1] or "api",
            user_id=user_id,
            status="success" if response.status_code < 400 else "failure",
            details={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
                "ip_address": client_ip,
                "request_id": request_id,
            },
            ip_address=client_ip,
        )

    return response


async def request_tracking_middleware(request: Request, call_next: CallNext) -> Response:
    """
    请求追踪中间件

    功能:
    - 为每个请求分配唯一 ID
    - 记录响应耗时
    - 输出结构化请求日志
    """
    start_time: float = time.time()
    request_id: str = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])

    # 注入到 request.state
    request.state.request_id = request_id
    request.state.start_time = start_time

    response = await call_next(request)

    # 添加追踪头
    duration_ms: float = (time.time() - start_time) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

    # 结构化日志
    log_level = logging.WARNING if response.status_code >= 400 else logging.DEBUG
    logger.log(
        log_level,
        f"{request.method} {request.url.path} → {response.status_code} "
        f"({duration_ms:.1f}ms) [req:{request_id}]",
    )

    return response


async def error_handler_middleware(request: Request, call_next: CallNext) -> Response:
    """
    错误处理中间件（最外层）

    统一捕获所有异常，转换为标准 JSON 错误响应。
    确保:
    - CryptoQuantException → 对应 status_code + 结构化 body
    - HTTPException → 保留原始状态码
    - 未知异常 → 500 + 通用错误格式
    """
    request_id: str = getattr(request.state, "request_id", "unknown")

    try:
        return await call_next(request)

    except CryptoQuantException as e:
        log_level = logging.WARNING if e.status_code < 500 else logging.ERROR
        logger.log(log_level, f"[{e.error_code}] {request.url.path}: {e.message}")
        return JSONResponse(
            status_code=e.status_code,
            content={**e.to_dict(), "request_id": request_id},
        )

    except HTTPException as e:
        logger.warning(f"HTTP {e.status_code} {request.url.path}: {e.detail}")
        return JSONResponse(
            status_code=e.status_code,
            content={
                "error": True,
                "error_code": "HTTP_ERROR",
                "message": str(e.detail),
                "request_id": request_id,
            },
            headers=getattr(e, "headers", None),
        )

    except Exception as e:
        converted = handle_exception(e)
        logger.error(
            f"Unhandled: {type(e).__name__} on {request.url.path}: {e}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=converted.status_code,
            content={**converted.to_dict(), "request_id": request_id},
        )
