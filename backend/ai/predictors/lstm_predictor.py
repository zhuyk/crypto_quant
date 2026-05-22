"""
LSTM 价格预测器
"""

import time as _time
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """预测结果"""
    symbol: str
    timestamp: int
    predicted_price: float
    predicted_change: float
    confidence: float
    direction: str  # 'up' or 'down'
    time_horizon: int  # 预测时间范围（分钟）


class LSTMPredictor:
    """
    LSTM 价格预测器
    
    使用 LSTM 网络预测短期价格走势
    
    特性:
    - 多时间尺度预测
    - 置信度评估
    - 自适应学习
    """
    
    def __init__(
        self,
        lookback_window: int = 60,
        prediction_horizons: List[int] = None,
        threshold: float = 0.001,
    ):
        """
        Args:
            lookback_window: 回溯窗口大小（K 线数量）
            prediction_horizons: 预测时间范围（分钟）
            threshold: 交易信号阈值
        """
        self.lookback_window = lookback_window
        self.prediction_horizons = prediction_horizons or [5, 15, 30, 60]
        self.threshold = threshold
        
        # 模型状态（简化实现，实际应加载训练好的模型）
        self._is_initialized = False
        self._symbol_models = {}
        
        # 预测历史
        self._prediction_history = []
        
        # 性能统计
        self._total_predictions = 0
        self._accurate_predictions = 0
    
    def initialize(self, symbol: str, historical_data: List[dict]):
        """
        初始化模型
        
        Args:
            symbol: 交易对
            historical_data: 历史数据 [{time, open, high, low, close, volume}]
        """
        if len(historical_data) < self.lookback_window:
            logger.warning(f"历史数据不足：{len(historical_data)} < {self.lookback_window}")
            return
        
        # 准备数据
        prices = [d['close'] for d in historical_data[-self.lookback_window:]]
        volumes = [d['volume'] for d in historical_data[-self.lookback_window:]]
        
        # 计算特征
        returns = self._calculate_returns(prices)
        volatility = self._calculate_volatility(returns)
        
        # 初始化模型（简化实现）
        self._symbol_models[symbol] = {
            'last_prices': prices,
            'last_volumes': volumes,
            'mean_return': np.mean(returns),
            'volatility': volatility,
            'trend': self._detect_trend(prices),
        }
        
        self._is_initialized = True
        logger.info(f"LSTM 预测器初始化：{symbol}")
    
    def predict(
        self,
        symbol: str,
        current_price: float,
        recent_data: Optional[List[dict]] = None,
    ) -> List[PredictionResult]:
        """
        预测价格走势
        
        Args:
            symbol: 交易对
            current_price: 当前价格
            recent_data: 最近数据
            
        Returns:
            List[PredictionResult]: 多个时间范围的预测结果
        """
        if not self._is_initialized:
            raise Exception("预测器未初始化")
        
        if symbol not in self._symbol_models:
            raise Exception(f"符号 {symbol} 未初始化")
        
        model_data = self._symbol_models[symbol]
        predictions = []
        
        for horizon in self.prediction_horizons:
            # 简化预测逻辑（实际应使用训练好的 LSTM 模型）
            predicted_change = self._predict_change(
                model_data,
                current_price,
                horizon,
            )
            
            predicted_price = current_price * (1 + predicted_change)
            confidence = self._calculate_confidence(model_data, horizon)
            direction = 'up' if predicted_change > 0 else 'down'
            
            result = PredictionResult(
                symbol=symbol,
                timestamp=int(_time.time() * 1000),
                predicted_price=predicted_price,
                predicted_change=predicted_change,
                confidence=confidence,
                direction=direction,
                time_horizon=horizon,
            )
            
            predictions.append(result)
        
        # 更新历史
        self._prediction_history.extend(predictions)
        self._total_predictions += len(predictions)
        
        return predictions
    
    def get_signal(self, predictions: List[PredictionResult]) -> dict:
        """
        根据预测生成交易信号
        
        Args:
            predictions: 预测结果列表
            
        Returns:
            dict: 交易信号 {action, strength, confidence}
        """
        if not predictions:
            return {'action': 'hold', 'strength': 0, 'confidence': 0}
        
        # 加权平均预测
        weighted_change = 0
        total_weight = 0
        
        for pred in predictions:
            # 短期预测权重更高
            weight = 1.0 / pred.time_horizon
            weighted_change += pred.predicted_change * weight * pred.confidence
            total_weight += weight
        
        avg_change = weighted_change / total_weight if total_weight > 0 else 0
        
        # 生成信号
        if avg_change > self.threshold:
            action = 'buy'
            strength = min(abs(avg_change) / self.threshold, 1.0)
        elif avg_change < -self.threshold:
            action = 'sell'
            strength = min(abs(avg_change) / self.threshold, 1.0)
        else:
            action = 'hold'
            strength = 0
        
        avg_confidence = np.mean([p.confidence for p in predictions])
        
        return {
            'action': action,
            'strength': strength,
            'confidence': avg_confidence,
            'predicted_change': avg_change,
        }
    
    def _predict_change(
        self,
        model_data: dict,
        current_price: float,
        horizon: int,
    ) -> float:
        """
        预测价格变化
        
        简化实现：基于历史均值回归和趋势
        """
        mean_return = model_data['mean_return']
        volatility = model_data['volatility']
        trend = model_data['trend']
        
        # 时间因子（长期预测不确定性更高）
        time_factor = np.sqrt(horizon / 60)
        
        # 预测变化 = 趋势 + 均值回归 + 随机扰动
        trend_component = trend * time_factor
        mean_reversion = -mean_return * time_factor * 0.5
        random_component = np.random.normal(0, volatility * time_factor)
        
        predicted_change = trend_component + mean_reversion + random_component
        
        return predicted_change
    
    def _calculate_confidence(self, model_data: dict, horizon: int) -> float:
        """计算预测置信度"""
        volatility = model_data['volatility']
        
        # 置信度随时间范围降低
        base_confidence = 0.8
        time_decay = 1.0 / (1 + horizon / 60)
        
        # 波动率越高，置信度越低
        volatility_factor = 1.0 / (1 + volatility * 10)
        
        confidence = base_confidence * time_decay * volatility_factor
        
        return max(0.3, min(0.95, confidence))
    
    def _calculate_returns(self, prices: List[float]) -> np.ndarray:
        """计算收益率"""
        prices = np.array(prices)
        returns = np.diff(prices) / prices[:-1]
        return returns
    
    def _calculate_volatility(self, returns: np.ndarray) -> float:
        """计算波动率"""
        return float(np.std(returns))
    
    def _detect_trend(self, prices: List[float]) -> float:
        """检测趋势强度"""
        prices = np.array(prices)
        
        # 简单线性回归斜率
        x = np.arange(len(prices))
        slope = np.polyfit(x, prices, 1)[0]
        
        # 归一化
        trend = slope / prices.mean()
        
        return trend
    
    def update(self, symbol: str, new_data: dict):
        """
        更新模型数据
        
        Args:
            symbol: 交易对
            new_data: 新数据 {time, open, high, low, close, volume}
        """
        if symbol not in self._symbol_models:
            return
        
        model_data = self._symbol_models[symbol]
        
        # 更新价格序列
        model_data['last_prices'].append(new_data['close'])
        model_data['last_volumes'].append(new_data['volume'])
        
        # 保持窗口大小
        if len(model_data['last_prices']) > self.lookback_window:
            model_data['last_prices'].pop(0)
            model_data['last_volumes'].pop(0)
        
        # 重新计算特征
        prices = model_data['last_prices']
        returns = self._calculate_returns(prices)
        model_data['mean_return'] = np.mean(returns)
        model_data['volatility'] = self._calculate_volatility(returns)
        model_data['trend'] = self._detect_trend(prices)
    
    def get_statistics(self) -> dict:
        """获取预测统计"""
        accuracy = (
            self._accurate_predictions / self._total_predictions
            if self._total_predictions > 0 else 0
        )
        
        return {
            'total_predictions': self._total_predictions,
            'accurate_predictions': self._accurate_predictions,
            'accuracy': f"{accuracy:.2%}",
            'initialized_symbols': list(self._symbol_models.keys()),
            'prediction_horizons': self.prediction_horizons,
        }
    
    def record_prediction_accuracy(self, symbol: str, actual_change: float):
        """记录预测准确度"""
        # 查找最近的预测
        recent_predictions = [
            p for p in self._prediction_history
            if p.symbol == symbol
        ]
        
        if recent_predictions:
            latest = recent_predictions[-1]
            predicted = latest.predicted_change
            
            # 判断是否准确（方向正确）
            if (predicted > 0 and actual_change > 0) or \
               (predicted < 0 and actual_change < 0):
                self._accurate_predictions += 1
