"""
实盘交易引擎模块
"""
from .core import (
    TradingEngine,
    Order,
    TraderPosition,
    OrderSide,
    OrderType,
    OrderStatus,
)

# 向后兼容: 旧代码 `from engine.trader import Position` 仍可使用
Position = TraderPosition

__all__ = [
    "TradingEngine",
    "Order",
    "TraderPosition",
    "Position",  # 向后兼容别名
    "OrderSide",
    "OrderType",
    "OrderStatus",
]
