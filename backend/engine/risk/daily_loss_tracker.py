"""
每日亏损追踪器
"""

from datetime import datetime, date
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class DailyPnLRecord:
    """每日盈亏记录"""
    date: date
    pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0


class DailyLossTracker:
    """
    每日亏损追踪器
    
    追踪单日亏损，触发阈值时停止交易
    """
    
    def __init__(
        self,
        max_daily_loss: float = 0.05,
        warning_daily_loss: float = 0.03,
        initial_capital: float = 100000
    ):
        """
        Args:
            max_daily_loss: 最大单日亏损阈值 (0-1)
            warning_daily_loss: 预警单日亏损阈值 (0-1)
            initial_capital: 初始资金
        """
        self.max_daily_loss = max_daily_loss
        self.warning_daily_loss = warning_daily_loss
        self.initial_capital = initial_capital
        
        self._current_date = date.today()
        self._today_pnl = 0.0
        self._today_realized_pnl = 0.0
        self._today_unrealized_pnl = 0.0
        self._today_trade_count = 0
        self._today_win_count = 0
        self._today_loss_count = 0
        self._is_trading_stopped = False
        
        self._history: list[DailyPnLRecord] = []
    
    def _check_date_change(self):
        """检查日期变更，重置日统计"""
        today = date.today()
        if today != self._current_date:
            # 保存昨日记录
            record = DailyPnLRecord(
                date=self._current_date,
                pnl=self._today_pnl,
                realized_pnl=self._today_realized_pnl,
                unrealized_pnl=self._today_unrealized_pnl,
                trade_count=self._today_trade_count,
                win_count=self._today_win_count,
                loss_count=self._today_loss_count,
            )
            self._history.append(record)
            
            # 重置今日统计
            self._current_date = today
            self._today_pnl = 0.0
            self._today_realized_pnl = 0.0
            self._today_unrealized_pnl = 0.0
            self._today_trade_count = 0
            self._today_win_count = 0
            self._today_loss_count = 0
            self._is_trading_stopped = False
    
    def record_realized_pnl(self, pnl: float):
        """
        记录已实现盈亏
        
        Args:
            pnl: 盈亏金额 (正为盈，负为亏)
        """
        self._check_date_change()
        
        self._today_realized_pnl += pnl
        self._today_pnl = self._today_realized_pnl + self._today_unrealized_pnl
        self._today_trade_count += 1
        
        if pnl > 0:
            self._today_win_count += 1
        elif pnl < 0:
            self._today_loss_count += 1
        
        # 检查是否触发止损
        daily_loss_ratio = -self._today_pnl / self.initial_capital
        if daily_loss_ratio >= self.max_daily_loss:
            self._is_trading_stopped = True
    
    def update_unrealized_pnl(self, unrealized_pnl: float):
        """
        更新未实现盈亏
        
        Args:
            unrealized_pnl: 未实现盈亏金额
        """
        self._check_date_change()
        self._today_unrealized_pnl = unrealized_pnl
        self._today_pnl = self._today_realized_pnl + self._today_unrealized_pnl
    
    @property
    def today_pnl(self) -> float:
        """今日盈亏"""
        self._check_date_change()
        return self._today_pnl
    
    @property
    def today_pnl_ratio(self) -> float:
        """今日盈亏比例"""
        self._check_date_change()
        if self.initial_capital == 0:
            return 0.0
        return self._today_pnl / self.initial_capital
    
    @property
    def is_warning(self) -> bool:
        """是否达到预警线"""
        self._check_date_change()
        return -self._today_pnl / self.initial_capital >= self.warning_daily_loss
    
    @property
    def is_limit_reached(self) -> bool:
        """是否达到最大亏损限制"""
        self._check_date_change()
        return -self._today_pnl / self.initial_capital >= self.max_daily_loss
    
    @property
    def is_trading_stopped(self) -> bool:
        """是否已停止交易"""
        self._check_date_change()
        return self._is_trading_stopped
    
    def can_trade(self) -> bool:
        """是否可以继续交易"""
        self._check_date_change()
        return not self._is_trading_stopped
    
    def reset(self):
        """手动重置（用于测试）"""
        self._is_trading_stopped = False
    
    def get_status(self) -> dict:
        """获取状态"""
        self._check_date_change()
        daily_loss_ratio = -self._today_pnl / self.initial_capital if self.initial_capital > 0 else 0
        
        return {
            "date": self._current_date.isoformat(),
            "today_pnl": self._today_pnl,
            "today_pnl_ratio": f"{self.today_pnl_ratio:.2%}",
            "today_realized_pnl": self._today_realized_pnl,
            "today_unrealized_pnl": self._today_unrealized_pnl,
            "today_trade_count": self._today_trade_count,
            "today_win_count": self._today_win_count,
            "today_loss_count": self._today_loss_count,
            "win_rate": f"{self._today_win_count / self._today_trade_count:.2%}" if self._today_trade_count > 0 else "0%",
            "daily_loss_ratio": f"{daily_loss_ratio:.2%}",
            "warning_daily_loss": f"{self.warning_daily_loss:.2%}",
            "max_daily_loss": f"{self.max_daily_loss:.2%}",
            "is_warning": self.is_warning,
            "is_limit_reached": self.is_limit_reached,
            "is_trading_stopped": self.is_trading_stopped,
            "can_trade": self.can_trade(),
        }
    
    def get_history(self, days: int = 30) -> list[dict]:
        """
        获取历史盈亏记录
        
        Args:
            days: 返回最近 N 天
        """
        records = self._history[-days:]
        return [
            {
                "date": record.date.isoformat(),
                "pnl": record.pnl,
                "realized_pnl": record.realized_pnl,
                "unrealized_pnl": record.unrealized_pnl,
                "trade_count": record.trade_count,
                "win_count": record.win_count,
                "loss_count": record.loss_count,
            }
            for record in records
        ]
