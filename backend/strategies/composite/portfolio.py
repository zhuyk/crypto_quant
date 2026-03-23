"""
多策略组合策略 - Portfolio Strategy

支持多个策略并行运行，按权重分配资金
"""
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from strategies.base import Strategy, Signal, SignalSide, SignalType, Position


class PortfolioStrategy(Strategy):
    """
    多策略组合策略
    
    将资金按权重分配给多个子策略，每个子策略独立运行
    
    特点:
    - 资金分散配置
    - 策略间风险隔离
    - 可自定义权重
    """
    
    def __init__(self, params: Dict[str, Any]):
        """
        初始化组合策略
        
        Args:
            params: {
                "strategies": [
                    {"name": "ma_cross", "params": {...}, "weight": 0.5},
                    {"name": "macd", "params": {...}, "weight": 0.5},
                ],
                "rebalance_period": 24,  # 再平衡周期 (小时)
                "max_position_per_strategy": 0.3,  # 单个策略最大仓位
            }
        """
        self.name = "portfolio"
        self.params = params
        self.sub_strategies = []
        self.weights = []
        self.strategy_capital = {}
        self.rebalance_period = params.get("rebalance_period", 24)
        self.max_position_per_strategy = params.get("max_position_per_strategy", 0.3)
        self.last_rebalance_bar = 0
        
        # 初始化子策略
        self._init_sub_strategies(params.get("strategies", []))
    
    def _init_sub_strategies(self, strategy_configs: List[Dict[str, Any]]):
        """初始化子策略"""
        from strategies.registry import get_strategy_class
        
        for config in strategy_configs:
            strategy_name = config["name"]
            strategy_params = config.get("params", {})
            weight = config.get("weight", 1.0 / len(strategy_configs))
            
            strategy_class = get_strategy_class(strategy_name)
            strategy = strategy_class(strategy_params)
            
            self.sub_strategies.append(strategy)
            self.weights.append(weight)
            self.strategy_capital[strategy.name] = 0.0
        
        # 归一化权重
        total_weight = sum(self.weights)
        self.weights = [w / total_weight for w in self.weights]
    
    def set_params(self, params: Dict[str, Any]):
        """更新参数"""
        self.params.update(params)
    
    def generate_signals(self, data: pd.DataFrame, symbol: str) -> List[Signal]:
        """
        生成组合信号
        
        每个子策略独立生成信号，按权重汇总
        """
        all_signals = []
        
        for i, strategy in enumerate(self.sub_strategies):
            # 为每个策略生成信号
            try:
                # 尝试调用 generate_signals (新接口)
                signals = strategy.generate_signals(data, symbol)
            except AttributeError:
                # 回退到 generate_signal (旧接口)
                sig = strategy.generate_signal(data)
                signals = [sig] if sig else []
            
            # 按权重调整信号强度
            for signal in signals:
                signal.strength *= self.weights[i]
                signal.symbol = symbol  # 确保 symbol 正确
            
            all_signals.extend(signals)
        
        return all_signals
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """兼容基类接口"""
        signals = self.generate_signals(data, "BTCUSDT")
        return signals[0] if signals else None
    
    def should_rebalance(self, current_bar: int) -> bool:
        """检查是否需要再平衡"""
        if current_bar - self.last_rebalance_bar >= self.rebalance_period:
            self.last_rebalance_bar = current_bar
            return True
        return False
    
    def get_strategy_allocation(self, total_capital: float) -> Dict[str, float]:
        """获取各策略资金分配"""
        allocation = {}
        for i, strategy in enumerate(self.sub_strategies):
            allocation[strategy.name] = total_capital * self.weights[i]
        return allocation
    
    def get_performance_breakdown(self) -> Dict[str, Any]:
        """获取各策略表现分解"""
        breakdown = {}
        for strategy in self.sub_strategies:
            breakdown[strategy.name] = {
                "weight": self.weights[self.sub_strategies.index(strategy)],
                "params": strategy.params,
            }
        return breakdown
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """验证数据格式"""
        required_columns = ["open", "high", "low", "close", "volume", "timestamp"]
        return all(col in data.columns for col in required_columns)
