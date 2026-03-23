"""
机器学习策略基类
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


@dataclass
class MLSignal:
    """
    ML 策略信号
    
    Attributes:
        symbol: 交易对
        action: 操作 (buy/sell/hold)
        strength: 信号强度 (0-1)
        confidence: 置信度 (0-1)
        predicted_return: 预期收益
        time_horizon: 时间范围（分钟）
        features: 使用的特征
        model_version: 模型版本
    """
    symbol: str
    action: str
    strength: float = 0.5
    confidence: float = 0.5
    predicted_return: float = 0.0
    time_horizon: int = 60
    features: Dict[str, float] = None
    model_version: str = "1.0"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'action': self.action,
            'strength': self.strength,
            'confidence': self.confidence,
            'predicted_return': self.predicted_return,
            'time_horizon': self.time_horizon,
            'features': self.features,
            'model_version': self.model_version,
        }


class MLStrategy(ABC):
    """
    机器学习策略基类
    
    所有 ML 策略必须继承此类并实现抽象方法
    """
    
    def __init__(
        self,
        name: str,
        model_config: Optional[Dict] = None,
        threshold: float = 0.001,
    ):
        """
        Args:
            name: 策略名称
            model_config: 模型配置
            threshold: 交易信号阈值
        """
        self.name = name
        self.model_config = model_config or {}
        self.threshold = threshold
        
        self._is_initialized = False
        self._symbol_data = {}
        
        # 性能统计
        self._total_signals = 0
        self._profitable_signals = 0
        self._total_return = 0.0
    
    @abstractmethod
    def initialize(self, symbol: str, historical_data: List[dict]):
        """
        初始化策略
        
        Args:
            symbol: 交易对
            historical_data: 历史数据
        """
        pass
    
    @abstractmethod
    def generate_signal(
        self,
        symbol: str,
        current_data: dict,
        context: Optional[Dict] = None,
    ) -> MLSignal:
        """
        生成交易信号
        
        Args:
            symbol: 交易对
            current_data: 当前数据
            context: 上下文信息
            
        Returns:
            MLSignal: 交易信号
        """
        pass
    
    def update(self, symbol: str, new_data: dict):
        """
        更新策略数据
        
        Args:
            symbol: 交易对
            new_data: 新数据
        """
        if symbol not in self._symbol_data:
            self._symbol_data[symbol] = []
        
        self._symbol_data[symbol].append(new_data)
        
        # 保持数据窗口
        max_window = self.model_config.get('max_data_window', 1000)
        if len(self._symbol_data[symbol]) > max_window:
            self._symbol_data[symbol] = self._symbol_data[symbol][-max_window:]
    
    def record_outcome(self, symbol: str, actual_return: float):
        """
        记录信号结果
        
        Args:
            symbol: 交易对
            actual_return: 实际收益
        """
        self._total_signals += 1
        self._total_return += actual_return
        
        if actual_return > 0:
            self._profitable_signals += 1
        
        # 更新模型（在线学习）
        self._online_learn(symbol, actual_return)
    
    @abstractmethod
    def _online_learn(self, symbol: str, outcome: float):
        """
        在线学习
        
        Args:
            symbol: 交易对
            outcome: 结果
        """
        pass
    
    def get_signals(
        self,
        symbols: List[str],
        current_prices: Dict[str, float],
        context: Optional[Dict] = None,
    ) -> List[MLSignal]:
        """
        批量生成信号
        
        Args:
            symbols: 交易对列表
            current_prices: 当前价格
            context: 上下文
            
        Returns:
            List[MLSignal]: 信号列表
        """
        signals = []
        
        for symbol in symbols:
            if symbol not in current_prices:
                continue
            
            try:
                signal = self.generate_signal(
                    symbol=symbol,
                    current_data={'price': current_prices[symbol]},
                    context=context,
                )
                signals.append(signal)
            except Exception as e:
                logger.error(f"生成信号失败 {symbol}: {e}")
        
        return signals
    
    def filter_signals(
        self,
        signals: List[MLSignal],
        min_confidence: float = 0.6,
        min_strength: float = 0.3,
    ) -> List[MLSignal]:
        """
        过滤信号
        
        Args:
            signals: 信号列表
            min_confidence: 最小置信度
            min_strength: 最小强度
            
        Returns:
            List[MLSignal]: 过滤后的信号
        """
        return [
            s for s in signals
            if s.confidence >= min_confidence and s.strength >= min_strength
        ]
    
    def get_performance(self) -> dict:
        """获取策略性能"""
        win_rate = (
            self._profitable_signals / self._total_signals
            if self._total_signals > 0 else 0
        )
        
        avg_return = (
            self._total_return / self._total_signals
            if self._total_signals > 0 else 0
        )
        
        return {
            'name': self.name,
            'total_signals': self._total_signals,
            'profitable_signals': self._profitable_signals,
            'win_rate': f"{win_rate:.2%}",
            'total_return': f"{self._total_return:.4%}",
            'avg_return': f"{avg_return:.4%}",
            'is_initialized': self._is_initialized,
        }
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'name': self.name,
            'model_config': self.model_config,
            'threshold': self.threshold,
            'is_initialized': self._is_initialized,
            'performance': self.get_performance(),
        }
