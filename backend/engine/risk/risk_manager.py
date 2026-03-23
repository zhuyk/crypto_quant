"""
风险管理器 - 统一的风险控制入口
"""

from enum import Enum
from typing import Optional, Dict
from dataclasses import dataclass

from .circuit_breaker import CircuitBreaker, CircuitState
from .position_limits import PositionLimits, PositionChecker
from .drawdown_monitor import DrawdownMonitor
from .daily_loss_tracker import DailyLossTracker


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskCheckResult:
    """风险检查结果"""
    can_trade: bool
    risk_level: RiskLevel
    reasons: list[str]
    warnings: list[str]


class RiskManager:
    """
    风险管理器
    
    整合所有风险控制组件，提供统一的风险检查接口
    """
    
    def __init__(
        self,
        initial_capital: float = 100000,
        max_drawdown: float = 0.08,
        max_daily_loss: float = 0.02,
        max_position_ratio: float = 0.3,
        max_total_position_ratio: float = 0.8,
    ):
        """
        Args:
            initial_capital: 初始资金
            max_drawdown: 最大回撤阈值
            max_daily_loss: 最大单日亏损阈值
            max_position_ratio: 单个标的最大仓位比例
            max_total_position_ratio: 总仓位上限
        """
        self.initial_capital = initial_capital
        
        # 初始化各风控组件
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            success_threshold=3,
            timeout=60,
            name="trading"
        )
        
        self.position_checker = PositionChecker(
            PositionLimits(
                max_position_ratio=max_position_ratio,
                max_total_position_ratio=max_total_position_ratio,
                max_single_order_ratio=0.1,
            )
        )
        
        self.drawdown_monitor = DrawdownMonitor(
            max_drawdown=max_drawdown,
            warning_drawdown=max_drawdown * 0.6,
            initial_capital=initial_capital
        )
        
        self.daily_loss_tracker = DailyLossTracker(
            max_daily_loss=max_daily_loss,
            warning_daily_loss=max_daily_loss * 0.6,
            initial_capital=initial_capital
        )
    
    def check_trade_permission(
        self,
        symbol: Optional[str] = None,
        order_value: Optional[float] = None,
        current_positions: Optional[Dict[str, float]] = None,
        current_equity: Optional[float] = None
    ) -> RiskCheckResult:
        """
        检查是否允许交易
        
        Args:
            symbol: 交易对（可选）
            order_value: 订单价值（可选）
            current_positions: 当前持仓（可选）
            current_equity: 当前权益（可选）
            
        Returns:
            RiskCheckResult: 风险检查结果
        """
        reasons = []
        warnings = []
        risk_level = RiskLevel.LOW
        
        # 更新权益值
        if current_equity:
            self.drawdown_monitor.update_equity(current_equity)
            self.daily_loss_tracker.update_unrealized_pnl(current_equity - self.initial_capital)
        
        # 1. 检查熔断器
        if not self.circuit_breaker.is_closed:
            reasons.append(f"熔断器处于 {self.circuit_breaker.state.value} 状态")
            return RiskCheckResult(
                can_trade=False,
                risk_level=RiskLevel.CRITICAL,
                reasons=reasons,
                warnings=[]
            )
        
        # 2. 检查回撤
        if self.drawdown_monitor.is_emergency_stop:
            reasons.append(f"达到最大回撤限制 ({self.drawdown_monitor.current_drawdown:.2%})")
            return RiskCheckResult(
                can_trade=False,
                risk_level=RiskLevel.CRITICAL,
                reasons=reasons,
                warnings=[]
            )
        elif self.drawdown_monitor.is_warning:
            warnings.append(f"回撤预警 ({self.drawdown_monitor.current_drawdown:.2%})")
            risk_level = RiskLevel.HIGH
        
        # 3. 检查单日亏损
        if self.daily_loss_tracker.is_trading_stopped:
            reasons.append(f"达到单日亏损限制 ({self.daily_loss_tracker.today_pnl_ratio:.2%})")
            return RiskCheckResult(
                can_trade=False,
                risk_level=RiskLevel.CRITICAL,
                reasons=reasons,
                warnings=[]
            )
        elif self.daily_loss_tracker.is_warning:
            warnings.append(f"单日亏损预警 ({self.daily_loss_tracker.today_pnl_ratio:.2%})")
            if risk_level != RiskLevel.HIGH:
                risk_level = RiskLevel.MEDIUM
        
        # 4. 检查仓位限制
        if symbol and order_value and current_positions is not None:
            can_open, position_reason = self.position_checker.can_open_position(
                symbol=symbol,
                order_value=order_value,
                current_positions=current_positions,
                total_capital=self.initial_capital
            )
            
            if not can_open:
                reasons.append(position_reason)
                return RiskCheckResult(
                    can_trade=False,
                    risk_level=RiskLevel.HIGH,
                    reasons=reasons,
                    warnings=warnings
                )
        
        # 综合判断
        can_trade = len(reasons) == 0
        
        return RiskCheckResult(
            can_trade=can_trade,
            risk_level=risk_level,
            reasons=reasons,
            warnings=warnings
        )
    
    def record_trade_success(self):
        """记录交易成功"""
        self.circuit_breaker.record_success()
    
    def record_trade_failure(self):
        """记录交易失败"""
        self.circuit_breaker.record_failure()
    
    def record_realized_pnl(self, pnl: float):
        """
        记录已实现盈亏
        
        Args:
            pnl: 盈亏金额
        """
        self.daily_loss_tracker.record_realized_pnl(pnl)
    
    def get_full_status(self) -> dict:
        """获取完整风控状态"""
        return {
            "initial_capital": self.initial_capital,
            "risk_level": self.check_trade_permission().risk_level.value,
            "circuit_breaker": self.circuit_breaker.get_status(),
            "drawdown_monitor": self.drawdown_monitor.get_status(),
            "daily_loss_tracker": self.daily_loss_tracker.get_status(),
            "position_checker": self.position_checker.get_status(),
        }
    
    def emergency_stop(self, reason: str = "手动紧急停止"):
        """
        紧急停止交易
        
        Args:
            reason: 停止原因
        """
        self.circuit_breaker._transition_to(CircuitState.OPEN)
        self.drawdown_monitor._is_emergency_stop = True
        self.daily_loss_tracker._is_trading_stopped = True
    
    def reset(self, new_initial_capital: Optional[float] = None):
        """
        重置风控系统
        
        Args:
            new_initial_capital: 新的初始资金
        """
        if new_initial_capital:
            self.initial_capital = new_initial_capital
        
        self.circuit_breaker.reset()
        self.drawdown_monitor.reset(new_initial_capital)
        self.daily_loss_tracker.reset()
        self.position_checker.reset_daily_count()
