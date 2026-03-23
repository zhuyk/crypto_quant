"""
套利策略 API

提供资金费率套利的管理接口
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from decimal import Decimal
import asyncio

from app.core.auth.auth_middleware import get_current_user
from app.models.user import User
from strategies.arbitrage.funding_rate import FundingRateArbitrage
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/arbitrage", tags=["套利策略"])

# 全局策略实例（生产环境应该用更完善的状态管理）
_arbitrage_strategies: Dict[str, FundingRateArbitrage] = {}


class FundingRateConfig(BaseModel):
    """资金费率套利配置"""
    min_funding_rate: float = Field(0.0001, description="最小费率阈值")
    max_position_size: float = Field(1000, description="单笔仓位大小 (USDT)")
    max_positions: int = Field(5, description="最大同时持仓数")
    exchanges: List[str] = Field(["binance", "bybit"], description="支持的交易所")


class ArbitrageSignal(BaseModel):
    """套利信号"""
    symbol: str
    exchange: str
    funding_rate: float
    annual_return: float
    side: str  # LONG 或 SHORT
    reason: str


class PositionInfo(BaseModel):
    """持仓信息"""
    symbol: str
    side: str
    entry_price: float
    quantity: float
    funding_earned: float
    open_time: str


@router.post("/funding_rate/start")
async def start_funding_rate_arbitrage(
    config: FundingRateConfig,
    current_user: User = Depends(get_current_user)
):
    """启动资金费率套利"""
    try:
        strategy_id = f"funding_rate_{current_user.id}"
        
        # 创建策略实例
        strategy = FundingRateArbitrage(config={
            "min_funding_rate": config.min_funding_rate,
            "position_size_usdt": config.max_position_size,
            "max_positions": config.max_positions,
            "exchanges": config.exchanges,
        })
        
        # 初始化策略
        await strategy.initialize()
        
        # 保存策略
        _arbitrage_strategies[strategy_id] = strategy
        
        logger.info(f"用户 {current_user.id} 启动资金费率套利")
        
        return {
            "success": True,
            "message": "资金费率套利已启动",
            "strategy_id": strategy_id,
        }
        
    except Exception as e:
        logger.error(f"启动资金费率套利失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/funding_rate/stop")
async def stop_funding_rate_arbitrage(
    strategy_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """停止资金费率套利"""
    if not strategy_id:
        strategy_id = f"funding_rate_{current_user.id}"
    
    if strategy_id not in _arbitrage_strategies:
        raise HTTPException(status_code=404, detail="策略未运行")
    
    try:
        strategy = _arbitrage_strategies[strategy_id]
        
        # 平掉所有持仓
        positions = list(strategy.positions.keys())
        for symbol in positions:
            await strategy.close_position(symbol)
        
        # 移除策略
        del _arbitrage_strategies[strategy_id]
        
        logger.info(f"用户 {current_user.id} 停止资金费率套利")
        
        return {
            "success": True,
            "message": f"已停止套利，平仓 {len(positions)} 个持仓",
        }
        
    except Exception as e:
        logger.error(f"停止资金费率套利失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funding_rate/signals")
async def get_funding_rate_signals(
    min_rate: float = 0.0001,
    current_user: User = Depends(get_current_user)
):
    """获取资金费率套利机会"""
    try:
        # 创建临时策略实例用于扫描
        strategy = FundingRateArbitrage(config={"min_funding_rate": min_rate})
        await strategy._load_funding_rates()
        
        # 生成信号
        signals = await strategy.generate_signals()
        
        return {
            "success": True,
            "signals": [
                {
                    "symbol": signal.symbol,
                    "exchange": signal.exchange,
                    "side": signal.signal_type.name,
                    "funding_rate": signal.metadata["funding_rate"],
                    "annual_return": signal.metadata["annual_return"],
                    "reason": signal.metadata["reason"],
                }
                for signal in signals
            ],
        }
        
    except Exception as e:
        logger.error(f"获取套利信号失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funding_rate/positions")
async def get_funding_rate_positions(
    current_user: User = Depends(get_current_user)
):
    """获取当前套利持仓"""
    strategy_id = f"funding_rate_{current_user.id}"
    
    if strategy_id not in _arbitrage_strategies:
        return {
            "success": True,
            "positions": [],
            "total_earned": 0,
        }
    
    try:
        strategy = _arbitrage_strategies[strategy_id]
        status = await strategy.get_status()
        
        return {
            "success": True,
            "positions": status["positions"],
            "total_earned": status["total_funding_earned"],
            "active_count": status["active_positions"],
        }
        
    except Exception as e:
        logger.error(f"获取持仓信息失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/funding_rate/close/{symbol}")
async def close_position(
    symbol: str,
    current_user: User = Depends(get_current_user)
):
    """平掉某个持仓"""
    strategy_id = f"funding_rate_{current_user.id}"
    
    if strategy_id not in _arbitrage_strategies:
        raise HTTPException(status_code=404, detail="策略未运行")
    
    try:
        strategy = _arbitrage_strategies[strategy_id]
        
        if symbol not in strategy.positions:
            raise HTTPException(status_code=404, detail=f"未找到持仓：{symbol}")
        
        success = await strategy.close_position(symbol)
        
        if success:
            return {
                "success": True,
                "message": f"已平仓 {symbol}",
            }
        else:
            raise HTTPException(status_code=500, detail="平仓失败")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"平仓失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funding_rate/status")
async def get_strategy_status(
    current_user: User = Depends(get_current_user)
):
    """获取策略运行状态"""
    strategy_id = f"funding_rate_{current_user.id}"
    
    if strategy_id not in _arbitrage_strategies:
        return {
            "running": False,
            "message": "策略未运行",
        }
    
    try:
        strategy = _arbitrage_strategies[strategy_id]
        status = await strategy.get_status()
        risk_metrics = strategy.get_risk_metrics()
        
        return {
            "running": True,
            "status": status,
            "risk_metrics": risk_metrics,
        }
        
    except Exception as e:
        logger.error(f"获取策略状态失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funding_rate/rates")
async def get_funding_rates(
    exchange: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """获取最新资金费率"""
    try:
        strategy = FundingRateArbitrage()
        await strategy._load_funding_rates()
        
        if exchange:
            rates = strategy.funding_rates.get(exchange, {})
        else:
            rates = strategy.funding_rates
        
        # 格式化返回
        formatted_rates = []
        for exch, symbols in rates.items():
            for symbol, data in symbols.items():
                formatted_rates.append({
                    "exchange": exch,
                    "symbol": symbol,
                    "funding_rate": data["funding_rate"],
                    "annual_rate": data["funding_rate"] * 3 * 365,
                    "next_funding_time": data["next_funding_time"].isoformat(),
                    "mark_price": data["mark_price"],
                    "index_price": data["index_price"],
                    "price_diff_percent": ((data["mark_price"] - data["index_price"]) / data["index_price"]) * 100,
                })
        
        # 按费率排序
        formatted_rates.sort(key=lambda x: x["funding_rate"], reverse=True)
        
        return {
            "success": True,
            "rates": formatted_rates,
        }
        
    except Exception as e:
        logger.error(f"获取资金费率失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))
