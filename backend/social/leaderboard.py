"""
排行榜 - 交易员排名
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class TraderStats:
    """
    交易员统计
    
    Attributes:
        trader_id: 交易员 ID
        trader_name: 交易员名称
        total_pnl: 总盈亏
        total_return: 总收益率
        win_rate: 胜率
        total_trades: 交易次数
        follower_count: 粉丝数量
        aum: 管理资金
        sharpe_ratio: Sharpe 比率
        max_drawdown: 最大回撤
        trading_days: 交易天数
    """
    trader_id: str
    trader_name: str
    total_pnl: float = 0.0
    total_return: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    follower_count: int = 0
    aum: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    trading_days: int = 0


class Leaderboard:
    """
    排行榜
    
    支持多种排名维度
    """
    
    def __init__(self):
        """初始化排行榜"""
        # 交易员统计：{trader_id: TraderStats}
        self._trader_stats: Dict[str, TraderStats] = {}
        
        # 历史排名缓存
        self._ranking_cache: Dict[str, List[tuple]] = {}
    
    def update_trader_stats(
        self,
        trader_id: str,
        trader_name: str,
        **kwargs,
    ) -> TraderStats:
        """
        更新交易员统计
        
        Args:
            trader_id: 交易员 ID
            trader_name: 交易员名称
            **kwargs: 统计字段
            
        Returns:
            TraderStats: 统计对象
        """
        if trader_id not in self._trader_stats:
            self._trader_stats[trader_id] = TraderStats(
                trader_id=trader_id,
                trader_name=trader_name,
            )
        
        stats = self._trader_stats[trader_id]
        
        # 更新字段
        for key, value in kwargs.items():
            if hasattr(stats, key):
                setattr(stats, key, value)
        
        # 清除缓存
        self._ranking_cache.clear()
        
        return stats
    
    def get_ranking(
        self,
        metric: str = "total_return",
        limit: int = 100,
        period: str = "all",
    ) -> List[tuple]:
        """
        获取排行榜
        
        Args:
            metric: 排名指标
            limit: 数量限制
            period: 时间周期
            
        Returns:
            List[tuple]: [(trader_id, value), ...]
        """
        cache_key = f"{metric}:{period}"
        
        if cache_key in self._ranking_cache:
            return self._ranking_cache[cache_key][:limit]
        
        # 获取所有交易员
        traders = list(self._trader_stats.values())
        
        # 过滤（按周期）
        if period != "all":
            # TODO: 实现周期过滤
            pass
        
        # 排序
        if hasattr(TraderStats, metric):
            traders.sort(
                key=lambda t: getattr(t, metric),
                reverse=(metric not in ['max_drawdown']),
            )
        else:
            traders.sort(key=lambda t: t.trader_id)
        
        # 生成排名
        ranking = [
            (t.trader_id, getattr(t, metric, 0))
            for t in traders
        ]
        
        # 缓存
        self._ranking_cache[cache_key] = ranking
        
        return ranking[:limit]
    
    def get_top_traders(
        self,
        metric: str = "total_return",
        limit: int = 10,
    ) -> List[TraderStats]:
        """获取顶级交易员"""
        ranking = self.get_ranking(metric, limit * 2)
        
        return [
            self._trader_stats[tid]
            for tid, _ in ranking
            if tid in self._trader_stats
        ][:limit]
    
    def get_trader_rank(
        self,
        trader_id: str,
        metric: str = "total_return",
    ) -> int:
        """获取交易员排名"""
        ranking = self.get_ranking(metric, limit=1000)
        
        for i, (tid, _) in enumerate(ranking, 1):
            if tid == trader_id:
                return i
        
        return -1
    
    def get_trader_stats(self, trader_id: str) -> Optional[TraderStats]:
        """获取交易员统计"""
        return self._trader_stats.get(trader_id)
    
    def get_statistics(self) -> dict:
        """获取排行榜统计"""
        return {
            'total_traders': len(self._trader_stats),
            'metrics': [
                'total_pnl',
                'total_return',
                'win_rate',
                'sharpe_ratio',
                'follower_count',
                'aum',
            ],
        }
