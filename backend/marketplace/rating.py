"""
评分系统 - 策略评分和评论
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Review:
    """
    评论
    
    Attributes:
        id: 评论 ID
        strategy_id: 策略 ID
        user_id: 用户 ID
        username: 用户名
        rating: 评分 (1-5)
        title: 标题
        content: 内容
        created_at: 创建时间
        helpful_count: 有帮助次数
    """
    id: str
    strategy_id: str
    user_id: str
    username: str
    rating: int
    title: str = ""
    content: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    helpful_count: int = 0


class RatingSystem:
    """
    评分系统
    
    管理策略评分和评论
    """
    
    def __init__(self):
        """初始化评分系统"""
        # 评论存储：{review_id: Review}
        self._reviews: Dict[str, Review] = {}
        
        # 策略评论索引：{strategy_id: [review_id]}
        self._strategy_index: Dict[str, List[str]] = {}
        
        # 用户评论索引：{user_id: [review_id]}
        self._user_index: Dict[str, List[str]] = {}
        
        # 策略评分缓存：{strategy_id: {avg, count}}
        self._rating_cache: Dict[str, dict] = {}
    
    def create_review(
        self,
        strategy_id: str,
        user_id: str,
        username: str,
        rating: int,
        title: str = "",
        content: str = "",
    ) -> Review:
        """
        创建评论
        
        Args:
            strategy_id: 策略 ID
            user_id: 用户 ID
            username: 用户名
            rating: 评分 (1-5)
            title: 标题
            content: 内容
            
        Returns:
            Review: 评论对象
        """
        import hashlib
        review_id = hashlib.md5(
            f"{strategy_id}:{user_id}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
        
        review = Review(
            id=review_id,
            strategy_id=strategy_id,
            user_id=user_id,
            username=username,
            rating=min(5, max(1, rating)),
            title=title,
            content=content,
        )
        
        # 存储
        self._reviews[review_id] = review
        
        # 更新索引
        if strategy_id not in self._strategy_index:
            self._strategy_index[strategy_id] = []
        self._strategy_index[strategy_id].append(review_id)
        
        if user_id not in self._user_index:
            self._user_index[user_id] = []
        self._user_index[user_id].append(review_id)
        
        # 更新评分缓存
        self._update_rating_cache(strategy_id)
        
        logger.info(f"创建评论：{review_id} - {strategy_id} - {rating}星")
        
        return review
    
    def delete_review(self, review_id: str) -> bool:
        """删除评论"""
        review = self._reviews.get(review_id)
        if not review:
            return False
        
        # 从索引中移除
        strategy_id = review.strategy_id
        user_id = review.user_id
        
        if strategy_id in self._strategy_index:
            if review_id in self._strategy_index[strategy_id]:
                self._strategy_index[strategy_id].remove(review_id)
        
        if user_id in self._user_index:
            if review_id in self._user_index[user_id]:
                self._user_index[user_id].remove(review_id)
        
        # 删除评论
        del self._reviews[review_id]
        
        # 更新评分缓存
        self._update_rating_cache(strategy_id)
        
        logger.info(f"删除评论：{review_id}")
        
        return True
    
    def mark_helpful(self, review_id: str) -> bool:
        """标记评论有帮助"""
        review = self._reviews.get(review_id)
        if not review:
            return False
        
        review.helpful_count += 1
        
        return True
    
    def get_strategy_rating(self, strategy_id: str) -> dict:
        """获取策略评分"""
        if strategy_id in self._rating_cache:
            return self._rating_cache[strategy_id]
        
        return {'average': 0.0, 'count': 0}
    
    def get_strategy_reviews(
        self,
        strategy_id: str,
        limit: int = 10,
        sort_by: str = "created_at",
    ) -> List[Review]:
        """
        获取策略评论
        
        Args:
            strategy_id: 策略 ID
            limit: 数量限制
            sort_by: 排序字段
            
        Returns:
            List[Review]: 评论列表
        """
        review_ids = self._strategy_index.get(strategy_id, [])
        reviews = [
            self._reviews[rid]
            for rid in review_ids
            if rid in self._reviews
        ]
        
        # 排序
        if sort_by == "created_at":
            reviews.sort(key=lambda r: r.created_at, reverse=True)
        elif sort_by == "rating":
            reviews.sort(key=lambda r: r.rating, reverse=True)
        elif sort_by == "helpful":
            reviews.sort(key=lambda r: r.helpful_count, reverse=True)
        
        return reviews[:limit]
    
    def get_user_reviews(self, user_id: str) -> List[Review]:
        """获取用户的评论"""
        review_ids = self._user_index.get(user_id, [])
        return [
            self._reviews[rid]
            for rid in review_ids
            if rid in self._reviews
        ]
    
    def _update_rating_cache(self, strategy_id: str):
        """更新评分缓存"""
        review_ids = self._strategy_index.get(strategy_id, [])
        reviews = [
            self._reviews[rid]
            for rid in review_ids
            if rid in self._reviews
        ]
        
        if reviews:
            avg_rating = sum(r.rating for r in reviews) / len(reviews)
            self._rating_cache[strategy_id] = {
                'average': round(avg_rating, 2),
                'count': len(reviews),
                'distribution': {
                    i: sum(1 for r in reviews if r.rating == i)
                    for i in range(1, 6)
                },
            }
        else:
            self._rating_cache[strategy_id] = {
                'average': 0.0,
                'count': 0,
                'distribution': {i: 0 for i in range(1, 6)},
            }
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        total_reviews = len(self._reviews)
        avg_rating = (
            sum(r.rating for r in self._reviews.values()) / total_reviews
            if total_reviews > 0 else 0
        )
        
        return {
            'total_reviews': total_reviews,
            'avg_rating': round(avg_rating, 2),
            'strategies_with_reviews': len(self._strategy_index),
            'unique_reviewers': len(self._user_index),
        }
