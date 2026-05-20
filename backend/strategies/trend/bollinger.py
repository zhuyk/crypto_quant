"""
布林带均值回归策略

原理：
- 当价格触及下轨时，如果偏离均线过大，做多
- 当价格触及上轨时，如果偏离均线过大，做空
- 回归均线时平仓

特点：
- 震荡行情表现好
- 趋势行情需配合止损
"""
import pandas as pd
import numpy as np
from typing import Optional
from strategies.base import Strategy, Signal, SignalSide, SignalType


class BollingerStrategy(Strategy):
    """布林带均值回归策略"""
    
    name = "bollinger"
    category = "trend"
    version = "1.0.0"
    author = "CryptoQuant"
    description = "基于布林带的均值回归策略，适合震荡行情"
    
    timeframes = ["15m", "1h", "4h", "1d"]
    
    params = {
        "bb_period": 20,           # 布林带周期
        "bb_std": 2.0,             # 标准差倍数
        "stop_loss_pct": 0.03,     # 止损百分比
        "take_profit_pct": 0.06,   # 止盈百分比（回归均线）
        "position_pct": 0.95,      # 仓位比例（预留子弹）
        "min_bb_width": 0.01,      # 最小布林带宽度（过滤窄带）
        "rsi_period": 14,          # RSI 周期（辅助过滤）
        "rsi_oversold": 30,        # RSI 超卖阈值
        "rsi_overbought": 70,      # RSI 超买阈值
        "min_strength": 0.3,       # 最小信号强度
    }
    
    def on_init(self):
        self._last_signal = None
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """
        生成布林带信号
        
        买入条件：
        1. 价格触及下轨或下轨附近
        2. RSI 处于超卖区域（可选）
        3. 布林带宽度足够大（市场有波动）
        
        卖出条件：
        1. 价格触及中轨（均线）或上轨
        2. 或者触发止损/止盈
        """
        if not self.validate_data(data):
            return None
        
        period = self.params["bb_period"]
        if len(data) < period + 1:
            return None
        
        close = data["close"]
        current_price = close.iloc[-1]
        symbol = data.get("symbol", ["UNKNOWN"]).iloc[-1] if "symbol" in data.columns else "UNKNOWN"
        
        # 计算布林带
        middle = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = middle + self.params["bb_std"] * std
        lower = middle - self.params["bb_std"] * std
        
        bb_width = (upper.iloc[-1] - lower.iloc[-1]) / middle.iloc[-1]
        if bb_width < self.params["min_bb_width"]:
            return None  # 市场波动太小，不操作
        
        upper_val = upper.iloc[-1]
        lower_val = lower.iloc[-1]
        middle_val = middle.iloc[-1]
        
        prev_price = close.iloc[-2]
        prev_upper = upper.iloc[-2]
        prev_lower = lower.iloc[-2]
        
        # 计算 RSI（可选）
        rsi = self._calculate_rsi(close)
        rsi_val = rsi.iloc[-1] if rsi is not None else 50
        
        position = self.get_position(symbol)
        
        # ========== 做多信号 ==========
        # 价格从下轨下方反弹（触及下轨后回升）
        if prev_price <= prev_lower and current_price > lower_val:
            # 价格回归中轨的过程中
            if current_price < middle_val:  # 还在均线下方，说明还没回归完
                strength = self._calculate_strength(data, rsi_val, bb_width)
                
                if strength < self.params.get("min_strength", 0.3):
                    return None
                
                stop_loss = lower_val * (1 - self.params["stop_loss_pct"])
                take_profit = middle_val * (1 + self.params["take_profit_pct"])
                
                return Signal(
                    symbol=symbol,
                    side=SignalSide.LONG,
                    signal_type=SignalType.ENTRY,
                    price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    strength=strength,
                    metadata={
                        "bb_upper": upper_val,
                        "bb_middle": middle_val,
                        "bb_lower": lower_val,
                        "bb_width": bb_width,
                        "rsi": rsi_val,
                        "signal_type": "bb_long",
                    }
                )
        
        # ========== 做空信号 ==========
        # 价格从上轨上方回落
        if prev_price >= prev_upper and current_price < upper_val:
            if current_price > middle_val:  # 还在均线上方
                strength = self._calculate_strength(data, rsi_val, bb_width)
                
                if strength < self.params.get("min_strength", 0.3):
                    return None
                
                stop_loss = upper_val * (1 + self.params["stop_loss_pct"])
                take_profit = middle_val * (1 - self.params["take_profit_pct"])
                
                return Signal(
                    symbol=symbol,
                    side=SignalSide.SHORT,
                    signal_type=SignalType.ENTRY,
                    price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    strength=strength,
                    metadata={
                        "bb_upper": upper_val,
                        "bb_middle": middle_val,
                        "bb_lower": lower_val,
                        "bb_width": bb_width,
                        "rsi": rsi_val,
                        "signal_type": "bb_short",
                    }
                )
        
        # ========== 平仓信号 ==========
        if position:
            # 价格回归均线附近（做多仓位）
            if position.side == SignalSide.LONG:
                # 回到中轨附近
                if current_price >= middle_val * 0.995:
                    return Signal(
                        symbol=symbol,
                        side=SignalSide.CLOSE,
                        signal_type=SignalType.EXIT,
                        price=current_price,
                        strength=0.8,
                        metadata={
                            "exit_reason": "mean_reversion",
                            "bb_middle": middle_val,
                        }
                    )
                # 触及中轨
                if prev_price < middle_val and current_price >= middle_val:
                    return Signal(
                        symbol=symbol,
                        side=SignalSide.CLOSE,
                        signal_type=SignalType.EXIT,
                        price=current_price,
                        strength=0.9,
                        metadata={
                            "exit_reason": "touched_middle",
                            "bb_middle": middle_val,
                        }
                    )
            
            # 做空仓位回归均线
            if position.side == SignalSide.SHORT:
                if current_price <= middle_val * 1.005:
                    return Signal(
                        symbol=symbol,
                        side=SignalSide.CLOSE,
                        signal_type=SignalType.EXIT,
                        price=current_price,
                        strength=0.8,
                        metadata={
                            "exit_reason": "mean_reversion",
                            "bb_middle": middle_val,
                        }
                    )
                if prev_price > middle_val and current_price <= middle_val:
                    return Signal(
                        symbol=symbol,
                        side=SignalSide.CLOSE,
                        signal_type=SignalType.EXIT,
                        price=current_price,
                        strength=0.9,
                        metadata={
                            "exit_reason": "touched_middle",
                            "bb_middle": middle_val,
                        }
                    )
        
        return None
    
    def _calculate_rsi(self, close: pd.Series) -> Optional[pd.Series]:
        """计算 RSI"""
        period = self.params.get("rsi_period", 14)
        if len(close) < period + 1:
            return None
        
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        
        if avg_loss.iloc[-1] == 0:
            return pd.Series(100, index=close.index)
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_strength(
        self,
        data: pd.DataFrame,
        rsi_val: float,
        bb_width: float,
    ) -> float:
        """
        计算信号强度
        
        基于：
        1. 布林带宽度（波动率）
        2. RSI 位置
        3. 成交量
        """
        close = data["close"]
        volume = data["volume"]
        
        # 1. 布林带宽度得分（越宽越强）
        bb_score = min(1.0, bb_width / 0.05)  # 归一化
        
        # 2. RSI 得分（越接近极值越强）
        rsi_oversold = self.params.get("rsi_oversold", 30)
        rsi_overbought = self.params.get("rsi_overbought", 70)
        mid_rsi = (rsi_overbought + rsi_oversold) / 2
        rsi_dist = abs(rsi_val - mid_rsi) / mid_rsi
        rsi_score = min(1.0, rsi_dist * 3)
        
        # 3. 成交量得分
        avg_volume = volume.rolling(20).mean()
        vol_ratio = volume.iloc[-1] / avg_volume.iloc[-1]
        vol_score = min(1.0, max(0, (vol_ratio - 0.5) * 2))
        
        # 加权综合
        strength = (
            0.5 * bb_score +
            0.3 * rsi_score +
            0.2 * vol_score
        )
        
        return min(1.0, max(0.0, strength))
