"""
ATR 移动止损趋势跟踪策略

核心逻辑:
- 使用 SuperTrend 指标 (基于 ATR) 判断趋势方向
- 价格突破 SuperTrend 上轨 → 做多，跌破下轨 → 做空
- 持仓期间使用 ATR 动态移动止损，让利润奔跑
- 波动率扩张时加宽止损，收缩时收紧止损
"""
import pandas as pd
import numpy as np
from typing import Optional
import logging

from strategies.base import Strategy, Signal, SignalSide, SignalType

logger = logging.getLogger(__name__)


class ATRTrailingStrategy(Strategy):
    """
    ATR 移动止损趋势跟踪策略 (SuperTrend)
    
    适用场景: 趋势明确的行情，让利润奔跑
    优势: 自适应波动率、不会过早止损、趋势结束时自动退出
    """
    
    name = "atr_trailing"
    category = "volatility"
    version = "1.0.0"
    author = "CryptoQuant"
    description = "ATR 移动止损策略 - SuperTrend 趋势跟踪"
    
    timeframes = ["1h", "4h", "1d"]
    
    params = {
        "atr_period": 14,           # ATR 计算周期
        "atr_multiplier": 3.0,      # ATR 乘数 (越大止损越宽)
        "use_ema": True,            # 使用 EMA 计算 ATR (更灵敏)
        "entry_confirm_bars": 2,    # 突破确认K线数
        "trail_step": 0.0,          # 最小移动步长 (0=每根K线更新)
        "take_profit_atr": 5.0,     # 止盈 ATR 倍数 (0=不设止盈)
        "volume_filter": True,      # 突破时成交量过滤
        "volume_mult": 1.2,         # 成交量倍数
    }
    
    def on_init(self):
        self._trend_direction = 0  # 1=上升, -1=下降, 0=未知
        self._supertrend_upper = None
        self._supertrend_lower = None
        self._trailing_stop = None
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """生成 ATR 移动止损信号"""
        if not self.validate_data(data):
            return None
        
        if len(data) < self.params["atr_period"] + 20:
            return None
        
        high = data["high"]
        low = data["low"]
        close = data["close"]
        volume = data["volume"]
        
        # 计算 ATR
        atr = self._calculate_atr(high, low, close, self.params["atr_period"])
        current_atr = atr.iloc[-1]
        
        # 计算 SuperTrend
        supertrend, direction = self._calculate_supertrend(
            high, low, close, atr, self.params["atr_multiplier"]
        )
        
        current_price = close.iloc[-1]
        current_dir = direction.iloc[-1]
        prev_dir = direction.iloc[-2]
        
        symbol = data["symbol"].iloc[-1] if "symbol" in data.columns else "UNKNOWN"
        
        # === 趋势切换信号 ===
        
        # 从下降趋势切换到上升趋势 → 做多
        if prev_dir == -1 and current_dir == 1:
            # 成交量确认
            if self.params["volume_filter"]:
                avg_vol = volume.rolling(20).mean().iloc[-1]
                if volume.iloc[-1] < avg_vol * self.params["volume_mult"]:
                    return None
            
            # 确认K线数
            if self.params["entry_confirm_bars"] > 1:
                confirm_count = sum(1 for i in range(-self.params["entry_confirm_bars"], 0)
                                    if close.iloc[i] > supertrend.iloc[i])
                if confirm_count < self.params["entry_confirm_bars"] - 1:
                    return None
            
            stop_loss = supertrend.iloc[-1]  # SuperTrend 线即止损
            take_profit = None
            if self.params["take_profit_atr"] > 0:
                take_profit = current_price + current_atr * self.params["take_profit_atr"]
            
            strength = self._calc_strength(current_price, supertrend.iloc[-1], current_atr, volume, "long")
            
            self._trend_direction = 1
            self._trailing_stop = stop_loss
            
            return Signal(
                symbol=symbol,
                side=SignalSide.LONG,
                signal_type=SignalType.ENTRY,
                price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strength=strength,
                metadata={
                    "atr": round(current_atr, 4),
                    "supertrend": round(supertrend.iloc[-1], 4),
                    "trend_direction": "bullish",
                    "signal_reason": "supertrend_bullish_flip",
                },
            )
        
        # 从上升趋势切换到下降趋势 → 做空
        elif prev_dir == 1 and current_dir == -1:
            if self.params["volume_filter"]:
                avg_vol = volume.rolling(20).mean().iloc[-1]
                if volume.iloc[-1] < avg_vol * self.params["volume_mult"]:
                    return None
            
            stop_loss = supertrend.iloc[-1]
            take_profit = None
            if self.params["take_profit_atr"] > 0:
                take_profit = current_price - current_atr * self.params["take_profit_atr"]
            
            strength = self._calc_strength(current_price, supertrend.iloc[-1], current_atr, volume, "short")
            
            self._trend_direction = -1
            self._trailing_stop = stop_loss
            
            return Signal(
                symbol=symbol,
                side=SignalSide.SHORT,
                signal_type=SignalType.ENTRY,
                price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strength=strength,
                metadata={
                    "atr": round(current_atr, 4),
                    "supertrend": round(supertrend.iloc[-1], 4),
                    "trend_direction": "bearish",
                    "signal_reason": "supertrend_bearish_flip",
                },
            )
        
        return None
    
    def on_bar(self, candle: pd.Series):
        """K 线更新回调 - 更新移动止损"""
        if not self._positions or self._trailing_stop is None:
            return
        
        for symbol, position in self._positions.items():
            if self._trend_direction == 1:  # 多头
                # 止损只能向上移动
                new_stop = candle["close"] - candle.get("atr", 0) * self.params["atr_multiplier"]
                if new_stop > self._trailing_stop:
                    if self.params["trail_step"] == 0 or (new_stop - self._trailing_stop) >= self.params["trail_step"]:
                        self._trailing_stop = new_stop
                        position.stop_loss = new_stop
            
            elif self._trend_direction == -1:  # 空头
                new_stop = candle["close"] + candle.get("atr", 0) * self.params["atr_multiplier"]
                if new_stop < self._trailing_stop:
                    if self.params["trail_step"] == 0 or (self._trailing_stop - new_stop) >= self.params["trail_step"]:
                        self._trailing_stop = new_stop
                        position.stop_loss = new_stop
    
    @staticmethod
    def _calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        """计算 ATR"""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def _calculate_supertrend(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        atr: pd.Series,
        multiplier: float,
    ) -> tuple:
        """
        计算 SuperTrend 指标
        
        Returns:
            (supertrend_values, direction) where direction: 1=上升趋势, -1=下降趋势
        """
        hl2 = (high + low) / 2
        
        # 基础上下轨
        upper_band = hl2 + multiplier * atr
        lower_band = hl2 - multiplier * atr
        
        supertrend = pd.Series(index=close.index, dtype=float)
        direction = pd.Series(index=close.index, dtype=int)
        
        # 初始化
        supertrend.iloc[0] = upper_band.iloc[0]
        direction.iloc[0] = -1
        
        for i in range(1, len(close)):
            # 上轨调整：只能下移
            if upper_band.iloc[i] < supertrend.iloc[i-1] or close.iloc[i-1] > supertrend.iloc[i-1]:
                pass  # 保持
            else:
                upper_band.iloc[i] = min(upper_band.iloc[i], supertrend.iloc[i-1])
            
            # 下轨调整：只能上移
            if lower_band.iloc[i] > supertrend.iloc[i-1] or close.iloc[i-1] < supertrend.iloc[i-1]:
                pass
            else:
                lower_band.iloc[i] = max(lower_band.iloc[i], supertrend.iloc[i-1])
            
            # 判断方向
            if direction.iloc[i-1] == -1:  # 之前是下降趋势
                if close.iloc[i] > upper_band.iloc[i-1]:
                    direction.iloc[i] = 1  # 切换到上升
                    supertrend.iloc[i] = lower_band.iloc[i]
                else:
                    direction.iloc[i] = -1
                    supertrend.iloc[i] = upper_band.iloc[i]
            else:  # 之前是上升趋势
                if close.iloc[i] < lower_band.iloc[i-1]:
                    direction.iloc[i] = -1  # 切换到下降
                    supertrend.iloc[i] = upper_band.iloc[i]
                else:
                    direction.iloc[i] = 1
                    supertrend.iloc[i] = lower_band.iloc[i]
        
        return supertrend, direction
    
    def _calc_strength(self, price: float, st_value: float, atr: float, volume: pd.Series, direction: str) -> float:
        """计算信号强度"""
        # 1. 突破距离 (相对ATR)
        dist = abs(price - st_value) / atr if atr > 0 else 0
        dist_score = min(dist / 2.0, 1.0)
        
        # 2. 成交量
        avg_vol = volume.rolling(20).mean().iloc[-1]
        vol_ratio = volume.iloc[-1] / avg_vol if avg_vol > 0 else 1
        vol_score = min(vol_ratio / 2.0, 1.0)
        
        return min(dist_score * 0.5 + vol_score * 0.5, 1.0)
