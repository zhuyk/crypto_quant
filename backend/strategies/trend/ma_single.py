"""
单均线突破/跌破策略

价格突破 MA(N) 做多，跌破 MA(N) 平仓。
默认参数 N=120，适合日线级别趋势判断。
"""
import pandas as pd
import numpy as np
from typing import Optional
from strategies.base import Strategy, Signal, SignalSide, SignalType


class MASingleStrategy(Strategy):
    """单均线突破/跌破趋势策略"""
    
    # 策略元数据
    name = "ma_single"
    category = "trend"
    version = "1.0.0"
    author = "CryptoQuant"
    description = "价格突破单均线(默认MA120)做多，跌破平仓的趋势跟踪策略"
    
    # 支持的时间周期
    timeframes = ["1h", "4h", "1d"]
    
    # 默认参数
    params = {
        "ma_period": 120,       # 均线周期
        "use_ema": False,       # 使用 EMA 而非 SMA
        "stop_loss_pct": 0.08,  # 止损百分比
        "take_profit_pct": 0.0, # 止盈百分比 (0=不止盈，靠跌破均线出场)
    }
    
    def on_init(self):
        """策略初始化"""
        self._prev_above_ma = None
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """
        生成单均线突破/跌破信号

        价格从下方突破 MA → 做多
        价格从上方跌破 MA → 平仓
        """
        if not self.validate_data(data):
            return None
        
        ma_period = self.params["ma_period"]
        
        # 数据不够计算均线
        if len(data) < ma_period + 1:
            return None
        
        close = data["close"]
        
        # 计算均线
        if self.params.get("use_ema", False):
            ma = close.ewm(span=ma_period, adjust=False).mean()
        else:
            ma = close.rolling(ma_period).mean()
        
        current_price = close.iloc[-1]
        prev_price = close.iloc[-2]
        current_ma = ma.iloc[-1]
        prev_ma = ma.iloc[-2]
        
        symbol = data.get("symbol", ["UNKNOWN"]).iloc[-1] if "symbol" in data.columns else "UNKNOWN"
        
        # 判断穿越
        prev_above = prev_price > prev_ma
        curr_above = current_price > current_ma
        
        # 向上突破 MA → 做多
        if not prev_above and curr_above:
            stop_loss = None
            if self.params.get("stop_loss_pct", 0) > 0:
                stop_loss = current_price * (1 - self.params["stop_loss_pct"])
            
            take_profit = None
            if self.params.get("take_profit_pct", 0) > 0:
                take_profit = current_price * (1 + self.params["take_profit_pct"])
            
            return Signal(
                symbol=symbol,
                side=SignalSide.LONG,
                signal_type=SignalType.ENTRY,
                price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strength=min(1.0, abs(current_price - current_ma) / current_ma * 100),
                metadata={
                    "ma_value": float(current_ma),
                    "ma_period": ma_period,
                    "reason": f"价格突破 MA{ma_period}",
                },
            )
        
        # 向下跌破 MA → 平仓
        if prev_above and not curr_above:
            # 检查是否有持仓
            if self.has_position(symbol):
                return Signal(
                    symbol=symbol,
                    side=SignalSide.CLOSE,
                    signal_type=SignalType.EXIT,
                    price=current_price,
                    strength=min(1.0, abs(current_price - current_ma) / current_ma * 100),
                    metadata={
                        "ma_value": float(current_ma),
                        "ma_period": ma_period,
                        "reason": f"价格跌破 MA{ma_period}",
                    },
                )
        
        return None
