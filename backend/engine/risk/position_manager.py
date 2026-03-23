#!/usr/bin/env python3
"""
仓位管理模块
实现资金管理、风险控制、仓位计算等功能
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger
from enum import Enum


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class PositionConfig:
    """仓位配置"""
    # 基础配置
    initial_capital: float = 100000.0
    max_position_ratio: float = 0.2  # 单个仓位最大占总资金比例
    max_total_exposure: float = 0.8  # 最大总仓位比例
    max_daily_loss: float = 0.05  # 最大日亏损比例
    max_drawdown: float = 0.20  # 最大回撤比例
    
    # 止损止盈
    default_stop_loss: float = 0.05  # 默认止损 5%
    default_take_profit: float = 0.15  # 默认止盈 15%
    trailing_stop: bool = True  # 启用移动止损
    trailing_stop_pct: float = 0.03  # 移动止损比例
    
    # 仓位调整
    position_sizing_method: str = "fixed_ratio"  # fixed_ratio/kelly/volatility
    kelly_fraction: float = 0.25  # Kelly 公式分数（降低风险）
    
    # 风险控制
    max_correlation: float = 0.7  # 最大相关性
    max_sector_exposure: float = 0.3  # 最大行业暴露
    max_leverage: float = 1.0  # 最大杠杆


@dataclass
class RiskMetrics:
    """风险指标"""
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    daily_pnl: float = 0.0
    daily_pnl_pct: float = 0.0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    var_95: float = 0.0  # 95% VaR
    exposure: float = 0.0  # 当前暴露度
    correlation_risk: float = 0.0  # 相关性风险
    
    def get_risk_level(self) -> RiskLevel:
        """评估当前风险等级"""
        if self.current_drawdown > 0.15 or self.daily_pnl_pct < -0.05:
            return RiskLevel.EXTREME
        elif self.current_drawdown > 0.10 or self.daily_pnl_pct < -0.03:
            return RiskLevel.HIGH
        elif self.current_drawdown > 0.05 or self.daily_pnl_pct < -0.02:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW


class PositionManager:
    """仓位管理器"""
    
    def __init__(self, config: PositionConfig = None):
        self.config = config or PositionConfig()
        self.initial_capital = self.config.initial_capital
        self.capital = self.config.initial_capital
        self.peak_capital = self.config.initial_capital
        
        # 持仓记录
        self.positions: Dict[str, Dict] = {}
        
        # 交易历史
        self.trade_history: List[Dict] = []
        
        # 每日盈亏
        self.daily_pnl: Dict[str, float] = {}
        
        # 权益曲线
        self.equity_curve: List[Dict] = []
        
        logger.info("✅ 仓位管理器初始化完成")
    
    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss_price: Optional[float] = None,
        volatility: Optional[float] = None,
        win_rate: Optional[float] = None,
        avg_win_loss_ratio: Optional[float] = None,
    ) -> float:
        """
        计算仓位大小
        
        Args:
            symbol: 交易对
            entry_price: 入场价格
            stop_loss_price: 止损价格
            volatility: 波动率 (可选)
            win_rate: 胜率 (可选，用于 Kelly 公式)
            avg_win_loss_ratio: 盈亏比 (可选，用于 Kelly 公式)
        
        Returns:
            仓位大小 (数量)
        """
        method = self.config.position_sizing_method
        
        if method == "fixed_ratio":
            size = self._fixed_ratio_size(entry_price)
        elif method == "kelly":
            size = self._kelly_size(entry_price, win_rate, avg_win_loss_ratio)
        elif method == "volatility":
            size = self._volatility_size(entry_price, volatility)
        elif method == "risk_parity":
            size = self._risk_parity_size(entry_price, stop_loss_price)
        else:
            size = self._fixed_ratio_size(entry_price)
        
        # 应用最大仓位限制
        max_size = self._get_max_position_size(entry_price)
        size = min(size, max_size)
        
        # 检查剩余可用资金
        available = self.get_available_capital()
        required = size * entry_price
        if required > available:
            size = available / entry_price
            logger.warning(f"⚠️  资金不足，调整仓位大小：{size}")
        
        return round(size, 8)  # 保留 8 位小数 (加密货币精度)
    
    def _fixed_ratio_size(self, price: float) -> float:
        """固定比例仓位计算"""
        if price <= 0:
            logger.warning(f"无效价格：{price}，返回 0")
            return 0.0
        
        position_value = self.capital * self.config.max_position_ratio
        return position_value / price
    
    def _kelly_size(
        self,
        price: float,
        win_rate: Optional[float] = None,
        avg_win_loss_ratio: Optional[float] = None,
    ) -> float:
        """Kelly 公式仓位计算"""
        if price <= 0:
            logger.warning(f"无效价格：{price}，返回 0")
            return 0.0
        
        if win_rate is None or avg_win_loss_ratio is None:
            # 默认值
            win_rate = 0.5
            avg_win_loss_ratio = 2.0
        
        # Kelly 公式：f = W - (1-W)/R
        kelly_pct = win_rate - (1 - win_rate) / avg_win_loss_ratio
        
        # 应用 Kelly 分数 (降低风险)
        kelly_pct *= self.config.kelly_fraction
        
        # 确保不超过最大仓位
        kelly_pct = min(kelly_pct, self.config.max_position_ratio)
        kelly_pct = max(kelly_pct, 0)  # 不允许负仓位
        
        position_value = self.capital * kelly_pct
        return position_value / price
    
    def _volatility_size(self, price: float, volatility: Optional[float] = None) -> float:
        """基于波动率的仓位计算 (波动率越大，仓位越小)"""
        if price <= 0:
            logger.warning(f"无效价格：{price}，返回 0")
            return 0.0
        
        if volatility is None:
            volatility = 0.05  # 默认 5% 波动率
        
        # 目标风险：固定金额风险
        target_risk = self.capital * 0.01  # 每笔交易风险 1%
        
        # 基于波动率调整仓位
        if volatility > 0:
            position_value = target_risk / volatility
        else:
            position_value = self.capital * self.config.max_position_ratio
        
        return position_value / price
    
    def _risk_parity_size(
        self,
        price: float,
        stop_loss_price: Optional[float] = None,
    ) -> float:
        """风险平价仓位计算 (基于止损距离)"""
        if price <= 0:
            logger.warning(f"无效价格：{price}，返回 0")
            return 0.0
        
        if stop_loss_price is None:
            return self._fixed_ratio_size(price)
        
        # 计算止损距离
        risk_distance = abs(price - stop_loss_price) / price
        
        if risk_distance > 0:
            # 固定风险金额
            risk_amount = self.capital * 0.01  # 每笔交易风险 1%
            position_value = risk_amount / risk_distance
        else:
            position_value = self.capital * self.config.max_position_ratio
        
        return position_value / price
    
    def _get_max_position_size(self, price: float) -> float:
        """获取最大允许仓位大小"""
        max_value = self.capital * self.config.max_position_ratio
        return max_value / price
    
    def get_available_capital(self) -> float:
        """获取可用资金"""
        used_capital = sum(
            pos.get("amount", 0) * pos.get("entry_price", 0)
            for pos in self.positions.values()
        )
        return self.capital - used_capital
    
    def get_total_exposure(self) -> float:
        """获取总暴露度"""
        total_value = sum(
            pos.get("amount", 0) * pos.get("current_price", pos.get("entry_price", 0))
            for pos in self.positions.values()
        )
        return total_value / self.capital
    
    def can_open_position(self, symbol: str, price: float) -> Tuple[bool, str]:
        """
        检查是否可以开仓
        
        Returns:
            (是否允许，原因)
        """
        # 检查是否已有该仓位
        if symbol in self.positions:
            return False, f"已有 {symbol} 持仓"
        
        # 检查总暴露度
        current_exposure = self.get_total_exposure()
        new_exposure = (price * self._fixed_ratio_size(price)) / self.capital
        
        if current_exposure + new_exposure > self.config.max_total_exposure:
            return False, f"总暴露度过高 ({current_exposure:.2%})"
        
        # 检查日亏损
        today = datetime.now().strftime("%Y-%m-%d")
        daily_pnl = self.daily_pnl.get(today, 0)
        daily_pnl_pct = daily_pnl / self.capital
        
        if daily_pnl_pct < -self.config.max_daily_loss:
            return False, f"已达到日亏损限制 ({daily_pnl_pct:.2%})"
        
        # 检查回撤
        drawdown = (self.peak_capital - self.capital) / self.peak_capital
        if drawdown > self.config.max_drawdown:
            return False, f"已达到最大回撤限制 ({drawdown:.2%})"
        
        return True, "允许开仓"
    
    def add_position(
        self,
        symbol: str,
        side: str,
        amount: float,
        entry_price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict:
        """添加持仓"""
        position = {
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "entry_price": entry_price,
            "current_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "opened_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        
        self.positions[symbol] = position
        logger.info(f"✅ 开仓 - {symbol} {side} {amount} @ ${entry_price}")
        
        return position
    
    def update_position_price(self, symbol: str, current_price: float):
        """更新持仓价格"""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        position["current_price"] = current_price
        position["updated_at"] = datetime.now().isoformat()
        
        # 计算未实现盈亏
        if position["side"] == "buy":
            pnl = (current_price - position["entry_price"]) * position["amount"]
            pnl_pct = (current_price - position["entry_price"]) / position["entry_price"] * 100
        else:
            pnl = (position["entry_price"] - current_price) * position["amount"]
            pnl_pct = (position["entry_price"] - current_price) / position["entry_price"] * 100
        
        position["unrealized_pnl"] = pnl
        position["unrealized_pnl_pct"] = pnl_pct
        
        # 检查止损止盈
        self._check_stop_loss_take_profit(symbol, current_price)
    
    def _check_stop_loss_take_profit(self, symbol: str, current_price: float):
        """检查止损止盈触发"""
        position = self.positions[symbol]
        
        stop_loss = position.get("stop_loss")
        take_profit = position.get("take_profit")
        
        triggered = None
        
        if stop_loss and current_price <= stop_loss:
            triggered = "stop_loss"
        elif take_profit and current_price >= take_profit:
            triggered = "take_profit"
        
        if triggered:
            logger.warning(f"⚠️  {triggered} 触发 - {symbol} @ ${current_price}")
            # 这里可以触发自动平仓
            # self.close_position(symbol)
    
    def close_position(
        self,
        symbol: str,
        exit_price: float,
    ) -> Dict:
        """平仓"""
        if symbol not in self.positions:
            return {"error": "Position not found"}
        
        position = self.positions[symbol]
        
        # 计算已实现盈亏
        if position["side"] == "buy":
            pnl = (exit_price - position["entry_price"]) * position["amount"]
        else:
            pnl = (position["entry_price"] - exit_price) * position["amount"]
        
        # 更新资金
        self.capital += pnl
        
        # 更新峰值资金
        if self.capital > self.peak_capital:
            self.peak_capital = self.capital
        
        # 记录交易历史
        trade = {
            "symbol": symbol,
            "side": position["side"],
            "entry_price": position["entry_price"],
            "exit_price": exit_price,
            "amount": position["amount"],
            "pnl": pnl,
            "pnl_pct": pnl / (position["entry_price"] * position["amount"]) * 100,
            "opened_at": position["opened_at"],
            "closed_at": datetime.now().isoformat(),
        }
        self.trade_history.append(trade)
        
        # 更新每日盈亏
        today = datetime.now().strftime("%Y-%m-%d")
        self.daily_pnl[today] = self.daily_pnl.get(today, 0) + pnl
        
        # 记录权益曲线
        self.equity_curve.append({
            "timestamp": datetime.now().isoformat(),
            "capital": self.capital,
            "pnl": pnl,
        })
        
        # 移除持仓
        del self.positions[symbol]
        
        logger.info(f"✅ 平仓 - {symbol} 盈亏：${pnl:.2f} ({pnl/position['entry_price']/position['amount']*100:.2f}%)")
        
        return trade
    
    def get_risk_metrics(self) -> RiskMetrics:
        """计算风险指标"""
        # 当前回撤
        current_drawdown = (self.peak_capital - self.capital) / self.peak_capital
        
        # 总盈亏
        total_pnl = self.capital - self.initial_capital
        total_pnl_pct = total_pnl / self.initial_capital * 100
        
        # 今日盈亏
        today = datetime.now().strftime("%Y-%m-%d")
        daily_pnl = self.daily_pnl.get(today, 0)
        daily_pnl_pct = daily_pnl / self.capital * 100
        
        # 胜率
        winning_trades = sum(1 for t in self.trade_history if t["pnl"] > 0)
        total_trades = len(self.trade_history)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # 盈亏比
        winning_pnl = sum(t["pnl"] for t in self.trade_history if t["pnl"] > 0)
        losing_pnl = abs(sum(t["pnl"] for t in self.trade_history if t["pnl"] < 0))
        profit_factor = winning_pnl / losing_pnl if losing_pnl > 0 else 0
        
        # 暴露度
        exposure = self.get_total_exposure()
        
        return RiskMetrics(
            current_drawdown=current_drawdown,
            max_drawdown=self.config.max_drawdown,
            daily_pnl=daily_pnl,
            daily_pnl_pct=daily_pnl_pct,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            win_rate=win_rate,
            profit_factor=profit_factor,
            sharpe_ratio=0.0,  # TODO: 计算夏普比率
            var_95=0.0,  # TODO: 计算 VaR
            exposure=exposure,
            correlation_risk=0.0,  # TODO: 计算相关性风险
        )
    
    def get_portfolio_summary(self) -> Dict:
        """获取投资组合汇总"""
        metrics = self.get_risk_metrics()
        
        return {
            "capital": self.capital,
            "initial_capital": self.initial_capital,
            "peak_capital": self.peak_capital,
            "available_capital": self.get_available_capital(),
            "total_exposure": metrics.exposure,
            "open_positions": len(self.positions),
            "positions": list(self.positions.values()),
            "total_trades": len(self.trade_history),
            "win_rate": metrics.win_rate,
            "profit_factor": metrics.profit_factor,
            "total_pnl": metrics.total_pnl,
            "total_pnl_pct": metrics.total_pnl_pct,
            "daily_pnl": metrics.daily_pnl,
            "daily_pnl_pct": metrics.daily_pnl_pct,
            "current_drawdown": metrics.current_drawdown,
            "risk_level": metrics.get_risk_level().value,
        }
