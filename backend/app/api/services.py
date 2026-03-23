"""
服务 API 路由
WebSocket、告警等服务管理
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import asyncio
import threading

from app.core.exceptions import success_response, NotFoundError
from app.services import (
    create_binance_ws,
    get_binance_ws,
    create_alert_service,
    get_alert_service,
    AlertLevel,
    AlertType,
)

router = APIRouter(tags=["服务管理"])

# 全局状态
_binance_ws_thread: Optional[threading.Thread] = None
_alert_service_initialized = False


# ==================== Binance WebSocket ====================

class StartBinanceWSRequest(BaseModel):
    """启动 Binance WebSocket 请求"""
    symbols: List[str] = Field(
        default=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
        description="交易对列表",
    )
    intervals: List[str] = Field(
        default=["1m", "5m", "1h"],
        description="K 线时间间隔",
    )


@router.post("/binance-ws/start")
async def start_binance_websocket(request: StartBinanceWSRequest):
    """启动 Binance WebSocket 数据采集"""
    global _binance_ws_thread
    
    ws = get_binance_ws()
    if ws and ws._running:
        return success_response(
            data={"status": "already_running"},
            message="Binance WebSocket 已在运行中"
        )
    
    # 创建实例
    ws = create_binance_ws(
        symbols=request.symbols,
        intervals=request.intervals,
    )
    
    # 在后台线程启动
    def run_ws():
        ws.start()
    
    _binance_ws_thread = threading.Thread(target=run_ws, daemon=True)
    _binance_ws_thread.start()
    
    # 等待启动
    await asyncio.sleep(1)
    
    return success_response(
        data={
            "status": "started",
            "symbols": request.symbols,
            "intervals": request.intervals,
        },
        message="Binance WebSocket 已启动"
    )


@router.post("/binance-ws/stop")
async def stop_binance_websocket():
    """停止 Binance WebSocket"""
    ws = get_binance_ws()
    if not ws:
        raise NotFoundError("Binance WebSocket", "未初始化")
    
    ws.stop()
    
    return success_response(message="Binance WebSocket 已停止")


@router.get("/binance-ws/stats")
async def get_binance_websocket_stats():
    """获取 Binance WebSocket 统计"""
    ws = get_binance_ws()
    if not ws:
        return {"status": "not_initialized"}
    
    return {
        "status": "running" if ws._running else "stopped",
        "stats": ws.get_stats(),
    }


@router.get("/binance-ws/price/{symbol}")
async def get_symbol_price(symbol: str):
    """获取实时价格 (从缓存)"""
    from app.utils.cache import get_cache, CacheKeys
    
    cache = get_cache()
    cache_key = CacheKeys.make_key(CacheKeys.SYMBOL_PRICE, symbol)
    
    price_data = cache.get(cache_key)
    if not price_data:
        raise NotFoundError("价格数据", symbol)
    
    return success_response(data=price_data)


# ==================== 告警服务 ====================

class SetupDingTalkRequest(BaseModel):
    """配置钉钉通知"""
    webhook_url: str = Field(..., description="钉钉机器人 Webhook URL")
    secret: Optional[str] = Field(None, description="加签密钥")


class SetupEmailRequest(BaseModel):
    """配置邮件通知"""
    smtp_server: str = Field(..., description="SMTP 服务器")
    smtp_port: int = Field(587, description="SMTP 端口")
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    from_addr: str = Field(..., description="发件人")
    to_addrs: List[str] = Field(..., description="收件人列表")


class SendTestAlertRequest(BaseModel):
    """发送测试告警"""
    title: str = Field(default="测试告警", description="告警标题")
    content: str = Field(default="这是一条测试告警消息", description="告警内容")
    level: str = Field(default="info", description="告警级别")


@router.post("/alert/setup/dingtalk")
async def setup_dingtalk(request: SetupDingTalkRequest):
    """配置钉钉通知"""
    global _alert_service_initialized
    
    alert_svc = get_alert_service()
    if not alert_svc:
        alert_svc = create_alert_service()
        _alert_service_initialized = True
    
    alert_svc.add_dingtalk(
        name="main",
        webhook_url=request.webhook_url,
        secret=request.secret,
    )
    
    return success_response(message="钉钉通知配置成功")


@router.post("/alert/setup/email")
async def setup_email(request: SetupEmailRequest):
    """配置邮件通知"""
    global _alert_service_initialized
    
    alert_svc = get_alert_service()
    if not alert_svc:
        alert_svc = create_alert_service()
        _alert_service_initialized = True
    
    alert_svc.add_email(
        name="main",
        smtp_server=request.smtp_server,
        smtp_port=request.smtp_port,
        username=request.username,
        password=request.password,
        from_addr=request.from_addr,
        to_addrs=request.to_addrs,
    )
    
    return success_response(message="邮件通知配置成功")


@router.post("/alert/send")
async def send_alert(request: SendTestAlertRequest):
    """发送测试告警"""
    alert_svc = get_alert_service()
    if not alert_svc:
        raise NotFoundError("告警服务", "未初始化")
    
    level_map = {
        "info": AlertLevel.INFO,
        "warning": AlertLevel.WARNING,
        "error": AlertLevel.ERROR,
        "critical": AlertLevel.CRITICAL,
    }
    
    from app.services.alert_service import AlertMessage
    
    alert = AlertMessage(
        title=request.title,
        content=request.content,
        level=level_map.get(request.level.lower(), AlertLevel.INFO),
    )
    
    results = await alert_svc.send_alert(alert)
    
    return success_response(
        data={
            "results": results,
            "success_count": sum(results.values()),
            "total": len(results),
        },
        message=f"告警已发送 - 成功 {sum(results.values())}/{len(results)}"
    )


@router.get("/alert/history")
async def get_alert_history(
    limit: int = 50,
    alert_type: Optional[str] = None,
):
    """获取告警历史"""
    alert_svc = get_alert_service()
    if not alert_svc:
        return {"history": [], "total": 0}
    
    atype = AlertType(alert_type) if alert_type else None
    history = alert_svc.get_alert_history(limit=limit, alert_type=atype)
    
    return {
        "history": history,
        "total": len(history),
    }


@router.get("/alert/stats")
async def get_alert_stats():
    """获取告警服务统计"""
    alert_svc = get_alert_service()
    if not alert_svc:
        return {"status": "not_initialized"}
    
    return {
        "status": "initialized",
        "stats": alert_svc.get_stats(),
    }


# ==================== 系统服务 ====================

@router.get("/status")
async def get_services_status():
    """获取所有服务状态"""
    ws = get_binance_ws()
    alert_svc = get_alert_service()
    
    return {
        "binance_websocket": {
            "status": "running" if ws and ws._running else "stopped",
            "stats": ws.get_stats() if ws else None,
        },
        "alert_service": {
            "status": "initialized" if alert_svc else "not_initialized",
            "stats": alert_svc.get_stats() if alert_svc else None,
        },
    }
