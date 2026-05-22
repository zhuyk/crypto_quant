"""
实盘交易 API 路由（统一交易服务）

整合功能:
- 交易所连接和状态管理
- 手动订单 (市价/限价/批量)
- 策略信号自动执行
- 仓位和风控管理
- 交易服务生命周期 (启动/停止)
- API 密钥管理
- 并发订单执行

增强错误处理、重试机制、并发执行
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from decimal import Decimal
from loguru import logger
import asyncio
import time
import uuid

from app.core.config import settings
from app.core.exceptions import (
    TradingError,
    OrderError,
    InsufficientFundsError,
    ExternalAPIError,
    NotFoundError,
    retry_on_exception,
    success_response,
)
from app.core.security import get_api_key_manager, mask_sensitive_data
from app.core.trading_state import is_connected, set_connected, set_disconnected
from engine.concurrent.trading_executor import get_trading_executor


router = APIRouter(tags=["实盘交易"])


class TestConnectionRequest(BaseModel):
    """测试连接请求"""
    exchange: str = "binance"
    api_key: str
    api_secret: str
    passphrase: Optional[str] = None
    testnet: bool = True


@router.post("/test")
async def test_connection(request: TestConnectionRequest):
    """
    测试 API 连接
    
    真实调用交易所 API 验证 Key/Secret 有效性
    """
    try:
        from app.api.exchanges import (
            create_authenticated_exchange,
            SUPPORTED_EXCHANGES,
        )
        import ccxt
        
        if request.exchange not in SUPPORTED_EXCHANGES:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的交易所: {request.exchange}",
            )
        
        logger.info(f"测试连接 - 交易所: {request.exchange}, 测试网: {request.testnet}")
        
        # 创建认证交易所实例
        exchange = create_authenticated_exchange(
            exchange_id=request.exchange,
            api_key=request.api_key,
            api_secret=request.api_secret,
            passphrase=request.passphrase,
            testnet=request.testnet,
        )
        
        # 真实 API 调用测试
        start_time = time.time()
        balance = exchange.fetch_balance()
        latency_ms = (time.time() - start_time) * 1000
        
        # 提取非零余额
        non_zero = {
            k: float(v) for k, v in balance.get('total', {}).items()
            if v and float(v) > 0
        }
        
        # 保存连接状态
        set_connected(request.exchange, request.testnet)
        
        logger.info(f"✅ 连接测试成功: {request.exchange} ({latency_ms:.0f}ms)")
        
        return {
            "success": True,
            "message": "连接成功",
            "exchange": request.exchange,
            "testnet": request.testnet,
            "balance": non_zero or {"USDT": 0},
            "latency_ms": round(latency_ms, 2),
        }
        
    except ccxt.AuthenticationError:
        return {
            "success": False,
            "message": "认证失败: API Key 或 Secret 无效",
            "exchange": request.exchange,
            "testnet": request.testnet,
        }
    except ccxt.NetworkError as e:
        return {
            "success": False,
            "message": f"网络错误: 无法连接到交易所 ({str(e)[:80]})",
            "exchange": request.exchange,
            "testnet": request.testnet,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试连接失败: {e}")
        return {
            "success": False,
            "message": f"连接失败: {str(e)[:100]}",
            "exchange": request.exchange,
            "testnet": request.testnet,
        }


# ==================== 请求/响应模型 ====================

class OrderRequest(BaseModel):
    """订单请求"""
    symbol: str = Field(..., description="交易对 (如 BTCUSDT)")
    side: str = Field(..., description="方向：buy/sell")
    amount: float = Field(..., description="数量")
    order_type: str = Field(default="market", description="类型：market/limit")
    price: Optional[float] = Field(None, description="价格 (限价单必填)")
    stop_loss: Optional[float] = Field(None, description="止损价格")
    take_profit: Optional[float] = Field(None, description="止盈价格")


class OrderResponse(BaseModel):
    """订单响应"""
    id: str
    symbol: str
    side: str
    type: str
    amount: float
    price: Optional[float]
    status: str
    filled_amount: float
    filled_price: float
    created_at: str


class PositionResponse(BaseModel):
    """持仓响应"""
    symbol: str
    side: str
    amount: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    stop_loss: Optional[float]
    take_profit: Optional[float]


class PortfolioSummary(BaseModel):
    """投资组合汇总"""
    capital: float
    initial_capital: float
    available_capital: float
    total_exposure: float
    open_positions: int
    total_pnl: float
    total_pnl_pct: float
    daily_pnl: float
    daily_pnl_pct: float
    current_drawdown: float
    risk_level: str


# ==================== 全局状态 (临时) ====================

# TODO: 替换为数据库存储
_trading_engine = None
_position_manager = None


def get_trading_engine():
    """获取交易引擎实例"""
    global _trading_engine
    if _trading_engine is None:
        # 延迟初始化
        from engine.trader import TradingEngine
        
        _trading_engine = TradingEngine(
            exchange_id="binance",
            api_key=settings.BINANCE_API_KEY,
            api_secret=settings.BINANCE_API_SECRET,
            testnet=settings.BINANCE_TESTNET,
            initial_capital=settings.DEFAULT_INITIAL_CAPITAL,
        )
    return _trading_engine


def get_position_manager():
    """获取仓位管理器实例"""
    global _position_manager
    if _position_manager is None:
        from engine.risk import PositionManager, PositionConfig
        
        config = PositionConfig(
            initial_capital=settings.DEFAULT_INITIAL_CAPITAL,
            max_position_ratio=settings.MAX_POSITION_RATIO,
            max_daily_loss=settings.MAX_DAILY_LOSS,
            max_drawdown=settings.MAX_DRAWDOWN,
        )
        _position_manager = PositionManager(config)
    return _position_manager


# ==================== API 端点 ====================

@router.get("/status")
async def get_trading_status():
    """获取交易状态"""
    engine = get_trading_engine()
    
    # 使用状态管理而不是实际连接
    connected = is_connected()
    
    return {
        "connected": connected,
        "exchange": "binance" if connected else None,
        "testnet": True if connected else None,
        "initial_capital": engine.initial_capital if engine else 100000.0,
    }


@router.get("/balance")
async def get_balance():
    """获取账户余额"""
    engine = get_trading_engine()
    
    if not engine:
        raise HTTPException(status_code=500, detail="交易引擎未初始化")
    
    balance = engine.get_balance()
    return {"balance": balance}


@router.get("/positions")
async def get_positions():
    """获取所有持仓"""
    pm = get_position_manager()
    summary = pm.get_portfolio_summary()
    
    return {
        "positions": summary["positions"],
        "count": summary["open_positions"],
    }


@router.get("/position/{symbol}")
async def get_position(symbol: str):
    """获取指定持仓"""
    pm = get_position_manager()
    
    if symbol not in pm.positions:
        raise HTTPException(status_code=404, detail=f"未找到 {symbol} 的持仓")
    
    return pm.positions[symbol]


@router.post("/order", response_model=OrderResponse)
async def create_order(order: OrderRequest):
    """
    创建订单 - 增强错误处理和重试机制
    
    支持市价单和限价单，自动设置止损止盈
    """
    engine = get_trading_engine()
    pm = get_position_manager()
    
    if not engine:
        raise TradingError("交易引擎未初始化", error_code="ENGINE_NOT_INITIALIZED")
    
    # 参数验证
    if order.amount <= 0:
        raise OrderError("订单数量必须大于 0", error_code="INVALID_AMOUNT")
    
    if order.side not in ["buy", "sell"]:
        raise OrderError("订单方向必须是 buy 或 sell", error_code="INVALID_SIDE")
    
    if order.order_type not in ["market", "limit"]:
        raise OrderError("订单类型必须是 market 或 limit", error_code="INVALID_ORDER_TYPE")
    
    # 限价单必须指定价格
    if order.order_type == "limit" and not order.price:
        raise OrderError("限价单必须指定价格", error_code="MISSING_PRICE")
    
    # 检查是否可以开仓
    can_open, reason = pm.can_open_position(order.symbol, order.price or 0)
    if not can_open and order.side == "buy":
        raise OrderError(reason, error_code="POSITION_LIMIT_EXCEEDED")
    
    # 创建订单 (带重试)
    from engine.trader import OrderSide, OrderType
    
    start_time = time.time()
    request_id = f"order_{int(start_time * 1000)}"
    
    logger.info(f"📋 [REQ-{request_id}] 创建订单：{order.side.upper()} {order.symbol} {order.amount}")
    
    try:
        # 重试逻辑：网络错误时最多重试 3 次
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                order_obj = engine.create_order(
                    symbol=order.symbol,
                    side=OrderSide(order.side),
                    amount=order.amount,
                    order_type=OrderType(order.order_type),
                    price=order.price,
                    stop_loss=order.stop_loss,
                    take_profit=order.take_profit,
                )
                
                if order_obj:
                    break
                    
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(f"订单创建失败，重试 {attempt + 1}/{max_retries}: {str(e)}")
                    await asyncio.sleep(1.0 * (attempt + 1))  # 非阻塞递增延迟
                else:
                    raise
        
        if not order_obj:
            raise OrderError(
                f"订单创建失败：{str(last_error) if last_error else '未知错误'}",
                error_code="ORDER_CREATION_FAILED"
            )
        
        # 记录订单创建成功
        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"✅ [REQ-{request_id}] 订单创建成功：{order_obj.id} ({duration_ms:.2f}ms)")
        
        # 添加到仓位管理
        if order.side == "buy":
            pm.add_position(
                symbol=order.symbol,
                side=order.side,
                amount=order.amount,
                entry_price=order.price or order_obj.filled_price,
                stop_loss=order.stop_loss,
                take_profit=order.take_profit,
            )
        
        return OrderResponse(
            id=order_obj.id,
            symbol=order_obj.symbol,
            side=order_obj.side.value,
            type=order_obj.type.value,
            amount=order_obj.amount,
            price=order_obj.price,
            status=order_obj.status.value,
            filled_amount=order_obj.filled_amount,
            filled_price=order_obj.filled_price,
            created_at=order_obj.created_at.isoformat(),
        )
        
    except Exception as e:
        logger.error(f"订单创建失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/order/{order_id}/cancel")
async def cancel_order(order_id: str, symbol: str):
    """
    取消订单 - 增强错误处理
    
    Args:
        order_id: 订单 ID
        symbol: 交易对
    """
    engine = get_trading_engine()
    
    if not engine:
        raise TradingError("交易引擎未初始化", error_code="ENGINE_NOT_INITIALIZED")
    
    if not order_id:
        raise OrderError("订单 ID 不能为空", error_code="INVALID_ORDER_ID")
    
    if not symbol:
        raise OrderError("交易对不能为空", error_code="INVALID_SYMBOL")
    
    start_time = time.time()
    request_id = f"cancel_{order_id[:8]}"
    
    logger.info(f"📋 [REQ-{request_id}] 取消订单：{order_id}")
    
    try:
        success = engine.cancel_order(order_id, symbol)
        
        if not success:
            raise OrderError("取消订单失败 - 订单可能已成交或不存在", error_code="CANCEL_FAILED")
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"✅ [REQ-{request_id}] 订单取消成功 ({duration_ms:.2f}ms)")
        
        return success_response(
            data={"order_id": order_id, "status": "cancelled"},
            message="订单已取消"
        )
        
    except OrderError:
        raise
    except Exception as e:
        logger.error(f"取消订单失败：{e}", exc_info=True)
        raise OrderError(f"取消订单异常：{str(e)}", error_code="CANCEL_EXCEPTION")


@router.post("/position/{symbol}/close")
async def close_position(symbol: str, amount: Optional[float] = None):
    """
    平仓 - 增强错误处理
    
    Args:
        symbol: 交易对
        amount: 平仓数量 (None 表示全部平仓)
    """
    engine = get_trading_engine()
    pm = get_position_manager()
    
    if not engine:
        raise TradingError("交易引擎未初始化", error_code="ENGINE_NOT_INITIALIZED")
    
    if not symbol:
        raise OrderError("交易对不能为空", error_code="INVALID_SYMBOL")
    
    # 检查持仓是否存在
    if symbol not in pm.positions:
        raise NotFoundError("持仓", symbol)
    
    position = pm.positions[symbol]
    
    # 验证平仓数量
    if amount is not None:
        if amount <= 0:
            raise OrderError("平仓数量必须大于 0", error_code="INVALID_AMOUNT")
        if amount > position.amount:
            raise OrderError(
                f"平仓数量 ({amount}) 超过持仓数量 ({position.amount})",
                error_code="INSUFFICIENT_POSITION"
            )
    
    start_time = time.time()
    request_id = f"close_{symbol}"
    
    logger.info(f"📊 [REQ-{request_id}] 平仓：{symbol} (数量：{amount or '全部'})")
    
    try:
        # 获取当前价格 (带重试)
        max_retries = 3
        ticker = None
        last_error = None
        
        for attempt in range(max_retries):
            try:
                ticker = engine.get_ticker(symbol)
                if ticker and ticker.get("last"):
                    break
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(f"获取价格失败，重试 {attempt + 1}/{max_retries}: {str(e)}")
                    await asyncio.sleep(0.5 * (attempt + 1))
        
        if not ticker or not ticker.get("last"):
            raise ExternalAPIError(
                f"无法获取 {symbol} 当前价格",
                service="Binance",
                details={"last_error": str(last_error) if last_error else None}
            )
        
        current_price = ticker["last"]
        
        # 执行平仓
        trade = pm.close_position(symbol, current_price, amount=amount)
        
        # 在交易所执行卖出
        close_amount = amount or position.amount
        order_obj = engine.create_order(
            symbol=symbol,
            side=engine.OrderSide.SELL,
            amount=close_amount,
            order_type=engine.OrderType.MARKET,
        )
        
        if not order_obj:
            raise OrderError("平仓订单创建失败", error_code="CLOSE_ORDER_FAILED")
        
        duration_ms = (time.time() - start_time) * 1000
        pnl = trade.get("pnl", 0)
        pnl_pct = trade.get("pnl_pct", 0)
        
        logger.info(
            f"✅ [REQ-{request_id}] 平仓成功：{symbol} @ ${current_price} | "
            f"盈亏：${pnl:.2f} ({pnl_pct:.2f}%) ({duration_ms:.2f}ms)"
        )
        
        return success_response(
            data={
                "symbol": symbol,
                "exit_price": current_price,
                "amount": close_amount,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "order_id": order_obj.id,
            },
            message=f"平仓成功，盈亏：${pnl:.2f} ({pnl_pct:.2f}%)"
        )
        
    except (NotFoundError, OrderError, ExternalAPIError):
        raise
    except Exception as e:
        logger.error(f"平仓失败：{e}", exc_info=True)
        raise TradingError(f"平仓异常：{str(e)}", error_code="CLOSE_EXCEPTION")


@router.get("/portfolio")
async def get_portfolio():
    """获取投资组合汇总"""
    pm = get_position_manager()
    summary = pm.get_portfolio_summary()
    
    return summary


@router.get("/risk-metrics")
async def get_risk_metrics():
    """获取风险指标"""
    pm = get_position_manager()
    metrics = pm.get_risk_metrics()
    
    return {
        "current_drawdown": metrics.current_drawdown,
        "max_drawdown": metrics.max_drawdown,
        "daily_pnl": metrics.daily_pnl,
        "daily_pnl_pct": metrics.daily_pnl_pct,
        "total_pnl": metrics.total_pnl,
        "total_pnl_pct": metrics.total_pnl_pct,
        "win_rate": metrics.win_rate,
        "profit_factor": metrics.profit_factor,
        "exposure": metrics.exposure,
        "risk_level": metrics.get_risk_level().value,
    }


@router.get("/history")
async def get_trade_history(limit: int = 50):
    """获取交易历史"""
    pm = get_position_manager()
    
    history = pm.trade_history[-limit:]
    
    return {
        "history": history,
        "total": len(pm.trade_history),
    }


# ==================== API 密钥管理 ====================

class StoreApiKeyRequest(BaseModel):
    """存储 API 密钥请求"""
    exchange: str = Field(..., description="交易所名称 (binance/okx/bybit)")
    api_key: str = Field(..., description="API Key")
    api_secret: str = Field(..., description="API Secret")


@router.post("/api-key/store")
async def store_api_key(request: StoreApiKeyRequest):
    """
    存储 API 密钥 (加密存储)
    
    API 密钥将被加密后存储在内存中，不会明文保存
    """
    api_key_mgr = get_api_key_manager()
    
    try:
        # 加密并存储
        encrypted_key, encrypted_secret = api_key_mgr.store_api_key(
            exchange=request.exchange,
            api_key=request.api_key,
            api_secret=request.api_secret,
            encrypt=True,
        )
        
        # 返回脱敏后的密钥
        masked_key = api_key_mgr.mask_api_key(request.api_key)
        
        logger.info(f"✅ API 密钥已加密存储 - 交易所：{request.exchange}, Key: {masked_key}")
        
        return success_response(
            data={
                "exchange": request.exchange,
                "api_key_masked": masked_key,
                "stored_at": time.time(),
            },
            message="API 密钥已加密存储"
        )
        
    except Exception as e:
        logger.error(f"存储 API 密钥失败：{e}")
        raise TradingError(f"存储 API 密钥失败：{str(e)}", error_code="API_KEY_STORE_FAILED")


@router.get("/api-key/list")
async def list_api_keys():
    """列出已存储的 API 密钥 (仅显示交易所和脱敏后的 Key)"""
    api_key_mgr = get_api_key_manager()
    
    exchanges = api_key_mgr.list_exchanges()
    
    return success_response(
        data={
            "exchanges": exchanges,
            "count": len(exchanges),
        }
    )


@router.delete("/api-key/remove")
async def remove_api_key(exchange: str, api_key: str):
    """移除 API 密钥"""
    api_key_mgr = get_api_key_manager()
    
    success = api_key_mgr.remove_api_key(exchange, api_key)
    
    if success:
        return success_response(message=f"API 密钥已移除 - {exchange}")
    else:
        raise NotFoundError("API 密钥", f"{exchange}:{api_key[:8]}...")


# ==================== 并发订单执行 ====================

class BatchOrderRequest(BaseModel):
    """批量订单请求"""
    orders: List[OrderRequest] = Field(..., description="订单列表")
    execute_parallel: bool = Field(True, description="是否并行执行")


@router.post("/order/batch")
async def create_batch_orders(request: BatchOrderRequest):
    """
    批量创建订单 (支持并发执行)
    
    Args:
        orders: 订单列表
        execute_parallel: 是否并行执行
    """
    executor = get_trading_executor()
    engine = get_trading_engine()
    
    if not engine:
        raise TradingError("交易引擎未初始化", error_code="ENGINE_NOT_INITIALIZED")
    
    if len(request.orders) > 10:
        raise OrderError("批量订单最多 10 个", error_code="BATCH_SIZE_EXCEEDED")
    
    # 验证所有订单
    for i, order in enumerate(request.orders):
        if order.amount <= 0:
            raise OrderError(f"订单 {i+1} 数量无效", error_code="INVALID_AMOUNT")
        if order.side not in ["buy", "sell"]:
            raise OrderError(f"订单 {i+1} 方向无效", error_code="INVALID_SIDE")
    
    task_ids = []
    
    # 提交订单
    for i, order in enumerate(request.orders):
        order_id = f"batch_{uuid.uuid4().hex[:8]}_{i}"
        
        def execute_order(symbol, side, amount, order_type, price=None, **kwargs):
            """执行单个订单"""
            from engine.trader import OrderSide, OrderType
            
            order_obj = engine.create_order(
                symbol=symbol,
                side=OrderSide(side),
                amount=amount,
                order_type=OrderType(order_type),
                price=price,
                **kwargs,
            )
            
            if not order_obj:
                raise OrderError("订单创建失败")
            
            return order_obj.to_dict()
        
        task_id = executor.submit_order(
            order_id=order_id,
            order_func=execute_order,
            symbol=order.symbol,
            side=order.side,
            amount=order.amount,
            order_type=order.order_type,
            price=order.price,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            priority=5,
        )
        
        task_ids.append(task_id)
    
    # 等待所有订单完成
    executor.wait(task_ids, timeout=60.0)
    
    # 收集结果
    results = []
    for task_id in task_ids:
        result = executor.get_result(task_id)
        if result:
            results.append(result.to_dict())
    
    stats = executor.get_stats()
    
    logger.info(f"📦 批量订单完成 - 成功：{stats['completed']}, 失败：{stats['failed']}")
    
    return success_response(
        data={
            "total": len(task_ids),
            "results": results,
            "stats": stats,
        },
        message=f"批量订单完成 - 成功 {stats['completed']}/{len(task_ids)}"
    )


@router.get("/executor/stats")
async def get_executor_stats():
    """获取并发执行器统计"""
    executor = get_trading_executor()
    
    return {
        "stats": executor.get_stats(),
        "running_tasks": len(executor._futures),
    }


@router.get("/statistics")
async def get_trade_statistics():
    """获取交易统计信息"""
    executor = get_trading_executor()
    
    stats = executor.get_stats()
    
    return {
        "total_orders": stats.get('total', 0),
        "completed_orders": stats.get('completed', 0),
        "failed_orders": stats.get('failed', 0),
        "running_tasks": len(executor._futures),
        "success_rate": stats.get('completed', 0) / max(stats.get('total', 1), 1) * 100,
    }



# ============================================================
# 策略信号执行 (整合自 trader.py)
# ============================================================

class ExecuteSignalRequest(BaseModel):
    """执行交易信号请求"""
    strategy_id: str = Field(..., description="策略ID")
    symbol: str = Field(..., description="交易对")
    side: str = Field(..., description="买卖方向 (buy/sell)")
    quantity: Optional[str] = Field(None, description="数量 (为空则根据资金自动计算)")
    signal_strength: float = Field(default=1.0, ge=0, le=1, description="信号强度")
    price: Optional[str] = Field(None, description="价格 (限价单)")
    order_type: str = Field(default="market", description="订单类型 (market/limit)")
    stop_loss: Optional[str] = Field(None, description="止损价格")
    take_profit: Optional[str] = Field(None, description="止盈价格")
    priority: bool = Field(default=False, description="是否优先执行")


class SignalExecutionResponse(BaseModel):
    """信号执行响应"""
    success: bool
    order_id: Optional[str] = None
    client_order_id: str
    message: str
    state: str
    strategy_id: str
    symbol: str
    filled_quantity: str = "0"
    avg_fill_price: str = "0"


@router.post("/signal/execute", response_model=SignalExecutionResponse)
async def execute_strategy_signal(request: ExecuteSignalRequest):
    """
    执行策略信号
    
    接收策略产生的交易信号，经风控校验后执行订单。
    这是策略系统到交易系统的桥梁。
    
    流程:
    1. 验证策略和信号有效性
    2. 风控检查（仓位限制、日损失限制等）
    3. 计算下单量（如未指定）
    4. 提交订单执行
    """
    engine = get_trading_engine()
    pm = get_position_manager()
    
    if not engine:
        raise TradingError("交易引擎未初始化", error_code="ENGINE_NOT_INITIALIZED")
    
    # 参数验证
    if request.side not in ["buy", "sell"]:
        raise OrderError("方向必须是 buy 或 sell", error_code="INVALID_SIDE")
    
    client_order_id = f"sig_{request.strategy_id}_{request.symbol}_{int(time.time())}"
    
    logger.info(
        f"📡 策略信号: [{request.strategy_id}] {request.side.upper()} {request.symbol} "
        f"强度={request.signal_strength}"
    )
    
    try:
        # 风控检查
        if request.side == "buy":
            can_open, reason = pm.can_open_position(
                request.symbol, 
                float(request.price) if request.price else 0
            )
            if not can_open:
                logger.warning(f"⚠️ 风控拒绝信号: {reason}")
                return SignalExecutionResponse(
                    success=False,
                    client_order_id=client_order_id,
                    message=f"风控拒绝: {reason}",
                    state="rejected",
                    strategy_id=request.strategy_id,
                    symbol=request.symbol,
                )
        
        # 计算下单量
        quantity = Decimal(request.quantity) if request.quantity else None
        if not quantity:
            # 根据信号强度和资金自动计算
            portfolio = pm.get_portfolio_summary()
            available = float(portfolio.get("available_capital", 0))
            # 基础仓位 = 可用资金 * 5% * 信号强度
            position_size = available * 0.05 * request.signal_strength
            quantity = Decimal(str(max(position_size, 0)))
        
        price = Decimal(request.price) if request.price else None
        
        # 尝试通过 TraderService 执行 (如果存在)
        try:
            from engine.trader.service import get_trader_service
            service = get_trader_service()
            
            if service and service._is_running:
                success = await service.execute_signal(
                    strategy_id=request.strategy_id,
                    symbol=request.symbol,
                    side=request.side,
                    quantity=quantity,
                    price=price,
                    order_type=request.order_type,
                    priority=request.priority,
                )
                
                state = "submitted" if success else "rejected"
                return SignalExecutionResponse(
                    success=success,
                    client_order_id=client_order_id,
                    message="信号执行成功" if success else "信号执行失败",
                    state=state,
                    strategy_id=request.strategy_id,
                    symbol=request.symbol,
                )
        except ImportError:
            pass  # TraderService 不可用，回退到直接执行
        
        # 回退: 直接通过交易引擎执行
        from engine.trader import OrderSide, OrderType
        
        order_obj = engine.create_order(
            symbol=request.symbol,
            side=OrderSide(request.side),
            amount=float(quantity),
            order_type=OrderType(request.order_type),
            price=float(price) if price else None,
            stop_loss=float(request.stop_loss) if request.stop_loss else None,
            take_profit=float(request.take_profit) if request.take_profit else None,
        )
        
        if order_obj:
            # 更新仓位
            if request.side == "buy":
                pm.add_position(
                    symbol=request.symbol,
                    side=request.side,
                    amount=float(quantity),
                    entry_price=float(price or order_obj.filled_price),
                    stop_loss=float(request.stop_loss) if request.stop_loss else None,
                    take_profit=float(request.take_profit) if request.take_profit else None,
                )
            
            return SignalExecutionResponse(
                success=True,
                order_id=order_obj.id,
                client_order_id=client_order_id,
                message="信号执行成功 (直接执行)",
                state="submitted",
                strategy_id=request.strategy_id,
                symbol=request.symbol,
                filled_quantity=str(order_obj.filled_amount),
                avg_fill_price=str(order_obj.filled_price),
            )
        else:
            return SignalExecutionResponse(
                success=False,
                client_order_id=client_order_id,
                message="订单创建失败",
                state="rejected",
                strategy_id=request.strategy_id,
                symbol=request.symbol,
            )
    
    except (TradingError, OrderError):
        raise
    except Exception as e:
        logger.error(f"执行策略信号异常: {e}")
        return SignalExecutionResponse(
            success=False,
            client_order_id=client_order_id,
            message=f"执行异常: {str(e)}",
            state="error",
            strategy_id=request.strategy_id,
            symbol=request.symbol,
        )


# ============================================================
# 交易服务生命周期管理 (整合自 trader.py)
# ============================================================

class ServiceStatusResponse(BaseModel):
    """交易服务状态"""
    is_running: bool
    exchange: Optional[str] = None
    testnet: Optional[bool] = None
    current_equity: Optional[str] = None
    initial_capital: str
    total_pnl: Optional[str] = None
    total_pnl_ratio: Optional[str] = None
    active_orders: int = 0
    open_positions: int = 0
    risk_level: str = "normal"


@router.get("/service/status", response_model=ServiceStatusResponse)
async def get_service_status():
    """
    获取交易服务综合状态
    
    整合交易引擎、仓位管理、风控的全面信息
    """
    connected = is_connected()
    pm = get_position_manager()
    
    # 尝试获取 TraderService 状态
    try:
        from engine.trader.service import get_trader_service
        service = get_trader_service()
        
        if service and service._is_running:
            status = service.get_full_status()
            initial = Decimal(status['initial_capital'])
            current = Decimal(status['current_equity'])
            total_pnl = current - initial
            total_pnl_ratio = total_pnl / initial if initial != 0 else Decimal('0')
            
            return ServiceStatusResponse(
                is_running=True,
                exchange="binance" if connected else None,
                testnet=True if connected else None,
                current_equity=status['current_equity'],
                initial_capital=status['initial_capital'],
                total_pnl=str(total_pnl),
                total_pnl_ratio=str(total_pnl_ratio),
                active_orders=status['order_statistics']['active_orders'],
                open_positions=len(status['positions']),
                risk_level=status['risk_status']['risk_level'],
            )
    except (ImportError, Exception):
        pass
    
    # 回退: 从仓位管理器获取状态
    portfolio = pm.get_portfolio_summary()
    
    return ServiceStatusResponse(
        is_running=connected,
        exchange="binance" if connected else None,
        testnet=True if connected else None,
        initial_capital=str(settings.DEFAULT_INITIAL_CAPITAL),
        open_positions=portfolio.get("open_positions", 0),
        risk_level="normal",
    )


@router.post("/service/start")
async def start_trading_service():
    """
    启动交易服务
    
    初始化交易引擎、风控管理器，开始接受策略信号
    """
    try:
        from engine.trader.service import get_trader_service, init_trader_service
        from engine.risk.risk_manager import RiskManager
        
        service = get_trader_service()
        if service and service._is_running:
            return {"success": True, "message": "交易服务已在运行", "status": "running"}
        
        # 初始化风控
        risk_manager = RiskManager(
            initial_capital=settings.DEFAULT_INITIAL_CAPITAL,
            max_drawdown=settings.MAX_DRAWDOWN,
            max_daily_loss=settings.MAX_DAILY_LOSS,
        )
        
        # 初始化并启动服务
        service = init_trader_service(risk_manager=risk_manager)
        await service.start()
        
        logger.info("✅ 交易服务已启动")
        
        return {
            "success": True,
            "message": "交易服务已启动",
            "status": "running",
            "config": {
                "initial_capital": settings.DEFAULT_INITIAL_CAPITAL,
                "max_drawdown": settings.MAX_DRAWDOWN,
                "max_daily_loss": settings.MAX_DAILY_LOSS,
            },
        }
        
    except ImportError as e:
        # TraderService 模块不可用，使用基础模式
        logger.warning(f"TraderService 不可用，使用基础交易模式: {e}")
        set_connected("binance", True)
        return {
            "success": True,
            "message": "交易服务已启动 (基础模式)",
            "status": "running_basic",
        }
    except Exception as e:
        logger.error(f"启动交易服务失败: {e}")
        raise TradingError(f"启动失败: {str(e)}", error_code="SERVICE_START_FAILED")


@router.post("/service/stop")
async def stop_trading_service():
    """
    停止交易服务
    
    优雅关闭：取消挂单、停止信号接收、保存状态
    """
    try:
        from engine.trader.service import get_trader_service
        
        service = get_trader_service()
        if service and service._is_running:
            await service.stop()
            logger.info("⏹️ 交易服务已停止")
            set_disconnected()
            return {"success": True, "message": "交易服务已停止", "status": "stopped"}
        
    except ImportError:
        pass
    
    # 基础模式下停止
    set_disconnected()
    return {"success": True, "message": "交易服务已停止", "status": "stopped"}


@router.get("/service/statistics")
async def get_service_statistics():
    """
    获取交易服务详细统计
    
    包含订单统计、执行统计、对账统计、滑点统计、风控状态等
    """
    # 执行器统计
    executor = get_trading_executor()
    executor_stats = executor.get_stats()
    
    result = {
        "executor": executor_stats,
        "running_tasks": len(executor._futures),
    }
    
    # 尝试获取 TraderService 详细统计
    try:
        from engine.trader.service import get_trader_service
        service = get_trader_service()
        
        if service:
            status = service.get_full_status()
            result.update({
                "order_statistics": status.get('order_statistics', {}),
                "execution_statistics": status.get('execution_statistics', {}),
                "reconciliation_statistics": status.get('reconciliation_statistics', {}),
                "slippage_statistics": status.get('slippage_statistics', {}),
                "risk_status": status.get('risk_status', {}),
            })
            
            # 策略统计
            try:
                result["strategy_statistics"] = service.strategy_runner.get_strategy_statistics()
            except Exception:
                pass
    except (ImportError, Exception):
        pass
    
    return result
