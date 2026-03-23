"""
交易相关模型
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, func, Text, JSON
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
    """回测运行记录表"""
    __tablename__ = "backtest_runs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    strategy_name = Column(String(128), nullable=False)
    symbol = Column(String(32), nullable=False)
    timeframe = Column(String(16), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    initial_capital = Column(Float, nullable=False, default=100000)
    final_capital = Column(Float)
    total_return = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    total_trades = Column(Integer)
    win_rate = Column(Float)
    params = Column(JSON)
    status = Column(String(32), default="pending")  # pending/running/completed/failed
    error_message = Column(Text)
    created_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<BacktestRun(id={self.id}, strategy={self.strategy_name})>"


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
