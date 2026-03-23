"""
策略商店 - 策略发布和管理
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import logging

logger = logging.getLogger(__name__)


class StrategyStatus(Enum):
    """策略状态"""
    DRAFT = "draft"           # 草稿
    PENDING = "pending"       # 待审核
    PUBLISHED = "published"   # 已发布
    SUSPENDED = "suspended"   # 已暂停
    ARCHIVED = "archived"     # 已归档


class PricingModel(Enum):
    """定价模型"""
    FREE = "free"             # 免费
    SUBSCRIPTION = "subscription"  # 订阅制
    ONE_TIME = "one_time"     # 一次性购买
    PROFIT_SHARE = "profit_share"  # 收益分成


@dataclass
class Strategy:
    """
    策略数据
    
    Attributes:
        id: 策略 ID
        name: 策略名称
        description: 描述
        author_id: 作者 ID
        author_name: 作者名称
        category: 分类
        version: 版本
        status: 状态
        pricing_model: 定价模型
        price: 价格
        profit_share_ratio: 收益分成比例
        code: 策略代码
        params: 参数定义
        performance: 表现数据
        downloads: 下载次数
        rating: 评分
        created_at: 创建时间
        updated_at: 更新时间
    """
    id: str = field(default_factory=lambda: hashlib.md5(
        f"{datetime.utcnow().isoformat()}".encode()
    ).hexdigest()[:16])
    name: str = ""
    description: str = ""
    author_id: str = ""
    author_name: str = ""
    category: str = "trend"
    version: str = "1.0.0"
    status: StrategyStatus = StrategyStatus.DRAFT
    pricing_model: PricingModel = PricingModel.FREE
    price: float = 0.0
    profit_share_ratio: float = 0.0
    code: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    performance: Dict[str, float] = field(default_factory=dict)
    downloads: int = 0
    rating: float = 0.0
    rating_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'author_name': self.author_name,
            'category': self.category,
            'version': self.version,
            'status': self.status.value,
            'pricing_model': self.pricing_model.value,
            'price': self.price,
            'profit_share_ratio': self.profit_share_ratio,
            'performance': self.performance,
            'downloads': self.downloads,
            'rating': self.rating,
            'rating_count': self.rating_count,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class StrategyStore:
    """
    策略商店
    
    管理策略的发布、审核、下架等
    """
    
    def __init__(self):
        """初始化策略商店"""
        # 策略存储：{strategy_id: Strategy}
        self._strategies: Dict[str, Strategy] = {}
        
        # 作者策略索引：{author_id: [strategy_id]}
        self._author_index: Dict[str, List[str]] = {}
        
        # 分类索引：{category: [strategy_id]}
        self._category_index: Dict[str, List[str]] = {}
        
        # 统计
        self._total_downloads = 0
        self._total_revenue = 0.0
    
    def create_strategy(
        self,
        name: str,
        description: str,
        author_id: str,
        author_name: str,
        code: str,
        category: str = "trend",
        pricing_model: PricingModel = PricingModel.FREE,
        price: float = 0.0,
        profit_share_ratio: float = 0.0,
        params: Optional[Dict] = None,
    ) -> Strategy:
        """
        创建策略
        
        Args:
            name: 策略名称
            description: 描述
            author_id: 作者 ID
            author_name: 作者名称
            code: 策略代码
            category: 分类
            pricing_model: 定价模型
            price: 价格
            profit_share_ratio: 收益分成比例
            params: 参数定义
            
        Returns:
            Strategy: 策略对象
        """
        strategy = Strategy(
            name=name,
            description=description,
            author_id=author_id,
            author_name=author_name,
            code=code,
            category=category,
            pricing_model=pricing_model,
            price=price,
            profit_share_ratio=profit_share_ratio,
            params=params or {},
        )
        
        # 存储
        self._strategies[strategy.id] = strategy
        
        # 更新索引
        if author_id not in self._author_index:
            self._author_index[author_id] = []
        self._author_index[author_id].append(strategy.id)
        
        if category not in self._category_index:
            self._category_index[category] = []
        self._category_index[category].append(strategy.id)
        
        logger.info(f"创建策略：{strategy.name} ({strategy.id})")
        
        return strategy
    
    def get_strategy(self, strategy_id: str) -> Optional[Strategy]:
        """获取策略"""
        return self._strategies.get(strategy_id)
    
    def publish_strategy(self, strategy_id: str) -> bool:
        """发布策略"""
        strategy = self._strategies.get(strategy_id)
        if not strategy:
            return False
        
        strategy.status = StrategyStatus.PUBLISHED
        strategy.updated_at = datetime.utcnow()
        
        logger.info(f"发布策略：{strategy.name}")
        
        return True
    
    def suspend_strategy(self, strategy_id: str, reason: str = "") -> bool:
        """暂停策略"""
        strategy = self._strategies.get(strategy_id)
        if not strategy:
            return False
        
        strategy.status = StrategyStatus.SUSPENDED
        strategy.updated_at = datetime.utcnow()
        
        logger.info(f"暂停策略：{strategy.name} - {reason}")
        
        return True
    
    def update_performance(
        self,
        strategy_id: str,
        performance: Dict[str, float],
    ) -> bool:
        """更新策略表现"""
        strategy = self._strategies.get(strategy_id)
        if not strategy:
            return False
        
        strategy.performance = performance
        strategy.updated_at = datetime.utcnow()
        
        return True
    
    def record_download(self, strategy_id: str) -> bool:
        """记录下载"""
        strategy = self._strategies.get(strategy_id)
        if not strategy:
            return False
        
        strategy.downloads += 1
        self._total_downloads += 1
        
        return True
    
    def search_strategies(
        self,
        category: Optional[str] = None,
        min_rating: float = 0.0,
        pricing_model: Optional[PricingModel] = None,
        sort_by: str = "rating",
    ) -> List[Strategy]:
        """
        搜索策略
        
        Args:
            category: 分类
            min_rating: 最低评分
            pricing_model: 定价模型
            sort_by: 排序字段
            
        Returns:
            List[Strategy]: 策略列表
        """
        results = list(self._strategies.values())
        
        # 过滤
        results = [
            s for s in results
            if s.status == StrategyStatus.PUBLISHED
        ]
        
        if category:
            results = [s for s in results if s.category == category]
        
        if min_rating > 0:
            results = [s for s in results if s.rating >= min_rating]
        
        if pricing_model:
            results = [s for s in results if s.pricing_model == pricing_model]
        
        # 排序
        if sort_by == "rating":
            results.sort(key=lambda s: s.rating, reverse=True)
        elif sort_by == "downloads":
            results.sort(key=lambda s: s.downloads, reverse=True)
        elif sort_by == "price":
            results.sort(key=lambda s: s.price)
        elif sort_by == "created_at":
            results.sort(key=lambda s: s.created_at, reverse=True)
        
        return results
    
    def get_author_strategies(self, author_id: str) -> List[Strategy]:
        """获取作者的策略"""
        strategy_ids = self._author_index.get(author_id, [])
        return [
            self._strategies[sid]
            for sid in strategy_ids
            if sid in self._strategies
        ]
    
    def get_categories(self) -> Dict[str, int]:
        """获取分类统计"""
        return {
            category: len(ids)
            for category, ids in self._category_index.items()
        }
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        published = sum(
            1 for s in self._strategies.values()
            if s.status == StrategyStatus.PUBLISHED
        )
        
        avg_rating = (
            sum(s.rating for s in self._strategies.values() if s.rating_count > 0) /
            sum(1 for s in self._strategies.values() if s.rating_count > 0)
            if any(s.rating_count > 0 for s in self._strategies.values())
            else 0
        )
        
        return {
            'total_strategies': len(self._strategies),
            'published_strategies': published,
            'total_downloads': self._total_downloads,
            'total_revenue': self._total_revenue,
            'avg_rating': avg_rating,
            'categories': self.get_categories(),
        }
