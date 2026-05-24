"""
统一类型定义 - 共享枚举和转换工具

解决 engine/trader/core.py 和 strategies/base.py 类型不兼容的问题。

策略层使用:
- SignalSide (LONG/SHORT/CLOSE)
- Signal, Position (quantity)

交易层使用:
- OrderSide (BUY/SELL)
- Order, Position (amount)

本模块提供两者之间的映射和转换。
"""
from __future__ import annotations

from enum import Enum
from typing import Optional


# ============================================================
# 方向映射
# ============================================================

class TradeSide(Enum):
    """统一交易方向（兼容策略和交易两层）"""
    LONG = "long"       # 做多 (策略层 SignalSide.LONG, 交易层 OrderSide.BUY)
    SHORT = "short"     # 做空 (策略层 SignalSide.SHORT, 交易层 OrderSide.SELL)
    CLOSE = "close"     # 平仓 (仅策略层使用)


def signal_side_to_order_side(signal_side) -> str:
    """
    策略信号方向 → 交易订单方向

    SignalSide.LONG  → "buy"
    SignalSide.SHORT → "sell"
    SignalSide.CLOSE → (需要根据持仓方向确定)
    """
    val = signal_side.value if hasattr(signal_side, "value") else str(signal_side)
    mapping = {
        "long": "buy",
        "short": "sell",
    }
    return mapping.get(val, val)


def order_side_to_signal_side(order_side) -> str:
    """
    交易订单方向 → 策略信号方向

    OrderSide.BUY  → "long"
    OrderSide.SELL → "short"
    """
    val = order_side.value if hasattr(order_side, "value") else str(order_side)
    mapping = {
        "buy": "long",
        "sell": "short",
    }
    return mapping.get(val, val)


# ============================================================
# Position 转换
# ============================================================

def strategy_position_to_trader_position(strategy_pos) -> dict:
    """
    strategies.base.Position → engine.trader.core.TraderPosition 格式的字典

    策略层 Position (规范类型):
        symbol, side (SignalSide), quantity, entry_price, current_price, stop_loss, take_profit

    交易层 TraderPosition (引擎内部):
        symbol, side (OrderSide), amount, entry_price, current_price, stop_loss, take_profit, ...
    """
    return {
        "symbol": strategy_pos.symbol,
        "side": signal_side_to_order_side(strategy_pos.side),
        "amount": strategy_pos.quantity,
        "entry_price": strategy_pos.entry_price,
        "current_price": strategy_pos.current_price,
        "stop_loss": strategy_pos.stop_loss,
        "take_profit": strategy_pos.take_profit,
        "unrealized_pnl": strategy_pos.unrealized_pnl,
        "unrealized_pnl_pct": strategy_pos.unrealized_pnl_pct * 100,  # 转为百分比
    }


def trader_position_to_strategy_position(trader_pos) -> dict:
    """
    engine.trader.core.TraderPosition → strategies.base.Position 格式的字典

    交易层 TraderPosition → 策略层 Position
    """
    return {
        "symbol": trader_pos.symbol,
        "side": order_side_to_signal_side(trader_pos.side),
        "quantity": trader_pos.amount,
        "entry_price": trader_pos.entry_price,
        "current_price": trader_pos.current_price,
        "stop_loss": trader_pos.stop_loss,
        "take_profit": trader_pos.take_profit,
    }


def convert_signal_to_order_params(signal) -> dict:
    """
    将策略 Signal 转换为交易引擎 create_order 的参数

    Args:
        signal: strategies.base.Signal 实例

    Returns:
        dict: 可直接传给 TradingEngine.create_order 的参数
    """
    side_str = signal_side_to_order_side(signal.side)

    return {
        "symbol": signal.symbol,
        "side": side_str,
        "order_type": "market",
        "price": signal.price if signal.price > 0 else None,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
    }
