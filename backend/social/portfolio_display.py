"""
组合展示 - 公开投资组合
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Portfolio:
    """
    投资组合
    
    Attributes:
        id: 组合 ID
        trader_id: 交易员 ID
        trader_name: 交易员名称
        name: 组合名称
        description: 描述
        is_public: 是否公开
        positions: 持仓
        performance: 表现数据
        created_at: 创建时间
        updated_at: 更新时间
    """
    id: str
    trader_id: str
    trader_name: str
    name: str = ""
    description: str = ""
    is_public: bool = True
    positions: Dict[str, dict] = field(default_factory=dict)
    performance: Dict[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class PortfolioDisplay:
    """
    组合展示
    
    管理公开投资组合的展示
    """
    
    def __init__(self):
        """初始化组合展示"""
        # 组合存储：{portfolio_id: Portfolio}
        self._portfolios: Dict[str, Portfolio] = {}
        
        # 交易员组合索引：{trader_id: [portfolio_id]}
        self._trader_index: Dict[str, List[str]] = {}
    
    def create_portfolio(
        self,
        trader_id: str,
        trader_name: str,
        name: str,
        description: str = "",
        is_public: bool = True,
    ) -> Portfolio:
        """
        创建投资组合
        
        Args:
            trader_id: 交易员 ID
            trader_name: 交易员名称
            name: 组合名称
            description: 描述
            is_public: 是否公开
            
        Returns:
            Portfolio: 组合对象
        """
        import hashlib
        portfolio_id = hashlib.md5(
            f"{trader_id}:{name}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
        
        portfolio = Portfolio(
            id=portfolio_id,
            trader_id=trader_id,
            trader_name=trader_name,
            name=name,
            description=description,
            is_public=is_public,
        )
        
        # 存储
        self._portfolios[portfolio_id] = portfolio
        
        # 更新索引
        if trader_id not in self._trader_index:
            self._trader_index[trader_id] = []
        self._trader_index[trader_id].append(portfolio_id)
        
        logger.info(f"创建投资组合：{portfolio_id} - {name}")
        
        return portfolio
    
    def update_positions(
        self,
        portfolio_id: str,
        positions: Dict[str, dict],
    ) -> bool:
        """更新持仓"""
        portfolio = self._portfolios.get(portfolio_id)
        if not portfolio:
            return False
        
        portfolio.positions = positions
        portfolio.updated_at = datetime.utcnow()
        
        return True
    
    def update_performance(
        self,
        portfolio_id: str,
        performance: Dict[str, float],
    ) -> bool:
        """更新表现数据"""
        portfolio = self._portfolios.get(portfolio_id)
        if not portfolio:
            return False
        
        portfolio.performance = performance
        portfolio.updated_at = datetime.utcnow()
        
        return True
    
    def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """获取组合"""
        return self._portfolios.get(portfolio_id)
    
    def get_public_portfolios(
        self,
        trader_id: Optional[str] = None,
    ) -> List[Portfolio]:
        """获取公开组合"""
        portfolios = list(self._portfolios.values())
        
        # 过滤
        portfolios = [p for p in portfolios if p.is_public]
        
        if trader_id:
            portfolios = [p for p in portfolios if p.trader_id == trader_id]
        
        return portfolios
    
    def get_trader_portfolios(self, trader_id: str) -> List[Portfolio]:
        """获取交易员的组合"""
        portfolio_ids = self._trader_index.get(trader_id, [])
        return [
            self._portfolios[pid]
            for pid in portfolio_ids
            if pid in self._portfolios
        ]
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        public_count = sum(1 for p in self._portfolios.values() if p.is_public)
        
        return {
            'total_portfolios': len(self._portfolios),
            'public_portfolios': public_count,
            'traders_with_portfolios': len(self._trader_index),
        }
