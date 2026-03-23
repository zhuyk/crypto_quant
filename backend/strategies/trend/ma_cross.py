"""
双均线交叉趋势策略
"""
import pandas as pd
import numpy as np
from typing import Optional
from strategies.base import Strategy, Signal, SignalSide, SignalType


class MACrossStrategy(Strategy):
    """双均线交叉趋势策略"""
    
    # 策略元数据
    name = "ma_cross"
    category = "trend"
    version = "1.0.0"
    author = "CryptoQuant"
    description = "基于快慢均线交叉的趋势跟踪策略"
    
    # 支持的时间周期
    timeframes = ["15m", "1h", "4h", "1d"]
    
    # 默认参数
    params = {
        "fast_period": 20,      # 快线周期
        "slow_period": 60,      # 慢线周期
        "stop_loss_pct": 0.05,  # 止损百分比
        "take_profit_pct": 0.15, # 止盈百分比
        "use_ema": False,       # 使用 EMA 而非 SMA
        "min_strength": 0.3,    # 最小信号强度
    }
    
    def on_init(self):
        """策略初始化"""
        self._last_fast_ma = None
        self._last_slow_ma = None
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """
        生成双均线交叉信号
        
        金叉 (快线上穿慢线) -> 做多
        死叉 (快线下穿慢线) -> 平仓/做空
        """
        if not self.validate_data(data):
            return None
        
        # 检查数据长度
        if len(data) < self.params["slow_period"]:
            return None
        
        close = data["close"]
        
        # 计算均线
        if self.params.get("use_ema", False):
            fast_ma = close.ewm(span=self.params["fast_period"], adjust=False).mean()
            slow_ma = close.ewm(span=self.params["slow_period"], adjust=False).mean()
        else:
            fast_ma = close.rolling(self.params["fast_period"]).mean()
            slow_ma = close.rolling(self.params["slow_period"]).mean()
        
        # 获取当前和前一根 K 线的均线值
        current_fast = fast_ma.iloc[-1]
        current_slow = slow_ma.iloc[-1]
        prev_fast = fast_ma.iloc[-2]
        prev_slow = slow_ma.iloc[-2]
        
        # 保存当前值用于下次比较
        self._last_fast_ma = current_fast
        self._last_slow_ma = current_slow
        
        current_price = close.iloc[-1]
        symbol = data.get("symbol", ["UNKNOWN"]).iloc[-1] if "symbol" in data.columns else "UNKNOWN"
        
        # 金叉 - 做多信号
        if prev_fast <= prev_slow and current_fast > current_slow:
            strength = self._calculate_strength(data, "bullish")
            
            if strength < self.params.get("min_strength", 0.3):
                return None
            
            stop_loss = current_price * (1 - self.params["stop_loss_pct"])
            take_profit = current_price * (1 + self.params["take_profit_pct"])
            
            return Signal(
                symbol=symbol,
                side=SignalSide.LONG,
                signal_type=SignalType.ENTRY,
                price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strength=strength,
                metadata={
                    "fast_ma": current_fast,
                    "slow_ma": current_slow,
                    "cross_type": "golden",
                }
            )
        
        # 死叉 - 平仓信号
        elif prev_fast >= prev_slow and current_fast < current_slow:
            strength = self._calculate_strength(data, "bearish")
            
            if strength < self.params.get("min_strength", 0.3):
                return None
            
            return Signal(
                symbol=symbol,
                side=SignalSide.CLOSE,
                signal_type=SignalType.EXIT,
                price=current_price,
                strength=strength,
                metadata={
                    "fast_ma": current_fast,
                    "slow_ma": current_slow,
                    "cross_type": "death",
                }
            )
        
        return None
    
    def _calculate_strength(self, data: pd.DataFrame, market_state: str) -> float:
        """
        计算信号强度
        
        基于:
        1. 均线价差比例
        2. 均线斜率
        3. 成交量
        4. 波动率
        """
        close = data["close"]
        volume = data["volume"]
        
        # 1. 均线价差比例
        fast_ma = close.rolling(self.params["fast_period"]).mean()
        slow_ma = close.rolling(self.params["slow_period"]).mean()
        diff_ratio = abs(fast_ma.iloc[-1] - slow_ma.iloc[-1]) / slow_ma.iloc[-1]
        diff_score = min(1.0, diff_ratio * 20)  # 归一化到 0-1
        
        # 2. 均线斜率
        fast_slope = (fast_ma.iloc[-1] - fast_ma.iloc[-5]) / fast_ma.iloc[-5]
        slope_score = min(1.0, abs(fast_slope) * 50)
        
        # 3. 成交量放大
        avg_volume = volume.rolling(20).mean()
        volume_ratio = volume.iloc[-1] / avg_volume.iloc[-1]
        volume_score = min(1.0, (volume_ratio - 1) * 0.5)
        
        # 4. 波动率
        returns = close.pct_change()
        volatility = returns.rolling(20).std().iloc[-1]
        volatility_score = min(1.0, volatility * 10)
        
        # 综合评分 (加权平均)
        weights = [0.4, 0.3, 0.2, 0.1]
        strength = (
            weights[0] * diff_score +
            weights[1] * slope_score +
            weights[2] * max(0, volume_score) +
            weights[3] * volatility_score
        )
        
        return min(1.0, max(0.0, strength))
    
    def on_bar(self, candle: pd.Series):
        """K 线更新回调 - 可用于更新内部状态"""
        # 这里可以添加止损止盈检查逻辑
        if self._positions:
            for symbol, position in self._positions.items():
                current_price = candle["close"]
                position.current_price = current_price
                
                # 检查止损
                if position.stop_loss and current_price <= position.stop_loss:
                    # 触发止损 - 可以在这里生成平仓信号
                    pass
                
                # 检查止盈
                if position.take_profit and current_price >= position.take_profit:
                    # 触发止盈
                    pass
