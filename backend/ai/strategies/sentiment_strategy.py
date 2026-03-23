"""
情绪分析策略 - 基于市场情绪的交易策略
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
import numpy as np
import logging
import re

from .ml_strategy import MLStrategy, MLSignal

logger = logging.getLogger(__name__)


@dataclass
class SentimentData:
    """情绪数据"""
    timestamp: int
    sentiment_score: float  # -1 (极度负面) 到 1 (极度正面)
    news_count: int
    social_volume: float
    fear_greed_index: Optional[float] = None


class SentimentStrategy(MLStrategy):
    """
    情绪分析策略
    
    基于新闻、社交媒体、恐惧贪婪指数等情绪指标进行交易
    
    特性:
    - 新闻情绪分析
    - 社交媒体情绪
    - 恐惧贪婪指数
    - 情绪极值反转
    """
    
    def __init__(
        self,
        name: str = "sentiment_strategy",
        model_config: Optional[Dict] = None,
        threshold: float = 0.001,
    ):
        """
        Args:
            name: 策略名称
            model_config: 模型配置
            threshold: 交易信号阈值
        """
        default_config = {
            'sentiment_threshold': 0.5,  # 情绪阈值
            'extreme_threshold': 0.8,    # 极值阈值
            'lookback_period': 24,       # 回溯时间（小时）
            'use_fear_greed': True,      # 使用恐惧贪婪指数
            'contrarian': True,          # 反向策略（极值反转）
        }
        
        default_config.update(model_config or {})
        
        super().__init__(name, default_config, threshold)
        
        self._sentiment_history: Dict[str, List[SentimentData]] = {}
    
    def initialize(self, symbol: str, historical_data: List[dict]):
        """初始化策略"""
        self._sentiment_history[symbol] = []
        self._is_initialized = True
        
        logger.info(f"情绪策略初始化：{symbol}")
    
    def generate_signal(
        self,
        symbol: str,
        current_data: dict,
        context: Optional[Dict] = None,
    ) -> MLSignal:
        """生成交易信号"""
        if not self._is_initialized:
            raise Exception("策略未初始化")
        
        # 获取情绪数据
        sentiment_data = context.get('sentiment') if context else None
        
        if not sentiment_data:
            # 无情绪数据，返回持有
            return MLSignal(
                symbol=symbol,
                action='hold',
                confidence=0.5,
                model_version='sentiment_v1',
            )
        
        sentiment_score = sentiment_data.get('sentiment_score', 0)
        social_volume = sentiment_data.get('social_volume', 0)
        fear_greed = sentiment_data.get('fear_greed_index')
        
        # 计算综合情绪
        composite_sentiment = self._calculate_composite_sentiment(
            sentiment_score,
            social_volume,
            fear_greed,
        )
        
        # 生成信号
        if self.model_config.get('contrarian', True):
            # 反向策略：极度悲观时买入，极度乐观时卖出
            signal = self._contrarian_signal(symbol, composite_sentiment, sentiment_data)
        else:
            # 趋势策略：跟随情绪
            signal = self._trend_signal(symbol, composite_sentiment, sentiment_data)
        
        # 添加特征
        signal.features = {
            'sentiment_score': sentiment_score,
            'social_volume': social_volume,
            'fear_greed_index': fear_greed,
            'composite_sentiment': composite_sentiment,
        }
        
        return signal
    
    def _calculate_composite_sentiment(
        self,
        sentiment_score: float,
        social_volume: float,
        fear_greed: Optional[float],
    ) -> float:
        """计算综合情绪分数"""
        # 基础情绪权重
        weights = {'sentiment': 0.5, 'volume': 0.3, 'fear_greed': 0.2}
        
        # 标准化社交量（0-1）
        normalized_volume = min(1.0, social_volume / 100)
        
        # 综合情绪
        composite = (
            weights['sentiment'] * sentiment_score +
            weights['volume'] * normalized_volume
        )
        
        if fear_greed is not None and self.model_config.get('use_fear_greed', True):
            # 恐惧贪婪指数标准化（0-100 -> -1 到 1）
            normalized_fg = (fear_greed - 50) / 50
            composite += weights['fear_greed'] * normalized_fg
        
        return composite
    
    def _contrarian_signal(
        self,
        symbol: str,
        sentiment: float,
        sentiment_data: dict,
    ) -> MLSignal:
        """
        反向策略信号
        
        极度悲观时买入，极度乐观时卖出
        """
        extreme_threshold = self.model_config.get('extreme_threshold', 0.8)
        
        if sentiment < -extreme_threshold:
            # 极度悲观，买入
            strength = min(1.0, abs(sentiment) / extreme_threshold)
            return MLSignal(
                symbol=symbol,
                action='buy',
                strength=strength,
                confidence=0.7,
                predicted_return=abs(sentiment) * 0.5,
                time_horizon=60,
                model_version='sentiment_contrarian_v1',
            )
        
        elif sentiment > extreme_threshold:
            # 极度乐观，卖出
            strength = min(1.0, sentiment / extreme_threshold)
            return MLSignal(
                symbol=symbol,
                action='sell',
                strength=strength,
                confidence=0.7,
                predicted_return=-sentiment * 0.5,
                time_horizon=60,
                model_version='sentiment_contrarian_v1',
            )
        
        else:
            # 中性，持有
            return MLSignal(
                symbol=symbol,
                action='hold',
                confidence=0.5,
                model_version='sentiment_contrarian_v1',
            )
    
    def _trend_signal(
        self,
        symbol: str,
        sentiment: float,
        sentiment_data: dict,
    ) -> MLSignal:
        """
        趋势策略信号
        
        跟随市场情绪
        """
        threshold = self.model_config.get('sentiment_threshold', 0.5)
        
        if sentiment > threshold:
            # 正面情绪，买入
            strength = min(1.0, sentiment / threshold)
            return MLSignal(
                symbol=symbol,
                action='buy',
                strength=strength,
                confidence=0.6,
                predicted_return=sentiment * 0.3,
                time_horizon=30,
                model_version='sentiment_trend_v1',
            )
        
        elif sentiment < -threshold:
            # 负面情绪，卖出
            strength = min(1.0, abs(sentiment) / threshold)
            return MLSignal(
                symbol=symbol,
                action='sell',
                strength=strength,
                confidence=0.6,
                predicted_return=sentiment * 0.3,
                time_horizon=30,
                model_version='sentiment_trend_v1',
            )
        
        else:
            return MLSignal(
                symbol=symbol,
                action='hold',
                confidence=0.5,
                model_version='sentiment_trend_v1',
            )
    
    def update_sentiment(
        self,
        symbol: str,
        sentiment_score: float,
        news_count: int,
        social_volume: float,
        fear_greed_index: Optional[float] = None,
    ):
        """
        更新情绪数据
        
        Args:
            symbol: 交易对
            sentiment_score: 情绪分数 (-1 到 1)
            news_count: 新闻数量
            social_volume: 社交媒体热度
            fear_greed_index: 恐惧贪婪指数 (0-100)
        """
        if symbol not in self._sentiment_history:
            self._sentiment_history[symbol] = []
        
        data = SentimentData(
            timestamp=int(np.time.time() * 1000),
            sentiment_score=sentiment_score,
            news_count=news_count,
            social_volume=social_volume,
            fear_greed_index=fear_greed_index,
        )
        
        self._sentiment_history[symbol].append(data)
        
        # 保持历史数据
        max_history = self.model_config.get('lookback_period', 24) * 60  # 分钟
        if len(self._sentiment_history[symbol]) > max_history:
            self._sentiment_history[symbol] = self._sentiment_history[symbol][-max_history:]
    
    def _online_learn(self, symbol: str, outcome: float):
        """在线学习（简化实现）"""
        # 实际应调整情绪阈值和权重
        pass
    
    def get_sentiment_trend(self, symbol: str, periods: int = 6) -> str:
        """
        获取情绪趋势
        
        Args:
            symbol: 交易对
            periods: 分析周期数
            
        Returns:
            str: 趋势方向 (improving/worsening/stable)
        """
        history = self._sentiment_history.get(symbol, [])
        
        if len(history) < periods:
            return 'unknown'
        
        recent = history[-periods:]
        scores = [s.sentiment_score for s in recent]
        
        # 计算趋势
        trend = scores[-1] - scores[0]
        
        if trend > 0.2:
            return 'improving'
        elif trend < -0.2:
            return 'worsening'
        else:
            return 'stable'
