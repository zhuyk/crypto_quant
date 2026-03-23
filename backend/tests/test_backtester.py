#!/usr/bin/env python3
"""
回测引擎测试脚本
"""
import sys
import pandas as pd
import numpy as np
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategies.trend.ma_cross import MACrossStrategy
from strategies.trend.breakout import BreakoutStrategy
from strategies.trend.macd import MACDStrategy
from engine.backtester import Backtester


def generate_mock_data(symbol: str = "BTCUSDT", n_bars: int = 1000) -> pd.DataFrame:
    """生成模拟 K 线数据"""
    dates = pd.date_range(start="2025-01-01", periods=n_bars, freq="H")
    
    # 随机游走 + 趋势
    np.random.seed(42)
    trend = np.linspace(0, 0.5, n_bars)  # 50% 上涨趋势
    noise = np.random.randn(n_bars) * 0.02
    returns = trend / n_bars + noise
    close = 100 * np.cumprod(1 + returns)
    
    # 生成 OHLC
    data = pd.DataFrame({
        "timestamp": dates,
        "open": close * (1 + np.random.randn(n_bars) * 0.001),
        "high": close * (1 + np.abs(np.random.randn(n_bars)) * 0.005),
        "low": close * (1 - np.abs(np.random.randn(n_bars)) * 0.005),
        "close": close,
        "volume": np.random.rand(n_bars) * 1000000 + 500000,
        "symbol": symbol,
    })
    
    return data


def test_ma_cross():
    """测试双均线策略"""
    print("\n" + "="*60)
    print("测试：双均线交叉策略 (MA Cross)")
    print("="*60)
    
    # 生成数据
    data = generate_mock_data()
    
    # 创建策略
    strategy = MACrossStrategy(params={
        "fast_period": 20,
        "slow_period": 60,
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.15,
    })
    
    # 创建回测引擎
    backtester = Backtester(
        initial_capital=100000,
        commission_rate=0.001,
        slippage=0.0005,
    )
    
    # 执行回测
    report = backtester.run(strategy, data)
    
    # 打印结果
    report.print_summary()
    
    return report


def test_breakout():
    """测试突破策略"""
    print("\n" + "="*60)
    print("测试：通道突破策略 (Breakout)")
    print("="*60)
    
    data = generate_mock_data()
    
    strategy = BreakoutStrategy(params={
        "lookback_period": 20,
        "stop_loss_pct": 0.08,
        "take_profit_pct": 0.20,
        "use_trailing_stop": True,
        "volume_filter": True,
    })
    
    backtester = Backtester(initial_capital=100000)
    report = backtester.run(strategy, data)
    
    report.print_summary()
    
    return report


def test_macd():
    """测试 MACD 策略"""
    print("\n" + "="*60)
    print("测试：MACD 趋势策略")
    print("="*60)
    
    data = generate_mock_data()
    
    strategy = MACDStrategy(params={
        "fast_period": 12,
        "slow_period": 26,
        "signal_period": 9,
        "stop_loss_pct": 0.06,
        "take_profit_pct": 0.18,
        "use_zero_cross": True,
    })
    
    backtester = Backtester(initial_capital=100000)
    report = backtester.run(strategy, data)
    
    report.print_summary()
    
    return report


def test_parameter_optimization():
    """测试参数优化"""
    print("\n" + "="*60)
    print("测试：参数优化 (网格搜索)")
    print("="*60)
    
    from engine.backtester import ParameterOptimizer
    
    data = generate_mock_data()
    
    backtester = Backtester(initial_capital=100000)
    
    optimizer = ParameterOptimizer(
        backtester=backtester,
        data=data,
        strategy_class=MACrossStrategy,
        metric="sharpe_ratio",
    )
    
    # 网格搜索
    param_grid = {
        "fast_period": [10, 20, 30],
        "slow_period": [50, 60, 70],
        "stop_loss_pct": [0.05, 0.08],
    }
    
    results = optimizer.grid_search(param_grid)
    
    if results:
        best = results[0]
        print(f"\n最佳参数：{best['params']}")
        print(f"最佳夏普比率：{best['metric_value']:.4f}")
        print(f"\n前 3 名结果:")
        for i, r in enumerate(results[:3], 1):
            print(f"  {i}. {r['params']} -> Sharpe: {r['metric_value']:.4f}")
    
    return results


if __name__ == "__main__":
    print("\n🚀 CryptoQuant 回测引擎测试\n")
    
    # 运行测试
    reports = {}
    
    try:
        reports["ma_cross"] = test_ma_cross()
    except Exception as e:
        print(f"MA Cross 测试失败：{e}")
    
    try:
        reports["breakout"] = test_breakout()
    except Exception as e:
        print(f"Breakout 测试失败：{e}")
    
    try:
        reports["macd"] = test_macd()
    except Exception as e:
        print(f"MACD 测试失败：{e}")
    
    try:
        reports["optimization"] = test_parameter_optimization()
    except Exception as e:
        print(f"参数优化测试失败：{e}")
    
    print("\n✅ 测试完成!\n")
