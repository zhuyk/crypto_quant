"""
回测 API 路由

支持:
- 单策略回测（结果自动保存）
- 多策略组合回测
- 参数优化
- 回测历史查询
- 回测结果对比
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
import pandas as pd
import logging

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import async_get_db
from app.models.trade import BacktestRun
from strategies.base import Strategy
from strategies.registry import registry, get_strategy_class as registry_get_strategy
from engine.backtester import Backtester, ParameterOptimizer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["回测"])


# ============================================================
# Request / Response 模型
# ============================================================

class BacktestRequest(BaseModel):
    """回测请求"""
    strategy_name: str = Field(..., description="策略名称")
    symbol: str = Field("BTCUSDT", description="交易对")
    timeframe: str = Field("1h", description="时间周期")
    params: Dict[str, Any] = Field(default_factory=dict, description="策略参数")
    initial_capital: float = Field(100000.0, description="初始资金")
    start_time: Optional[int] = Field(None, description="开始时间 (毫秒时间戳)")
    end_time: Optional[int] = Field(None, description="结束时间 (毫秒时间戳)")


class BacktestResponse(BaseModel):
    """回测响应"""
    success: bool
    report: Optional[Dict[str, Any]] = None
    backtest_id: Optional[int] = None
    warning: Optional[str] = None  # 数据来源警告
    error: Optional[str] = None


class OptimizeRequest(BaseModel):
    """参数优化请求"""
    strategy_name: str = Field(..., description="策略名称")
    symbol: str = Field("BTCUSDT", description="交易对")
    timeframe: str = Field("1h", description="时间周期")
    param_ranges: Dict[str, List[Any]] = Field(..., description="参数范围")
    method: str = Field("grid_search", description="优化方法：grid_search, random_search, genetic")
    iterations: int = Field(100, description="迭代次数")


class PortfolioBacktestRequest(BaseModel):
    """组合回测请求"""
    strategies: List[Dict[str, Any]] = Field(..., description="策略配置列表")
    symbol: str = Field("BTCUSDT", description="交易对")
    timeframe: str = Field("1h", description="时间周期")
    allocation: Dict[str, float] = Field(default_factory=dict, description="资金分配权重")
    initial_capital: float = Field(100000.0, description="初始资金")


class EnsembleBacktestRequest(BaseModel):
    """集成回测请求"""
    strategies: List[str] = Field(..., description="策略名称列表")
    strategy_params: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="各策略参数")
    symbol: str = Field("BTCUSDT", description="交易对")
    timeframe: str = Field("1h", description="时间周期")
    voting_mode: str = Field("majority", description="投票模式")
    threshold: float = Field(0.5, description="信号阈值")
    initial_capital: float = Field(100000.0, description="初始资金")


# ============================================================
# 核心回测接口
# ============================================================

@router.post("/run", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest, db: Session = Depends(async_get_db)):
    """
    执行回测（结果自动保存到数据库）
    
    支持策略：
    - ma_cross: 双均线交叉
    - breakout: 通道突破
    - macd: MACD 趋势
    """
    try:
        # 加载数据
        data = await _load_data(request.symbol, request.timeframe, request.start_time, request.end_time)
        
        if data.empty:
            raise HTTPException(status_code=404, detail="未找到数据")
        
        # 创建策略
        strategy = _create_strategy(request.strategy_name, request.params)
        
        # 创建回测引擎
        backtester = Backtester(
            initial_capital=request.initial_capital,
            commission_rate=0.001,
            slippage=0.0005,
            timeframe=request.timeframe,
        )
        
        # 执行回测
        report = backtester.run(strategy, data)
        report_dict = report.to_dict()
        
        # 解析时间范围
        start_date = _parse_timestamp(request.start_time) or data.index[0].to_pydatetime()
        end_date = _parse_timestamp(request.end_time) or data.index[-1].to_pydatetime()
        
        # 保存回测记录
        backtest_id = _save_backtest_run(
            db=db,
            strategy_name=request.strategy_name,
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=request.initial_capital,
            report=report_dict,
            params=request.params,
        )
        
        logger.info(f"✅ 回测保存成功 [id={backtest_id}] {request.strategy_name} {request.symbol}")
        
        # 标注数据来源
        data_source = getattr(data, 'attrs', {}).get('_data_source', 'unknown')
        report_dict['data_source'] = data_source
        report_dict['data_points'] = len(data)
        
        # 如果使用了模拟数据，在响应中明确警告
        warning = None
        if data_source == 'mock':
            warning = "⚠️ 本次回测使用模拟随机数据，结果仅供参考，不代表真实市场表现"
        
        return BacktestResponse(
            success=True,
            report=report_dict,
            backtest_id=backtest_id,
            warning=warning,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("回测执行失败")
        return BacktestResponse(
            success=False,
            error=str(e),
        )


@router.post("/optimize")
async def optimize_parameters(request: OptimizeRequest, background_tasks: BackgroundTasks):
    """
    参数优化
    
    支持三种优化方法：
    - grid_search: 网格搜索 (适合参数少的情况)
    - random_search: 随机搜索 (适合参数多的情况)
    - genetic: 遗传算法 (适合复杂参数空间)
    """
    try:
        data = await _load_data(request.symbol, request.timeframe)
        
        if data.empty:
            raise HTTPException(status_code=404, detail="未找到数据")
        
        strategy_class = _get_strategy_class(request.strategy_name)
        backtester = Backtester(initial_capital=100000.0, timeframe=request.timeframe)
        
        optimizer = ParameterOptimizer(
            backtester=backtester,
            data=data,
            strategy_class=strategy_class,
            metric="sharpe_ratio",
        )
        
        if request.method == "grid_search":
            results = optimizer.grid_search(request.param_ranges)
        elif request.method == "random_search":
            results = optimizer.random_search(request.param_ranges, request.iterations)
        elif request.method == "genetic":
            results = optimizer.genetic_algorithm(request.param_ranges, population_size=request.iterations//5)
        else:
            raise ValueError(f"不支持的优化方法：{request.method}")
        
        best_result = results[0] if results else None
        
        return {
            "success": True,
            "param_ranges": request.param_ranges,      # 原始参数范围，便于核对
            "total_combinations": len(results),
            "best_params": best_result["params"] if best_result else None,
            "best_metric": best_result["metric_value"] if best_result else None,
            "top_10": [
                {
                    "params": r["params"],
                    "metric": r["metric_value"],
                    "total_return": r.get("total_return"),
                    "sharpe_ratio": r.get("sharpe_ratio"),
                    "max_drawdown": r.get("max_drawdown"),
                    "win_rate": r.get("win_rate"),
                    "total_trades": r.get("total_trades"),
                }
                for r in results[:10]
            ],
            "all_results": [
                {
                    "params": r["params"],
                    "metric": r["metric_value"],
                }
                for r in results
            ],
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("参数优化失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/run")
async def run_portfolio_backtest(request: PortfolioBacktestRequest, db: Session = Depends(async_get_db)):
    """
    执行多策略组合回测
    """
    try:
        data = await _load_data(request.symbol, request.timeframe)
        
        if data.empty:
            raise HTTPException(status_code=404, detail="未找到数据")
        
        portfolio_params = {
            "strategies": request.strategies,
            "rebalance_period": 24,
        }
        portfolio = PortfolioStrategy(portfolio_params)
        
        backtester = Backtester(
            initial_capital=request.initial_capital,
            commission_rate=0.001,
            slippage=0.0005,
        )
        
        report = backtester.run(portfolio, data)
        report_dict = report.to_dict()
        report_dict["portfolio_breakdown"] = portfolio.get_performance_breakdown()
        
        start_date = data.index[0].to_pydatetime()
        end_date = data.index[-1].to_pydatetime()
        
        backtest_id = _save_backtest_run(
            db=db,
            strategy_name="portfolio",
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=request.initial_capital,
            report=report_dict,
            params={"strategies": request.strategies},
        )
        
        return {
            "success": True,
            "report": report_dict,
            "backtest_id": backtest_id,
            "type": "portfolio",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("组合回测执行失败")
        return {"success": False, "error": str(e)}


@router.post("/ensemble/run", response_model=BacktestResponse)
async def run_ensemble_backtest(request: EnsembleBacktestRequest, db: Session = Depends(async_get_db)):
    """
    执行集成策略回测
    """
    try:
        data = await _load_data(request.symbol, request.timeframe)
        
        if data.empty:
            raise HTTPException(status_code=404, detail="未找到数据")
        
        ensemble_params = {
            "strategies": request.strategies,
            "strategy_params": request.strategy_params,
            "voting_mode": request.voting_mode,
            "threshold": request.threshold,
            "min_strength": 0.3,
        }
        ensemble = EnsembleStrategy(ensemble_params)
        
        backtester = Backtester(initial_capital=request.initial_capital)
        report = backtester.run(ensemble, data)
        report_dict = report.to_dict()
        
        start_date = data.index[0].to_pydatetime()
        end_date = data.index[-1].to_pydatetime()
        
        backtest_id = _save_backtest_run(
            db=db,
            strategy_name="ensemble",
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=request.initial_capital,
            report=report_dict,
            params=ensemble_params,
        )
        
        return BacktestResponse(
            success=True,
            report=report_dict,
            backtest_id=backtest_id,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("集成回测执行失败")
        return BacktestResponse(success=False, error=str(e))


# ============================================================
# 历史查询 & 对比
# ============================================================

class BacktestHistoryItem(BaseModel):
    """历史回测条目"""
    id: int
    strategy_name: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    status: str
    created_at: str


@router.get("/history")
async def get_backtest_history(
    symbol: Optional[str] = Query(None, description="按交易对筛选"),
    strategy_name: Optional[str] = Query(None, description="按策略名筛选"),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    db: Session = Depends(async_get_db),
):
    """
    查询回测历史记录
    """
    import json as _json
    
    query = db.query(BacktestRun).order_by(BacktestRun.created_at.desc())
    
    if symbol:
        # symbols 列是 JSON 字符串，搜索包含该交易对的记录
        query = query.filter(BacktestRun.symbols.contains(f'"{symbol}"'))
    if strategy_name:
        query = query.filter(BacktestRun.name == strategy_name)
    
    runs = query.limit(limit).all()
    
    def _parse_symbol(syms) -> str:
        try:
            if isinstance(syms, str):
                lst = _json.loads(syms)
            else:
                lst = syms
            return lst[0] if lst else ""
        except Exception:
            return ""
    
    return {
        "success": True,
        "total": len(runs),
        "items": [
            BacktestHistoryItem(
                id=r.id,
                strategy_name=r.name,
                symbol=_parse_symbol(r.symbols),
                timeframe="",  # 实际表无此列
                start_date=r.start_date.isoformat() if r.start_date else "",
                end_date=r.end_date.isoformat() if r.end_date else "",
                initial_capital=float(r.initial_capital) if r.initial_capital else 0,
                final_capital=float(r.final_capital) if r.final_capital else 0,
                total_return=float(r.total_return) if r.total_return else 0,
                sharpe_ratio=float(r.sharpe_ratio) if r.sharpe_ratio else 0,
                max_drawdown=float(r.max_drawdown) if r.max_drawdown else 0,
                win_rate=float(r.win_rate) if r.win_rate else 0,
                total_trades=r.total_trades or 0,
                status=r.status or "",
                created_at=r.created_at.isoformat() if r.created_at else "",
            ).model_dump()
            for r in runs
        ],
    }


@router.get("/compare")
async def compare_backtests(
    ids: str = Query(..., description="回测 ID，多个用逗号分隔，如 1,2,3"),
    db: Session = Depends(async_get_db),
):
    """
    对比多次回测结果
    """
    try:
        id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="id 参数格式错误，需为逗号分隔的数字")
    
    if len(id_list) < 2:
        raise HTTPException(status_code=400, detail="至少需要 2 个回测 ID 进行对比")
    
    if len(id_list) > 10:
        raise HTTPException(status_code=400, detail="最多对比 10 个回测")
    
    runs = db.query(BacktestRun).filter(BacktestRun.id.in_(id_list)).all()
    
    if len(runs) < 2:
        raise HTTPException(status_code=404, detail="未找到足够的回测记录")
    
    # 构建对比数据
    items = []
    metrics = ["total_return", "sharpe_ratio", "max_drawdown", "win_rate",
               "total_trades", "annual_return", "profit_factor", "initial_capital",
               "final_capital"]
    
    import json as _json
    
    def _parse_symbol(syms):
        try:
            if isinstance(syms, str):
                lst = _json.loads(syms)
            else:
                lst = syms
            return lst[0] if lst else ""
        except Exception:
            return ""
    
    for r in runs:
        items.append({
            "id": r.id,
            "strategy_name": r.name,       # name 列实际存策略名
            "symbol": _parse_symbol(r.symbols),
            "timeframe": "",               # 实际表无此列
            "params": r.params,
            "metrics": {m: getattr(r, m, None) for m in metrics},
        })
    
    # 汇总对比表
    comparison = _build_comparison_table(items, metrics)
    
    return {
        "success": True,
        "runs": items,
        "comparison": comparison,
    }


@router.delete("/{backtest_id}")
async def delete_backtest(backtest_id: int, db: Session = Depends(async_get_db)):
    """
    删除某条回测记录
    """
    run = db.query(BacktestRun).filter(BacktestRun.id == backtest_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="回测记录不存在")
    
    db.delete(run)
    db.commit()
    
    return {"success": True, "message": f"回测 #{backtest_id} 已删除"}


@router.get("/strategies")
async def list_strategies():
    """获取可用策略列表（含详细说明）"""
    strategies = {
        "ma_cross": {
            "name": "双均线交叉",
            "category": "trend",
            "type": "single",
            "description": (
                "最经典的趋势跟踪策略之一。通过观察短期均线上穿/下穿长期均线的交叉点，"
                "来判断趋势方向并产生交易信号。当快线从下方穿越慢线（金叉），视为上涨趋势确立，做多；"
                "当快线从上方穿越慢线（死叉），视为下跌趋势确立，平仓或做空。"
                "适合趋势明显的市场，在震荡行情中容易反复开平仓造成亏损。"
            ),
            "params": {
                "fast_period": 20,
                "slow_period": 60,
                "stop_loss_pct": 0.05,
                "take_profit_pct": 0.15,
            },
            "param_ranges": {
                "fast_period": [5, 10, 15, 20, 30],
                "slow_period": [30, 60, 90, 120],
                "stop_loss_pct": [0.02, 0.03, 0.05, 0.08],
                "take_profit_pct": [0.05, 0.10, 0.15, 0.20],
            },
            "param_descriptions": {
                "fast_period": "快线周期：计算短期均线的 K 线数量。值越小，对价格变化越敏感，信号越多但假信号也越多。",
                "slow_period": "慢线周期：计算长期均线的 K 线数量。值越大，趋势确认越慢，但信号更可靠。",
                "stop_loss_pct": "止损比例：入场后如果价格反向波动超过这个比例，自动平仓止损。",
                "take_profit_pct": "止盈比例：入场后如果盈利达到这个比例，自动平仓止盈。",
            },
        },
        "breakout": {
            "name": "通道突破",
            "category": "trend",
            "type": "single",
            "description": (
                "基于唐奇安通道（Donchian Channel）的突破策略。"
                "在最近 N 根 K 线中，最高价形成上轨，最低价形成下轨。"
                "当价格向上突破上轨时，认为趋势向上，做多；当价格向下突破下轨时，做空。"
                "突破类策略的核心思想是【趋势一旦形成，会持续一段时间】，"
                "在价格波动大、趋势明显的市场中表现较好。配合成交量过滤可以减少假突破。"
            ),
            "params": {
                "lookback_period": 20,
                "stop_loss_pct": 0.08,
            },
            "param_ranges": {
                "lookback_period": [10, 20, 30, 50],
                "stop_loss_pct": [0.03, 0.05, 0.08, 0.10],
                "volume_multiplier": [1.0, 1.5, 2.0],
            },
            "param_descriptions": {
                "lookback_period": "通道周期：取最近多少根 K 线的最高/最低价作为通道上下轨。周期越长，轨道越宽，突破信号越少但越可靠。",
                "stop_loss_pct": "止损比例：入场后价格反向波动超过此比例时止损。",
                "volume_multiplier": "成交量倍数：突破时要求成交量不低于均量的多少倍，过滤无量突破。",
            },
        },
        "macd": {
            "name": "MACD 趋势",
            "category": "trend",
            "type": "single",
            "description": (
                "MACD（Moving Average Convergence Divergence）是市场最流行的技术指标之一。"
                "由快线（DIF）、慢线（DEA/MACD 线）和柱状图组成。"
                "当 DIF 从下方上穿 DEA（金叉）时做多，从上方下穿 DEA（死叉）时平仓或做空。"
                "MACD 能较好地捕捉中期趋势，对噪音有一定的过滤作用。"
                "柱状图（MACD Histogram）还能显示动能变化，顶底背离是重要的反转信号。"
            ),
            "params": {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
            },
            "param_ranges": {
                "fast_period": [8, 10, 12, 15],
                "slow_period": [20, 26, 30, 40],
                "signal_period": [6, 9, 12],
            },
            "param_descriptions": {
                "fast_period": "快线周期：短期 EMA 周期。值越小，MACD 对价格越敏感。",
                "slow_period": "慢线周期：长期 EMA 周期。值越大，MACD 变化越平缓。",
                "signal_period": "信号线周期：DIF 的 EMA 平滑周期，用于生成交易信号。",
            },
        },
        "bollinger": {
            "name": "布林带均值回归",
            "category": "trend",
            "type": "single",
            "description": (
                "基于统计学原理的趋势跟踪策略。布林带由中轨（均线）和上下轨（均线 ± N 倍标准差）组成。"
                "价格触及下轨时认为偏低，可能反弹；触及上轨时认为偏高，可能回落。"
                "配合 RSI 指标过滤，只在超卖区域做多、超买区域做空，提高信号质量。"
                "本质是均值回归思想——价格偏离均值过远后，终将向均值回归。"
                "适合震荡行情，在强趋势中价格可能沿布林带持续单边运行，造成亏损。"
            ),
            "params": {
                "bb_period": 20,
                "bb_std": 2.0,
                "stop_loss_pct": 0.03,
                "take_profit_pct": 0.06,
                "rsi_period": 14,
                "rsi_oversold": 30,
                "rsi_overbought": 70,
            },
            "param_ranges": {
                "bb_period": [10, 15, 20, 30],
                "bb_std": [1.5, 2.0, 2.5, 3.0],
                "stop_loss_pct": [0.02, 0.03, 0.05],
                "take_profit_pct": [0.04, 0.06, 0.08, 0.10],
                "rsi_oversold": [20, 25, 30],
                "rsi_overbought": [70, 75, 80],
            },
            "param_descriptions": {
                "bb_period": "布林周期：中轨均线的计算周期。值越大，布林带越平滑；值越小，对价格越敏感。",
                "bb_std": "标准差倍数：上下轨与中轨的距离（标准差倍数）。倍数越大，轨道越宽，信号越少但越可靠。",
                "stop_loss_pct": "止损比例：入场后价格反向超过此比例止损。布林策略止损相对较小。",
                "take_profit_pct": "止盈比例：价格回到均线附近时止盈。布林策略靠均值回归盈利，止盈目标不宜过高。",
                "rsi_period": "RSI 周期：用于过滤信号的相对强弱指标周期。",
                "rsi_oversold": "RSI 超卖阈值：只有当 RSI 低于此值时，才在布林下轨做多。数值越低，过滤越严格。",
                "rsi_overbought": "RSI 超买阈值：只有当 RSI 高于此值时，才在布林上轨做空。数值越高，过滤越严格。",
            },
        },
        "turtle": {
            "name": "海龟趋势跟踪",
            "category": "trend",
            "type": "single",
            "description": (
                "源自传奇交易员理查德·丹尼斯的经典趋势跟踪系统。"
                "核心思想：等待价格创出 N 日新高/新低，确认趋势方向后顺势入场，"
                "用 ATR（N 倍平均真实波幅）计算止损位，趋势持续则每隔一段加仓，"
                "反向突破时平仓。"
                "海龟策略在趋势行情中表现优异，能长期持有趋势；但在震荡行情中会反复止损。"
                "这是唯一一个支持【加仓】的策略，通过分批建仓降低单次入场风险。"
            ),
            "params": {
                "entry_period": 20,
                "exit_period": 10,
                "atr_period": 20,
                "atr_multiplier": 2.0,
                "max_units": 4,
                "unit_size_pct": 0.02,
            },
            "param_ranges": {
                "entry_period": [15, 20, 30, 55],
                "exit_period": [5, 10, 20],
                "atr_period": [14, 20, 30],
                "atr_multiplier": [1.5, 2.0, 2.5, 3.0],
                "max_units": [1, 2, 4, 6],
            },
            "param_descriptions": {
                "entry_period": "入场周期：价格突破此周期内的最高价做多，跌破最低价做空。周期越长，趋势确认越慢但越可靠。",
                "exit_period": "出场周期：价格反向突破此周期内的高/低价时平仓。周期越短，持仓时间越短，止损越频繁。",
                "atr_period": "ATR 周期：计算平均真实波幅的周期。ATR 反映市场波动程度，ATR 越大止损越宽。",
                "atr_multiplier": "ATR 倍数：止损距离 = ATR × 此倍数。倍数越大，每次亏损越大，但持仓更稳定。",
                "max_units": "最大加仓数：顺势加仓的最大次数。加仓越多，总仓位越大，但风险也越高。",
                "unit_size_pct": "单笔仓位比：每次入场（每个单位）占总资金的比例。配合 max_units 控制总仓位上限。",
            },
        },
        "portfolio": {
            "name": "多策略组合",
            "category": "composite",
            "type": "composite",
            "description": (
                "将资金按权重分配给多个子策略并行运行，实现策略层面的分散投资。"
                "例如 50% 资金运行均线策略，50% 运行 MACD 策略。"
                "不同策略在不同时刻表现不同，组合后可以降低单一策略失效的风险，"
                "让整体收益曲线更平滑。子策略之间的相关性越低，组合效果越好。"
            ),
            "params": {
                "strategies": [
                    {"name": "ma_cross", "params": {}, "weight": 0.5},
                    {"name": "macd", "params": {}, "weight": 0.5},
                ],
                "rebalance_period": 24,
            },
            "param_descriptions": {
                "strategies": "子策略列表：每个子策略的 name、params 和资金权重（weight）。",
                "rebalance_period": "再平衡周期：每隔多少根 K 线重新评估各策略的盈亏并调整资金分配。",
            },
        },
        "ensemble": {
            "name": "集成投票策略",
            "category": "composite",
            "type": "composite",
            "description": (
                "让多个策略同时运行，每个策略独立给出做多/做空/观望的判断，"
                "最终根据投票结果（多数票、权重票等）决定是否下单。"
                "例如均线策略说做多，MACD 策略说观望，突破策略说做多，则做多。"
                "集成策略通过综合多个视角，降低单个策略误判的影响，"
                "特别适合在市场状态不明确时减少错误交易。"
            ),
            "params": {
                "strategies": ["ma_cross", "macd", "breakout"],
                "strategy_params": {},
                "voting_mode": "majority",
                "threshold": 0.5,
            },
            "param_descriptions": {
                "strategies": "参与的策略名称列表。策略越多，投票结果越稳健，但计算量越大。",
                "strategy_params": "各策略的独立参数配置。如为空则使用各策略默认参数。",
                "voting_mode": "投票模式：majority（多数票胜）/ unanimity（全票通过）/ weighted（按历史表现加权）。",
                "threshold": "信号阈值：只有当投票支持率超过此阈值才开仓。阈值越高，信号越严格，开仓越少。",
            },
        },
        "sector_rotation": {
            "name": "板块轮动策略",
            "category": "composite",
            "type": "composite",
            "description": (
                "根据市场当前状态（趋势/震荡）自动选择最适合的策略运行。"
                "当市场呈现明显趋势时，切换到趋势跟踪策略（均线交叉）；"
                "当市场处于震荡盘整时，切换到均值回归策略（RSI 类）。"
                "通过 ADX 指标判断市场状态：ADX 高说明趋势强，ADX 低说明震荡。"
                "这是一种【聪明的】策略，能适应不同市场环境，但状态切换本身也有滞后风险。"
            ),
            "params": {
                "trend_strategy": {"name": "ma_cross", "params": {}},
                "mean_reversion_strategy": {"name": "rsi", "params": {}},
                "adx_period": 14,
            },
            "param_descriptions": {
                "trend_strategy": "趋势策略配置：市场有明显趋势时使用。",
                "mean_reversion_strategy": "均值回归策略配置：市场震荡时使用。",
                "adx_period": "ADX 周期：用于判断市场趋势强度的指标周期。",
            },
        },
    }
    return {"strategies": strategies}


# ============================================================
# 内部辅助函数
# ============================================================

def _to_native(val):
    """将 numpy/float 类型转为原生 Python 类型，带溢出保护"""
    import numpy as np
    import math
    if val is None:
        return None
    if isinstance(val, (np.integer,)):
        val = int(val)
    elif isinstance(val, (np.floating,)):
        val = float(val)
    # 检查并修正溢出/NaN
    try:
        if math.isnan(val) or math.isinf(val):
            val = None
        elif val > 1e10:   # decimal(10,4) 最大约 10000
            val = 9999.9999
        elif val < -1e10:
            val = -9999.9999
    except (TypeError, ValueError):
        val = None
    return val


def _clamp_for_decimal(val):
    """确保值在 decimal(10,4) 范围内（小数转百分比时如 1016.0 会超限）"""
    if val is None:
        return None
    # 小数形式（如 0.05）没问题，百分数形式（如 5.0）也没问题
    # 但总收益率可能出现 >9999 的情况，直接 clamp
    if val > 9999.9999:
        return 9999.9999
    if val < -9999.9999:
        return -9999.9999
    return val


def _save_backtest_run(
    db: Session,
    strategy_name: str,
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
    initial_capital: float,
    report: Dict[str, Any],
    params: Dict[str, Any],
    user_id: Optional[int] = None,
) -> int:
    """保存回测结果到数据库，返回记录 ID（对齐实际表结构）"""
    import json as _json
    
    def _to_ms(dt):
        return int(dt.timestamp() * 1000) if dt else 0
    
    run = BacktestRun(
        user_id=user_id,
        name=strategy_name,
        start_time=_to_ms(start_date),
        end_time=_to_ms(end_date),
        symbols=_json.dumps([symbol]),
        initial_capital=_to_native(initial_capital),
        final_capital=_to_native(report.get("final_capital")),
        total_return=_clamp_for_decimal(_to_native(report.get("total_return"))),
        annual_return=_clamp_for_decimal(_to_native(report.get("annual_return"))),
        sharpe_ratio=_to_native(report.get("sharpe_ratio")),
        max_drawdown=_clamp_for_decimal(_to_native(report.get("max_drawdown"))),
        total_trades=report.get("total_trades"),
        winning_trades=report.get("winning_trades"),
        losing_trades=report.get("losing_trades"),
        win_rate=_clamp_for_decimal(_to_native(report.get("win_rate"))),
        profit_factor=_to_native(report.get("profit_factor")),
        params=params,
        status="completed",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run.id


def _build_comparison_table(items: List[Dict], metrics: List[str]) -> Dict[str, Any]:
    """构建对比表格，找最优指标"""
    rows = []
    for item in items:
        row = {"id": item["id"], "strategy": f"{item['strategy_name']} {item['symbol']}"}
        for m in metrics:
            val = item["metrics"].get(m)
            if val is not None:
                if m in ("total_return", "max_drawdown", "win_rate"):
                    row[m] = f"{float(val):.2%}"
                elif m in ("sharpe_ratio", "profit_factor"):
                    row[m] = f"{float(val):.2f}"
                elif m in ("total_trades", "winning_trades", "losing_trades"):
                    row[m] = str(int(val))
                else:
                    row[m] = f"{float(val):,.2f}"
            else:
                row[m] = "-"
        rows.append(row)
    
    # 标记最优值
    best = {}
    for m in metrics:
        vals = []
        for item in items:
            v = item["metrics"].get(m)
            if v is not None:
                vals.append((item["id"], v))
        if not vals:
            continue
        if m == "max_drawdown":
            best[m] = min(vals, key=lambda x: x[1])[0]
        else:
            best[m] = max(vals, key=lambda x: x[1])[0]
    
    for row in rows:
        row["best"] = {m: (row.get(m, "-") != "-" and row["id"] == best.get(m)) for m in metrics if best.get(m)}
    
    return {"columns": ["id", "strategy"] + metrics, "rows": rows, "best": best}


def _parse_timestamp(ts: Optional[int]) -> Optional[datetime]:
    """将毫秒时间戳转为 datetime"""
    if not ts:
        return None
    return datetime.fromtimestamp(ts / 1000)


# ============================================================
# 数据加载（与原有逻辑相同）
# ============================================================

_TIMEFRAME_MINUTES = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360, "8h": 480,
    "12h": 720, "1d": 1440, "3d": 4320, "1w": 10080,
}

_RESAMPLE_FREQ = {
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min", "30m": "30min",
    "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "8h": "8h",
    "12h": "12h", "1d": "1D", "3d": "3D", "1w": "1W",
}


def _read_klines_file(symbol: str, timeframe: str) -> pd.DataFrame:
    """从本地 JSON 文件读取 K 线数据"""
    import json, os
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if '/' not in symbol and len(symbol) >= 6:
        symbol = f"{symbol[:-4]}/{symbol[-4:]}" if symbol.endswith('USDT') else f"{symbol[:3]}/{symbol[3:]}"
    file_path = os.path.join(base_dir, "data", "klines", symbol, f"{timeframe}.json")
    if not os.path.exists(file_path):
        return pd.DataFrame()
    with open(file_path, 'r') as f:
        klines = json.load(f)
    if not klines:
        return pd.DataFrame()
    df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df.set_index('timestamp', inplace=True)
    df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    df['symbol'] = symbol
    return df


def _resample_from_5m(df5m: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
    """从 5m 数据合成目标周期"""
    freq = _RESAMPLE_FREQ.get(target_timeframe)
    if not freq:
        raise ValueError(f"不支持的目标周期：{target_timeframe}")
    ohlc = df5m.resample(freq).agg({
        'open':   'first',
        'high':   'max',
        'low':    'min',
        'close':  'last',
        'volume': 'sum',
    }).dropna()
    ohlc['symbol'] = df5m['symbol'].iloc[0] if len(df5m) > 0 else ''
    return ohlc


async def _load_data(
    symbol: str,
    timeframe: str,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
) -> pd.DataFrame:
    """
    加载 K 线数据
    
    优先级:
    1. 数据库 (kline_storage) — 主数据源
    2. 本地 JSON 文件 — 兼容旧数据
    3. 从 5m 数据合成目标周期
    4. 模拟数据 (最后手段, 在 DataFrame 中标记 _data_source)
    """
    from datetime import timezone as tz
    
    # --- 1. 优先从数据库读取 ---
    try:
        from data.persistence.kline_storage import get_kline_storage
        storage = get_kline_storage()
        
        # 标准化 symbol (BTCUSDT / BTC/USDT → BTCUSDT)
        stor_symbol = symbol.replace("/", "")
        
        start_dt = datetime.fromtimestamp(start_time / 1000, tz=tz.utc).replace(tzinfo=None) if start_time else None
        end_dt = datetime.fromtimestamp(end_time / 1000, tz=tz.utc).replace(tzinfo=None) if end_time else None
        
        df = storage.get_klines(
            symbol=stor_symbol,
            timeframe=timeframe,
            start_time=start_dt,
            end_time=end_dt,
            limit=50000,  # 回测允许更多数据
        )
        
        if not df.empty:
            df['symbol'] = symbol
            df.attrs['_data_source'] = 'database'
            logger.info(f"📊 从数据库加载 {symbol} {timeframe}: {len(df)} 条")
            return df
    except Exception as e:
        logger.debug(f"数据库加载失败 (尝试文件): {e}")
    
    # --- 2. 尝试本地 JSON 文件 ---
    df = _read_klines_file(symbol, timeframe)

    if df.empty:
        tf_mins = _TIMEFRAME_MINUTES.get(timeframe, 0)
        base_mins = _TIMEFRAME_MINUTES.get("5m", 5)
        if tf_mins > base_mins and tf_mins % base_mins == 0:
            logger.info(f"本地无 {timeframe} 数据，尝试从 5m 合成...")
            df5m = _read_klines_file(symbol, "5m")
            if not df5m.empty:
                df = _resample_from_5m(df5m, timeframe)
                df.attrs['_data_source'] = 'resampled_5m'
                logger.info(f"✅ 从 5m 合成 {timeframe} 数据 {len(df)} 条")
            else:
                logger.warning(f"⚠️ {symbol} {timeframe} 无真实数据，使用模拟数据")
                mock_df = _generate_mock_data(symbol, timeframe)
                mock_df.attrs['_data_source'] = 'mock'
                return mock_df
        else:
            logger.warning(f"⚠️ {symbol} {timeframe} 无真实数据，使用模拟数据")
            mock_df = _generate_mock_data(symbol, timeframe)
            mock_df.attrs['_data_source'] = 'mock'
            return mock_df
    else:
        df.attrs['_data_source'] = 'json_file'

    if start_time:
        start_dt_pd = pd.Timestamp(start_time, unit='ms', tz='UTC')
        df = df[df.index >= start_dt_pd]
    if end_time:
        end_dt_pd = pd.Timestamp(end_time, unit='ms', tz='UTC')
        df = df[df.index <= end_dt_pd]

    return df


def _generate_mock_data(symbol: str, timeframe: str) -> pd.DataFrame:
    """生成模拟数据"""
    import numpy as np
    
    n_bars = 1000
    freq_map = {
        "1m": "min", "5m": "5min", "15m": "15min",
        "1h": "h", "4h": "4h", "1d": "D",
    }
    freq = freq_map.get(timeframe, "h")
    dates = pd.date_range(start="2025-01-01", periods=n_bars, freq=freq)
    
    np.random.seed(42)
    returns = np.random.randn(n_bars) * 0.02
    close = 100 * np.cumprod(1 + returns)
    
    return pd.DataFrame({
        "timestamp": dates,
        "open": close * (1 + np.random.randn(n_bars) * 0.001),
        "high": close * (1 + np.abs(np.random.randn(n_bars)) * 0.005),
        "low": close * (1 - np.abs(np.random.randn(n_bars)) * 0.005),
        "close": close,
        "volume": np.random.rand(n_bars) * 1000000,
        "symbol": symbol,
    })


def _create_strategy(strategy_name: str, params: Dict[str, Any]) -> Strategy:
    """创建策略实例"""
    strategy_class = _get_strategy_class(strategy_name)
    return strategy_class(params)


def _get_strategy_class(strategy_name: str) -> type:
    """获取策略类 - 统一使用策略注册表"""
    strategy_class = registry_get_strategy(strategy_name)
    if strategy_class:
        return strategy_class
    
    # 注册表中未找到，报错并列出可用策略
    available = sorted(registry.list_all().keys())
    raise ValueError(
        f"不支持的策略: {strategy_name}。"
        f"可用策略 ({len(available)} 个): {available}"
    )
