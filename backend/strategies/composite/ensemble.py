"""
集成策略 - Ensemble Strategy

多个策略投票决定交易信号，适合降低误判率
"""
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from strategies.base import Strategy, Signal, SignalSide, SignalType


class EnsembleStrategy(Strategy):
    """
    集成策略
    
    使用多个策略进行投票，只有达到阈值才生成信号
    
    投票模式:
    - majority: 多数票 (超过 50%)
    - unanimity: 全票通过
    - weighted: 加权投票
    - confidence: 置信度加权
    """
    
    def __init__(self, params: Dict[str, Any]):
        """
        初始化集成策略
        
        Args:
            params: {
                "strategies": ["ma_cross", "macd", "breakout"],
                "strategy_params": {
                    "ma_cross": {"fast_period": 20, "slow_period": 60},
                    "macd": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
                    "breakout": {"lookback_period": 20},
                },
                "voting_mode": "majority",  # majority, unanimity, weighted, confidence
                "threshold": 0.5,  # 信号阈值 (0-1)
                "min_strength": 0.3,  # 最小信号强度
            }
        """
        self.name = "ensemble"
        self.params = params
        self.sub_strategies = []
        self.voting_mode = params.get("voting_mode", "majority")
        self.threshold = params.get("threshold", 0.5)
        self.min_strength = params.get("min_strength", 0.3)
        
        # 初始化子策略
        self._init_sub_strategies(
            params.get("strategies", []),
            params.get("strategy_params", {})
        )
    
    def _init_sub_strategies(self, strategy_names: List[str], strategy_params: Dict[str, Dict]):
        """初始化子策略"""
        from strategies.registry import get_strategy_class
        
        for name in strategy_names:
            strategy_class = get_strategy_class(name)
            params = strategy_params.get(name, {})
            strategy = strategy_class(params)
            self.sub_strategies.append(strategy)
    
    def set_params(self, params: Dict[str, Any]):
        """更新参数"""
        self.params.update(params)
    
    def generate_signals(self, data: pd.DataFrame, symbol: str) -> List[Signal]:
        """
        生成集成信号
        
        收集所有子策略的信号，按投票模式决定是否生成最终信号
        """
        signals = []
        
        # 收集所有子策略的信号
        strategy_signals = {}
        for strategy in self.sub_strategies:
            try:
                sigs = strategy.generate_signals(data, symbol)
            except AttributeError:
                sig = strategy.generate_signal(data)
                sigs = [sig] if sig else []
            strategy_signals[strategy.name] = sigs
        
        # 按投票模式汇总
        if self.voting_mode == "majority":
            signals = self._vote_majority(strategy_signals, symbol, data)
        elif self.voting_mode == "unanimity":
            signals = self._vote_unanimity(strategy_signals, symbol, data)
        elif self.voting_mode == "weighted":
            signals = self._vote_weighted(strategy_signals, symbol, data)
        elif self.voting_mode == "confidence":
            signals = self._vote_confidence(strategy_signals, symbol, data)
        
        return signals
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """兼容基类接口"""
        signals = self.generate_signals(data, "BTCUSDT")
        return signals[0] if signals else None
    
    def _vote_majority(self, strategy_signals: Dict[str, List[Signal]], symbol: str, data: pd.DataFrame) -> List[Signal]:
        """多数票投票"""
        signals = []
        n_strategies = len(self.sub_strategies)
        required_votes = int(n_strategies * self.threshold) + 1
        
        # 统计多空票数
        long_votes = sum(1 for sigs in strategy_signals.values() 
                        for s in sigs if s.side == SignalSide.LONG)
        short_votes = sum(1 for sigs in strategy_signals.values() 
                         for s in sigs if s.side == SignalSide.SHORT)
        
        # 计算平均强度
        all_signals = [s for sigs in strategy_signals.values() for s in sigs]
        avg_strength = np.mean([s.strength for s in all_signals]) if all_signals else 0
        
        # 生成最终信号
        if long_votes >= required_votes and avg_strength >= self.min_strength:
            signals.append(Signal(
                symbol=symbol,
                side=SignalSide.LONG,
                signal_type=SignalType.ENTRY,
                price=data.iloc[-1]["close"],
                strength=avg_strength,
                metadata={"votes": long_votes, "total": n_strategies}
            ))
        elif short_votes >= required_votes and avg_strength >= self.min_strength:
            signals.append(Signal(
                symbol=symbol,
                side=SignalSide.SHORT,
                signal_type=SignalType.ENTRY,
                price=data.iloc[-1]["close"],
                strength=avg_strength,
                metadata={"votes": short_votes, "total": n_strategies}
            ))
        
        return signals
    
    def _vote_unanimity(self, strategy_signals: Dict[str, List[Signal]], symbol: str, data: pd.DataFrame) -> List[Signal]:
        """全票通过投票"""
        signals = []
        n_strategies = len(self.sub_strategies)
        
        # 检查是否所有策略都看多或看空
        all_long = all(
            any(s.side == SignalSide.LONG for s in sigs)
            for sigs in strategy_signals.values()
        )
        all_short = all(
            any(s.side == SignalSide.SHORT for s in sigs)
            for sigs in strategy_signals.values()
        )
        
        all_signals = [s for sigs in strategy_signals.values() for s in sigs]
        avg_strength = np.mean([s.strength for s in all_signals]) if all_signals else 0
        
        if all_long and avg_strength >= self.min_strength:
            signals.append(Signal(
                symbol=symbol,
                side=SignalSide.LONG,
                signal_type=SignalType.ENTRY,
                price=data.iloc[-1]["close"],
                strength=avg_strength,
                metadata={"votes": n_strategies, "total": n_strategies, "mode": "unanimity"}
            ))
        elif all_short and avg_strength >= self.min_strength:
            signals.append(Signal(
                symbol=symbol,
                side=SignalSide.SHORT,
                signal_type=SignalType.ENTRY,
                price=data.iloc[-1]["close"],
                strength=avg_strength,
                metadata={"votes": n_strategies, "total": n_strategies, "mode": "unanimity"}
            ))
        
        return signals
    
    def _vote_weighted(self, strategy_signals: Dict[str, List[Signal]], symbol: str, data: pd.DataFrame) -> List[Signal]:
        """加权投票"""
        # TODO: 根据策略历史表现分配权重
        return self._vote_majority(strategy_signals, symbol, data)
    
    def _vote_confidence(self, strategy_signals: Dict[str, List[Signal]], symbol: str, data: pd.DataFrame) -> List[Signal]:
        """置信度加权投票"""
        # 使用信号强度作为置信度
        return self._vote_majority(strategy_signals, symbol, data)
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """验证数据格式"""
        required_columns = ["open", "high", "low", "close", "volume", "timestamp"]
        return all(col in data.columns for col in required_columns)
