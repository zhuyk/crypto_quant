"""
集成预测器 - 多模型融合
"""

import time as _time
from typing import List, Dict, Optional
from dataclasses import dataclass
import numpy as np
import logging

from .lstm_predictor import LSTMPredictor, PredictionResult

logger = logging.getLogger(__name__)


@dataclass
class EnsemblePrediction:
    """集成预测结果"""
    symbol: str
    timestamp: int
    predicted_price: float
    predicted_change: float
    confidence: float
    direction: str
    model_predictions: Dict[str, PredictionResult]
    model_weights: Dict[str, float]


class EnsemblePredictor:
    """
    集成预测器
    
    融合多个模型的预测结果，提高预测准确性
    
    支持:
    - 加权平均
    - 投票机制
    - 置信度加权
    """
    
    def __init__(self):
        """初始化集成预测器"""
        # 子模型
        self._models = {}
        
        # 模型权重
        self._model_weights = {}
        
        # 模型性能历史
        self._model_performance = {}
        
        # 预测历史
        self._predictions = []
    
    def add_model(
        self,
        name: str,
        model: LSTMPredictor,
        initial_weight: float = 1.0,
    ):
        """
        添加子模型
        
        Args:
            name: 模型名称
            model: 模型实例
            initial_weight: 初始权重
        """
        self._models[name] = model
        self._model_weights[name] = initial_weight
        self._model_performance[name] = {
            'total': 0,
            'accurate': 0,
            'accuracy': 0.5,
        }
        
        logger.info(f"添加模型到集成：{name} (weight={initial_weight})")
    
    def remove_model(self, name: str):
        """移除模型"""
        if name in self._models:
            del self._models[name]
            del self._model_weights[name]
            del self._model_performance[name]
            logger.info(f"从集成移除模型：{name}")
    
    def predict(
        self,
        symbol: str,
        current_price: float,
        recent_data: Optional[List[dict]] = None,
    ) -> EnsemblePrediction:
        """
        集成预测
        
        Args:
            symbol: 交易对
            current_price: 当前价格
            recent_data: 最近数据
            
        Returns:
            EnsemblePrediction: 集成预测结果
        """
        if not self._models:
            raise Exception("没有可用的模型")
        
        model_predictions = {}
        
        # 获取各模型预测
        for name, model in self._models.items():
            try:
                predictions = model.predict(symbol, current_price, recent_data)
                # 取最短时间范围的预测
                if predictions:
                    model_predictions[name] = min(
                        predictions,
                        key=lambda p: p.time_horizon,
                    )
            except Exception as e:
                logger.warning(f"模型 {name} 预测失败：{e}")
        
        if not model_predictions:
            raise Exception("所有模型预测失败")
        
        # 计算加权预测
        weighted_change = 0
        total_weight = 0
        
        for name, pred in model_predictions.items():
            weight = self._model_weights.get(name, 1.0)
            weighted_change += pred.predicted_change * weight
            total_weight += weight
        
        avg_change = weighted_change / total_weight
        predicted_price = current_price * (1 + avg_change)
        
        # 计算置信度（模型一致性）
        changes = [p.predicted_change for p in model_predictions.values()]
        consensus = 1.0 - (np.std(changes) / np.mean(abs(np.array(changes))) if np.mean(abs(np.array(changes))) > 0 else 0)
        confidence = min(0.95, max(0.3, consensus))
        
        direction = 'up' if avg_change > 0 else 'down'
        
        result = EnsemblePrediction(
            symbol=symbol,
            timestamp=int(_time.time() * 1000),
            predicted_price=predicted_price,
            predicted_change=avg_change,
            confidence=confidence,
            direction=direction,
            model_predictions=model_predictions,
            model_weights={name: self._model_weights.get(name, 1.0) for name in model_predictions},
        )
        
        self._predictions.append(result)
        
        return result
    
    def get_signal(self, prediction: EnsemblePrediction) -> dict:
        """
        生成交易信号
        
        Args:
            prediction: 集成预测结果
            
        Returns:
            dict: 交易信号
        """
        # 投票机制
        buy_votes = sum(1 for p in prediction.model_predictions.values() if p.direction == 'up')
        sell_votes = sum(1 for p in prediction.model_predictions.values() if p.direction == 'down')
        total_models = len(prediction.model_predictions)
        
        # 加权投票
        buy_weight = sum(
            self._model_weights[name]
            for name, p in prediction.model_predictions.items()
            if p.direction == 'up'
        )
        sell_weight = sum(
            self._model_weights[name]
            for name, p in prediction.model_predictions.items()
            if p.direction == 'down'
        )
        
        # 决定信号
        if buy_votes > sell_votes and buy_weight > total_models * 0.5:
            action = 'buy'
        elif sell_votes > buy_votes and sell_weight > total_models * 0.5:
            action = 'sell'
        else:
            action = 'hold'
        
        strength = min(abs(prediction.predicted_change) * 100, 1.0)
        
        return {
            'action': action,
            'strength': strength,
            'confidence': prediction.confidence,
            'buy_votes': buy_votes,
            'sell_votes': sell_votes,
            'total_models': total_models,
            'consensus': prediction.direction,
        }
    
    def update_model_weights(self, performances: Dict[str, float]):
        """
        根据性能更新模型权重
        
        Args:
            performances: 模型性能 {name: accuracy}
        """
        for name, accuracy in performances.items():
            if name in self._model_weights:
                # 性能越好，权重越高
                old_weight = self._model_weights[name]
                new_weight = old_weight * (1 + (accuracy - 0.5) * 0.2)
                self._model_weights[name] = max(0.1, min(2.0, new_weight))
                
                # 更新性能记录
                self._model_performance[name]['accuracy'] = accuracy
        
        logger.info(f"更新模型权重：{self._model_weights}")
    
    def get_model_statistics(self) -> dict:
        """获取模型统计"""
        return {
            'models': {
                name: {
                    'weight': self._model_weights.get(name, 1.0),
                    'accuracy': self._model_performance.get(name, {}).get('accuracy', 0),
                }
                for name in self._models
            },
            'total_predictions': len(self._predictions),
        }
