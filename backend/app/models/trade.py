"""
交易相关模型
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, func, Text, JSON, BigInteger, Numeric
from sqlalchemy.orm import relationship
from app.core.database import Base


class Strategy(Base):
    """策略定义表"""
    __tablename__ = "strategies"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False, index=True)
    category = Column(String(64), nullable=False, index=True)
    class_name = Column(String(128), nullable=False)
    description = Column(Text)
    default_params = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Strategy(id={self.id}, name={self.name})>"


class StrategyInstance(Base):
    """策略实例表"""
    __tablename__ = "strategy_instances"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    params = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    user = relationship("User", back_populates="strategy_instances")
    strategy = relationship("Strategy")
    
    def __repr__(self):
        return f"<StrategyInstance(id={self.id}, name={self.name})>"


class BacktestRun(Base):
    """回测运行记录表（对齐实际数据库表结构）"""
    __tablename__ = "backtest_runs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    strategy_id = Column(Integer, nullable=True)  # 实际表中的字段
    name = Column(String(128), nullable=False)   # 实际表用 name 而非 strategy_name
    start_time = Column(BigInteger, nullable=False)  # 毫秒时间戳
    end_time = Column(BigInteger, nullable=False)    # 毫秒时间戳
    initial_capital = Column(Numeric(32, 16), nullable=False, default=100000)
    final_capital = Column(Numeric(32, 16))
    total_return = Column(Numeric(10, 4))
    annual_return = Column(Numeric(10, 4))
    sharpe_ratio = Column(Numeric(10, 4))
    sortino_ratio = Column(Numeric(10, 4))
    max_drawdown = Column(Numeric(10, 4))
    win_rate = Column(Numeric(10, 4))
    profit_factor = Column(Numeric(10, 4))
    total_trades = Column(Integer)
    winning_trades = Column(Integer)
    losing_trades = Column(Integer)
    avg_win = Column(Numeric(32, 16))
    avg_loss = Column(Numeric(32, 16))
    params = Column(JSON)
    symbols = Column(JSON)  # 实际表中有此列
    status = Column(String(16), default="pending")
    equity_curve_path = Column(String(256))
    created_at = Column(DateTime, default=func.now())
    
    # 方便访问的别名（兼容新代码）
    @property
    def strategy_name(self) -> str:
        return self.name
    
    @property
    def start_date(self):
        from datetime import datetime, timezone
        return datetime.fromtimestamp(self.start_time / 1000, tz=timezone.utc) if self.start_time else None
    
    @property
    def end_date(self):
        from datetime import datetime, timezone
        return datetime.fromtimestamp(self.end_time / 1000, tz=timezone.utc) if self.end_time else None
    
    @property
    def symbol(self) -> str:
        # symbols 是 JSON 列表，取第一个或返回空
        if self.symbols:
            import json
            if isinstance(self.symbols, str):
                s = json.loads(self.symbols)
            else:
                s = self.symbols
            return s[0] if s else ""
        return ""
    
    @property
    def timeframe(self) -> str:
        return ""  # 实际表中无此列
    
    def __repr__(self):
        return f"<BacktestRun(id={self.id}, name={self.name})>"


class Trade(Base):
    """交易记录表"""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    strategy_instance_id = Column(Integer, ForeignKey("strategy_instances.id"))
    symbol = Column(String(32), nullable=False, index=True)
    side = Column(String(16), nullable=False)  # buy/sell
    type = Column(String(32), default="market")  # market/limit
    amount = Column(Float, nullable=False)
    price = Column(Float)
    filled_amount = Column(Float, default=0)
    filled_price = Column(Float, default=0)
    fee = Column(Float, default=0)
    fee_currency = Column(String(16))
    status = Column(String(32), default="pending")  # pending/filled/cancelled
    order_id = Column(String(128), unique=True)
    pnl = Column(Float, default=0)
    pnl_pct = Column(Float, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    closed_at = Column(DateTime)
    
    # 关系
    strategy_instance = relationship("StrategyInstance")
    
    def __repr__(self):
        return f"<Trade(id={self.id}, symbol={self.symbol}, side={self.side})>"


class Position(Base):
    """持仓表"""
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    strategy_instance_id = Column(Integer, ForeignKey("strategy_instances.id"))
    symbol = Column(String(32), nullable=False, index=True)
    side = Column(String(16), nullable=False)  # buy/sell
    amount = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, default=0)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    unrealized_pnl = Column(Float, default=0)
    realized_pnl = Column(Float, default=0)
    is_active = Column(Boolean, default=True)
    opened_at = Column(DateTime, default=func.now())
    closed_at = Column(DateTime)
    
    # 关系
    strategy_instance = relationship("StrategyInstance")
    
    def __repr__(self):
        return f"<Position(id={self.id}, symbol={self.symbol}, side={self.side})>"


class Kline(Base):
    """K 线数据表"""
    __tablename__ = "klines"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    exchange = Column(String(32), nullable=False, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    timeframe = Column(String(16), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    
    def __repr__(self):
        return f"<Kline(symbol={self.symbol}, timeframe={self.timeframe}, timestamp={self.timestamp})>"
