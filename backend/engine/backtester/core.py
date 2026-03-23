"""
向量化回测引擎核心
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from strategies.base import Strategy, Signal, SignalSide, Position
from .report import BacktestReport

logger = logging.getLogger(__name__)


class Backtester:
    """
    向量化回测引擎
    
    支持：
    - 单策略回测
    - 多策略组合回测
    - 参数优化
    - 多币种回测
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        commission_rate: float = 0.001,  # 手续费 0.1%
        slippage: float = 0.0005,  # 滑点 0.05%
        leverage: float = 1.0,  # 杠杆倍数
    ):
        """
        初始化回测引擎
        
        Args:
            initial_capital: 初始资金
            commission_rate: 手续费率
            slippage: 滑点
            leverage: 杠杆倍数
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage = slippage
        self.leverage = leverage
        
        # 回测状态
        self.capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = []
        self.current_bar = 0
        
        # 统计指标
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
        """
        执行回测
        
        Args:
            strategy: 策略实例
            data: K 线数据 (columns: open, high, low, close, volume, timestamp)
            params: 策略参数
        
        Returns:
            BacktestReport: 回测报告
        """
        # 重置状态
        self._reset()
        
        # 设置策略参数
        if params:
            strategy.set_params(params)
        
        logger.info(f"开始回测 - 策略：{strategy.name}, 数据条数：{len(data)}")
        
        # 验证数据
        if not strategy.validate_data(data):
            raise ValueError("数据格式错误，缺少必要列")
        
        # 主回测循环
        for i in range(len(data)):
            self.current_bar = i
            current_candle = data.iloc[i]
            historical_data = data.iloc[:i+1]
            
            # 更新持仓的当前价格
            self._update_positions_price(current_candle)
            
            # 检查止损止盈
            self._check_stop_loss_take_profit(current_candle)
            
            # 生成信号
            signal = strategy.generate_signal(historical_data)
            
            # 执行交易
            if signal:
                self._execute_signal(signal, current_candle)
            
            # 记录权益
            self._record_equity(current_candle)
            
            # K 线更新回调
            strategy.on_bar(current_candle)
        
        # 平仓所有持仓
        self._close_all_positions(data.iloc[-1])
        
        # 生成报告
        report = self._generate_report(strategy)
        logger.info(f"回测完成 - 总收益率：{report.total_return:.2%}, 夏普比率：{report.sharpe_ratio:.2f}")
        
        return report
    
    def _reset(self):
        """重置回测状态"""
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
        """更新持仓的当前价格"""
        for position in self.positions.values():
            position.current_price = candle['close']
    
    def _check_stop_loss_take_profit(self, candle: pd.Series):
        """检查止损止盈"""
        symbols_to_close = []
        
        for symbol, position in self.positions.items():
            should_close = False
            close_price = candle['close']
            
            # 检查止损
            if position.stop_loss:
                if position.side == SignalSide.LONG and close_price <= position.stop_loss:
                    should_close = True
                elif position.side == SignalSide.SHORT and close_price >= position.stop_loss:
                    should_close = True
            
            # 检查止盈
            if position.take_profit and not should_close:
                if position.side == SignalSide.LONG and close_price >= position.take_profit:
                    should_close = True
                elif position.side == SignalSide.SHORT and close_price <= position.take_profit:
                    should_close = True
            
            if should_close:
                symbols_to_close.append((symbol, close_price, 'stop_loss' if 'stop_loss' in locals() else 'take_profit'))
        
        # 执行平仓
        for symbol, close_price, reason in symbols_to_close:
            self._close_position(symbol, close_price, reason)
    
    def _execute_signal(self, signal: Signal, candle: pd.Series):
        """执行交易信号"""
        symbol = signal.symbol
        current_price = candle['close']
        
        # 应用滑点
        if signal.side == SignalSide.LONG:
            exec_price = current_price * (1 + self.slippage)
        else:
            exec_price = current_price * (1 - self.slippage)
        
        # 平仓信号
        if signal.side == SignalSide.CLOSE:
            if symbol in self.positions:
                self._close_position(symbol, exec_price, 'signal')
            return
        
        # 开仓信号
        if symbol not in self.positions:
            # 计算仓位大小 (简单版本：全仓)
            position_value = self.capital * self.leverage
            quantity = position_value / exec_price
            
            # 计算手续费
            commission = position_value * self.commission_rate
            
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
            self.capital -= commission  # 扣除手续费
            
            # 记录交易
            self._record_trade(signal, exec_price, quantity, commission, 'open')
            
            # 回调
            strategy = None  # 需要传入策略实例
            if strategy:
                strategy.on_position_opened(position)
        else:
            # 已有持仓，可能是加仓或反向信号
            logger.debug(f"符号 {symbol} 已有持仓，忽略信号")
    
    def _close_position(self, symbol: str, close_price: float, reason: str):
        """平仓"""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        
        # 计算盈亏
        if position.side == SignalSide.LONG:
            pnl = (close_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - close_price) * position.quantity
        
        # 应用滑点
        if position.side == SignalSide.LONG:
            exec_price = close_price * (1 - self.slippage)
        else:
            exec_price = close_price * (1 + self.slippage)
        
        # 计算手续费
        position_value = exec_price * position.quantity
        commission = position_value * self.commission_rate
        
        # 更新资金
        self.capital += pnl - commission
        self.capital += position.entry_price * position.quantity  # 返还本金
        
        # 统计
        self.total_trades += 1
        if pnl > 0:
            self.winning_trades += 1
            self.gross_profit += pnl
        else:
            self.losing_trades += 1
            self.gross_loss += abs(pnl)
        
        # 记录交易
        trade_record = {
            'symbol': symbol,
            'side': position.side.value,
            'entry_price': position.entry_price,
            'exit_price': exec_price,
            'quantity': position.quantity,
            'pnl': pnl,
            'pnl_pct': pnl / (position.entry_price * position.quantity),
            'commission': commission,
            'entry_bar': 0,  # TODO: 记录入场 bar
            'exit_bar': self.current_bar,
            'exit_reason': reason,
            'timestamp': datetime.now(),
        }
        self.trades.append(trade_record)
        
        # 移除持仓
        del self.positions[symbol]
        
        logger.debug(f"平仓 {symbol}: 盈亏={pnl:.2f}, 原因={reason}")
    
    def _close_all_positions(self, last_candle: pd.Series):
        """平仓所有持仓"""
        for symbol in list(self.positions.keys()):
            self._close_position(symbol, last_candle['close'], 'end_of_backtest')
    
    def _record_equity(self, candle: pd.Series):
        """记录权益曲线"""
        # 计算当前总权益
        position_value = sum(
            p.quantity * candle['close'] if p.side == SignalSide.LONG else p.quantity * p.entry_price
            for p in self.positions.values()
        )
        total_equity = self.capital + position_value
        
        self.equity_curve.append({
            'bar': self.current_bar,
            'timestamp': candle.get('timestamp', datetime.now()),
            'capital': self.capital,
            'position_value': position_value,
            'total_equity': total_equity,
        })
    
    def _record_trade(self, signal: Signal, price: float, quantity: float, commission: float, action: str):
        """记录交易"""
        trade_record = {
            'symbol': signal.symbol,
            'side': signal.side.value,
            'action': action,
            'price': price,
            'quantity': quantity,
            'commission': commission,
            'bar': self.current_bar,
            'timestamp': datetime.now(),
        }
        self.trades.append(trade_record)
    
    def _generate_report(self, strategy: Strategy) -> BacktestReport:
        """生成回测报告"""
        equity_series = pd.Series([e['total_equity'] for e in self.equity_curve])
        
        # 计算收益率序列
        returns = equity_series.pct_change().dropna()
        
        # 总收益率
        total_return = (equity_series.iloc[-1] - equity_series.iloc[0]) / equity_series.iloc[0]
        
        # 年化收益率 (假设 365 天)
        days = len(equity_series) / 24  # 假设小时数据
        annual_return = (1 + total_return) ** (365 / max(days, 1)) - 1
        
        # 夏普比率 (假设无风险利率为 0)
        if returns.std() > 0:
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)  # 年化
        else:
            sharpe_ratio = 0.0
        
        # 最大回撤
        max_drawdown = self._calculate_max_drawdown(equity_series)
        
        # 胜率
        win_rate = self.winning_trades / max(self.total_trades, 1)
        
        # 盈亏比
        if self.losing_trades > 0:
            profit_factor = self.gross_profit / self.gross_loss
        else:
            profit_factor = float('inf') if self.gross_profit > 0 else 0.0
        
        # 平均盈亏
        avg_trade_pnl = np.mean([t.get('pnl', 0) for t in self.trades if 'pnl' in t]) if self.trades else 0.0
        
        return BacktestReport(
            strategy_name=strategy.name,
            initial_capital=self.initial_capital,
            final_capital=equity_series.iloc[-1],
            total_return=total_return,
            annual_return=annual_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=self.total_trades,
            winning_trades=self.winning_trades,
            losing_trades=self.losing_trades,
            avg_trade_pnl=avg_trade_pnl,
            equity_curve=equity_series.tolist(),
            trades=self.trades,
        )
    
    def _calculate_max_drawdown(self, equity_series: pd.Series) -> float:
        """计算最大回撤"""
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max
        return abs(drawdown.min()) if len(drawdown) > 0 else 0.0
