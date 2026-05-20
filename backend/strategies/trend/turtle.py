"""
海龟交易策略 (Turtle Strategy)

经典趋势跟踪系统，源自 Richard Dennis & William Eckhardt。

核心规则：
- 入场：价格突破 N 日最高价 → 做多；跌破 N 日最低价 → 做空
- 退出：固定 ATR 止损，或反向突破退出
- 加仓：顺势加仓，最多 N 个单位
- 风险管理：每笔风险敞口不超过账户的固定比例

两种系统：
- System 1（快）：20 日突破入，10 日反向突破出（短期）
- System 2（慢）：55 日突破入，20 日反向突破出（长期）
"""
import pandas as pd
import numpy as np
from typing import Optional, List
from strategies.base import Strategy, Signal, SignalSide, SignalType, Position


class TurtleStrategy(Strategy):
    """海龟交易策略"""
    
    name = "turtle"
    category = "trend"
    version = "1.0.0"
    author = "CryptoQuant"
    description = "经典海龟趋势跟踪策略，突破 N 日高低点入场，ATR 止损"
    
    timeframes = ["1h", "4h", "1d"]
    
    params = {
        # 入场周期
        "entry_period": 20,        # 突破此周期高点做多 / 低点做空
        "exit_period": 10,         # 反向突破此周期退出
        # ATR 参数
        "atr_period": 20,          # ATR 周期
        "atr_multiplier": 2.0,     # ATR 止损倍数
        # 仓位
        "max_units": 4,            # 最大加仓单位数
        "unit_size_pct": 0.02,    # 每个单位占账户比例（2%）
        # 风控
        "stop_loss_pct": 0.05,    # 备用止损（ATR 失效时）
        "max_position_pct": 0.25, # 最大仓位比例（所有单位合计）
        # 过滤
        "use_system1_only": False,  # 只用 System 1（短期）
        "min_volatility": 0.005,   # 最小波动率要求（过滤盘整）
        "min_strength": 0.3,       # 最小信号强度
    }
    
    def on_init(self):
        self._position_units = 0     # 当前持有的单位数
        self._entry_price = None    # 首次入场价格
        self._last_entry_unit_price = None  # 最近一次加仓价格
        self._atr = None            # 当前 ATR 值
        self._last_high = None
        self._last_low = None
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """
        海龟信号生成
        
        1. 先计算 ATR、N 日高、低
        2. 检查是否触发出场条件
        3. 检查是否触发加仓条件
        4. 检查是否触发出场条件
        """
        if not self.validate_data(data):
            return None
        
        p = self.params
        entry_period = p["entry_period"]
        exit_period = p["exit_period"]
        atr_period = p["atr_period"]
        
        min_len = max(entry_period, exit_period, atr_period) + 1
        if len(data) < min_len:
            return None
        
        close = data["close"]
        high = data["high"]
        low = data["low"]
        
        current_price = close.iloc[-1]
        prev_price = close.iloc[-2]
        symbol = data.get("symbol", ["UNKNOWN"]).iloc[-1] if "symbol" in data.columns else "UNKNOWN"
        
        # ========== 1. 计算 ATR ==========
        tr1 = high - low                          # 当日波动
        tr2 = (high - close.shift(1)).abs()      # 最高-昨收
        tr3 = (low - close.shift(1)).abs()        # 最低-昨收
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(atr_period).mean()
        self._atr = atr.iloc[-1]
        
        if self._atr is None or self._atr <= 0:
            return None
        
        # 波动率过滤：ATR/价格 应该足够大
        volatility_ratio = self._atr / current_price
        if volatility_ratio < p["min_volatility"]:
            return None
        
        # ========== 2. 计算入场/出场通道 ==========
        # System 2 更慢的周期（如果不用 System1）
        slow_entry = int(p["entry_period"] * 2.75)  # 55日
        slow_exit = int(p["exit_period"] * 2)       # 20日
        
        entry_high = high.rolling(entry_period).max().iloc[-1]
        entry_low = low.rolling(entry_period).min().iloc[-1]
        prev_entry_high = high.rolling(entry_period).max().iloc[-2]
        prev_entry_low = low.rolling(entry_period).min().iloc[-2]
        
        exit_high = high.rolling(exit_period).max().iloc[-1]
        exit_low = low.rolling(exit_period).min().iloc[-1]
        prev_exit_high = high.rolling(exit_period).max().iloc[-2]
        prev_exit_low = low.rolling(exit_period).min().iloc[-2]
        
        self._last_high = prev_entry_high
        self._last_low = prev_entry_low
        
        position = self.get_position(symbol)
        
        # ========== 3. 加仓信号 ==========
        if position and self._position_units < p["max_units"]:
            # 多头加仓：价格高于上次加仓价 + 0.5*ATR
            if position.side == SignalSide.LONG:
                add_long_price = self._last_entry_unit_price + self._atr * 0.5
                if current_price >= add_long_price:
                    strength = self._calculate_strength(data)
                    if strength >= p["min_strength"]:
                        self._last_entry_unit_price = current_price
                        self._position_units += 1
                        return Signal(
                            symbol=symbol,
                            side=SignalSide.LONG,
                            signal_type=SignalType.ADJUST,
                            price=current_price,
                            stop_loss=self._calc_stop(entry_low),
                            strength=strength,
                            metadata={
                                "action": "add_unit",
                                "unit": self._position_units,
                                "atr": self._atr,
                                "entry_high": entry_high,
                            }
                        )
            
            # 空头加仓
            elif position.side == SignalSide.SHORT:
                add_short_price = self._last_entry_unit_price - self._atr * 0.5
                if current_price <= add_short_price:
                    strength = self._calculate_strength(data)
                    if strength >= p["min_strength"]:
                        self._last_entry_unit_price = current_price
                        self._position_units += 1
                        return Signal(
                            symbol=symbol,
                            side=SignalSide.SHORT,
                            signal_type=SignalType.ADJUST,
                            price=current_price,
                            stop_loss=self._calc_stop_short(entry_high),
                            strength=strength,
                            metadata={
                                "action": "add_unit",
                                "unit": self._position_units,
                                "atr": self._atr,
                                "entry_low": entry_low,
                            }
                        )
        
        # ========== 4. 出场信号 ==========
        if position:
            # 多头出场：跌破 exit_low
            if position.side == SignalSide.LONG:
                if prev_price > prev_exit_low and current_price <= exit_low:
                    return Signal(
                        symbol=symbol,
                        side=SignalSide.CLOSE,
                        signal_type=SignalType.EXIT,
                        price=current_price,
                        strength=0.9,
                        metadata={
                            "exit_reason": "channel_breakdown",
                            "exit_low": exit_low,
                        }
                    )
                # ATR 止损
                atr_stop = self._calc_stop(entry_low)
                if current_price <= atr_stop:
                    return Signal(
                        symbol=symbol,
                        side=SignalSide.CLOSE,
                        signal_type=SignalType.EXIT,
                        price=current_price,
                        strength=1.0,
                        metadata={
                            "exit_reason": "atr_stop",
                            "atr_stop": atr_stop,
                            "atr": self._atr,
                        }
                    )
            
            # 空头出场：涨破 exit_high
            elif position.side == SignalSide.SHORT:
                if prev_price < prev_exit_high and current_price >= exit_high:
                    return Signal(
                        symbol=symbol,
                        side=SignalSide.CLOSE,
                        signal_type=SignalType.EXIT,
                        price=current_price,
                        strength=0.9,
                        metadata={
                            "exit_reason": "channel_breakout",
                            "exit_high": exit_high,
                        }
                    )
                # ATR 止损
                atr_stop = self._calc_stop_short(entry_high)
                if current_price >= atr_stop:
                    return Signal(
                        symbol=symbol,
                        side=SignalSide.CLOSE,
                        signal_type=SignalType.EXIT,
                        price=current_price,
                        strength=1.0,
                        metadata={
                            "exit_reason": "atr_stop",
                            "atr_stop": atr_stop,
                            "atr": self._atr,
                        }
                    )
        
        # ========== 5. 入场信号（无持仓时） ==========
        if not position or not self.has_position(symbol):
            # 多头入场：向上突破 entry_high
            if prev_price <= prev_entry_high and current_price > entry_high:
                strength = self._calculate_strength(data)
                if strength < p["min_strength"]:
                    return None
                
                self._position_units = 1
                self._entry_price = current_price
                self._last_entry_unit_price = current_price
                atr_stop = self._calc_stop(entry_low)
                
                return Signal(
                    symbol=symbol,
                    side=SignalSide.LONG,
                    signal_type=SignalType.ENTRY,
                    price=current_price,
                    stop_loss=atr_stop,
                    take_profit=None,  # 海龟不预设止盈，靠 ATR 追踪
                    strength=strength,
                    metadata={
                        "system": 1 if not p["use_system1_only"] else 1,
                        "entry_high": entry_high,
                        "entry_low": entry_low,
                        "atr": self._atr,
                        "atr_stop": atr_stop,
                        "atr_multiplier": p["atr_multiplier"],
                    }
                )
            
            # 空头入场：向下跌破 entry_low
            if prev_price >= prev_entry_low and current_price < entry_low:
                strength = self._calculate_strength(data)
                if strength < p["min_strength"]:
                    return None
                
                self._position_units = 1
                self._entry_price = current_price
                self._last_entry_unit_price = current_price
                atr_stop = self._calc_stop_short(entry_high)
                
                return Signal(
                    symbol=symbol,
                    side=SignalSide.SHORT,
                    signal_type=SignalType.ENTRY,
                    price=current_price,
                    stop_loss=atr_stop,
                    take_profit=None,
                    strength=strength,
                    metadata={
                        "system": 1 if not p["use_system1_only"] else 1,
                        "entry_high": entry_high,
                        "entry_low": entry_low,
                        "atr": self._atr,
                        "atr_stop": atr_stop,
                        "atr_multiplier": p["atr_multiplier"],
                    }
                )
        
        return None
    
    def _calc_stop(self, entry_low: float) -> float:
        """计算多头止损价格 = 入场最低价 - N * ATR"""
        return entry_low - self._atr * self.params["atr_multiplier"]
    
    def _calc_stop_short(self, entry_high: float) -> float:
        """计算空头止损价格 = 入场最高价 + N * ATR"""
        return entry_high + self._atr * self.params["atr_multiplier"]
    
    def _calculate_strength(self, data: pd.DataFrame) -> float:
        """
        计算信号强度
        
        基于：
        1. 突破幅度（相对 ATR）
        2. 趋势持续性（ADX）
        3. 成交量确认
        """
        close = data["close"]
        volume = data["volume"]
        high = data["high"]
        low = data["low"]
        
        # 1. 突破强度（相对 ATR）
        if self._atr and self._atr > 0:
            recent_range = (high.iloc[-1] - low.iloc[-1])
            breakout_ratio = min((recent_range / self._atr), 3.0) / 3.0
        else:
            breakout_ratio = 0.5
        
        # 2. 趋势强度（简化版 ADX）
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        tr14 = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        atr14 = tr14.rolling(14).mean()
        
        di14_pos = 100 * (plus_dm.rolling(14).mean() / atr14)
        di14_neg = 100 * (minus_dm.rolling(14).mean() / atr14)
        dx = 100 * (di14_pos - di14_neg).abs() / (di14_pos + di14_neg)
        adx = dx.rolling(14).mean()
        
        adx_val = adx.iloc[-1] if not adx.empty and adx.iloc[-1] > 0 else 20
        adx_score = min(adx_val / 40, 1.0)  # ADX > 40 表示强趋势
        
        # 3. 成交量
        avg_vol = volume.rolling(20).mean()
        vol_ratio = volume.iloc[-1] / avg_vol.iloc[-1]
        vol_score = min(vol_ratio / 2.0, 1.0)
        
        strength = (
            0.4 * breakout_ratio +
            0.4 * adx_score +
            0.2 * vol_score
        )
        
        return min(1.0, max(0.0, strength))
    
    def on_position_opened(self, position: Position):
        """持仓开启回调"""
        super().on_position_opened(position)
        # 入场时重置单位计数
        self._position_units = 1
        self._entry_price = position.entry_price
        self._last_entry_unit_price = position.entry_price
    
    def on_position_closed(self, symbol: str):
        """持仓关闭回调"""
        super().on_position_closed(symbol)
        self._position_units = 0
        self._entry_price = None
        self._last_entry_unit_price = None
