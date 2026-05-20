"""
套利策略 API

提供三大套利扫描器的管理接口:
1. 资金费率套利 (单所 + 跨所对比)
2. 三角套利扫描
3. 期现基差套利
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import asyncio
import logging

from strategies.arbitrage.funding_rate import FundingRateArbitrage
from strategies.arbitrage.funding_rate_monitor import (
    FundingRateMonitor,
    get_funding_rate_monitor,
)
from strategies.arbitrage.triangular_scanner import (
    TriangularArbitrageScanner,
    get_triangular_scanner,
)
from strategies.arbitrage.basis_arbitrage import (
    BasisArbitrageScanner,
    get_basis_scanner,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/arbitrage", tags=["套利策略"])

# 全局策略实例
_arbitrage_strategies: Dict[str, FundingRateArbitrage] = {}


# ============================================================
# 1. 资金费率监控 (新增: 跨所对比)
# ============================================================

class FundingRateConfig(BaseModel):
    """资金费率套利配置"""
    min_funding_rate: float = Field(0.0001, description="最小费率阈值")
    max_position_size: float = Field(1000, description="单笔仓位大小 (USDT)")
    max_positions: int = Field(5, description="最大同时持仓数")
    exchanges: List[str] = Field(["binance", "okx"], description="支持的交易所")


@router.get("/funding_rate/monitor")
async def get_funding_rate_monitor_data(
    min_rate: float = Query(0.0003, description="最小单所费率阈值"),
    min_spread: float = Query(0.0004, description="最小跨所价差阈值"),
):
    """
    获取多交易所资金费率监控数据
    
    返回:
    - 跨所费率套利机会 (Binance vs OKX 同品种费率差)
    - 单所高费率品种 (年化排序)
    """
    try:
        monitor = get_funding_rate_monitor()
        monitor.min_funding_rate = min_rate
        monitor.min_cross_spread = min_spread

        summary = await monitor.get_summary()

        return {
            "success": True,
            **summary,
        }

    except Exception as e:
        logger.error(f"资金费率监控失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funding_rate/cross_exchange")
async def get_cross_exchange_opportunities(
    min_spread: float = Query(0.0004, description="最小费率差"),
):
    """
    获取跨交易所费率套利机会
    
    逻辑: 同一品种在 Binance 和 OKX 的 funding rate 差异
    """
    try:
        monitor = get_funding_rate_monitor()
        monitor.min_cross_spread = min_spread

        opportunities = await monitor.find_cross_exchange_opportunities()

        return {
            "success": True,
            "count": len(opportunities),
            "opportunities": [o.to_dict() for o in opportunities],
        }

    except Exception as e:
        logger.error(f"跨所费率扫描失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funding_rate/single_exchange")
async def get_single_exchange_opportunities(
    min_rate: float = Query(0.0003, description="最小费率阈值 (0.03%)"),
):
    """
    获取单交易所高费率品种 (现货+永续对冲)
    
    逻辑: funding rate 高 → 买入现货 + 做空永续 → 收费率
    """
    try:
        monitor = get_funding_rate_monitor()
        monitor.min_funding_rate = min_rate

        opportunities = await monitor.find_single_exchange_opportunities()

        return {
            "success": True,
            "count": len(opportunities),
            "opportunities": [o.to_dict() for o in opportunities],
        }

    except Exception as e:
        logger.error(f"单所费率扫描失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/funding_rate/start")
async def start_funding_rate_arbitrage(config: FundingRateConfig):
    """启动资金费率套利"""
    try:
        strategy_id = "funding_rate_default"

        strategy = FundingRateArbitrage(config={
            "min_funding_rate": config.min_funding_rate,
            "position_size_usdt": config.max_position_size,
            "max_positions": config.max_positions,
            "exchanges": config.exchanges,
        })

        await strategy.initialize()
        _arbitrage_strategies[strategy_id] = strategy

        return {
            "success": True,
            "message": "资金费率套利已启动",
            "strategy_id": strategy_id,
        }

    except Exception as e:
        logger.error(f"启动资金费率套利失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/funding_rate/stop")
async def stop_funding_rate_arbitrage():
    """停止资金费率套利"""
    strategy_id = "funding_rate_default"

    if strategy_id not in _arbitrage_strategies:
        raise HTTPException(status_code=404, detail="策略未运行")

    strategy = _arbitrage_strategies[strategy_id]
    positions = list(strategy.positions.keys())
    for symbol in positions:
        await strategy.close_position(symbol)

    del _arbitrage_strategies[strategy_id]

    return {
        "success": True,
        "message": f"已停止套利，平仓 {len(positions)} 个持仓",
    }


@router.get("/funding_rate/positions")
async def get_funding_rate_positions():
    """获取当前套利持仓"""
    strategy_id = "funding_rate_default"

    if strategy_id not in _arbitrage_strategies:
        return {"success": True, "positions": [], "total_earned": 0}

    strategy = _arbitrage_strategies[strategy_id]
    status = await strategy.get_status()

    return {
        "success": True,
        "positions": status["positions"],
        "total_earned": status["total_funding_earned"],
        "active_count": status["active_positions"],
    }


@router.get("/funding_rate/status")
async def get_strategy_status():
    """获取策略运行状态"""
    strategy_id = "funding_rate_default"

    if strategy_id not in _arbitrage_strategies:
        return {"running": False, "message": "策略未运行"}

    strategy = _arbitrage_strategies[strategy_id]
    status = await strategy.get_status()
    risk_metrics = strategy.get_risk_metrics()

    return {"running": True, "status": status, "risk_metrics": risk_metrics}


@router.post("/funding_rate/close/{symbol}")
async def close_funding_position(symbol: str):
    """平掉某个持仓"""
    strategy_id = "funding_rate_default"

    if strategy_id not in _arbitrage_strategies:
        raise HTTPException(status_code=404, detail="策略未运行")

    strategy = _arbitrage_strategies[strategy_id]
    if symbol not in strategy.positions:
        raise HTTPException(status_code=404, detail=f"未找到持仓: {symbol}")

    success = await strategy.close_position(symbol)
    if success:
        return {"success": True, "message": f"已平仓 {symbol}"}
    raise HTTPException(status_code=500, detail="平仓失败")


# ============================================================
# 2. 三角套利扫描
# ============================================================

@router.get("/triangular/scan")
async def scan_triangular_arbitrage(
    exchange: str = Query("binance", description="交易所 (binance/okx)"),
    min_profit: float = Query(0.05, description="最小净利润 % (扣费后)"),
):
    """
    扫描三角套利机会
    
    在指定交易所内扫描所有 3 步交易路径，
    找出扣除 taker 手续费后仍盈利的套利路径。
    
    示例路径: USDT → BTC → ETH → USDT
    """
    try:
        scanner = get_triangular_scanner(exchange)
        scanner.min_net_profit_pct = min_profit

        summary = await scanner.get_summary()

        return {
            "success": True,
            **summary,
        }

    except Exception as e:
        logger.error(f"三角套利扫描失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/triangular/opportunities")
async def get_triangular_opportunities(
    exchange: str = Query("binance", description="交易所"),
    min_profit: float = Query(0.02, description="最小净利润 %"),
    limit: int = Query(20, description="最大返回数"),
):
    """
    获取三角套利机会列表 (仅盈利路径)
    """
    try:
        scanner = get_triangular_scanner(exchange)
        scanner.min_net_profit_pct = min_profit
        scanner.max_results = limit

        opportunities = await scanner.scan()

        return {
            "success": True,
            "exchange": exchange,
            "count": len(opportunities),
            "fee_rate_pct": scanner.FEES.get(exchange, 0.001) * 100,
            "opportunities": [o.to_dict() for o in opportunities],
        }

    except Exception as e:
        logger.error(f"获取三角套利机会失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 3. 期现基差套利
# ============================================================

@router.get("/basis/scan")
async def scan_basis_arbitrage(
    min_annualized: float = Query(5.0, description="最小年化收益 %"),
    max_days: int = Query(120, description="最大到期天数"),
):
    """
    扫描期现基差套利机会
    
    监控 Binance/OKX 所有交割合约与现货的价差，
    计算扣费后年化收益率。
    
    策略: 当正溢价(contango)足够大时 → 现货买入 + 期货做空 → 到期收敛获利
    """
    try:
        scanner = get_basis_scanner()
        scanner.min_annualized_rate = min_annualized / 100  # 转为小数
        scanner.max_days_to_expiry = max_days

        summary = await scanner.get_summary()

        return {
            "success": True,
            **summary,
        }

    except Exception as e:
        logger.error(f"期现基差扫描失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/basis/opportunities")
async def get_basis_opportunities(
    min_annualized: float = Query(5.0, description="最小年化 %"),
    exchange: Optional[str] = Query(None, description="指定交易所 (可选)"),
    symbol: Optional[str] = Query(None, description="指定币种 (可选, 如 BTC)"),
    limit: int = Query(20, description="最大返回数"),
):
    """
    获取期现基差套利机会列表
    """
    try:
        scanner = get_basis_scanner()
        scanner.min_annualized_rate = min_annualized / 100
        scanner.max_results = limit

        if exchange:
            scanner.exchange_names = [exchange]
        if symbol:
            scanner.symbols_filter = [symbol]

        opportunities = await scanner.scan()

        return {
            "success": True,
            "count": len(opportunities),
            "opportunities": [o.to_dict() for o in opportunities],
        }

    except Exception as e:
        logger.error(f"获取基差套利机会失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 4. 综合套利仪表盘
# ============================================================

@router.get("/dashboard")
async def get_arbitrage_dashboard():
    """
    套利机会总览仪表盘
    
    一次性返回所有类型套利机会的摘要信息，供前端 Dashboard 展示。
    """
    try:
        # 并行扫描三类套利
        monitor = get_funding_rate_monitor()
        tri_scanner_binance = get_triangular_scanner("binance")
        basis_scanner = get_basis_scanner()

        results = await asyncio.gather(
            monitor.get_summary(),
            tri_scanner_binance.get_summary(),
            basis_scanner.get_summary(),
            return_exceptions=True,
        )

        funding_data = results[0] if not isinstance(results[0], Exception) else {"error": str(results[0])}
        triangular_data = results[1] if not isinstance(results[1], Exception) else {"error": str(results[1])}
        basis_data = results[2] if not isinstance(results[2], Exception) else {"error": str(results[2])}

        return {
            "success": True,
            "funding_rate": {
                "type": "资金费率套利",
                "description": "利用永续合约 funding rate 赚取费率收益",
                "risk_level": "低",
                "expected_apy": "8-20%",
                **funding_data,
            },
            "triangular": {
                "type": "三角套利",
                "description": "利用所内三个交易对的定价偏差获利",
                "risk_level": "低",
                "expected_profit": "0.02-0.5% / 次",
                **triangular_data,
            },
            "basis": {
                "type": "期现基差套利",
                "description": "利用交割合约与现货的价差，到期收敛获利",
                "risk_level": "极低",
                "expected_apy": "5-15%",
                **basis_data,
            },
            "strategy_running": "funding_rate_default" in _arbitrage_strategies,
        }

    except Exception as e:
        logger.error(f"套利仪表盘加载失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
