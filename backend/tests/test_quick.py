#!/usr/bin/env python3
"""
快速测试 - 验证回测引擎
"""
import sys
import pandas as pd
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from strategies.trend.ma_cross import MACrossStrategy
from engine.backtester import Backtester


def generate_mock_data(n_bars: int = 1000) -> pd.DataFrame:
    """生成模拟数据"""
    dates = pd.date_range(start="2025-01-01", periods=n_bars, freq="h")
    
    np.random.seed(42)
    trend = np.linspace(0, 0.5, n_bars)
    noise = np.random.randn(n_bars) * 0.02
    returns = trend / n_bars + noise
    close = 100 * np.cumprod(1 + returns)
    
    return pd.DataFrame({
        "timestamp": dates,
        "open": close * (1 + np.random.randn(n_bars) * 0.001),
        "high": close * (1 + np.abs(np.random.randn(n_bars)) * 0.005),
        "low": close * (1 - np.abs(np.random.randn(n_bars)) * 0.005),
        "close": close,
        "volume": np.random.rand(n_bars) * 1000000 + 500000,
        "symbol": "BTCUSDT",
    })


# 测试
print("🧪 测试回测引擎...\n")

data = generate_mock_data()
strategy = MACrossStrategy(params={
    "fast_period": 20,
    "slow_period": 60,
    "stop_loss_pct": 0.05,
    "take_profit_pct": 0.15,
})

backtester = Backtester(initial_capital=100000)
report = backtester.run(strategy, data)

report.print_summary()

print("✅ 测试通过!\n")
