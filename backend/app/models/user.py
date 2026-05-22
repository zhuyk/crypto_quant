"""
用户模型 - SQLAlchemy 2.0 类型标注风格
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.trade import StrategyInstance


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # 关系
    accounts: Mapped[List["Account"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    strategy_instances: Mapped[List["StrategyInstance"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"


class Account(Base):
    """交易所账户表"""
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False, default="binance")
    api_key: Mapped[str] = mapped_column(String(256), nullable=False)
    api_secret: Mapped[str] = mapped_column(String(256), nullable=False)
    passphrase: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    is_testnet: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # 关系
    user: Mapped["User"] = relationship(back_populates="accounts")

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, user_id={self.user_id}, exchange={self.exchange})>"
