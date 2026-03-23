"""
特征工程 - 为 ML 模型准备特征
"""

import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FeatureSet:
    """特征集合"""
    symbol: str
    timestamp: int
    features: Dict[str, float]
    label: Optional[float] = None


class FeatureEngineer:
    """
    特征工程
    
    从原始市场数据中提取特征
    
    特征类别:
    - 价格特征
    - 技术指标
    - 成交量特征
    - 波动率特征
    - 趋势特征
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Args:
            config: 配置
        """
        self.config = config or {
            'use_price_features': True,
            'use_technical_indicators': True,
            'use_volume_features': True,
            'use_volatility_features': True,
            'lookback_periods': [5, 10, 20, 60],
        }
    
    def extract_features(
        self,
        symbol: str,
        historical_data: List[dict],
        current_data: Optional[dict] = None,
    ) -> FeatureSet:
        """
        提取特征
        
        Args:
            symbol: 交易对
            historical_data: 历史数据
            current_data: 当前数据
            
        Returns:
            FeatureSet: 特征集合
        """
        features = {}
        
        # 价格特征
        if self.config.get('use_price_features', True):
            features.update(self._extract_price_features(historical_data))
        
        # 技术指标
        if self.config.get('use_technical_indicators', True):
            features.update(self._extract_technical_indicators(historical_data))
        
        # 成交量特征
        if self.config.get('use_volume_features', True):
            features.update(self._extract_volume_features(historical_data))
        
        # 波动率特征
        if self.config.get('use_volatility_features', True):
            features.update(self._extract_volatility_features(historical_data))
        
        return FeatureSet(
            symbol=symbol,
            timestamp=int(np.time.time() * 1000),
            features=features,
        )
    
    def _extract_price_features(self, data: List[dict]) -> Dict[str, float]:
        """提取价格特征"""
        if len(data) < 2:
            return {}
        
        prices = np.array([d['close'] for d in data])
        
        features = {}
        
        # 收益率
        returns = np.diff(prices) / prices[:-1]
        features['return_1'] = returns[-1] if len(returns) > 0 else 0
        features['return_5'] = np.mean(returns[-5:]) if len(returns) >= 5 else 0
        features['return_10'] = np.mean(returns[-10:]) if len(returns) >= 10 else 0
        
        # 价格位置
        high = np.array([d['high'] for d in data])
        low = np.array([d['low'] for d in data])
        
        features['price_position'] = (prices[-1] - low[-1]) / (high[-1] - low[-1]) if high[-1] != low[-1] else 0.5
        
        # 价格动量
        for period in self.config.get('lookback_periods', [5, 10, 20]):
            if len(prices) >= period:
                features[f'momentum_{period}'] = (prices[-1] - prices[-period]) / prices[-period]
        
        return features
    
    def _extract_technical_indicators(self, data: List[dict]) -> Dict[str, float]:
        """提取技术指标"""
        if len(data) < 30:
            return {}
        
        closes = np.array([d['close'] for d in data])
        highs = np.array([d['high'] for d in data])
        lows = np.array([d['low'] for d in data])
        volumes = np.array([d['volume'] for d in data])
        
        features = {}
        
        # MA
        for period in [5, 10, 20, 60]:
            if len(closes) >= period:
                ma = np.mean(closes[-period:])
                features[f'ma_{period}'] = (closes[-1] - ma) / ma
        
        # RSI
        features['rsi_14'] = self._calculate_rsi(closes, 14)
        features['rsi_7'] = self._calculate_rsi(closes, 7)
        
        # MACD
        macd, signal_line = self._calculate_macd(closes)
        features['macd'] = macd
        features['macd_signal'] = signal_line
        features['macd_hist'] = macd - signal_line
        
        # Bollinger Bands
        bb_upper, bb_lower = self._calculate_bollinger(closes)
        features['bb_position'] = (closes[-1] - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
        
        return features
    
    def _extract_volume_features(self, data: List[dict]) -> Dict[str, float]:
        """提取成交量特征"""
        if len(data) < 10:
            return {}
        
        volumes = np.array([d['volume'] for d in data])
        
        features = {}
        
        # 成交量变化
        features['volume_change'] = (volumes[-1] - volumes[-2]) / volumes[-2] if volumes[-2] > 0 else 0
        
        # 成交量均线
        for period in [5, 10, 20]:
            if len(volumes) >= period:
                avg_vol = np.mean(volumes[-period:])
                features[f'volume_ratio_{period}'] = volumes[-1] / avg_vol if avg_vol > 0 else 1
        
        # 成交量加权价格
        vwap = np.sum(volumes * np.array([d['close'] for d in data])) / np.sum(volumes)
        features['vwap_ratio'] = (data[-1]['close'] - vwap) / vwap if vwap > 0 else 0
        
        return features
    
    def _extract_volatility_features(self, data: List[dict]) -> Dict[str, float]:
        """提取波动率特征"""
        if len(data) < 20:
            return {}
        
        closes = np.array([d['close'] for d in data])
        returns = np.diff(closes) / closes[:-1]
        
        features = {}
        
        # 历史波动率
        for period in [5, 10, 20]:
            if len(returns) >= period:
                features[f'volatility_{period}'] = np.std(returns[-period:]) * np.sqrt(365)
        
        # ATR
        features['atr_14'] = self._calculate_atr(data, 14)
        
        # 波动率变化
        if len(returns) >= 20:
            recent_vol = np.std(returns[-10:])
            past_vol = np.std(returns[-20:-10])
            features['volatility_change'] = (recent_vol - past_vol) / past_vol if past_vol > 0 else 0
        
        return features
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """计算 RSI"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = deltas.copy()
        gains[gains < 0] = 0
        losses = -deltas.copy()
        losses[losses < 0] = 0
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_macd(self, prices: np.ndarray) -> tuple:
        """计算 MACD"""
        if len(prices) < 26:
            return 0.0, 0.0
        
        ema12 = self._ema(prices, 12)
        ema26 = self._ema(prices, 26)
        
        macd = ema12 - ema26
        signal = self._ema(np.array([macd]), 9)
        
        return macd, signal
    
    def _ema(self, prices: np.ndarray, period: int) -> float:
        """计算 EMA"""
        if len(prices) < period:
            return np.mean(prices)
        
        multiplier = 2 / (period + 1)
        ema = np.mean(prices[:period])
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def _calculate_bollinger(self, prices: np.ndarray, period: int = 20) -> tuple:
        """计算布林带"""
        if len(prices) < period:
            return prices[-1], prices[-1]
        
        middle = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        upper = middle + 2 * std
        lower = middle - 2 * std
        
        return upper, lower
    
    def _calculate_atr(self, data: List[dict], period: int = 14) -> float:
        """计算 ATR"""
        if len(data) < period + 1:
            return 0.0
        
        trs = []
        for i in range(1, len(data)):
            high = data[i]['high']
            low = data[i]['low']
            prev_close = data[i-1]['close']
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close),
            )
            trs.append(tr)
        
        return np.mean(trs[-period:])
    
    def normalize_features(self, features: Dict[str, float]) -> Dict[str, float]:
        """
        标准化特征
        
        Args:
            features: 原始特征
            
        Returns:
            Dict[str, float]: 标准化特征
        """
        normalized = {}
        
        for key, value in features.items():
            # 简单标准化（实际应使用训练数据统计）
            if 'volatility' in key or 'return' in key:
                normalized[key] = value * 100  # 转为百分比
            elif 'rsi' in key or 'bb_position' in key or 'price_position' in key:
                normalized[key] = value / 100  # 归一化到 0-1
            else:
                normalized[key] = value
        
        return normalized
    
    def get_feature_names(self) -> List[str]:
        """获取所有特征名称"""
        # 返回特征名称模板
        return [
            'return_1', 'return_5', 'return_10',
            'momentum_5', 'momentum_10', 'momentum_20',
            'ma_5', 'ma_10', 'ma_20', 'ma_60',
            'rsi_7', 'rsi_14',
            'macd', 'macd_signal', 'macd_hist',
            'bb_position',
            'volume_change',
            'volume_ratio_5', 'volume_ratio_10', 'volume_ratio_20',
            'vwap_ratio',
            'volatility_5', 'volatility_10', 'volatility_20',
            'atr_14',
        ]
