"""
仓位限制管理
"""

from dataclasses import dataclass
from typing import Dict, Optional
from decimal import Decimal


@dataclass
class PositionLimits:
    """
    仓位限制配置
    
    Attributes:
        max_position_ratio: 单个标的最大仓位比例 (0-1)
        max_total_position_ratio: 总仓位上限 (0-1)
        max_single_order_ratio: 单笔订单最大仓位比例
        max_position_value: 单个标的最大持仓价值 (USDT)
        max_daily_trade_count: 单日最大交易次数
    """
    max_position_ratio: float = 0.3
    max_total_position_ratio: float = 0.8
    max_single_order_ratio: float = 0.1
    max_position_value: Optional[float] = None
    max_daily_trade_count: int = 100


class PositionChecker:
    """
    仓位检查器
    
    检查新订单是否违反仓位限制
    """
    
    def __init__(self, limits: PositionLimits):
        self.limits = limits
        self._daily_trade_count = 0
    
    def can_open_position(
        self,
        symbol: str,
        order_value: float,
        current_positions: Dict[str, float],
        total_capital: float
    ) -> tuple[bool, str]:
        """
        检查是否可以开仓
        
        Args:
            symbol: 交易对
            order_value: 订单价值 (USDT)
            current_positions: 当前持仓 {symbol: value}
            total_capital: 总资金
            
        Returns:
            (是否允许，原因)
        """
        # 检查单日交易次数
        if self._daily_trade_count >= self.limits.max_daily_trade_count:
            return False, f"达到单日最大交易次数限制 ({self.limits.max_daily_trade_count})"
        
        # 检查单笔订单大小
        max_order_value = total_capital * self.limits.max_single_order_ratio
        if order_value > max_order_value:
            return False, f"单笔订单超过限制：{order_value:.2f} > {max_order_value:.2f} USDT"
        
        # 检查单个标的仓位
        current_position = current_positions.get(symbol, 0)
        new_position = current_position + order_value
        max_position = total_capital * self.limits.max_position_ratio
        
        if new_position > max_position:
            return False, f"标的 {symbol} 仓位超限：{new_position:.2f} > {max_position:.2f} USDT"
        
        # 检查总仓位
        total_position = sum(current_positions.values()) + order_value
        max_total_position = total_capital * self.limits.max_total_position_ratio
        
        if total_position > max_total_position:
            return False, f"总仓位超限：{total_position:.2f} > {max_total_position:.2f} USDT"
        
        # 检查绝对金额限制
        if self.limits.max_position_value and new_position > self.limits.max_position_value:
            return False, f"标的 {symbol} 仓位超过最大金额限制"
        
        return True, "通过检查"
    
    def can_close_position(
        self,
        symbol: str,
        close_ratio: float,
        current_position: float
    ) -> tuple[bool, str]:
        """
        检查是否可以平仓
        
        Args:
            symbol: 交易对
            close_ratio: 平仓比例 (0-1)
            current_position: 当前持仓价值
            
        Returns:
            (是否允许，原因)
        """
        if close_ratio < 0 or close_ratio > 1:
            return False, "平仓比例必须在 0-1 之间"
        
        if close_ratio * current_position > current_position:
            return False, "平仓价值超过当前持仓"
        
        return True, "通过检查"
    
    def record_trade(self):
        """记录一次交易"""
        self._daily_trade_count += 1
    
    def reset_daily_count(self):
        """重置单日交易计数"""
        self._daily_trade_count = 0
    
    def get_status(self) -> dict:
        """获取状态"""
        return {
            "daily_trade_count": self._daily_trade_count,
            "max_daily_trades": self.limits.max_daily_trade_count,
            "limits": {
                "max_position_ratio": self.limits.max_position_ratio,
                "max_total_position_ratio": self.limits.max_total_position_ratio,
                "max_single_order_ratio": self.limits.max_single_order_ratio,
            }
        }
