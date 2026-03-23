"""
MACD 趋势策略
"""
import pandas as pd
import numpy as np
from typing import Optional
import logging

from strategies.base import Strategy, Signal, SignalSide, SignalType

logger = logging.getLogger(__name__)


class MACDStrategy(Strategy):
    """
    MACD 趋势跟踪策略
    
    基于 MACD 指标的 trend 跟随策略：
    - MACD 金叉 + 柱状图放大：做多
    - MACD 死叉 + 柱状图缩小：做空/平仓
    """
    
    name = "macd"
    category = "trend"
    version = "1.0.0"
    author = "CryptoQuant"
    description = "MACD 趋势跟踪策略"
    
    timeframes = ["1h", "4h", "1d"]
    
    params = {
        "fast_period": 12,  # 快线周期
        "slow_period": 26,  # 慢线周期
        "signal_period": 9,  # 信号线周期
        "stop_loss_pct": 0.06,  # 止损百分比
        "take_profit_pct": 0.18,  # 止盈百分比
        "histogram_threshold": 0,  # 柱状图阈值
        "use_zero_cross": False,  # 使用零轴穿越过滤
    }
    
    def on_init(self):
        """初始化"""
        self._last_macd = None
        self._last_signal = None
        self._last_histogram = None
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """生成 MACD 信号"""
        if not self.validate_data(data):
            return None
        
        if len(data) < self.params["slow_period"] + 5:
            return None
        
        close = data["close"]
        
        # 计算 MACD
        macd, signal, histogram = self._calculate_macd(close)
        
        current_macd = macd.iloc[-1]
        current_signal = signal.iloc[-1]
        current_histogram = histogram.iloc[-1]
        
        last_macd = macd.iloc[-2]
        last_signal = signal.iloc[-2]
        last_histogram = histogram.iloc[-2]
        
        # 保存历史值
        self._last_macd = last_macd
        self._last_signal = last_signal
        self._last_histogram = last_histogram
        
        # 零轴过滤
        if self.params["use_zero_cross"]:
            if current_macd < 0 and current_signal < 0:
                # 零轴下方，只做空或观望
                pass
            elif current_macd > 0 and current_signal > 0:
                # 零轴上方，只做多或观望
                pass
        
        # 金叉 - MACD 上穿信号线
        if last_macd <= last_signal and current_macd > current_signal:
            # 确认柱状图放大
            if current_histogram > last_histogram and current_histogram > self.params["histogram_threshold"]:
                strength = self._calculate_strength(data, macd, signal, histogram, "bullish")
                
                price = close.iloc[-1]
                stop_loss = price * (1 - self.params["stop_loss_pct"])
                take_profit = price * (1 + self.params["take_profit_pct"])
                
                logger.debug(f"MACD 金叉 - 做多：{data['symbol'].iloc[-1]}, 价格={price:.2f}")
                
                return Signal(
                    symbol=data["symbol"].iloc[-1],
                    side=SignalSide.LONG,
                    signal_type=SignalType.ENTRY,
                    price=price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    strength=strength,
                    metadata={
                        "macd": float(current_macd),
                        "signal": float(current_signal),
                        "histogram": float(current_histogram),
                        "cross_type": "bullish",
                    },
                )
        
        # 死叉 - MACD 下穿信号线
        elif last_macd >= last_signal and current_macd < current_signal:
            # 确认柱状图缩小
            if current_histogram < last_histogram and current_histogram < self.params["histogram_threshold"]:
                strength = self._calculate_strength(data, macd, signal, histogram, "bearish")
                
                price = close.iloc[-1]
                stop_loss = price * (1 + self.params["stop_loss_pct"])
                take_profit = price * (1 - self.params["take_profit_pct"])
                
                logger.debug(f"MACD 死叉 - 做空：{data['symbol'].iloc[-1]}, 价格={price:.2f}")
                
                return Signal(
                    symbol=data["symbol"].iloc[-1],
                    side=SignalSide.SHORT,
                    signal_type=SignalType.ENTRY,
                    price=price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    strength=strength,
                    metadata={
                        "macd": float(current_macd),
                        "signal": float(current_signal),
                        "histogram": float(current_histogram),
                        "cross_type": "bearish",
                    },
                )
        
        return None
    
    def _calculate_macd(
        self,
        close: pd.Series,
    ) -> tuple:
        """
        计算 MACD 指标
        
        Returns:
            (macd_line, signal_line, histogram)
        """
        # EMA 计算
        ema_fast = close.ewm(span=self.params["fast_period"], adjust=False).mean()
        ema_slow = close.ewm(span=self.params["slow_period"], adjust=False).mean()
        
        # MACD 线
        macd_line = ema_fast - ema_slow
        
        # 信号线
        signal_line = macd_line.ewm(span=self.params["signal_period"], adjust=False).mean()
        
        # 柱状图
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def _calculate_strength(
        self,
        data: pd.DataFrame,
        macd: pd.Series,
        signal: pd.Series,
        histogram: pd.Series,
        direction: str,
    ) -> float:
        """
        计算信号强度
        
        基于：
        1. MACD 与信号线的距离
        2. 柱状图变化率
        3. 趋势一致性
        """
        close = data["close"]
        
        # 1. MACD 分离度
        current_macd = macd.iloc[-1]
        current_signal = signal.iloc[-1]
        separation = abs(current_macd - current_signal) / abs(current_signal) if current_signal != 0 else 0
        separation_score = min(separation * 10, 1.0)
        
        # 2. 柱状图动量
        current_hist = histogram.iloc[-1]
        last_hist = histogram.iloc[-2]
        if last_hist != 0:
            hist_momentum = abs(current_hist - last_hist) / abs(last_hist)
        else:
            hist_momentum = 0
        hist_score = min(hist_momentum * 5, 1.0)
        
        # 3. 趋势一致性 (价格趋势与 MACD 方向)
        ma_20 = close.rolling(20).mean()
        ma_60 = close.rolling(60).mean()
        
        if direction == "bullish":
            trend_aligned = close.iloc[-1] > ma_20.iloc[-1] > ma_60.iloc[-1]
        else:
            trend_aligned = close.iloc[-1] < ma_20.iloc[-1] < ma_60.iloc[-1]
        
        trend_score = 1.0 if trend_aligned else 0.5
        
        # 综合强度
        strength = (separation_score * 0.4 + hist_score * 0.3 + trend_score * 0.3)
        
        return min(max(strength, 0.0), 1.0)
