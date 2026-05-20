"""
Dual Thrust 动量突破策略

经典日内/短线突破策略，由 Michael Chalek 开发。
核心逻辑:
- 根据前 N 日的最高价、最低价、收盘价计算上下轨
- 上轨 = 开盘价 + K1 * Range
- 下轨 = 开盘价 - K2 * Range
- 突破上轨做多，突破下轨做空
- Range 取 max(HH-LC, HC-LL) 具有更强的适应性
"""
import pandas as pd
import numpy as np
from typing import Optional
import logging

from strategies.base import Strategy, Signal, SignalSide, SignalType

logger = logging.getLogger(__name__)


class DualThrustStrategy(Strategy):
    """
    Dual Thrust 动量突破策略
    
    适用场景: 日内趋势、波动较大的品种
    优势: 参数少、适应性强、双向交易
    """
    
    name = "dual_thrust"
    category = "momentum"
    version = "1.0.0"
    author = "CryptoQuant"
    description = "Dual Thrust 动量突破策略 - 日内区间突破"
    
    timeframes = ["15m", "1h", "4h"]
    
    params = {
        "lookback_days": 4,         # 回溯天数 (计算 Range)
        "k1": 0.5,                  # 上轨系数 (越大越不容易触发)
        "k2": 0.5,                  # 下轨系数
        "stop_loss_pct": 0.03,      # 止损比例
        "take_profit_pct": 0.06,    # 止盈比例
        "use_atr_filter": True,     # ATR 波动率过滤
        "min_atr_pct": 0.01,        # 最小 ATR 百分比 (过滤低波动)
        "volume_confirm": True,     # 成交量确认
        "trail_stop": False,        # 移动止损
    }
    
    def on_init(self):
        self._upper_band = None
        self._lower_band = None
        self._range_value = None
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """生成 Dual Thrust 信号"""
        if not self.validate_data(data):
            return None
        
        lookback = self.params["lookback_days"]
        # 至少需要 lookback 天的数据（假设1h为24根K线/天）
        min_bars = lookback * 24 if "1h" in str(self.timeframes) else lookback * 96
        min_bars = max(min_bars, lookback * 4 + 10)  # 保底
        
        if len(data) < min_bars:
            return None
        
        high = data["high"]
        low = data["low"]
        close = data["close"]
        open_price = data["open"]
        volume = data["volume"]
        
        # 计算 Range
        # 使用最近 lookback 个周期（不含当前 bar）
        period_high = high.iloc[-(lookback+1):-1]
        period_low = low.iloc[-(lookback+1):-1]
        period_close = close.iloc[-(lookback+1):-1]
        
        hh = period_high.max()   # 最高价的最高
        ll = period_low.min()    # 最低价的最低
        hc = period_close.max()  # 收盘价的最高
        lc = period_close.min()  # 收盘价的最低
        
        # Dual Thrust Range = max(HH - LC, HC - LL)
        range_value = max(hh - lc, hc - ll)
        self._range_value = range_value
        
        if range_value <= 0:
            return None
        
        # 当前 bar 的开盘价作为基准
        current_open = open_price.iloc[-1]
        current_close = close.iloc[-1]
        current_price = current_close
        
        # 计算上下轨
        upper_band = current_open + self.params["k1"] * range_value
        lower_band = current_open - self.params["k2"] * range_value
        
        self._upper_band = upper_band
        self._lower_band = lower_band
        
        symbol = data["symbol"].iloc[-1] if "symbol" in data.columns else "UNKNOWN"
        
        # ATR 波动率过滤
        if self.params["use_atr_filter"]:
            atr = self._calculate_atr(high, low, close, 14).iloc[-1]
            atr_pct = atr / current_price if current_price > 0 else 0
            if atr_pct < self.params["min_atr_pct"]:
                return None  # 波动率过低，不适合突破策略
        
        # 成交量确认
        if self.params["volume_confirm"]:
            avg_vol = volume.rolling(20).mean().iloc[-1]
            if volume.iloc[-1] < avg_vol * 1.0:
                return None
        
        # === 突破上轨 → 做多 ===
        if current_close > upper_band and close.iloc[-2] <= upper_band:
            strength = self._calc_strength(current_close, upper_band, range_value, volume, "long")
            
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
                    "upper_band": round(upper_band, 4),
                    "lower_band": round(lower_band, 4),
                    "range": round(range_value, 4),
                    "k1": self.params["k1"],
                    "signal_reason": "dual_thrust_upper_break",
                },
            )
        
        # === 跌破下轨 → 做空 ===
        elif current_close < lower_band and close.iloc[-2] >= lower_band:
            strength = self._calc_strength(current_close, lower_band, range_value, volume, "short")
            
            stop_loss = current_price * (1 + self.params["stop_loss_pct"])
            take_profit = current_price * (1 - self.params["take_profit_pct"])
            
            return Signal(
                symbol=symbol,
                side=SignalSide.SHORT,
                signal_type=SignalType.ENTRY,
                price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strength=strength,
                metadata={
                    "upper_band": round(upper_band, 4),
                    "lower_band": round(lower_band, 4),
                    "range": round(range_value, 4),
                    "k2": self.params["k2"],
                    "signal_reason": "dual_thrust_lower_break",
                },
            )
        
        return None
    
    @staticmethod
    def _calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        """计算 ATR"""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()
    
    def _calc_strength(self, price: float, band: float, range_val: float, volume: pd.Series, direction: str) -> float:
        """计算信号强度"""
        # 1. 突破幅度 (相对 range)
        breakout_dist = abs(price - band) / range_val if range_val > 0 else 0
        breakout_score = min(breakout_dist * 5, 1.0)
        
        # 2. 成交量
        avg_vol = volume.rolling(20).mean().iloc[-1]
        vol_ratio = volume.iloc[-1] / avg_vol if avg_vol > 0 else 1
        vol_score = min(vol_ratio / 2.5, 1.0)
        
        # 3. Range 大小 (Range 越大突破越有效)
        range_pct = range_val / price if price > 0 else 0
        range_score = min(range_pct / 0.05, 1.0)
        
        return min(breakout_score * 0.4 + vol_score * 0.3 + range_score * 0.3, 1.0)
