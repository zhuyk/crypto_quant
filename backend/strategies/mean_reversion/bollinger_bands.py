"""
布林带均值回归策略

核心逻辑:
- 价格触及下轨且 %B < 0 → 做多 (超卖反弹)
- 价格触及上轨且 %B > 1 → 做空 (超买回落)
- 价格回归中轨 → 平仓
- 配合带宽收窄后展开识别波动率突破
"""
import pandas as pd
import numpy as np
from typing import Optional
import logging

from strategies.base import Strategy, Signal, SignalSide, SignalType

logger = logging.getLogger(__name__)


class BollingerBandsStrategy(Strategy):
    """
    布林带均值回归策略
    
    适用场景: 震荡区间、波动率回归
    核心思想: 价格在 ±2 标准差范围内波动的概率约 95%，
    触及边界后大概率回归均值
    """
    
    name = "bollinger_bands"
    category = "mean_reversion"
    version = "1.0.0"
    author = "CryptoQuant"
    description = "布林带均值回归策略 - 上下轨反转交易"
    
    timeframes = ["15m", "1h", "4h"]
    
    params = {
        "bb_period": 20,            # 布林带周期
        "bb_std": 2.0,              # 标准差倍数
        "use_percent_b": True,      # 使用 %B 指标
        "percent_b_oversold": 0.0,  # %B 超卖阈值
        "percent_b_overbought": 1.0,  # %B 超买阈值
        "bandwidth_filter": True,   # 带宽过滤 (避免窄带中交易)
        "min_bandwidth": 0.02,      # 最小带宽 (相对中轨)
        "exit_at_middle": True,     # 回归中轨平仓
        "stop_loss_pct": 0.04,      # 止损百分比
        "atr_period": 14,           # ATR 周期
        "volume_confirm": True,     # 成交量确认
    }
    
    def on_init(self):
        self._last_percent_b = None
        self._last_bandwidth = None
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """生成布林带信号"""
        if not self.validate_data(data):
            return None
        
        if len(data) < self.params["bb_period"] + 10:
            return None
        
        close = data["close"]
        high = data["high"]
        low = data["low"]
        volume = data["volume"]
        
        # 计算布林带
        middle, upper, lower = self._calculate_bollinger(
            close, self.params["bb_period"], self.params["bb_std"]
        )
        
        current_price = close.iloc[-1]
        current_middle = middle.iloc[-1]
        current_upper = upper.iloc[-1]
        current_lower = lower.iloc[-1]
        
        # 计算 %B
        bandwidth = (current_upper - current_lower) / current_middle if current_middle > 0 else 0
        percent_b = (current_price - current_lower) / (current_upper - current_lower) if (current_upper - current_lower) > 0 else 0.5
        
        self._last_percent_b = percent_b
        self._last_bandwidth = bandwidth
        
        symbol = data["symbol"].iloc[-1] if "symbol" in data.columns else "UNKNOWN"
        
        # 带宽过滤：太窄的布林带说明即将突破，不适合均值回归
        if self.params["bandwidth_filter"]:
            if bandwidth < self.params["min_bandwidth"]:
                return None
        
        # 成交量确认
        vol_confirmed = True
        if self.params["volume_confirm"]:
            avg_vol = volume.rolling(20).mean().iloc[-1]
            vol_confirmed = volume.iloc[-1] > avg_vol * 0.7
        
        # === 触及下轨 - 做多 ===
        if percent_b <= self.params["percent_b_oversold"] and vol_confirmed:
            # 确认价格开始反弹 (当前收盘价高于前一根最低价)
            if close.iloc[-1] > low.iloc[-2]:
                strength = self._calc_strength(percent_b, bandwidth, volume, "long")
                
                # ATR 动态止损
                atr = self._calculate_atr(high, low, close, self.params["atr_period"]).iloc[-1]
                stop_loss = current_price - atr * 2
                take_profit = current_middle  # 目标回归中轨
                
                return Signal(
                    symbol=symbol,
                    side=SignalSide.LONG,
                    signal_type=SignalType.ENTRY,
                    price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    strength=strength,
                    metadata={
                        "percent_b": round(percent_b, 4),
                        "bandwidth": round(bandwidth, 4),
                        "bb_upper": round(current_upper, 2),
                        "bb_lower": round(current_lower, 2),
                        "bb_middle": round(current_middle, 2),
                        "signal_reason": "bb_lower_touch",
                    },
                )
        
        # === 触及上轨 - 做空 ===
        elif percent_b >= self.params["percent_b_overbought"] and vol_confirmed:
            # 确认价格开始回落
            if close.iloc[-1] < high.iloc[-2]:
                strength = self._calc_strength(percent_b, bandwidth, volume, "short")
                
                atr = self._calculate_atr(high, low, close, self.params["atr_period"]).iloc[-1]
                stop_loss = current_price + atr * 2
                take_profit = current_middle
                
                return Signal(
                    symbol=symbol,
                    side=SignalSide.SHORT,
                    signal_type=SignalType.ENTRY,
                    price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    strength=strength,
                    metadata={
                        "percent_b": round(percent_b, 4),
                        "bandwidth": round(bandwidth, 4),
                        "bb_upper": round(current_upper, 2),
                        "bb_lower": round(current_lower, 2),
                        "bb_middle": round(current_middle, 2),
                        "signal_reason": "bb_upper_touch",
                    },
                )
        
        # === 回归中轨 - 平仓信号 ===
        if self.params["exit_at_middle"] and self._positions:
            # 价格接近中轨 (±0.5% 范围内)
            near_middle = abs(current_price - current_middle) / current_middle < 0.005
            if near_middle:
                return Signal(
                    symbol=symbol,
                    side=SignalSide.CLOSE,
                    signal_type=SignalType.EXIT,
                    price=current_price,
                    strength=0.8,
                    metadata={"signal_reason": "bb_middle_reversion"},
                )
        
        return None
    
    @staticmethod
    def _calculate_bollinger(close: pd.Series, period: int, std_mult: float):
        """计算布林带"""
        middle = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = middle + std * std_mult
        lower = middle - std * std_mult
        return middle, upper, lower
    
    @staticmethod
    def _calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        """计算 ATR"""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()
    
    def _calc_strength(self, percent_b: float, bandwidth: float, volume: pd.Series, direction: str) -> float:
        """计算信号强度"""
        # 1. %B 极端程度
        if direction == "long":
            pb_score = max(0, -percent_b) + 0.5  # %B 越负越强
        else:
            pb_score = max(0, percent_b - 1) + 0.5  # %B 越大于1越强
        pb_score = min(pb_score, 1.0)
        
        # 2. 带宽 (越宽空间越大)
        bw_score = min(bandwidth / 0.06, 1.0)
        
        # 3. 成交量
        avg_vol = volume.rolling(20).mean().iloc[-1]
        vol_ratio = volume.iloc[-1] / avg_vol if avg_vol > 0 else 1
        vol_score = min(vol_ratio / 2.0, 1.0)
        
        return min(pb_score * 0.4 + bw_score * 0.3 + vol_score * 0.3, 1.0)
