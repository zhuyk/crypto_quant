"""
AI 策略适配器

将 AI/ML 策略（MLStrategy 接口）适配为传统策略（Strategy 接口），
使其可以被回测引擎和策略管理系统统一调用。

桥接两套接口:
- AI策略: generate_signal(symbol, current_data, context) -> MLSignal
- 传统策略: generate_signal(data: pd.DataFrame) -> Signal

适配后的AI策略可以:
1. 通过策略注册表统一管理
2. 被回测引擎直接调用
3. 被策略管理API统一暴露
4. 与传统技术分析策略混合使用（如组合策略）
"""

import pandas as pd
import numpy as np
import time
from typing import Optional, Dict, Any, List
import logging

from strategies.base import Strategy, Signal, SignalSide, SignalType
from ai.strategies.ml_strategy import MLStrategy, MLSignal
from ai.strategies.sentiment_strategy import SentimentStrategy
from ai.data.feature_engineering import FeatureEngineer

logger = logging.getLogger(__name__)


class MLStrategyAdapter(Strategy):
    """
    ML策略适配器基类
    
    将 MLStrategy 接口转换为 Strategy 接口，
    使 AI 策略可被回测引擎和策略管理系统调用。
    """
    
    # 元数据 - 子类覆盖
    name = "ml_adapter"
    category = "ai"
    version = "1.0.0"
    author = "CryptoQuant AI"
    description = "机器学习策略适配器"
    
    timeframes = ["1h", "4h", "1d"]
    
    params = {
        "min_confidence": 0.6,       # 最小置信度
        "min_strength": 0.3,         # 最小信号强度
        "stop_loss_pct": 0.05,       # 止损百分比
        "take_profit_pct": 0.10,     # 止盈百分比
    }
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """初始化适配器"""
        super().__init__(params)
        self._ml_strategy: Optional[MLStrategy] = None
        self._feature_engineer = FeatureEngineer()
    
    def _create_ml_strategy(self) -> MLStrategy:
        """
        创建内部 ML 策略实例（子类实现）
        """
        raise NotImplementedError
    
    def on_init(self):
        """策略初始化"""
        self._ml_strategy = self._create_ml_strategy()
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """
        适配方法：将 DataFrame 转为 ML 策略可用的格式并调用
        
        转换流程:
        1. 从 DataFrame 提取特征
        2. 构造 current_data 和 context
        3. 调用 ML 策略的 generate_signal
        4. 将 MLSignal 转换为 Signal
        """
        if not self.validate_data(data):
            return None
        
        if len(data) < 20:
            return None
        
        # 确保 ML 策略已初始化
        if not self._ml_strategy._is_initialized:
            symbol = data.get('symbol', data.iloc[-1].get('symbol', 'UNKNOWN'))
            if isinstance(symbol, pd.Series):
                symbol = symbol.iloc[-1] if len(symbol) > 0 else 'UNKNOWN'
            historical = self._df_to_historical(data)
            self._ml_strategy.initialize(symbol, historical)
        
        # 获取 symbol
        symbol = self._extract_symbol(data)
        
        # 构造 current_data
        latest = data.iloc[-1]
        current_data = {
            'price': float(latest['close']),
            'open': float(latest['open']),
            'high': float(latest['high']),
            'low': float(latest['low']),
            'close': float(latest['close']),
            'volume': float(latest['volume']),
            'timestamp': int(time.time() * 1000),
        }
        
        # 构造上下文（包含技术指标特征）
        context = self._build_context(data)
        
        # 调用 ML 策略
        try:
            ml_signal = self._ml_strategy.generate_signal(
                symbol=symbol,
                current_data=current_data,
                context=context,
            )
        except Exception as e:
            logger.debug(f"ML 策略信号生成失败: {e}")
            return None
        
        # 转换为标准 Signal
        return self._convert_signal(ml_signal, current_data['price'])
    
    def _convert_signal(self, ml_signal: MLSignal, current_price: float) -> Optional[Signal]:
        """将 MLSignal 转换为标准 Signal"""
        # 过滤低置信度/低强度信号
        min_confidence = self.params.get("min_confidence", 0.6)
        min_strength = self.params.get("min_strength", 0.3)
        
        if ml_signal.confidence < min_confidence:
            return None
        if ml_signal.strength < min_strength:
            return None
        
        # 映射 action -> SignalSide
        if ml_signal.action == 'buy':
            side = SignalSide.LONG
        elif ml_signal.action == 'sell':
            side = SignalSide.SHORT
        elif ml_signal.action == 'hold':
            return None  # hold 不产生信号
        else:
            return None
        
        # 计算止损止盈
        stop_loss_pct = self.params.get("stop_loss_pct", 0.05)
        take_profit_pct = self.params.get("take_profit_pct", 0.10)
        
        if side == SignalSide.LONG:
            stop_loss = current_price * (1 - stop_loss_pct)
            take_profit = current_price * (1 + take_profit_pct)
        else:
            stop_loss = current_price * (1 + stop_loss_pct)
            take_profit = current_price * (1 - take_profit_pct)
        
        return Signal(
            symbol=ml_signal.symbol,
            side=side,
            signal_type=SignalType.ENTRY,
            price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strength=ml_signal.strength,
            metadata={
                'confidence': ml_signal.confidence,
                'predicted_return': ml_signal.predicted_return,
                'time_horizon': ml_signal.time_horizon,
                'model_version': ml_signal.model_version,
                'features': ml_signal.features,
            },
        )
    
    def _build_context(self, data: pd.DataFrame) -> Dict[str, Any]:
        """从 DataFrame 构建 ML 策略上下文"""
        close = data['close'].values
        volume = data['volume'].values
        
        # 基础技术特征
        context = {
            'technical': {
                'sma_20': float(np.mean(close[-20:])),
                'sma_60': float(np.mean(close[-60:])) if len(close) >= 60 else float(np.mean(close)),
                'volatility': float(np.std(close[-20:]) / np.mean(close[-20:])),
                'volume_ma': float(np.mean(volume[-20:])),
                'price_change_1h': float((close[-1] - close[-2]) / close[-2]) if len(close) > 1 else 0,
                'price_change_24h': float((close[-1] - close[-24]) / close[-24]) if len(close) > 24 else 0,
            }
        }
        
        return context
    
    def _extract_symbol(self, data: pd.DataFrame) -> str:
        """从 DataFrame 提取 symbol"""
        if 'symbol' in data.columns:
            sym = data['symbol'].iloc[-1]
            if isinstance(sym, str):
                return sym
        return 'UNKNOWN'
    
    def _df_to_historical(self, data: pd.DataFrame) -> List[dict]:
        """将 DataFrame 转换为 ML 策略需要的历史数据格式"""
        records = []
        for _, row in data.tail(100).iterrows():
            records.append({
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume']),
            })
        return records


# ============================================================
# 具体适配器实现
# ============================================================

class SentimentStrategyAdapter(MLStrategyAdapter):
    """
    情绪分析策略（适配为传统策略接口）
    
    基于新闻情绪、社交媒体热度、恐惧贪婪指数进行交易。
    使用反向/趋势模式自动切换。
    """
    
    name = "ai_sentiment"
    category = "ai"
    version = "1.0.0"
    author = "CryptoQuant AI"
    description = "AI情绪分析策略 - 基于市场情绪指标的智能交易"
    
    timeframes = ["1h", "4h", "1d"]
    
    params = {
        "min_confidence": 0.6,
        "min_strength": 0.3,
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.10,
        "sentiment_threshold": 0.5,
        "extreme_threshold": 0.8,
        "contrarian": True,          # True=反向策略, False=趋势跟随
        "use_fear_greed": True,
        "lookback_period": 24,
    }
    
    def _create_ml_strategy(self) -> MLStrategy:
        """创建情绪策略实例"""
        model_config = {
            'sentiment_threshold': self.params.get('sentiment_threshold', 0.5),
            'extreme_threshold': self.params.get('extreme_threshold', 0.8),
            'contrarian': self.params.get('contrarian', True),
            'use_fear_greed': self.params.get('use_fear_greed', True),
            'lookback_period': self.params.get('lookback_period', 24),
        }
        return SentimentStrategy(
            name="sentiment_adapted",
            model_config=model_config,
        )
    
    def _build_context(self, data: pd.DataFrame) -> Dict[str, Any]:
        """为情绪策略构建上下文 - 从价格数据推导情绪指标"""
        base_context = super()._build_context(data)
        
        close = data['close'].values
        volume = data['volume'].values
        
        # 从价格行为推导简化情绪指标
        # 这在没有外部情绪数据API时作为代理
        sentiment_score = self._derive_sentiment_from_price(close, volume)
        social_volume = self._derive_social_volume_proxy(volume)
        fear_greed = self._derive_fear_greed_proxy(close)
        
        base_context['sentiment'] = {
            'sentiment_score': sentiment_score,
            'social_volume': social_volume,
            'fear_greed_index': fear_greed,
        }
        
        return base_context
    
    def _derive_sentiment_from_price(self, close: np.ndarray, volume: np.ndarray) -> float:
        """
        从价格行为推导情绪分数
        
        综合考虑: 短期动量 + 波动率 + 成交量变化
        """
        if len(close) < 20:
            return 0.0
        
        # 短期动量 (-1 to 1)
        returns_5 = (close[-1] - close[-5]) / close[-5] if close[-5] != 0 else 0
        momentum = np.clip(returns_5 * 10, -1, 1)  # 放大并限制范围
        
        # 相对成交量
        vol_ratio = volume[-1] / np.mean(volume[-20:]) if np.mean(volume[-20:]) > 0 else 1
        vol_signal = np.clip((vol_ratio - 1) * 0.5, -0.5, 0.5)
        
        # 综合 (动量为主)
        sentiment = 0.7 * momentum + 0.3 * vol_signal
        return float(np.clip(sentiment, -1, 1))
    
    def _derive_social_volume_proxy(self, volume: np.ndarray) -> float:
        """用交易量变化代理社交热度"""
        if len(volume) < 20:
            return 50.0
        
        vol_ratio = volume[-1] / np.mean(volume[-20:]) if np.mean(volume[-20:]) > 0 else 1
        return float(np.clip(vol_ratio * 50, 0, 200))
    
    def _derive_fear_greed_proxy(self, close: np.ndarray) -> float:
        """
        从价格行为推导恐惧贪婪代理指数 (0-100)
        
        - 长期上涨 + 低波动 = 贪婪 (>50)
        - 长期下跌 + 高波动 = 恐惧 (<50)
        """
        if len(close) < 30:
            return 50.0
        
        # 30日动量
        momentum_30d = (close[-1] - close[-30]) / close[-30] if close[-30] != 0 else 0
        
        # 波动率 (越高越恐惧)
        daily_returns = np.diff(close[-30:]) / close[-31:-1]
        volatility = np.std(daily_returns)
        
        # 动量贡献 (上涨=贪婪)
        momentum_score = np.clip(momentum_30d * 200 + 50, 0, 100)
        
        # 波动率贡献 (高波动=恐惧)
        volatility_score = np.clip(100 - volatility * 2000, 0, 100)
        
        # 综合
        fear_greed = 0.6 * momentum_score + 0.4 * volatility_score
        return float(np.clip(fear_greed, 0, 100))


class EnsemblePredictorAdapter(MLStrategyAdapter):
    """
    集成预测策略（适配为传统策略接口）
    
    融合多个 ML 模型的预测结果进行交易决策。
    使用加权投票机制确定交易方向。
    """
    
    name = "ai_ensemble"
    category = "ai"
    version = "1.0.0"
    author = "CryptoQuant AI"
    description = "AI集成预测策略 - 多模型融合预测交易"
    
    timeframes = ["1h", "4h"]
    
    params = {
        "min_confidence": 0.65,
        "min_strength": 0.4,
        "stop_loss_pct": 0.04,
        "take_profit_pct": 0.08,
        "momentum_weight": 0.3,
        "mean_reversion_weight": 0.3,
        "volatility_weight": 0.2,
        "trend_weight": 0.2,
        "lookback_period": 60,
    }
    
    def _create_ml_strategy(self) -> MLStrategy:
        """创建集成ML策略 - 使用简化的内嵌逻辑"""
        # 使用情绪策略作为内核（后续可替换为真正的集成模型）
        return SentimentStrategy(
            name="ensemble_core",
            model_config={
                'sentiment_threshold': 0.4,
                'extreme_threshold': 0.75,
                'contrarian': False,
                'use_fear_greed': True,
            },
        )
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """
        集成预测信号生成
        
        融合多个维度的分析:
        1. 动量分析
        2. 均值回归分析
        3. 波动率分析
        4. 趋势分析
        """
        if not self.validate_data(data):
            return None
        
        if len(data) < 60:
            return None
        
        close = data['close'].values
        volume = data['volume'].values
        high = data['high'].values
        low = data['low'].values
        
        # 多维度分析
        momentum_signal = self._momentum_analysis(close, volume)
        mean_rev_signal = self._mean_reversion_analysis(close)
        volatility_signal = self._volatility_analysis(close, high, low)
        trend_signal = self._trend_analysis(close)
        
        # 加权融合
        weights = {
            'momentum': self.params.get('momentum_weight', 0.3),
            'mean_reversion': self.params.get('mean_reversion_weight', 0.3),
            'volatility': self.params.get('volatility_weight', 0.2),
            'trend': self.params.get('trend_weight', 0.2),
        }
        
        composite_score = (
            weights['momentum'] * momentum_signal +
            weights['mean_reversion'] * mean_rev_signal +
            weights['volatility'] * volatility_signal +
            weights['trend'] * trend_signal
        )
        
        # 计算置信度（各子信号一致性越高，置信度越高）
        signals_list = [momentum_signal, mean_rev_signal, volatility_signal, trend_signal]
        agreement = 1 - np.std(signals_list)  # 一致性
        confidence = float(np.clip(0.5 + agreement * 0.3, 0.3, 0.95))
        strength = float(np.clip(abs(composite_score), 0, 1))
        
        # 最小阈值过滤
        if confidence < self.params.get('min_confidence', 0.65):
            return None
        if strength < self.params.get('min_strength', 0.4):
            return None
        
        # 确定方向
        current_price = float(close[-1])
        symbol = self._extract_symbol(data)
        
        if composite_score > 0.1:
            side = SignalSide.LONG
        elif composite_score < -0.1:
            side = SignalSide.SHORT
        else:
            return None
        
        # 止损止盈
        sl_pct = self.params.get('stop_loss_pct', 0.04)
        tp_pct = self.params.get('take_profit_pct', 0.08)
        
        if side == SignalSide.LONG:
            stop_loss = current_price * (1 - sl_pct)
            take_profit = current_price * (1 + tp_pct)
        else:
            stop_loss = current_price * (1 + sl_pct)
            take_profit = current_price * (1 - tp_pct)
        
        return Signal(
            symbol=symbol,
            side=side,
            signal_type=SignalType.ENTRY,
            price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strength=strength,
            metadata={
                'confidence': confidence,
                'composite_score': float(composite_score),
                'momentum': float(momentum_signal),
                'mean_reversion': float(mean_rev_signal),
                'volatility': float(volatility_signal),
                'trend': float(trend_signal),
                'model_version': 'ensemble_v1',
            },
        )
    
    def _momentum_analysis(self, close: np.ndarray, volume: np.ndarray) -> float:
        """动量分析 (-1 to 1)"""
        # ROC (Rate of Change)
        roc_5 = (close[-1] - close[-5]) / close[-5] if close[-5] != 0 else 0
        roc_10 = (close[-1] - close[-10]) / close[-10] if close[-10] != 0 else 0
        
        # 成交量动量
        vol_ratio = volume[-1] / np.mean(volume[-20:]) if np.mean(volume[-20:]) > 0 else 1
        vol_signal = (vol_ratio - 1) * 0.3
        
        momentum = 0.5 * roc_5 * 10 + 0.3 * roc_10 * 5 + 0.2 * vol_signal
        return float(np.clip(momentum, -1, 1))
    
    def _mean_reversion_analysis(self, close: np.ndarray) -> float:
        """均值回归分析 (-1 to 1)"""
        # Z-score
        mean_20 = np.mean(close[-20:])
        std_20 = np.std(close[-20:])
        
        if std_20 == 0:
            return 0.0
        
        z_score = (close[-1] - mean_20) / std_20
        
        # 均值回归信号（价格越偏离均值，信号越强）
        # 正z_score -> 做空信号，负z_score -> 做多信号
        signal = -z_score / 3  # 标准化到 [-1, 1] 范围
        return float(np.clip(signal, -1, 1))
    
    def _volatility_analysis(self, close: np.ndarray, high: np.ndarray, low: np.ndarray) -> float:
        """波动率分析 (-1 to 1)"""
        # ATR 相对变化
        tr = np.maximum(
            high[-14:] - low[-14:],
            np.maximum(
                np.abs(high[-14:] - close[-15:-1]),
                np.abs(low[-14:] - close[-15:-1])
            )
        )
        atr = np.mean(tr)
        atr_pct = atr / close[-1] if close[-1] != 0 else 0
        
        # 布林带位置
        mean_20 = np.mean(close[-20:])
        std_20 = np.std(close[-20:])
        
        if std_20 == 0:
            return 0.0
        
        bb_position = (close[-1] - mean_20) / (2 * std_20)
        
        # 波动率收缩后突破的倾向（低波动率 = 即将突破）
        vol_recent = np.std(close[-5:]) / np.mean(close[-5:])
        vol_history = np.std(close[-20:]) / np.mean(close[-20:])
        vol_squeeze = 1 - (vol_recent / vol_history) if vol_history > 0 else 0
        
        # 综合（布林带位置 + 波动率挤压方向）
        signal = -bb_position * 0.6 + vol_squeeze * 0.4 * np.sign(-bb_position)
        return float(np.clip(signal, -1, 1))
    
    def _trend_analysis(self, close: np.ndarray) -> float:
        """趋势分析 (-1 to 1)"""
        # 多周期均线排列
        sma_5 = np.mean(close[-5:])
        sma_20 = np.mean(close[-20:])
        sma_60 = np.mean(close[-60:]) if len(close) >= 60 else np.mean(close)
        
        # 均线多头/空头排列程度
        if sma_5 > sma_20 > sma_60:
            # 完美多头
            spread = (sma_5 - sma_60) / sma_60
            signal = min(1.0, spread * 20)
        elif sma_5 < sma_20 < sma_60:
            # 完美空头
            spread = (sma_60 - sma_5) / sma_60
            signal = -min(1.0, spread * 20)
        else:
            # 混乱
            signal = 0.0
        
        return float(np.clip(signal, -1, 1))
