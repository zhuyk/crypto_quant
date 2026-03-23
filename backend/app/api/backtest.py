"""
回测 API 路由

支持:
- 单策略回测
- 多策略组合回测
- 参数优化
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import pandas as pd
import logging

from strategies.base import Strategy
from strategies.trend.ma_cross import MACrossStrategy
from strategies.composite import PortfolioStrategy, EnsembleStrategy, SectorRotationStrategy
from engine.backtester import Backtester, ParameterOptimizer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["回测"])


class BacktestRequest(BaseModel):
    """回测请求"""
    strategy_name: str = Field(..., description="策略名称")
    symbol: str = Field("BTCUSDT", description="交易对")
    timeframe: str = Field("1h", description="时间周期")
    params: Dict[str, Any] = Field(default_factory=dict, description="策略参数")
    initial_capital: float = Field(100000.0, description="初始资金")
    start_time: Optional[int] = Field(None, description="开始时间 (时间戳)")
    end_time: Optional[int] = Field(None, description="结束时间 (时间戳)")


class BacktestResponse(BaseModel):
    """回测响应"""
    success: bool
    report: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class OptimizeRequest(BaseModel):
    """参数优化请求"""
    strategy_name: str = Field(..., description="策略名称")
    symbol: str = Field("BTCUSDT", description="交易对")
    timeframe: str = Field("1h", description="时间周期")
    param_ranges: Dict[str, List[Any]] = Field(..., description="参数范围")
    method: str = Field("grid_search", description="优化方法：grid_search, random_search, genetic")
    iterations: int = Field(100, description="迭代次数")


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest):
    """
    执行回测
    
    支持策略：
    - ma_cross: 双均线交叉
    - breakout: 通道突破
    - macd: MACD 趋势
    """
    try:
        # 获取数据
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
        )
        
        # 执行回测
        report = backtester.run(strategy, data)
        
        return BacktestResponse(
            success=True,
            report=report.to_dict(),
        )
        
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
        # 获取数据
        data = await _load_data(request.symbol, request.timeframe)
        
        if data.empty:
            raise HTTPException(status_code=404, detail="未找到数据")
        
        # 创建策略类
        strategy_class = _get_strategy_class(request.strategy_name)
        
        # 创建回测引擎
        backtester = Backtester(initial_capital=100000.0)
        
        # 创建优化器
        optimizer = ParameterOptimizer(
            backtester=backtester,
            data=data,
            strategy_class=strategy_class,
            metric="sharpe_ratio",
        )
        
        # 执行优化
        if request.method == "grid_search":
            results = optimizer.grid_search(request.param_ranges)
        elif request.method == "random_search":
            results = optimizer.random_search(request.param_ranges, request.iterations)
        elif request.method == "genetic":
            results = optimizer.genetic_algorithm(request.param_ranges, population_size=request.iterations//5)
        else:
            raise ValueError(f"不支持的优化方法：{request.method}")
        
        # 返回最佳结果
        best_result = results[0] if results else None
        
        return {
            "success": True,
            "best_params": best_result["params"] if best_result else None,
            "best_metric": best_result["metric_value"] if best_result else None,
            "total_combinations": len(results),
            "top_10": [
                {"params": r["params"], "metric": r["metric_value"]}
                for r in results[:10]
            ],
        }
        
    except Exception as e:
        logger.exception("参数优化失败")
        raise HTTPException(status_code=500, detail=str(e))


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


@router.post("/portfolio/run")
async def run_portfolio_backtest(request: PortfolioBacktestRequest):
    """
    执行多策略组合回测
    
    支持:
    - 资金分散配置
    - 策略间风险隔离
    - 组合表现分析
    """
    try:
        # 获取数据
        data = await _load_data(request.symbol, request.timeframe)
        
        if data.empty:
            raise HTTPException(status_code=404, detail="未找到数据")
        
        # 创建组合策略
        portfolio_params = {
            "strategies": request.strategies,
            "rebalance_period": 24,
        }
        portfolio = PortfolioStrategy(portfolio_params)
        
        # 创建回测引擎
        backtester = Backtester(
            initial_capital=request.initial_capital,
            commission_rate=0.001,
            slippage=0.0005,
        )
        
        # 执行回测
        report = backtester.run(portfolio, data)
        
        # 添加组合分解信息
        report_dict = report.to_dict()
        report_dict["portfolio_breakdown"] = portfolio.get_performance_breakdown()
        
        return {
            "success": True,
            "report": report_dict,
            "type": "portfolio",
        }
        
    except Exception as e:
        logger.exception("组合回测执行失败")
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/ensemble/run", response_model=BacktestResponse)
async def run_ensemble_backtest(request: EnsembleBacktestRequest):
    """
    执行集成策略回测
    
    多个策略投票决定交易信号，降低误判率
    """
    try:
        # 获取数据
        data = await _load_data(request.symbol, request.timeframe)
        
        if data.empty:
            raise HTTPException(status_code=404, detail="未找到数据")
        
        # 创建集成策略
        ensemble_params = {
            "strategies": request.strategies,
            "strategy_params": request.strategy_params,
            "voting_mode": request.voting_mode,
            "threshold": request.threshold,
            "min_strength": 0.3,
        }
        ensemble = EnsembleStrategy(ensemble_params)
        
        # 创建回测引擎
        backtester = Backtester(initial_capital=request.initial_capital)
        
        # 执行回测
        report = backtester.run(ensemble, data)
        
        return BacktestResponse(
            success=True,
            report=report.to_dict(),
        )
        
    except Exception as e:
        logger.exception("集成回测执行失败")
        return BacktestResponse(
            success=False,
            error=str(e),
        )


@router.get("/strategies")
async def list_strategies():
    """获取可用策略列表"""
    strategies = {
        # 单一策略
        "ma_cross": {
            "name": "双均线交叉",
            "category": "trend",
            "type": "single",
            "params": {
                "fast_period": 20,
                "slow_period": 60,
                "stop_loss_pct": 0.05,
                "take_profit_pct": 0.15,
            },
        },
        "breakout": {
            "name": "通道突破",
            "category": "trend",
            "type": "single",
            "params": {
                "lookback_period": 20,
                "stop_loss_pct": 0.08,
            },
        },
        "macd": {
            "name": "MACD 趋势",
            "category": "trend",
            "type": "single",
            "params": {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
            },
        },
        # 组合策略
        "portfolio": {
            "name": "多策略组合",
            "category": "composite",
            "type": "composite",
            "description": "将资金按权重分配给多个子策略并行运行",
            "params": {
                "strategies": [
                    {"name": "ma_cross", "params": {}, "weight": 0.5},
                    {"name": "macd", "params": {}, "weight": 0.5},
                ],
                "rebalance_period": 24,
                "max_position_per_strategy": 0.3,
            },
        },
        "ensemble": {
            "name": "集成投票策略",
            "category": "composite",
            "type": "composite",
            "description": "多个策略投票决定交易信号，降低误判率",
            "params": {
                "strategies": ["ma_cross", "macd", "breakout"],
                "strategy_params": {},
                "voting_mode": "majority",  # majority, unanimity, weighted, confidence
                "threshold": 0.5,
                "min_strength": 0.3,
            },
        },
        "sector_rotation": {
            "name": "板块轮动策略",
            "category": "composite",
            "type": "composite",
            "description": "根据市场状态 (趋势/震荡) 自动切换最适合的策略",
            "params": {
                "trend_strategy": {"name": "ma_cross", "params": {}},
                "mean_reversion_strategy": {"name": "rsi", "params": {}},
                "adx_period": 14,
                "trend_threshold": 25,
                "reversion_threshold": 20,
            },
        },
    }
    return {"strategies": strategies}


async def _load_data(
    symbol: str,
    timeframe: str,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
) -> pd.DataFrame:
    """加载 K 线数据"""
    # TODO: 从数据库加载数据
    # 这里先返回模拟数据用于测试
    return _generate_mock_data(symbol, timeframe)


def _generate_mock_data(symbol: str, timeframe: str) -> pd.DataFrame:
    """生成模拟数据 (用于测试)"""
    import numpy as np
    
    n_bars = 1000
    dates = pd.date_range(start="2025-01-01", periods=n_bars, freq="H")
    
    # 随机游走生成价格
    np.random.seed(42)
    returns = np.random.randn(n_bars) * 0.02
    close = 100 * np.cumprod(1 + returns)
    
    # 生成 OHLC
    data = pd.DataFrame({
        "timestamp": dates,
        "open": close * (1 + np.random.randn(n_bars) * 0.001),
        "high": close * (1 + np.abs(np.random.randn(n_bars)) * 0.005),
        "low": close * (1 - np.abs(np.random.randn(n_bars)) * 0.005),
        "close": close,
        "volume": np.random.rand(n_bars) * 1000000,
        "symbol": symbol,
    })
    
    return data


def _create_strategy(strategy_name: str, params: Dict[str, Any]) -> Strategy:
    """创建策略实例"""
    strategy_class = _get_strategy_class(strategy_name)
    return strategy_class(params)


def _get_strategy_class(strategy_name: str) -> type:
    """获取策略类"""
    strategies = {
        # 单一策略
        "ma_cross": MACrossStrategy,
        # TODO: 添加更多单一策略
        # 组合策略
        "portfolio": PortfolioStrategy,
        "ensemble": EnsembleStrategy,
        "sector_rotation": SectorRotationStrategy,
    }
    
    if strategy_name not in strategies:
        raise ValueError(f"不支持的策略：{strategy_name}")
    
    return strategies[strategy_name]
