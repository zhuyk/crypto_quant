"""
交易 API 路由
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["trader"])


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


@router.post("/execute", response_model=OrderResponse)
async def execute_signal(request: ExecuteSignalRequest):
    """
    执行交易信号
    
    接收策略产生的交易信号，执行订单
    """
    from engine.trader.service import get_trader_service
    
    service = get_trader_service()
    if not service:
        raise HTTPException(status_code=503, detail="交易服务未启动")
    
    try:
        # 转换数量
        quantity = Decimal(request.quantity) if request.quantity else None
        price = Decimal(request.price) if request.price else None
        stop_loss = Decimal(request.stop_loss) if request.stop_loss else None
        take_profit = Decimal(request.take_profit) if request.take_profit else None
        
        # 执行信号
        success = await service.execute_signal(
            strategy_id=request.strategy_id,
            symbol=request.symbol,
            side=request.side,
            quantity=quantity or Decimal('0'),
            price=price,
            order_type=request.order_type,
            priority=request.priority,
        )
        
        if success:
            return OrderResponse(
                success=True,
                client_order_id=f"order_{request.strategy_id}_{request.symbol}",
                message="信号执行成功",
                state="submitted",
                filled_quantity="0",
                avg_fill_price="0",
            )
        else:
            return OrderResponse(
                success=False,
                client_order_id=f"order_{request.strategy_id}_{request.symbol}",
                message="信号执行失败（可能触发风控）",
                state="rejected",
                filled_quantity="0",
                avg_fill_price="0",
            )
            
    except Exception as e:
        logger.error(f"执行信号失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=TraderStatusResponse)
async def get_trader_status():
    """
    获取交易员状态
    
    返回当前交易服务状态、持仓、风险等信息
    """
    from engine.trader.service import get_trader_service
    
    service = get_trader_service()
    if not service:
        raise HTTPException(status_code=503, detail="交易服务未启动")
    
    status = service.get_full_status()
    
    # 计算总盈亏
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


@router.get("/positions", response_model=List[PositionInfo])
async def get_positions():
    """获取当前持仓"""
    from engine.trader.service import get_trader_service
    
    service = get_trader_service()
    if not service:
        raise HTTPException(status_code=503, detail="交易服务未启动")
    
    status = service.get_full_status()
    
    return [
        PositionInfo(
            symbol=p['symbol'],
            quantity=p['quantity'],
            value=p['value'],
        )
        for p in status['positions']
    ]


@router.get("/orders/active", response_model=List[dict])
async def get_active_orders(symbol: Optional[str] = None):
    """获取活跃订单"""
    from engine.trader.service import get_trader_service
    
    service = get_trader_service()
    if not service:
        raise HTTPException(status_code=503, detail="交易服务未启动")
    
    orders = service.order_manager.get_active_orders(symbol=symbol)
    return [order.to_dict() for order in orders]


@router.post("/orders/{client_order_id}/cancel")
async def cancel_order(client_order_id: str):
    """取消订单"""
    from engine.trader.service import get_trader_service
    
    service = get_trader_service()
    if not service:
        raise HTTPException(status_code=503, detail="交易服务未启动")
    
    success = await service.execution_engine.cancel_order(client_order_id)
    
    if success:
        return {"success": True, "message": "订单已取消"}
    else:
        raise HTTPException(status_code=400, detail="取消订单失败")


@router.get("/statistics")
async def get_statistics():
    """获取交易统计"""
    from engine.trader.service import get_trader_service
    
    service = get_trader_service()
    if not service:
        raise HTTPException(status_code=503, detail="交易服务未启动")
    
    status = service.get_full_status()
    
    return {
        "order_statistics": status['order_statistics'],
        "execution_statistics": status['execution_statistics'],
        "reconciliation_statistics": status['reconciliation_statistics'],
        "slippage_statistics": status['slippage_statistics'],
        "risk_status": status['risk_status'],
        "strategy_statistics": service.strategy_runner.get_strategy_statistics(),
    }


@router.post("/start")
async def start_trader():
    """启动交易服务"""
    from engine.trader.service import get_trader_service, init_trader_service
    from engine.risk.risk_manager import RiskManager
    
    service = get_trader_service()
    if service and service._is_running:
        return {"success": True, "message": "交易服务已在运行"}
    
    # 初始化交易服务
    risk_manager = RiskManager(
        initial_capital=100000,
        max_drawdown=0.08,
        max_daily_loss=0.02,
    )
    
    service = init_trader_service(risk_manager=risk_manager)
    await service.start()
    
    return {"success": True, "message": "交易服务已启动"}


@router.post("/stop")
async def stop_trader():
    """停止交易服务"""
    from engine.trader.service import get_trader_service
    
    service = get_trader_service()
    if not service:
        raise HTTPException(status_code=503, detail="交易服务未启动")
    
    await service.stop()
    
    return {"success": True, "message": "交易服务已停止"}
