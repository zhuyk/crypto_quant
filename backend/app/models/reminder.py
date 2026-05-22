"""
日历提醒模型 - SQLAlchemy 2.0 类型标注风格
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, Dict, List, TYPE_CHECKING

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, JSON, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Reminder(Base):
    """日历提醒表"""
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 提醒时间
    remind_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # 类型: price_alert / funding_rate / rebalance / custom / expiry / report
    reminder_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="custom", index=True
    )

    # 优先级: low / medium / high / critical
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")

    # 重复规则: none / daily / weekly / monthly / custom_cron
    repeat_rule: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    repeat_cron: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # 关联数据 (JSON)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # 通知方式
    notify_channels: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    trigger_count: Mapped[int] = mapped_column(Integer, default=0)

    # 时间戳
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # 关系
    user: Mapped["User"] = relationship(backref="reminders")

    def __repr__(self) -> str:
        return f"<Reminder(id={self.id}, title={self.title}, remind_at={self.remind_at})>"

    def to_dict(self) -> Dict[str, Any]:
        """转为 API 响应字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "remind_at": self.remind_at.isoformat() if self.remind_at else None,
            "reminder_type": self.reminder_type,
            "priority": self.priority,
            "repeat_rule": self.repeat_rule,
            "repeat_cron": self.repeat_cron,
            "metadata": self.metadata_json,
            "notify_channels": self.notify_channels,
            "is_active": self.is_active,
            "is_triggered": self.is_triggered,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "trigger_count": self.trigger_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
