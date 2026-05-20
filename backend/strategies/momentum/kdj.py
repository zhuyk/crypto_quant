"""
KDJ 随机指标策略

核心逻辑:
- K 线上穿 D 线 (金叉) 且在超卖区 → 做多
- K 线下穿 D 线 (死叉) 且在超买区 → 做空
- J 值极端 (> 100 或 < 0) 为强烈信号
- 配合趋势过滤避免逆势交易
"""
import pandas as pd
import numpy as np
from typing import Optional
import logging

from strategies.base import Strategy, Signal, SignalSide, SignalType

logger = logging.getLogger(__name__)


class KDJStrategy(Strategy):
    """
    KDJ 随机指标策略
    
    适用场景: 短线震荡到趋势转换
    优势: 对价格敏感度高、J 值提供超前信号
    """
    
    name = "kdj"
    category = "momentum"
    version = "1.0.0"
    author = "CryptoQuant"
    description = "KDJ 随机指标策略 - 金叉死叉 + 超买超卖"
    
    timeframes = ["15m", "1h", "4h"]
    
    params = {
        "k_period": 9,              # K 线周期 (RSV 周期)
        "d_period": 3,              # D 线平滑周期
        "j_period": 3,              # J 线计算参数 (3K - 2D)
        "oversold": 20,             # 超卖区
        "overbought": 80,           # 超买区
        "j_extreme_low": 0,         # J 值极端低位
        "j_extreme_high": 100,      # J 值极端高位
        "use_trend_filter": True,   # 趋势过滤
        "trend_ma_period": 60,      # 趋势判断均线周期
        "stop_loss_pct": 0.03,      # 止损
        "take_profit_pct": 0.08,    # 止盈
        "min_strength": 0.35,       # 最小信号强度
    }
    
    def on_init(self):
        self._last_k = None
        self._last_d = None
        self._last_j = None
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """生成 KDJ 信号"""
        if not self.validate_data(data):
            return None
        
        min_len = max(self.params["k_period"], self.params["trend_ma_period"]) + 20
        if len(data) < min_len:
            return None
        
        high = data["high"]
        low = data["low"]
        close = data["close"]
        volume = data["volume"]
        
        # 计算 KDJ
        k_values, d_values, j_values = self._calculate_kdj(
            high, low, close,
            self.params["k_period"],
            self.params["d_period"],
        )
        
        current_k = k_values.iloc[-1]
        current_d = d_values.iloc[-1]
        current_j = j_values.iloc[-1]
        prev_k = k_values.iloc[-2]
        prev_d = d_values.iloc[-2]
        
        self._last_k = current_k
        self._last_d = current_d
        self._last_j = current_j
        
        current_price = close.iloc[-1]
        symbol = data["symbol"].iloc[-1] if "symbol" in data.columns else "UNKNOWN"
        
        # 趋势过滤
        trend_up = True
        trend_down = True
        if self.params["use_trend_filter"]:
            ma = close.rolling(self.params["trend_ma_period"]).mean().iloc[-1]
            trend_up = current_price > ma
            trend_down = current_price < ma
        
        # === 金叉做多信号 ===
        # K 上穿 D，且在超卖区（或 J 值极端低）
        if prev_k <= prev_d and current_k > current_d:
            in_oversold = current_k < self.params["oversold"] or current_j < self.params["j_extreme_low"]
            
            if in_oversold and trend_up:
                strength = self._calc_strength(
                    current_k, current_d, current_j,
                    volume, "long"
                )
                
                if strength < self.params["min_strength"]:
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
                        "K": round(current_k, 2),
                        "D": round(current_d, 2),
                        "J": round(current_j, 2),
                        "cross_type": "golden",
                        "signal_reason": "kdj_golden_cross_oversold",
                    },
                )
        
        # === 死叉做空信号 ===
        # K 下穿 D，且在超买区（或 J 值极端高）
        elif prev_k >= prev_d and current_k < current_d:
            in_overbought = current_k > self.params["overbought"] or current_j > self.params["j_extreme_high"]
            
            if in_overbought and trend_down:
                strength = self._calc_strength(
                    current_k, current_d, current_j,
                    volume, "short"
                )
                
                if strength < self.params["min_strength"]:
                    return None
                
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
                        "K": round(current_k, 2),
                        "D": round(current_d, 2),
                        "J": round(current_j, 2),
                        "cross_type": "death",
                        "signal_reason": "kdj_death_cross_overbought",
                    },
                )
        
        return None
    
    @staticmethod
    def _calculate_kdj(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        k_period: int,
        d_period: int,
    ) -> tuple:
        """
        计算 KDJ 指标
        
        RSV = (Close - Lowest Low) / (Highest High - Lowest Low) * 100
        K = SMA(RSV, d_period)
        D = SMA(K, d_period)
        J = 3*K - 2*D
        """
        # 最低价和最高价的滚动窗口
        lowest_low = low.rolling(k_period).min()
        highest_high = high.rolling(k_period).max()
        
        # RSV (未成熟随机值)
        denominator = highest_high - lowest_low
        denominator = denominator.replace(0, np.nan)
        rsv = ((close - lowest_low) / denominator * 100).fillna(50)
        
        # K 值 (RSV 的指数移动平均)
        k_values = rsv.ewm(span=d_period, adjust=False).mean()
        
        # D 值 (K 的指数移动平均)
        d_values = k_values.ewm(span=d_period, adjust=False).mean()
        
        # J 值
        j_values = 3 * k_values - 2 * d_values
        
        return k_values, d_values, j_values
    
    def _calc_strength(self, k: float, d: float, j: float, volume: pd.Series, direction: str) -> float:
        """计算信号强度"""
        # 1. KD 交叉幅度
        kd_diff = abs(k - d)
        cross_score = min(kd_diff / 20.0, 1.0)
        
        # 2. J 值极端程度
        if direction == "long":
            j_score = max(0, (self.params["j_extreme_low"] - j) / 50) + 0.3
        else:
            j_score = max(0, (j - self.params["j_extreme_high"]) / 50) + 0.3
        j_score = min(j_score, 1.0)
        
        # 3. 成交量
        avg_vol = volume.rolling(20).mean().iloc[-1]
        vol_ratio = volume.iloc[-1] / avg_vol if avg_vol > 0 else 1
        vol_score = min(vol_ratio / 2.0, 1.0)
        
        return min(cross_score * 0.3 + j_score * 0.4 + vol_score * 0.3, 1.0)
