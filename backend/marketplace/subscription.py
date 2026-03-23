"""
订阅管理 - 策略订阅和权限
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class Subscription:
    """
    订阅记录
    
    Attributes:
        id: 订阅 ID
        user_id: 用户 ID
        strategy_id: 策略 ID
        start_date: 开始日期
        end_date: 结束日期
        auto_renew: 自动续期
        status: 状态
        total_paid: 总支付金额
    """
    id: str
    user_id: str
    strategy_id: str
    start_date: datetime = field(default_factory=datetime.utcnow)
    end_date: Optional[datetime] = None
    auto_renew: bool = False
    status: str = "active"
    total_paid: float = 0.0


class SubscriptionManager:
    """
    订阅管理器
    
    管理策略订阅、续期、取消等
    """
    
    def __init__(self):
        """初始化订阅管理器"""
        # 订阅存储：{subscription_id: Subscription}
        self._subscriptions: Dict[str, Subscription] = {}
        
        # 用户订阅索引：{user_id: [subscription_id]}
        self._user_index: Dict[str, List[str]] = {}
        
        # 策略订阅索引：{strategy_id: [subscription_id]}
        self._strategy_index: Dict[str, List[str]] = {}
    
    def create_subscription(
        self,
        user_id: str,
        strategy_id: str,
        duration_days: int = 30,
        auto_renew: bool = False,
    ) -> Subscription:
        """
        创建订阅
        
        Args:
            user_id: 用户 ID
            strategy_id: 策略 ID
            duration_days: 订阅时长（天）
            auto_renew: 自动续期
            
        Returns:
            Subscription: 订阅对象
        """
        import hashlib
        subscription_id = hashlib.md5(
            f"{user_id}:{strategy_id}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
        
        subscription = Subscription(
            id=subscription_id,
            user_id=user_id,
            strategy_id=strategy_id,
            end_date=datetime.utcnow() + timedelta(days=duration_days),
            auto_renew=auto_renew,
            status="active",
        )
        
        # 存储
        self._subscriptions[subscription_id] = subscription
        
        # 更新索引
        if user_id not in self._user_index:
            self._user_index[user_id] = []
        self._user_index[user_id].append(subscription_id)
        
        if strategy_id not in self._strategy_index:
            self._strategy_index[strategy_id] = []
        self._strategy_index[strategy_id].append(subscription_id)
        
        logger.info(f"创建订阅：{subscription_id} - {user_id} -> {strategy_id}")
        
        return subscription
    
    def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """获取订阅"""
        return self._subscriptions.get(subscription_id)
    
    def is_subscribed(self, user_id: str, strategy_id: str) -> bool:
        """检查用户是否已订阅策略"""
        subscription_ids = self._user_index.get(user_id, [])
        
        for sid in subscription_ids:
            subscription = self._subscriptions.get(sid)
            if (
                subscription and
                subscription.strategy_id == strategy_id and
                subscription.status == "active" and
                (not subscription.end_date or subscription.end_date > datetime.utcnow())
            ):
                return True
        
        return False
    
    def cancel_subscription(self, subscription_id: str) -> bool:
        """取消订阅"""
        subscription = self._subscriptions.get(subscription_id)
        if not subscription:
            return False
        
        subscription.status = "cancelled"
        subscription.end_date = datetime.utcnow()
        
        logger.info(f"取消订阅：{subscription_id}")
        
        return True
    
    def renew_subscription(
        self,
        subscription_id: str,
        duration_days: int = 30,
    ) -> bool:
        """续期订阅"""
        subscription = self._subscriptions.get(subscription_id)
        if not subscription:
            return False
        
        if subscription.status != "active":
            return False
        
        # 延长结束日期
        if subscription.end_date:
            subscription.end_date += timedelta(days=duration_days)
        else:
            subscription.end_date = datetime.utcnow() + timedelta(days=duration_days)
        
        logger.info(f"续期订阅：{subscription_id}")
        
        return True
    
    def get_user_subscriptions(self, user_id: str) -> List[Subscription]:
        """获取用户的订阅"""
        subscription_ids = self._user_index.get(user_id, [])
        return [
            self._subscriptions[sid]
            for sid in subscription_ids
            if sid in self._subscriptions
        ]
    
    def get_active_subscriptions(self, user_id: str) -> List[Subscription]:
        """获取用户的有效订阅"""
        subscriptions = self.get_user_subscriptions(user_id)
        
        return [
            s for s in subscriptions
            if s.status == "active" and
            (not s.end_date or s.end_date > datetime.utcnow())
        ]
    
    def get_strategy_subscribers(self, strategy_id: str) -> int:
        """获取策略订阅者数量"""
        subscription_ids = self._strategy_index.get(strategy_id, [])
        
        # 统计活跃订阅
        count = 0
        for sid in subscription_ids:
            subscription = self._subscriptions.get(sid)
            if (
                subscription and
                subscription.status == "active" and
                (not subscription.end_date or subscription.end_date > datetime.utcnow())
            ):
                count += 1
        
        return count
    
    def check_expired_subscriptions(self) -> List[str]:
        """检查过期的订阅"""
        expired = []
        now = datetime.utcnow()
        
        for subscription in self._subscriptions.values():
            if (
                subscription.status == "active" and
                subscription.end_date and
                subscription.end_date < now
            ):
                if subscription.auto_renew:
                    # TODO: 自动续期逻辑
                    pass
                else:
                    subscription.status = "expired"
                    expired.append(subscription.id)
        
        return expired
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        active_count = sum(
            1 for s in self._subscriptions.values()
            if s.status == "active"
        )
        
        return {
            'total_subscriptions': len(self._subscriptions),
            'active_subscriptions': active_count,
            'unique_users': len(self._user_index),
            'unique_strategies': len(self._strategy_index),
        }
