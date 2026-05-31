"""
交易相关模型 - SQLAlchemy 2.0 类型标注风格

包含:
- Strategy: 策略定义
- StrategyInstance: 策略实例（用户绑定）
- BacktestRun: 回测记录
- Trade: 交易记录
- Position: 持仓
- Kline: K 线数据
"""
from __future__ import annotations

import json as _json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Any, Dict, List, TYPE_CHECKING

from sqlalchemy import (
    String, Float, Boolean, DateTime, ForeignKey, Text, JSON,
    BigInteger, Numeric, Integer, Index, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Strategy(Base):
    """策略定义表"""
    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    class_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Strategy(id={self.id}, name={self.name})>"


class StrategyInstance(Base):
    """策略实例表"""
    __tablename__ = "strategy_instances"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    strategy_id: Mapped[int] = mapped_column(
        ForeignKey("strategies.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    params: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # 关系
    user: Mapped["User"] = relationship(back_populates="strategy_instances")
    strategy: Mapped["Strategy"] = relationship()

    def __repr__(self) -> str:
        return f"<StrategyInstance(id={self.id}, name={self.name})>"


class BacktestRun(Base):
    """回测运行记录表"""
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    strategy_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    start_time: Mapped[int] = mapped_column(BigInteger, nullable=False)
    end_time: Mapped[int] = mapped_column(BigInteger, nullable=False)
    initial_capital: Mapped[Decimal] = mapped_column(
        Numeric(32, 16), nullable=False, default=100000
    )
    final_capital: Mapped[Optional[Decimal]] = mapped_column(Numeric(32, 16), nullable=True)
    total_return: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    annual_return: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    sharpe_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    sortino_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    max_drawdown: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    win_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    profit_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    total_trades: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    winning_trades: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    losing_trades: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    avg_win: Mapped[Optional[Decimal]] = mapped_column(Numeric(32, 16), nullable=True)
    avg_loss: Mapped[Optional[Decimal]] = mapped_column(Numeric(32, 16), nullable=True)
    params: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    symbols: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    equity_curve_path: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())

    # ==================== 便捷属性 ====================

    @property
    def strategy_name(self) -> str:
        """策略名称（name 列的别名）"""
        return self.name

    @property
    def start_date(self) -> Optional[datetime]:
        """开始时间（从毫秒时间戳转换）"""
        if self.start_time:
            return datetime.fromtimestamp(self.start_time / 1000, tz=timezone.utc)
        return None

    @property
    def end_date(self) -> Optional[datetime]:
        """结束时间（从毫秒时间戳转换）"""
        if self.end_time:
            return datetime.fromtimestamp(self.end_time / 1000, tz=timezone.utc)
        return None

    @property
    def symbol(self) -> str:
        """主交易对（symbols JSON 列表的第一个元素）"""
        if self.symbols:
            try:
                data = _json.loads(self.symbols) if isinstance(self.symbols, str) else self.symbols
                return data[0] if data else ""
            except (ValueError, IndexError, TypeError):
                return ""
        return ""

    @property
    def timeframe(self) -> str:
        """时间周期（表中无此列，返回空）"""
        return ""

    def __repr__(self) -> str:
        return f"<BacktestRun(id={self.id}, name={self.name}, status={self.status})>"


class Trade(Base):
    """交易记录表"""
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    strategy_instance_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("strategy_instances.id"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(16), nullable=False)  # buy/sell
    type: Mapped[str] = mapped_column(String(32), default="market")  # market/limit
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    filled_amount: Mapped[float] = mapped_column(Float, default=0.0)
    filled_price: Mapped[float] = mapped_column(Float, default=0.0)
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    fee_currency: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    order_id: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    pnl: Mapped[float] = mapped_column(Float, default=0.0)
    pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 关系
    strategy_instance: Mapped[Optional["StrategyInstance"]] = relationship()

    def __repr__(self) -> str:
        return f"<Trade(id={self.id}, symbol={self.symbol}, side={self.side}, status={self.status})>"


class Position(Base):
    """持仓表"""
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    strategy_instance_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("strategy_instances.id"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(16), nullable=False)  # long/short
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[float] = mapped_column(Float, default=0.0)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 关系
    strategy_instance: Mapped[Optional["StrategyInstance"]] = relationship()

    @property
    def unrealized_pnl_pct(self) -> float:
        """未实现盈亏百分比"""
        if self.entry_price and self.entry_price != 0:
            if self.side == "long":
                return (self.current_price - self.entry_price) / self.entry_price
            else:
                return (self.entry_price - self.current_price) / self.entry_price
        return 0.0

    def __repr__(self) -> str:
        return f"<Position(id={self.id}, symbol={self.symbol}, side={self.side}, active={self.is_active})>"


class Kline(Base):
    """K 线数据表"""
    __tablename__ = "klines"
    __table_args__ = (
        Index("ix_kline_composite", "exchange", "symbol", "timeframe", "timestamp", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:
        return f"<Kline({self.symbol} {self.timeframe} {self.timestamp})>"

    def to_dict(self) -> Dict[str, Any]:
        """转为字典"""
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }
