"""
板块轮动策略 - Sector Rotation Strategy

根据市场状态在不同策略间切换，适合趋势/震荡市场识别
"""
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from strategies.base import Strategy, Signal, SignalSide, SignalType


class SectorRotationStrategy(Strategy):
    """
    板块轮动策略
    
    根据市场状态 (趋势/震荡) 自动切换最适合的策略
    
    市场状态判断:
    - ADX > 25: 趋势市场 → 使用趋势策略
    - ADX < 20: 震荡市场 → 使用均值回归策略
    - 20 <= ADX <= 25: 过渡期 → 降低仓位
    """
    
    def __init__(self, params: Dict[str, Any]):
        """
        初始化轮动策略
        
        Args:
            params: {
                "trend_strategy": {"name": "ma_cross", "params": {...}},
                "mean_reversion_strategy": {"name": "rsi", "params": {...}},
                "adx_period": 14,
                "trend_threshold": 25,
                "reversion_threshold": 20,
                "lookback_period": 100,
            }
        """
        self.name = "sector_rotation"
        self.params = params
        self.adx_period = params.get("adx_period", 14)
        self.trend_threshold = params.get("trend_threshold", 25)
        self.reversion_threshold = params.get("reversion_threshold", 20)
        self.lookback_period = params.get("lookback_period", 100)
        self.current_market_state = "neutral"
        
        # 初始化子策略
        self._init_sub_strategies(params)
    
    def _init_sub_strategies(self, params: Dict[str, Any]):
        """初始化子策略"""
        from strategies.registry import get_strategy_class
        
        # 趋势策略
        trend_config = params.get("trend_strategy", {})
        if trend_config:
            strategy_class = get_strategy_class(trend_config["name"])
            self.trend_strategy = strategy_class(trend_config.get("params", {}))
        else:
            self.trend_strategy = None
        
        # 均值回归策略
        mr_config = params.get("mean_reversion_strategy", {})
        if mr_config:
            strategy_class = get_strategy_class(mr_config["name"])
            self.mr_strategy = strategy_class(mr_config.get("params", {}))
        else:
            self.mr_strategy = None
    
    def set_params(self, params: Dict[str, Any]):
        """更新参数"""
        self.params.update(params)
    
    def calculate_adx(self, data: pd.DataFrame) -> float:
        """
        计算 ADX 指标 (平均趋向指数)
        
        ADX > 25: 强趋势
        ADX < 20: 震荡市场
        """
        if len(data) < self.adx_period + 1:
            return 0.0
        
        high = data["high"].iloc[-self.adx_period-1:]
        low = data["low"].iloc[-self.adx_period-1:]
        close = data["close"].iloc[-self.adx_period-1:]
        
        # 计算 +DM 和 -DM
        plus_dm = np.zeros(self.adx_period)
        minus_dm = np.zeros(self.adx_period)
        
        for i in range(1, self.adx_period + 1):
            high_diff = high.iloc[i] - high.iloc[i-1]
            low_diff = low.iloc[i-1] - low.iloc[i]
            
            if high_diff > low_diff and high_diff > 0:
                plus_dm[i-1] = high_diff
            if low_diff > high_diff and low_diff > 0:
                minus_dm[i-1] = low_diff
        
        # 计算 TR
        tr = np.zeros(self.adx_period)
        for i in range(1, self.adx_period + 1):
            tr1 = high.iloc[i] - low.iloc[i]
            tr2 = abs(high.iloc[i] - close.iloc[i-1])
            tr3 = abs(low.iloc[i] - close.iloc[i-1])
            tr[i-1] = max(tr1, tr2, tr3)
        
        # 简化计算 (实际应该用 smoothed average)
        avg_plus_dm = np.mean(plus_dm)
        avg_minus_dm = np.mean(minus_dm)
        avg_tr = np.mean(tr)
        
        if avg_tr == 0:
            return 0.0
        
        plus_di = 100 * avg_plus_dm / avg_tr
        minus_di = 100 * avg_minus_dm / avg_tr
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0
        
        return dx
    
    def determine_market_state(self, data: pd.DataFrame) -> str:
        """判断市场状态"""
        adx = self.calculate_adx(data)
        
        if adx > self.trend_threshold:
            self.current_market_state = "trend"
        elif adx < self.reversion_threshold:
            self.current_market_state = "reversion"
        else:
            self.current_market_state = "neutral"
        
        return self.current_market_state
    
    def generate_signals(self, data: pd.DataFrame, symbol: str) -> List[Signal]:
        """
        生成轮动信号
        
        根据市场状态选择合适的策略
        """
        market_state = self.determine_market_state(data)
        
        if market_state == "trend" and self.trend_strategy:
            # 趋势市场 - 使用趋势策略
            try:
                return self.trend_strategy.generate_signals(data, symbol)
            except AttributeError:
                sig = self.trend_strategy.generate_signal(data)
                if sig:
                    sig.symbol = symbol
                    return [sig]
                return []
        
        elif market_state == "reversion" and self.mr_strategy:
            # 震荡市场 - 使用均值回归策略
            try:
                signals = self.mr_strategy.generate_signals(data, symbol)
            except AttributeError:
                sig = self.mr_strategy.generate_signal(data)
                signals = [sig] if sig else []
            
            # 降低信号强度 (震荡市场风险高)
            for signal in signals:
                signal.strength *= 0.7
                signal.symbol = symbol
            return signals
        
        else:
            # 过渡期 - 不生成信号或生成弱信号
            return []
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """兼容基类接口"""
        signals = self.generate_signals(data, "BTCUSDT")
        return signals[0] if signals else None
    
    def get_market_state(self) -> str:
        """获取当前市场状态"""
        return self.current_market_state
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """验证数据格式"""
        required_columns = ["open", "high", "low", "close", "volume", "timestamp"]
        return all(col in data.columns for col in required_columns)
