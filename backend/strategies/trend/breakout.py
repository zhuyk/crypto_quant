"""
突破策略 - Donchian Channel
"""
import pandas as pd
import numpy as np
from typing import Optional
import logging

from strategies.base import Strategy, Signal, SignalSide, SignalType

logger = logging.getLogger(__name__)


class BreakoutStrategy(Strategy):
    """
    通道突破策略
    
    使用 Donchian Channel (唐奇安通道) 识别突破信号：
    - 向上突破上轨：做多
    - 向下跌破下轨：做空
    """
    
    name = "breakout"
    category = "trend"
    version = "1.0.0"
    author = "CryptoQuant"
    description = "Donchian 通道突破策略"
    
    timeframes = ["15m", "1h", "4h", "1d"]
    
    params = {
        "lookback_period": 20,  # 通道周期
        "stop_loss_pct": 0.08,  # 止损百分比
        "take_profit_pct": 0.20,  # 止盈百分比
        "use_trailing_stop": True,  # 使用移动止损
        "volume_filter": True,  # 成交量过滤
        "volume_multiplier": 1.5,  # 成交量倍数
    }
    
    def on_init(self):
        """初始化"""
        self._last_upper = None
        self._last_lower = None
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """生成突破信号"""
        if not self.validate_data(data):
            return None
        
        if len(data) < self.params["lookback_period"] + 1:
            return None
        
        high = data["high"]
        low = data["low"]
        close = data["close"]
        volume = data["volume"]
        
        # 计算 Donchian 通道
        upper = high.rolling(self.params["lookback_period"]).max()
        lower = low.rolling(self.params["lookback_period"]).min()
        
        current_close = close.iloc[-1]
        current_upper = upper.iloc[-1]
        current_lower = lower.iloc[-1]
        last_upper = upper.iloc[-2]
        last_lower = lower.iloc[-2]
        
        # 保存上次通道值
        self._last_upper = last_upper
        self._last_lower = last_lower
        
        # 检查成交量过滤
        if self.params["volume_filter"]:
            avg_volume = volume.rolling(20).mean().iloc[-1]
            current_volume = volume.iloc[-1]
            if current_volume < avg_volume * self.params["volume_multiplier"]:
                # 成交量不足，不生成信号
                return None
        
        # 向上突破 - 做多信号
        if current_close > last_upper:
            signal_strength = self._calculate_strength(data, "long")
            
            stop_loss = current_lower  # 以下轨为止损
            take_profit = current_close * (1 + self.params["take_profit_pct"])
            
            logger.debug(f"突破信号 - 做多: {data['symbol'].iloc[-1]}, 价格={current_close:.2f}")
            
            return Signal(
                symbol=data["symbol"].iloc[-1],
                side=SignalSide.LONG,
                signal_type=SignalType.ENTRY,
                price=current_close,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strength=signal_strength,
                metadata={
                    "upper": current_upper,
                    "lower": current_lower,
                    "breakout_type": "upside",
                },
            )
        
        # 向下突破 - 做空信号
        elif current_close < last_lower:
            signal_strength = self._calculate_strength(data, "short")
            
            stop_loss = current_upper  # 以上轨为止损
            take_profit = current_close * (1 - self.params["take_profit_pct"])
            
            logger.debug(f"突破信号 - 做空：{data['symbol'].iloc[-1]}, 价格={current_close:.2f}")
            
            return Signal(
                symbol=data["symbol"].iloc[-1],
                side=SignalSide.SHORT,
                signal_type=SignalType.ENTRY,
                price=current_close,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strength=signal_strength,
                metadata={
                    "upper": current_upper,
                    "lower": current_lower,
                    "breakout_type": "downside",
                },
            )
        
        return None
    
    def _calculate_strength(self, data: pd.DataFrame, side: str) -> float:
        """
        计算信号强度
        
        基于：
        1. 突破幅度
        2. 成交量
        3. 波动率
        """
        close = data["close"]
        volume = data["volume"]
        
        # 1. 突破幅度
        if self._last_upper and self._last_lower:
            channel_width = self._last_upper - self._last_lower
            if channel_width > 0:
                if side == "long":
                    breakout_ratio = (close.iloc[-1] - self._last_upper) / channel_width
                else:
                    breakout_ratio = (self._last_lower - close.iloc[-1]) / channel_width
            else:
                breakout_ratio = 0
        else:
            breakout_ratio = 0
        
        # 2. 成交量强度
        avg_volume = volume.rolling(20).mean().iloc[-1]
        current_volume = volume.iloc[-1]
        volume_ratio = min(current_volume / avg_volume, 3.0) / 3.0  # 归一化到 0-1
        
        # 3. 波动率
        returns = close.pct_change()
        volatility = returns.rolling(20).std().iloc[-1]
        vol_strength = min(volatility * 10, 1.0)  # 归一化
        
        # 综合强度 (加权平均)
        strength = (breakout_ratio * 0.4 + volume_ratio * 0.4 + vol_strength * 0.2)
        
        return min(max(strength, 0.0), 1.0)
    
    def on_bar(self, candle: pd.Series):
        """K 线更新回调 - 更新移动止损"""
        if self.params["use_trailing_stop"] and self._positions:
            for symbol, position in self._positions.items():
                if position.side == SignalSide.LONG:
                    # 多头 - 提高止损
                    if self._last_lower and self._last_lower > position.stop_loss:
                        position.stop_loss = self._last_lower
                elif position.side == SignalSide.SHORT:
                    # 空头 - 降低止损
                    if self._last_upper and self._last_upper < position.stop_loss:
                        position.stop_loss = self._last_upper
