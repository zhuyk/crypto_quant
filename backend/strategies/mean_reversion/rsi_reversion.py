"""
RSI 均值回归策略

核心逻辑:
- RSI 超卖 (< 30) 且出现底背离 → 做多
- RSI 超买 (> 70) 且出现顶背离 → 做空/平仓
- 配合成交量确认和 ATR 动态止损
"""
import pandas as pd
import numpy as np
from typing import Optional
import logging

from strategies.base import Strategy, Signal, SignalSide, SignalType

logger = logging.getLogger(__name__)


class RSIReversionStrategy(Strategy):
    """
    RSI 均值回归策略
    
    适用场景: 震荡市、区间盘整
    核心思想: 价格偏离均值后倾向回归，利用 RSI 识别超买超卖区域
    """
    
    name = "rsi_reversion"
    category = "mean_reversion"
    version = "1.0.0"
    author = "CryptoQuant"
    description = "RSI 均值回归策略 - 超买超卖反转交易"
    
    timeframes = ["15m", "1h", "4h"]
    
    params = {
        "rsi_period": 14,           # RSI 周期
        "oversold": 30,             # 超卖阈值
        "overbought": 70,           # 超买阈值
        "rsi_exit_level": 50,       # RSI 回归平仓位置
        "use_divergence": True,     # 是否使用背离确认
        "atr_period": 14,           # ATR 周期 (用于动态止损)
        "atr_multiplier": 2.0,      # ATR 止损倍数
        "take_profit_atr": 3.0,     # ATR 止盈倍数
        "volume_confirm": True,     # 成交量确认
        "min_strength": 0.4,        # 最小信号强度
    }
    
    def on_init(self):
        self._last_rsi = None
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """生成 RSI 均值回归信号"""
        if not self.validate_data(data):
            return None
        
        min_len = max(self.params["rsi_period"], self.params["atr_period"]) + 20
        if len(data) < min_len:
            return None
        
        close = data["close"]
        high = data["high"]
        low = data["low"]
        volume = data["volume"]
        
        # 计算 RSI
        rsi = self._calculate_rsi(close, self.params["rsi_period"])
        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]
        
        # 计算 ATR (动态止损)
        atr = self._calculate_atr(high, low, close, self.params["atr_period"])
        current_atr = atr.iloc[-1]
        
        current_price = close.iloc[-1]
        symbol = data["symbol"].iloc[-1] if "symbol" in data.columns else "UNKNOWN"
        
        self._last_rsi = current_rsi
        
        # === 超卖做多信号 ===
        if current_rsi < self.params["oversold"]:
            # RSI 从超卖区开始回升
            if prev_rsi < current_rsi:
                # 背离确认：价格创新低但 RSI 没有创新低
                divergence_confirmed = True
                if self.params["use_divergence"]:
                    divergence_confirmed = self._check_bullish_divergence(close, rsi)
                
                if not divergence_confirmed:
                    return None
                
                # 成交量确认
                if self.params["volume_confirm"]:
                    avg_vol = volume.rolling(20).mean().iloc[-1]
                    if volume.iloc[-1] < avg_vol * 0.8:
                        return None
                
                strength = self._calculate_signal_strength(
                    rsi_value=current_rsi,
                    oversold=self.params["oversold"],
                    overbought=self.params["overbought"],
                    direction="long",
                    volume=volume,
                    atr=atr,
                )
                
                if strength < self.params["min_strength"]:
                    return None
                
                stop_loss = current_price - current_atr * self.params["atr_multiplier"]
                take_profit = current_price + current_atr * self.params["take_profit_atr"]
                
                return Signal(
                    symbol=symbol,
                    side=SignalSide.LONG,
                    signal_type=SignalType.ENTRY,
                    price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    strength=strength,
                    metadata={
                        "rsi": round(current_rsi, 2),
                        "atr": round(current_atr, 4),
                        "signal_reason": "rsi_oversold_reversal",
                        "divergence": divergence_confirmed,
                    },
                )
        
        # === 超买做空/平仓信号 ===
        elif current_rsi > self.params["overbought"]:
            if prev_rsi > current_rsi:  # RSI 开始回落
                divergence_confirmed = True
                if self.params["use_divergence"]:
                    divergence_confirmed = self._check_bearish_divergence(close, rsi)
                
                if not divergence_confirmed:
                    return None
                
                strength = self._calculate_signal_strength(
                    rsi_value=current_rsi,
                    oversold=self.params["oversold"],
                    overbought=self.params["overbought"],
                    direction="short",
                    volume=volume,
                    atr=atr,
                )
                
                if strength < self.params["min_strength"]:
                    return None
                
                stop_loss = current_price + current_atr * self.params["atr_multiplier"]
                take_profit = current_price - current_atr * self.params["take_profit_atr"]
                
                return Signal(
                    symbol=symbol,
                    side=SignalSide.SHORT,
                    signal_type=SignalType.ENTRY,
                    price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    strength=strength,
                    metadata={
                        "rsi": round(current_rsi, 2),
                        "atr": round(current_atr, 4),
                        "signal_reason": "rsi_overbought_reversal",
                        "divergence": divergence_confirmed,
                    },
                )
        
        return None
    
    @staticmethod
    def _calculate_rsi(close: pd.Series, period: int) -> pd.Series:
        """计算 RSI"""
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        
        avg_gain = gain.ewm(span=period, adjust=False).mean()
        avg_loss = loss.ewm(span=period, adjust=False).mean()
        
        rs = avg_gain / avg_loss.replace(0, np.inf)
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def _calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        """计算 ATR"""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()
    
    def _check_bullish_divergence(self, close: pd.Series, rsi: pd.Series, lookback: int = 10) -> bool:
        """检查看涨背离：价格创新低，RSI 未创新低"""
        recent_close = close.iloc[-lookback:]
        recent_rsi = rsi.iloc[-lookback:]
        
        # 价格最低点
        price_min_idx = recent_close.idxmin()
        current_price_near_low = close.iloc[-1] <= recent_close.quantile(0.2)
        
        # RSI 没有同步创新低
        rsi_at_price_low = rsi.loc[price_min_idx] if price_min_idx in rsi.index else rsi.iloc[-1]
        rsi_not_at_low = rsi.iloc[-1] > recent_rsi.min()
        
        return current_price_near_low and rsi_not_at_low
    
    def _check_bearish_divergence(self, close: pd.Series, rsi: pd.Series, lookback: int = 10) -> bool:
        """检查看跌背离：价格创新高，RSI 未创新高"""
        recent_close = close.iloc[-lookback:]
        recent_rsi = rsi.iloc[-lookback:]
        
        current_price_near_high = close.iloc[-1] >= recent_close.quantile(0.8)
        rsi_not_at_high = rsi.iloc[-1] < recent_rsi.max()
        
        return current_price_near_high and rsi_not_at_high
    
    def _calculate_signal_strength(
        self,
        rsi_value: float,
        oversold: float,
        overbought: float,
        direction: str,
        volume: pd.Series,
        atr: pd.Series,
    ) -> float:
        """计算信号强度"""
        # 1. RSI 极端程度 (越极端越强)
        if direction == "long":
            rsi_score = max(0, (oversold - rsi_value) / oversold)
        else:
            rsi_score = max(0, (rsi_value - overbought) / (100 - overbought))
        
        # 2. 成交量放大
        avg_vol = volume.rolling(20).mean().iloc[-1]
        vol_ratio = volume.iloc[-1] / avg_vol if avg_vol > 0 else 1
        vol_score = min(vol_ratio / 2.0, 1.0)
        
        # 3. 波动率（ATR 相对价格的比例）
        atr_pct = atr.iloc[-1] / volume.index[-1] if hasattr(volume.index[-1], '__float__') else 0.02
        vol_score_2 = min(atr_pct * 20, 1.0) if atr_pct > 0 else 0.5
        
        strength = rsi_score * 0.5 + vol_score * 0.3 + vol_score_2 * 0.2
        return min(max(strength, 0.0), 1.0)
