"""
健康检查端点
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    """健康状态"""
    status: str
    timestamp: str
    version: str
    environment: str


class ComponentHealth(BaseModel):
    """组件健康状态"""
    name: str
    status: str
    latency_ms: Optional[float] = None
    message: Optional[str] = None


class DetailedHealth(BaseModel):
    """详细健康检查"""
    overall_status: str
    timestamp: str
    version: str
    environment: str
    components: List[ComponentHealth]
    metrics: Optional[Dict] = None


@router.get("", response_model=HealthStatus)
async def health_check():
    """
    基础健康检查
    
    用于负载均衡器的健康探测
    """
    from app.core.config import settings
    
    return HealthStatus(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version=getattr(settings, 'VERSION', '1.0.0'),
        environment=settings.ENVIRONMENT,
    )


@router.get("/detailed", response_model=DetailedHealth)
async def detailed_health_check():
    """
    详细健康检查
    
    检查所有依赖组件的状态
    """
    from app.core.config import settings
    from app.core.database import get_db_connection_status
    from engine.risk.risk_manager import RiskManager
    
    components = []
    overall_status = "healthy"
    
    # 检查数据库
    try:
        db_status = await get_db_connection_status()
        components.append(ComponentHealth(
            name="database",
            status="healthy" if db_status else "unhealthy",
            message="Database connection OK" if db_status else "Database connection failed"
        ))
        if not db_status:
            overall_status = "unhealthy"
    except Exception as e:
        components.append(ComponentHealth(
            name="database",
            status="unhealthy",
            message=str(e)
        ))
        overall_status = "unhealthy"
    
    # 检查 Redis
    try:
        from app.core.redis_client import get_redis_client
        redis_client = get_redis_client()
        start = datetime.now()
        await redis_client.ping()
        latency = (datetime.now() - start).total_seconds() * 1000
        
        components.append(ComponentHealth(
            name="redis",
            status="healthy",
            latency_ms=latency,
            message=f"Redis ping OK ({latency:.2f}ms)"
        ))
    except Exception as e:
        components.append(ComponentHealth(
            name="redis",
            status="unhealthy",
            message=str(e)
        ))
        overall_status = "unhealthy"
    
    # 检查 Binance API
    try:
        from data.collector.binance_collector import BinanceCollector
        collector = BinanceCollector()
        start = datetime.now()
        await collector.get_server_time()
        latency = (datetime.now() - start).total_seconds() * 1000
        
        components.append(ComponentHealth(
            name="binance_api",
            status="healthy",
            latency_ms=latency,
            message=f"Binance API OK ({latency:.2f}ms)"
        ))
    except Exception as e:
        components.append(ComponentHealth(
            name="binance_api",
            status="degraded",
            message=f"Binance API error: {str(e)}"
        ))
        if overall_status == "healthy":
            overall_status = "degraded"
    
    # 检查风控系统
    try:
        risk_manager = RiskManager()
        risk_status = risk_manager.get_full_status()
        
        components.append(ComponentHealth(
            name="risk_management",
            status="healthy",
            message=f"Risk level: {risk_status['risk_level']}"
        ))
    except Exception as e:
        components.append(ComponentHealth(
            name="risk_management",
            status="unhealthy",
            message=str(e)
        ))
        overall_status = "unhealthy"
    
    return DetailedHealth(
        overall_status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        version=getattr(settings, 'VERSION', '1.0.0'),
        environment=settings.ENVIRONMENT,
        components=components,
    )


@router.get("/ready")
async def readiness_check():
    """
    就绪检查
    
    用于 Kubernetes 就绪探针
    """
    from app.core.config import settings
    
    # 检查关键依赖
    try:
        from app.core.database import get_db_connection_status
        db_ok = await get_db_connection_status()
        
        if not db_ok:
            raise HTTPException(status_code=503, detail="Database not ready")
        
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat(),
            "environment": settings.ENVIRONMENT,
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/live")
async def liveness_check():
    """
    存活检查
    
    用于 Kubernetes 存活探针
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
    }
