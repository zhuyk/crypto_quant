"""
策略基类 - 所有策略必须继承此类
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import pandas as pd
import numpy as np


class SignalSide(Enum):
    """交易方向"""
    LONG = "long"
    SHORT = "short"
    CLOSE = "close"


class SignalType(Enum):
    """信号类型"""
    ENTRY = "entry"
    EXIT = "exit"
    ADJUST = "adjust"


@dataclass
class Signal:
    """交易信号"""
    symbol: str
    side: SignalSide
    signal_type: SignalType = SignalType.ENTRY
    price: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strength: float = 1.0  # 信号强度 0-1
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "signal_type": self.signal_type.value,
            "price": self.price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "strength": self.strength,
            "metadata": self.metadata,
        }


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    side: SignalSide
    quantity: float
    entry_price: float
    current_price: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    @property
    def unrealized_pnl(self) -> float:
        """未实现盈亏"""
        if self.side == SignalSide.LONG:
            return (self.current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.current_price) * self.quantity
    
    @property
    def unrealized_pnl_pct(self) -> float:
        """未实现盈亏百分比"""
        if self.side == SignalSide.LONG:
            return (self.current_price - self.entry_price) / self.entry_price
        else:
            return (self.entry_price - self.current_price) / self.entry_price


class Strategy(ABC):
    """策略基类"""
    
    # 策略元数据
    name: str = "base_strategy"
    category: str = "base"
    version: str = "1.0.0"
    author: str = "CryptoQuant"
    description: str = "基础策略类"
    
    # 注意：以下类属性不再使用可变默认值
    # 每个实例在 __init__ 中初始化自己的副本
    timeframes: List[str] = None
    params: Dict[str, Any] = None
    
    def __post_init__(self):
        """数据类后处理"""
        if self.timeframes is None:
            self.timeframes = ["1h", "4h", "1d"]
        if self.params is None:
            self.params = {}
        if self._positions is None:
            self._positions = {}
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """初始化策略 - 每个实例创建独立的可变数据副本"""
        # 创建实例级别的副本，避免类级别的可变默认值共享
        if self.__class__.params is not None:
            self.params = dict(self.__class__.params)
        else:
            self.params = {}
        
        if self.__class__.timeframes is not None:
            self.timeframes = list(self.__class__.timeframes)
        else:
            self.timeframes = ["1h", "4h", "1d"]
        
        self._positions: Dict[str, Position] = {}
        self._initialized = False
        
        if params:
            self.params.update(params)
        self.on_init()
        self._initialized = True
    
    def on_init(self):
        """策略初始化回调"""
        pass
    
    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """
        生成交易信号
        
        Args:
            data: K 线数据，包含 columns: ['open', 'high', 'low', 'close', 'volume']
        
        Returns:
            Signal 或 None
        """
        pass
    
    def set_params(self, params: Dict[str, Any]):
        """设置策略参数"""
        self.params.update(params)
        self.on_params_changed()
    
    def on_params_changed(self):
        """参数变化回调"""
        pass
    
    def on_fill(self, order: dict):
        """订单成交回调"""
        pass
    
    def on_bar(self, candle: pd.Series):
        """K 线更新回调"""
        pass
    
    def on_position_opened(self, position: Position):
        """持仓打开回调"""
        self._positions[position.symbol] = position
    
    def on_position_closed(self, symbol: str):
        """持仓关闭回调"""
        if symbol in self._positions:
            del self._positions[symbol]
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """获取持仓"""
        return self._positions.get(symbol)
    
    def get_positions(self) -> Dict[str, Position]:
        """获取所有持仓"""
        return self._positions.copy()
    
    def has_position(self, symbol: str) -> bool:
        """是否有持仓"""
        return symbol in self._positions
    
    def get_metadata(self) -> dict:
        """获取策略元数据"""
        return {
            "name": self.name,
            "category": self.category,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "timeframes": self.timeframes,
            "params": self.params,
        }
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """验证数据有效性"""
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        return all(col in data.columns for col in required_columns)
    
    def check_data_length(self, data: pd.DataFrame, min_length: int) -> bool:
        """检查数据长度"""
        return len(data) >= min_length
