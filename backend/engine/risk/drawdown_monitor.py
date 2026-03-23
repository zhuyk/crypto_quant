"""
回撤监控
"""

from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class EquityPoint:
    """权益点"""
    timestamp: datetime
    value: float


class DrawdownMonitor:
    """
    回撤监控器
    
    实时监控账户回撤，触发阈值时告警
    """
    
    def __init__(
        self,
        max_drawdown: float = 0.20,
        warning_drawdown: float = 0.10,
        initial_capital: float = 100000
    ):
        """
        Args:
            max_drawdown: 最大回撤阈值 (0-1)
            warning_drawdown: 预警回撤阈值 (0-1)
            initial_capital: 初始资金
        """
        self.max_drawdown = max_drawdown
        self.warning_drawdown = warning_drawdown
        self.initial_capital = initial_capital
        
        self._peak_value = initial_capital
        self._current_value = initial_capital
        self._current_drawdown = 0.0
        self._max_historical_drawdown = 0.0
        self._equity_curve: List[EquityPoint] = []
        self._is_emergency_stop = False
    
    def update_equity(self, value: float, timestamp: Optional[datetime] = None):
        """
        更新权益值
        
        Args:
            value: 当前权益值
            timestamp: 时间戳
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        self._current_value = value
        self._equity_curve.append(EquityPoint(timestamp, value))
        
        # 更新峰值
        if value > self._peak_value:
            self._peak_value = value
        
        # 计算当前回撤
        if self._peak_value > 0:
            self._current_drawdown = (self._peak_value - value) / self._peak_value
        
        # 更新历史最大回撤
        if self._current_drawdown > self._max_historical_drawdown:
            self._max_historical_drawdown = self._current_drawdown
        
        # 检查是否需要紧急停止
        if self._current_drawdown >= self.max_drawdown:
            self._is_emergency_stop = True
    
    @property
    def current_drawdown(self) -> float:
        """当前回撤"""
        return self._current_drawdown
    
    @property
    def max_historical_drawdown(self) -> float:
        """历史最大回撤"""
        return self._max_historical_drawdown
    
    @property
    def is_warning(self) -> bool:
        """是否达到预警线"""
        return self._current_drawdown >= self.warning_drawdown
    
    @property
    def is_limit_reached(self) -> bool:
        """是否达到最大回撤限制"""
        return self._current_drawdown >= self.max_drawdown
    
    @property
    def is_emergency_stop(self) -> bool:
        """是否需要紧急停止"""
        return self._is_emergency_stop
    
    def can_trade(self) -> bool:
        """是否可以继续交易"""
        return not self._is_emergency_stop
    
    def reset(self, new_initial_capital: Optional[float] = None):
        """
        重置监控器
        
        Args:
            new_initial_capital: 新的初始资金
        """
        if new_initial_capital:
            self.initial_capital = new_initial_capital
            self._peak_value = new_initial_capital
            self._current_value = new_initial_capital
        
        self._current_drawdown = 0.0
        self._is_emergency_stop = False
    
    def get_status(self) -> dict:
        """获取状态"""
        return {
            "current_value": self._current_value,
            "peak_value": self._peak_value,
            "initial_capital": self.initial_capital,
            "current_drawdown": f"{self._current_drawdown:.2%}",
            "max_historical_drawdown": f"{self._max_historical_drawdown:.2%}",
            "warning_drawdown": f"{self.warning_drawdown:.2%}",
            "max_drawdown": f"{self.max_drawdown:.2%}",
            "is_warning": self.is_warning,
            "is_limit_reached": self.is_limit_reached,
            "is_emergency_stop": self.is_emergency_stop,
            "can_trade": self.can_trade(),
        }
    
    def get_equity_curve(self, limit: Optional[int] = None) -> List[dict]:
        """
        获取权益曲线
        
        Args:
            limit: 返回最近 N 条记录
        """
        curve = self._equity_curve
        if limit:
            curve = curve[-limit:]
        
        return [
            {
                "timestamp": point.timestamp.isoformat(),
                "value": point.value,
            }
            for point in curve
        ]
