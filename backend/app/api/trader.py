"""
交易 API 路由 (已弃用 - 已整合到 trade.py)

本模块的所有功能已合入 app.api.trade：
- 策略信号执行 → POST /api/v1/trade/signal/execute
- 交易员状态 → GET /api/v1/trade/service/status
- 启动服务 → POST /api/v1/trade/service/start
- 停止服务 → POST /api/v1/trade/service/stop
- 交易统计 → GET /api/v1/trade/service/statistics

保留此文件仅为向后兼容。新代码请使用 trade.py 中的统一接口。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
import logging
import warnings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["trader (deprecated)"])

# 弃用警告
_DEPRECATION_NOTE = (
    "此接口已弃用，请使用 /api/v1/trade/signal/execute 和 /api/v1/trade/service/* 替代"
)


class ExecuteSignalRequest(BaseModel):
    """执行交易信号请求"""
    strategy_id: str
    symbol: str
    side: str = Field(..., description="买卖方向 (buy/sell)")
    quantity: Optional[str] = None
    signal_strength: float = Field(default=1.0, ge=0, le=1)
    price: Optional[str] = None
    order_type: str = Field(default="market", description="订单类型 (market/limit)")
    stop_loss: Optional[str] = None
    take_profit: Optional[str] = None
    priority: bool = Field(default=False, description="是否优先执行")


class OrderResponse(BaseModel):
    """订单响应"""
    success: bool
    order_id: Optional[str] = None
    client_order_id: str
    message: str
    state: str
    filled_quantity: str
    avg_fill_price: str


class PositionInfo(BaseModel):
    """持仓信息"""
    symbol: str
    quantity: str
    value: str
    unrealized_pnl: Optional[str] = None


class TraderStatusResponse(BaseModel):
    """交易员状态响应"""
    is_running: bool
    current_equity: str
    initial_capital: str
    total_pnl: str
    total_pnl_ratio: str
    positions: List[PositionInfo]
    active_orders: int
    risk_level: str


@router.post("/execute", response_model=OrderResponse, deprecated=True)
async def execute_signal(request: ExecuteSignalRequest):
    """
    执行交易信号 [已弃用]
    
    请使用 POST /api/v1/trade/signal/execute
    """
    logger.warning(f"使用了弃用接口 /trader/execute，请迁移到 /trade/signal/execute")
    
    # 代理到新接口
    from app.api.trade import execute_strategy_signal, ExecuteSignalRequest as NewRequest
    
    new_request = NewRequest(
        strategy_id=request.strategy_id,
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
        signal_strength=request.signal_strength,
        price=request.price,
        order_type=request.order_type,
        stop_loss=request.stop_loss,
        take_profit=request.take_profit,
        priority=request.priority,
    )
    
    result = await execute_strategy_signal(new_request)
    
    return OrderResponse(
        success=result.success,
        order_id=result.order_id,
        client_order_id=result.client_order_id,
        message=result.message + f" ({_DEPRECATION_NOTE})",
        state=result.state,
        filled_quantity=result.filled_quantity,
        avg_fill_price=result.avg_fill_price,
    )


@router.get("/status", response_model=TraderStatusResponse, deprecated=True)
async def get_trader_status():
    """
    获取交易员状态 [已弃用]
    
    请使用 GET /api/v1/trade/service/status
    """
    logger.warning(f"使用了弃用接口 /trader/status，请迁移到 /trade/service/status")
    
    try:
        from engine.trader.service import get_trader_service
        service = get_trader_service()
        
        if not service:
            raise HTTPException(status_code=503, detail="交易服务未启动")
        
        status = service.get_full_status()
        initial = Decimal(status['initial_capital'])
        current = Decimal(status['current_equity'])
        total_pnl = current - initial
        total_pnl_ratio = total_pnl / initial if initial != 0 else Decimal('0')
        
        return TraderStatusResponse(
            is_running=status['is_running'],
            current_equity=status['current_equity'],
            initial_capital=status['initial_capital'],
            total_pnl=str(total_pnl),
            total_pnl_ratio=str(total_pnl_ratio),
            positions=[
                PositionInfo(
                    symbol=p['symbol'],
                    quantity=p['quantity'],
                    value=p['value'],
                )
                for p in status['positions']
            ],
            active_orders=status['order_statistics']['active_orders'],
            risk_level=status['risk_status']['risk_level'],
        )
    except ImportError:
        raise HTTPException(status_code=503, detail="交易服务模块不可用")


@router.post("/start", deprecated=True)
async def start_trader():
    """启动交易服务 [已弃用] - 请使用 POST /api/v1/trade/service/start"""
    from app.api.trade import start_trading_service
    return await start_trading_service()


@router.post("/stop", deprecated=True)
async def stop_trader():
    """停止交易服务 [已弃用] - 请使用 POST /api/v1/trade/service/stop"""
    from app.api.trade import stop_trading_service
    return await stop_trading_service()
