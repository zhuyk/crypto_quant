"""
用户模型
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True)
    password_hash = Column(String(256))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    strategy_instances = relationship("StrategyInstance", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"


class Account(Base):
    """交易所账户表"""
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    exchange = Column(String(32), nullable=False, default="binance")
    api_key = Column(String(256), nullable=False)
    api_secret = Column(String(256), nullable=False)
    passphrase = Column(String(256))
    is_testnet = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    user = relationship("User", back_populates="accounts")
    
    def __repr__(self):
        return f"<Account(id={self.id}, user_id={self.user_id}, exchange={self.exchange})>"
