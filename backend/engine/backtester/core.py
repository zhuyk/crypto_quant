"""
向量化回测引擎核心 (重构版)

修复:
1. 资金计算 Bug (开仓扣除本金, 平仓返还本金+盈亏)
2. 止损/止盈 reason 判断逻辑 (不再依赖 locals())
3. 夏普比率动态适配 timeframe (非硬编码 24h)
4. 仓位管理 (支持百分比仓位, 默认 95% 而非全仓)
5. equity curve 正确估值空头持仓
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from strategies.base import Strategy, Signal, SignalSide, Position
from .report import BacktestReport

logger = logging.getLogger(__name__)

# 时间周期 → 每年包含的 bar 数 (用于年化计算)
BARS_PER_YEAR = {
    "1m": 365 * 24 * 60,
    "5m": 365 * 24 * 12,
    "15m": 365 * 24 * 4,
    "30m": 365 * 24 * 2,
    "1h": 365 * 24,
    "4h": 365 * 6,
    "1d": 365,
    "1w": 52,
}


class Backtester:
    """
    向量化回测引擎
    
    支持：
    - 单策略回测
    - 多策略组合回测
    - 参数优化
    - 可配置仓位比例
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        commission_rate: float = 0.001,
        slippage: float = 0.0005,
        leverage: float = 1.0,
        position_size_pct: float = 0.95,
        timeframe: str = "1h",
    ):
        """
        Args:
            initial_capital: 初始资金
            commission_rate: 手续费率 (0.001 = 0.1%)
            slippage: 滑点 (0.0005 = 0.05%)
            leverage: 杠杆倍数
            position_size_pct: 仓位占可用资金比例 (0.95 = 95%)
            timeframe: 数据时间周期 (用于年化计算)
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage = slippage
        self.leverage = leverage
        self.position_size_pct = position_size_pct
        self.timeframe = timeframe
        
        # 回测状态
        self.capital = initial_capital      # 可用现金
        self.positions: Dict[str, Position] = {}
        self.trades: List[Dict[str, Any]] = []
        self.equity_curve: List[float] = []
        self.current_bar = 0
        
        # 统计
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.gross_profit = 0.0
        self.gross_loss = 0.0
    
    def run(
        self,
        strategy: Strategy,
        data: pd.DataFrame,
        params: Optional[Dict[str, Any]] = None,
    ) -> BacktestReport:
        """执行回测"""
        self._reset()
        
        if params:
            strategy.set_params(params)
        
        if not strategy.validate_data(data):
            raise ValueError("数据格式错误，缺少必要列")
        
        logger.info(f"开始回测 - 策略：{strategy.name}, 数据：{len(data)} 条")
        
        # 滑动窗口大小
        _window = int(strategy.params.get('slow_period', 200)) + 10
        
        # 主回测循环
        for i in range(len(data)):
            self.current_bar = i
            candle = data.iloc[i]
            
            # 历史窗口 (避免 O(n²))
            ws = max(0, i + 1 - _window)
            hist = data.iloc[ws:i+1]
            
            # 1. 更新持仓价格
            self._update_positions_price(candle)
            
            # 2. 检查止损止盈
            self._check_stop_loss_take_profit(candle)
            
            # 3. 生成信号
            signal = strategy.generate_signal(hist)
            
            # 4. 执行交易
            if signal:
                self._execute_signal(signal, candle)
            
            # 5. 记录权益
            self._record_equity(candle)
            
            # 6. K 线回调
            strategy.on_bar(candle)
        
        # 结束时强制平仓
        self._close_all_positions(data.iloc[-1])
        
        # 生成报告
        report = self._generate_report(strategy)
        logger.info(f"回测完成 - 收益率：{report.total_return:.2%}, 夏普：{report.sharpe_ratio:.2f}")
        
        return report
    
    def _reset(self):
        """重置状态"""
        self.capital = self.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []
        self.current_bar = 0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.gross_profit = 0.0
        self.gross_loss = 0.0
    
    def _update_positions_price(self, candle: pd.Series):
        """更新持仓当前价格（按各持仓 symbol 匹配）"""
        price = candle['close']
        candle_symbol = candle.get('symbol', None)
        
        for pos in self.positions.values():
            # 如果 candle 有 symbol 信息，只更新匹配的持仓
            # 如果没有 symbol 信息（单币种回测），更新所有
            if candle_symbol is None or pos.symbol == candle_symbol:
                pos.current_price = price
    
    def _check_stop_loss_take_profit(self, candle: pd.Series):
        """检查止损止盈"""
        to_close = []
        price = candle['close']
        candle_symbol = candle.get('symbol', None)
        
        for symbol, pos in self.positions.items():
            # 多币种回测时，只检查当前 candle 对应的持仓
            if candle_symbol is not None and pos.symbol != candle_symbol:
                continue
            
            reason = None
            
            # 止损检查
            if pos.stop_loss:
                if pos.side == SignalSide.LONG and price <= pos.stop_loss:
                    reason = "stop_loss"
                elif pos.side == SignalSide.SHORT and price >= pos.stop_loss:
                    reason = "stop_loss"
            
            # 止盈检查 (止损未触发时才检查止盈)
            if reason is None and pos.take_profit:
                if pos.side == SignalSide.LONG and price >= pos.take_profit:
                    reason = "take_profit"
                elif pos.side == SignalSide.SHORT and price <= pos.take_profit:
                    reason = "take_profit"
            
            if reason:
                to_close.append((symbol, price, reason))
        
        for symbol, price, reason in to_close:
            self._close_position(symbol, price, reason)
    
    def _execute_signal(self, signal: Signal, candle: pd.Series):
        """执行交易信号"""
        symbol = signal.symbol
        price = candle['close']
        
        # 平仓信号
        if signal.side == SignalSide.CLOSE:
            if symbol in self.positions:
                exec_price = price * (1 - self.slippage) if self.positions[symbol].side == SignalSide.LONG else price * (1 + self.slippage)
                self._close_position(symbol, exec_price, "signal")
            return
        
        # 已有持仓则忽略
        if symbol in self.positions:
            return
        
        # 计算执行价格 (含滑点)
        if signal.side == SignalSide.LONG:
            exec_price = price * (1 + self.slippage)
        else:
            exec_price = price * (1 - self.slippage)
        
        # 计算仓位
        available = self.capital * self.position_size_pct * self.leverage
        if available <= 0:
            return
        
        quantity = available / exec_price
        position_cost = quantity * exec_price  # 持仓成本
        commission = position_cost * self.commission_rate
        
        # 检查资金是否足够
        total_cost = position_cost + commission
        if total_cost > self.capital:
            # 资金不足，缩小仓位
            available = self.capital - commission
            if available <= 0:
                return
            quantity = available / exec_price
            position_cost = quantity * exec_price
            commission = position_cost * self.commission_rate
        
        # 扣除本金 + 手续费 (核心修复: 开仓时扣除持仓成本)
        self.capital -= (position_cost + commission)
        
        # 创建持仓
        position = Position(
            symbol=symbol,
            side=signal.side,
            quantity=quantity,
            entry_price=exec_price,
            current_price=exec_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
        )
        self.positions[symbol] = position
        
        # 记录开仓交易
        self.trades.append({
            'symbol': symbol,
            'side': signal.side.value,
            'action': 'open',
            'price': exec_price,
            'quantity': quantity,
            'value': position_cost,
            'commission': commission,
            'bar': self.current_bar,
        })
    
    def _close_position(self, symbol: str, close_price: float, reason: str):
        """平仓"""
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        
        # 应用滑点到平仓价
        if pos.side == SignalSide.LONG:
            exec_price = close_price * (1 - self.slippage)
        else:
            exec_price = close_price * (1 + self.slippage)
        
        # 计算盈亏
        if pos.side == SignalSide.LONG:
            pnl = (exec_price - pos.entry_price) * pos.quantity
        else:
            pnl = (pos.entry_price - exec_price) * pos.quantity
        
        # 平仓手续费
        close_value = exec_price * pos.quantity
        commission = close_value * self.commission_rate
        
        # 返还资金: 原始持仓成本 + 盈亏 - 平仓手续费
        # (核心修复: 开仓时扣了 entry_price * quantity, 平仓时返回实际价值)
        returned = pos.entry_price * pos.quantity + pnl - commission
        self.capital += returned
        
        # 统计
        net_pnl = pnl - commission  # 扣除平仓手续费的净盈亏
        self.total_trades += 1
        if net_pnl > 0:
            self.winning_trades += 1
            self.gross_profit += net_pnl
        else:
            self.losing_trades += 1
            self.gross_loss += abs(net_pnl)
        
        # 记录平仓交易
        self.trades.append({
            'symbol': symbol,
            'side': pos.side.value,
            'action': 'close',
            'entry_price': pos.entry_price,
            'exit_price': exec_price,
            'quantity': pos.quantity,
            'pnl': net_pnl,
            'pnl_pct': net_pnl / (pos.entry_price * pos.quantity) if pos.entry_price > 0 else 0,
            'commission': commission,
            'bar': self.current_bar,
            'exit_reason': reason,
        })
        
        del self.positions[symbol]
    
    def _close_all_positions(self, last_candle: pd.Series):
        """强制平仓所有持仓"""
        for symbol in list(self.positions.keys()):
            self._close_position(symbol, last_candle['close'], 'end_of_backtest')
    
    def _record_equity(self, candle: pd.Series):
        """
        记录权益曲线
        
        总权益 = 可用现金 + 所有持仓的市值
        (修复: 空头持仓正确计算浮动盈亏)
        """
        position_value = 0.0
        price = candle['close']
        
        for pos in self.positions.values():
            if pos.side == SignalSide.LONG:
                # 多头: 市值 = 当前价 * 数量
                position_value += price * pos.quantity
            else:
                # 空头: 市值 = 入场价 * 数量 + 浮动盈亏
                # 浮动盈亏 = (entry - current) * quantity
                unrealized_pnl = (pos.entry_price - price) * pos.quantity
                position_value += pos.entry_price * pos.quantity + unrealized_pnl
        
        total_equity = self.capital + position_value
        self.equity_curve.append(total_equity)
    
    def _generate_report(self, strategy: Strategy) -> BacktestReport:
        """生成回测报告"""
        equity = pd.Series(self.equity_curve)
        
        if len(equity) < 2:
            return self._empty_report(strategy)
        
        # 收益率序列
        returns = equity.pct_change().dropna()
        
        # 总收益率
        total_return = (equity.iloc[-1] - equity.iloc[0]) / equity.iloc[0]
        
        # 年化收益率 (根据实际 timeframe 动态计算)
        bars_year = BARS_PER_YEAR.get(self.timeframe, 365 * 24)
        n_bars = len(equity)
        years = n_bars / bars_year
        annual_return = (1 + total_return) ** (1 / max(years, 0.01)) - 1 if total_return > -1 else -1
        
        # 夏普比率 (修复: 根据 timeframe 年化)
        if returns.std() > 0 and len(returns) > 10:
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(bars_year)
        else:
            sharpe_ratio = 0.0
        
        # 最大回撤
        max_drawdown = self._calculate_max_drawdown(equity)
        
        # 胜率
        win_rate = self.winning_trades / max(self.total_trades, 1)
        
        # 盈亏比
        if self.gross_loss > 0:
            profit_factor = self.gross_profit / self.gross_loss
        else:
            profit_factor = float('inf') if self.gross_profit > 0 else 0.0
        
        # 平均盈亏
        close_trades = [t for t in self.trades if t.get('action') == 'close']
        avg_pnl = np.mean([t['pnl'] for t in close_trades]) if close_trades else 0.0
        
        return BacktestReport(
            strategy_name=strategy.name,
            initial_capital=self.initial_capital,
            final_capital=equity.iloc[-1],
            total_return=total_return,
            annual_return=annual_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=min(profit_factor, 999.99),
            total_trades=self.total_trades,
            winning_trades=self.winning_trades,
            losing_trades=self.losing_trades,
            avg_trade_pnl=avg_pnl,
            equity_curve=equity.tolist(),
            trades=close_trades,
        )
    
    def _calculate_max_drawdown(self, equity: pd.Series) -> float:
        """计算最大回撤"""
        peak = equity.expanding().max()
        drawdown = (equity - peak) / peak
        return abs(drawdown.min()) if len(drawdown) > 0 else 0.0
    
    def _empty_report(self, strategy: Strategy) -> BacktestReport:
        """数据不足时返回空报告"""
        return BacktestReport(
            strategy_name=strategy.name,
            initial_capital=self.initial_capital,
            final_capital=self.initial_capital,
            total_return=0.0,
            annual_return=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            avg_trade_pnl=0.0,
            equity_curve=[self.initial_capital],
            trades=[],
        )
