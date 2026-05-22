"""
AI 策略模块 - 机器学习和深度学习策略
"""

from .predictors.lstm_predictor import LSTMPredictor
from .predictors.ensemble_predictor import EnsemblePredictor
from .strategies.ml_strategy import MLStrategy
from .strategies.sentiment_strategy import SentimentStrategy
from .data.feature_engineering import FeatureEngineer
from .strategy_adapter import (
    MLStrategyAdapter,
    SentimentStrategyAdapter,
    EnsemblePredictorAdapter,
)

__all__ = [
    'LSTMPredictor',
    'EnsemblePredictor',
    'MLStrategy',
    'SentimentStrategy',
    'FeatureEngineer',
    # 适配器 (可被回测/策略管理系统直接使用)
    'MLStrategyAdapter',
    'SentimentStrategyAdapter',
    'EnsemblePredictorAdapter',
]
