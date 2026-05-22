"""
CryptoQuant Backend - FastAPI 应用入口
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import time
import logging

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.api.backtest import router as backtest_router
from app.api.strategy import router as strategy_router
from app.api.data import router as data_router
from app.api.trade import router as trade_router
from app.api.auth.auth import router as auth_router
from app.api.exchanges import router as exchanges_router
from app.api.marketplace import router as marketplace_router
from app.api.account import router as account_router
from app.api.example import router as example_router
from app.api.services import router as services_router
from app.api.tasks import router as tasks_router
from app.api.social import router as social_router
from app.api.health import router as health_router
from app.api.exchange_keys import router as exchange_keys_router
from app.api.arbitrage import router as arbitrage_router
from app.websocket import router as websocket_router
from app.core.database import init_db
from app.monitoring import get_metrics
from app.middleware import (
    rate_limit_middleware,
    audit_log_middleware,
    request_tracking_middleware,
    error_handler_middleware,
)

# 配置日志
setup_logging(
    log_level=settings.LOG_LEVEL,
    log_file=settings.LOG_FILE,
    log_format="text" if settings.DEBUG else "json",
)

logger = logging.getLogger(__name__)
metrics = get_metrics()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("🚀 CryptoQuant Backend 启动中...")
    
    # 启动 Prometheus 指标服务器
    metrics.start_server()
    
    # 初始化数据库（带重试）
    try:
        init_db()
        logger.info("✅ 数据库连接成功")
        metrics.set_system_status("database", True)
    except Exception as e:
        logger.error(f"❌ 数据库初始化失败：{e}")
        metrics.set_system_status("database", False)
    
    # 启动任务调度器
    try:
        from app.tasks import get_scheduler
        scheduler = get_scheduler()
        scheduler.start()
        logger.info("🕐 任务调度器已启动")
    except Exception as e:
        logger.error(f"❌ 任务调度器启动失败：{e}")
    
    # 设置系统状态
    metrics.set_system_status("api", True)
    metrics.set_system_status("cache", True)
    logger.info("✅ CryptoQuant Backend 启动完成")
    
    yield
    
    # 关闭时清理
    logger.info("👋 CryptoQuant Backend 关闭中...")
    metrics.set_system_status("api", False)
    
    # 关闭 WebSocket 连接
    try:
        from app.services.binance_websocket import get_binance_ws
        ws = get_binance_ws()
        if ws:
            await ws.stop_async()
            logger.info("📡 Binance WebSocket 已优雅关闭")
    except Exception as e:
        logger.error(f"❌ WebSocket 关闭失败：{e}")
    
    # 关闭任务调度器
    try:
        from app.tasks import get_scheduler
        scheduler = get_scheduler()
        scheduler.shutdown(wait=False)
        logger.info("🕐 任务调度器已关闭")
    except Exception as e:
        logger.error(f"❌ 任务调度器关闭失败：{e}")


# 创建 FastAPI 应用
app = FastAPI(
    title="CryptoQuant API",
    description="数字货币量化交易系统 API",
    version="0.1.0",
    lifespan=lifespan,
)

# 注册中间件（按顺序）- CORS 必须在最前面
app.middleware("http")(error_handler_middleware)
app.middleware("http")(request_tracking_middleware)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(audit_log_middleware)

# 配置 CORS（测试阶段完全开放）- 必须在所有 http 中间件之后添加
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由 (统一添加 /api/v1 前缀)
app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(account_router, prefix="/api/v1/account")
app.include_router(backtest_router, prefix="/api/v1/backtest")
app.include_router(strategy_router, prefix="/api/v1/strategy")
app.include_router(data_router, prefix="/api/v1/data")
app.include_router(trade_router, prefix="/api/v1/trade")
app.include_router(example_router, prefix="/api/v1/example")
app.include_router(services_router, prefix="/api/v1/services")
app.include_router(tasks_router, prefix="/api/v1/tasks")
app.include_router(exchanges_router, prefix="/api/v1/exchanges")
app.include_router(marketplace_router, prefix="/api/v1/marketplace")
app.include_router(exchange_keys_router)  # router 已包含 /api/v1/exchange-keys 前缀
app.include_router(arbitrage_router)  # router 已包含 /api/v1/arbitrage 前缀
app.include_router(websocket_router, prefix="/api/v1/ws")
app.include_router(social_router, prefix="/api/v1")


# 中间件 - 记录请求指标（Prometheus）
@app.middleware("http")
async def track_metrics(request: Request, call_next):
    """跟踪请求指标（Prometheus）"""
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    
    # 记录 Prometheus 指标
    metrics.record_api_request(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
        duration=duration,
    )
    
    return response


@app.get("/health")
async def health_check():
    """健康检查 - 简单快速探测"""
    return {"status": "healthy", "version": "0.1.0"}


# 注册详细健康检查路由 (/health/detailed, /health/ready, /health/live)
app.include_router(health_router, prefix="/health")


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "CryptoQuant API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "websocket": "/ws",
        "websocket_stats": "/stats",
    }


@app.get("/ws/help")
async def websocket_help():
    """WebSocket 使用帮助"""
    return {
        "description": "WebSocket 实时推送服务",
        "endpoint": "ws://localhost:8000/ws",
        "parameters": {
            "user_id": "用户 ID (可选)",
            "room": "房间名 (可选)",
            "token": "认证令牌 (可选)",
        },
        "message_types": {
            "subscribe": "订阅主题",
            "unsubscribe": "取消订阅",
            "ping": "心跳",
            "trade": "交易指令",
        },
        "push_types": {
            "welcome": "欢迎消息",
            "price_update": "价格更新",
            "trade_update": "交易更新",
            "strategy_signal": "策略信号",
            "pong": "心跳响应",
        },
        "example": "ws://localhost:8000/ws?user_id=user123&room=btc_traders",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
