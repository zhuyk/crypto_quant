"""
策略模块
"""
from .base import Strategy, Signal, SignalSide, SignalType, Position
from .registry import StrategyRegistry

# 导入所有策略
from .trend.ma_cross import MACrossStrategy
from .trend.breakout import BreakoutStrategy
from .trend.macd import MACDStrategy

__all__ = [
    # 基类
    "Strategy",
    "Signal",
    "SignalSide",
    "SignalType",
    "Position",
    # 注册表
    "StrategyRegistry",
    # 趋势策略
    "MACrossStrategy",
    "BreakoutStrategy",
    "MACDStrategy",
]
