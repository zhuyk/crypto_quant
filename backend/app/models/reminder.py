"""
日历提醒模型
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, func, Text, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base


class Reminder(Base):
    """日历提醒表"""
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)

    # 提醒时间
    remind_at = Column(DateTime, nullable=False, index=True)

    # 类型: price_alert / funding_rate / rebalance / custom / expiry / report
    reminder_type = Column(String(32), nullable=False, default="custom", index=True)

    # 优先级: low / medium / high / critical
    priority = Column(String(16), nullable=False, default="medium")

    # 重复规则: none / daily / weekly / monthly / custom_cron
    repeat_rule = Column(String(32), nullable=False, default="none")
    repeat_cron = Column(String(64), nullable=True)  # 自定义 cron 表达式

    # 关联数据 (JSON): 如 {symbol: "BTCUSDT", target_price: 70000, condition: "above"}
    metadata_json = Column(JSON, nullable=True)

    # 通知方式: ["app", "email", "dingtalk"]
    notify_channels = Column(JSON, nullable=True, default=["app"])

    # 状态
    is_active = Column(Boolean, default=True)
    is_triggered = Column(Boolean, default=False)
    triggered_at = Column(DateTime, nullable=True)
    trigger_count = Column(Integer, default=0)  # 重复提醒已触发次数

    # 时间戳
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # 关系
    user = relationship("User", backref="reminders")

    def __repr__(self):
        return f"<Reminder(id={self.id}, title={self.title}, remind_at={self.remind_at})>"

    def to_dict(self) -> dict:
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
