"""
跟单系统 - 复制交易
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


@dataclass
class Follower:
    """
    跟单者
    
    Attributes:
        id: 跟单 ID
        follower_id: 跟单者 ID
        trader_id: 交易员 ID
        copy_ratio: 复制比例 (0-1)
        max_position: 最大仓位
        status: 状态
        total_pnl: 总盈亏
        created_at: 创建时间
    """
    id: str
    follower_id: str
    trader_id: str
    copy_ratio: float = 1.0
    max_position: float = 10000.0
    status: str = "active"
    total_pnl: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CopiedTrade:
    """
    复制的交易
    
    Attributes:
        id: 交易 ID
        original_trade_id: 原始交易 ID
        follower_id: 跟单者 ID
        trader_id: 交易员 ID
        symbol: 交易对
        action: 操作
        original_quantity: 原始数量
        copied_quantity: 复制数量
        entry_price: 入场价格
        pnl: 盈亏
        status: 状态
    """
    id: str
    original_trade_id: str
    follower_id: str
    trader_id: str
    symbol: str
    action: str
    original_quantity: float
    copied_quantity: float
    entry_price: float
    pnl: float = 0.0
    status: str = "open"
    created_at: datetime = field(default_factory=datetime.utcnow)


class CopyTradingManager:
    """
    跟单管理器
    
    管理复制交易的整个流程
    """
    
    def __init__(self):
        """初始化跟单管理器"""
        # 跟单关系：{follower_id: Follower}
        self._followers: Dict[str, Follower] = {}
        
        # 交易员粉丝索引：{trader_id: [follower_id]}
        self._trader_index: Dict[str, List[str]] = {}
        
        # 复制的交易：{original_trade_id: [CopiedTrade]}
        self._copied_trades: Dict[str, List[CopiedTrade]] = {}
        
        # 统计
        self._total_copied_trades = 0
        self._total_follower_pnl = 0.0
    
    def start_following(
        self,
        follower_id: str,
        trader_id: str,
        copy_ratio: float = 1.0,
        max_position: float = 10000.0,
    ) -> Follower:
        """
        开始跟单
        
        Args:
            follower_id: 跟单者 ID
            trader_id: 交易员 ID
            copy_ratio: 复制比例
            max_position: 最大仓位
            
        Returns:
            Follower: 跟单对象
        """
        import hashlib
        follower_id_hash = hashlib.md5(
            f"{follower_id}:{trader_id}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
        
        follower = Follower(
            id=follower_id_hash,
            follower_id=follower_id,
            trader_id=trader_id,
            copy_ratio=copy_ratio,
            max_position=max_position,
        )
        
        # 存储
        self._followers[follower_id_hash] = follower
        
        # 更新索引
        if trader_id not in self._trader_index:
            self._trader_index[trader_id] = []
        self._trader_index[trader_id].append(follower_id_hash)
        
        logger.info(f"开始跟单：{follower_id} -> {trader_id}")
        
        return follower
    
    def stop_following(self, follower_id: str) -> bool:
        """停止跟单"""
        follower = self._followers.get(follower_id)
        if not follower:
            return False
        
        follower.status = "inactive"
        
        logger.info(f"停止跟单：{follower_id}")
        
        return True
    
    def copy_trade(
        self,
        original_trade_id: str,
        trader_id: str,
        symbol: str,
        action: str,
        quantity: float,
        entry_price: float,
    ) -> List[CopiedTrade]:
        """
        复制交易
        
        Args:
            original_trade_id: 原始交易 ID
            trader_id: 交易员 ID
            symbol: 交易对
            action: 操作
            quantity: 数量
            entry_price: 入场价格
            
        Returns:
            List[CopiedTrade]: 复制的交易列表
        """
        copied_trades = []
        
        # 获取所有活跃粉丝
        follower_ids = self._trader_index.get(trader_id, [])
        
        for fid in follower_ids:
            follower = self._followers.get(fid)
            if not follower or follower.status != "active":
                continue
            
            # 计算复制数量
            copied_quantity = quantity * follower.copy_ratio
            
            # 检查最大仓位
            if copied_quantity * entry_price > follower.max_position:
                logger.warning(f"超过最大仓位，跳过：{follower.follower_id}")
                continue
            
            # 创建复制交易
            import hashlib
            trade_id = hashlib.md5(
                f"{original_trade_id}:{follower.follower_id}:{datetime.utcnow().isoformat()}".encode()
            ).hexdigest()[:16]
            
            copied_trade = CopiedTrade(
                id=trade_id,
                original_trade_id=original_trade_id,
                follower_id=follower.follower_id,
                trader_id=trader_id,
                symbol=symbol,
                action=action,
                original_quantity=quantity,
                copied_quantity=copied_quantity,
                entry_price=entry_price,
            )
            
            copied_trades.append(copied_trade)
            self._total_copied_trades += 1
        
        # 存储
        if copied_trades:
            self._copied_trades[original_trade_id] = copied_trades
        
        return copied_trades
    
    def update_trade_pnl(
        self,
        original_trade_id: str,
        pnl: float,
    ) -> bool:
        """更新复制交易的盈亏"""
        copied_list = self._copied_trades.get(original_trade_id, [])
        
        if not copied_list:
            return False
        
        for copied_trade in copied_list:
            # 按比例分配盈亏
            ratio = copied_trade.copied_quantity / copied_trade.original_quantity
            copied_trade.pnl = pnl * ratio
            
            # 更新跟单者总盈亏
            follower = next(
                (f for f in self._followers.values() if f.follower_id == copied_trade.follower_id),
                None,
            )
            if follower:
                follower.total_pnl += copied_trade.pnl
                self._total_follower_pnl += copied_trade.pnl
        
        return True
    
    def get_follower_count(self, trader_id: str) -> int:
        """获取交易员的粉丝数量"""
        follower_ids = self._trader_index.get(trader_id, [])
        return sum(
            1 for fid in follower_ids
            if self._followers.get(fid) and self._followers[fid].status == "active"
        )
    
    def get_follower_trades(self, follower_id: str) -> List[CopiedTrade]:
        """获取跟单者的复制交易"""
        trades = []
        for trade_list in self._copied_trades.values():
            for trade in trade_list:
                if trade.follower_id == follower_id:
                    trades.append(trade)
        return trades
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        active_followers = sum(
            1 for f in self._followers.values()
            if f.status == "active"
        )
        
        return {
            'total_followers': len(self._followers),
            'active_followers': active_followers,
            'total_copied_trades': self._total_copied_trades,
            'total_follower_pnl': self._total_follower_pnl,
            'traders_with_followers': len(self._trader_index),
        }
