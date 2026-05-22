"""
健康检查端点
支持基础探测、详细依赖检查和 Kubernetes 探针
"""

import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class ComponentHealth(BaseModel):
    """组件健康状态"""
    name: str
    status: str  # healthy / degraded / unhealthy
    latency_ms: Optional[float] = None
    message: Optional[str] = None


class DetailedHealth(BaseModel):
    """详细健康检查"""
    overall_status: str
    timestamp: str
    version: str
    environment: str
    uptime_seconds: float
    components: List[ComponentHealth]


# 记录启动时间
_start_time = time.time()


async def _check_database() -> ComponentHealth:
    """检查数据库连接"""
    try:
        from app.core.database import engine
        from sqlalchemy import text

        start = time.time()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency = (time.time() - start) * 1000

        return ComponentHealth(
            name="database",
            status="healthy",
            latency_ms=round(latency, 2),
            message=f"OK ({latency:.1f}ms)",
        )
    except Exception as e:
        logger.warning(f"数据库健康检查失败: {e}")
        return ComponentHealth(
            name="database",
            status="unhealthy",
            message=str(e)[:200],
        )


async def _check_redis() -> ComponentHealth:
    """检查 Redis 连接"""
    try:
        from app.utils.cache import get_cache

        cache = get_cache()
        start = time.time()
        # 简单的 set/get 测试
        cache.set("__health_check__", "ok", expire=10)
        result = cache.get("__health_check__")
        latency = (time.time() - start) * 1000

        if result == "ok":
            return ComponentHealth(
                name="redis",
                status="healthy",
                latency_ms=round(latency, 2),
                message=f"OK ({latency:.1f}ms)",
            )
        else:
            return ComponentHealth(
                name="redis",
                status="degraded",
                latency_ms=round(latency, 2),
                message="Set/Get 验证失败",
            )
    except Exception as e:
        logger.warning(f"Redis 健康检查失败: {e}")
        return ComponentHealth(
            name="redis",
            status="unhealthy",
            message=str(e)[:200],
        )


async def _check_binance_api() -> ComponentHealth:
    """检查 Binance API 可达性"""
    try:
        import httpx

        start = time.time()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://api.binance.com/api/v3/ping")
        latency = (time.time() - start) * 1000

        if resp.status_code == 200:
            return ComponentHealth(
                name="binance_api",
                status="healthy",
                latency_ms=round(latency, 2),
                message=f"Ping OK ({latency:.1f}ms)",
            )
        else:
            return ComponentHealth(
                name="binance_api",
                status="degraded",
                message=f"HTTP {resp.status_code}",
            )
    except Exception as e:
        logger.warning(f"Binance API 健康检查失败: {e}")
        return ComponentHealth(
            name="binance_api",
            status="degraded",
            message=str(e)[:200],
        )


@router.get("")
async def health_check():
    """
    基础健康检查 (快速)

    用于负载均衡器的健康探测，不检查外部依赖。
    """
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/detailed", response_model=DetailedHealth)
async def detailed_health_check():
    """
    详细健康检查

    逐一检查所有依赖组件（数据库、Redis、外部 API）。
    适用于运维监控面板。
    """
    components: List[ComponentHealth] = []

    # 并行检查各组件
    db_health = await _check_database()
    redis_health = await _check_redis()
    binance_health = await _check_binance_api()

    components.extend([db_health, redis_health, binance_health])

    # 计算总体状态
    statuses = [c.status for c in components]
    if "unhealthy" in statuses:
        overall = "unhealthy"
    elif "degraded" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    return DetailedHealth(
        overall_status=overall,
        timestamp=datetime.utcnow().isoformat() + "Z",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        uptime_seconds=round(time.time() - _start_time, 1),
        components=components,
    )


@router.get("/ready")
async def readiness_check():
    """
    就绪检查 (Kubernetes readiness probe)

    只有数据库可用时才返回 200。
    """
    db_health = await _check_database()

    if db_health.status == "unhealthy":
        raise HTTPException(
            status_code=503,
            detail=f"Not ready: database - {db_health.message}",
        )

    return {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/live")
async def liveness_check():
    """
    存活检查 (Kubernetes liveness probe)

    只要进程活着就返回 200。
    """
    return {
        "status": "alive",
        "uptime_seconds": round(time.time() - _start_time, 1),
    }
