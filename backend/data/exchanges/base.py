"""
交易所统一接口 - 抽象基类
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, List, Any
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class ExchangeType(Enum):
    """交易所类型"""
    BINANCE = "binance"
    OKX = "okx"
    BYBIT = "bybit"
    HUOBI = "huobi"
    KUCOIN = "kucoin"


class ExchangeBase(ABC):
    """
    交易所抽象基类
    
    定义所有交易所必须实现的接口
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        passphrase: Optional[str] = None,
        testnet: bool = True,
    ):
        """
        Args:
            api_key: API Key
            api_secret: API Secret
            passphrase: API Passphrase（某些交易所需要）
            testnet: 是否使用测试网
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.testnet = testnet
        
        self._is_connected = False
    
    @property
    @abstractmethod
    def name(self) -> str:
        """交易所名称"""
        pass
    
    @property
    @abstractmethod
    def exchange_type(self) -> ExchangeType:
        """交易所类型"""
        pass
    
    # ========== 市场数据 ==========
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> dict:
        """
        获取行情
        
        Args:
            symbol: 交易对
            
        Returns:
            dict: {last, bid, ask, volume_24h, ...}
        """
        pass
    
    @abstractmethod
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[dict]:
        """
        获取 K 线数据
        
        Args:
            symbol: 交易对
            interval: 时间间隔
            limit: 数量限制
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            List[dict]: [{time, open, high, low, close, volume}, ...]
        """
        pass
    
    @abstractmethod
    async def get_orderbook(self, symbol: str, limit: int = 20) -> dict:
        """
        获取订单簿
        
        Args:
            symbol: 交易对
            limit: 深度
            
        Returns:
            dict: {bids: [[price, qty], ...], asks: [[price, qty], ...]}
        """
        pass
    
    # ========== 账户信息 ==========
    
    @abstractmethod
    async def get_balance(self) -> Dict[str, dict]:
        """
        获取账户余额
        
        Returns:
            Dict[str, dict]: {asset: {free, locked, total}, ...}
        """
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[dict]:
        """
        获取持仓信息
        
        Returns:
            List[dict]: [{symbol, side, size, entry_price, ...}, ...]
        """
        pass
    
    # ========== 订单操作 ==========
    
    @abstractmethod
    async def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
    ) -> dict:
        """
        市价单
        
        Args:
            symbol: 交易对
            side: 买卖方向
            quantity: 数量
            
        Returns:
            dict: {order_id, status, filled_qty, ...}
        """
        pass
    
    @abstractmethod
    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        time_in_force: str = "GTC",
    ) -> dict:
        """
        限价单
        
        Args:
            symbol: 交易对
            side: 买卖方向
            quantity: 数量
            price: 价格
            time_in_force: 有效期
            
        Returns:
            dict: {order_id, status, ...}
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> dict:
        """
        取消订单
        
        Args:
            symbol: 交易对
            order_id: 订单 ID
            
        Returns:
            dict: {success, ...}
        """
        pass
    
    @abstractmethod
    async def get_order(self, symbol: str, order_id: str) -> dict:
        """
        查询订单
        
        Args:
            symbol: 交易对
            order_id: 订单 ID
            
        Returns:
            dict: 订单详情
        """
        pass
    
    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[dict]:
        """
        获取当前委托
        
        Args:
            symbol: 交易对（可选）
            
        Returns:
            List[dict]: 订单列表
        """
        pass
    
    # ========== 交易历史 ==========
    
    @abstractmethod
    async def get_trades(
        self,
        symbol: str,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[dict]:
        """
        获取成交历史
        
        Args:
            symbol: 交易对
            limit: 数量限制
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            List[dict]: 成交记录列表
        """
        pass
    
    # ========== 连接管理 ==========
    
    @abstractmethod
    async def connect(self) -> bool:
        """建立连接"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """断开连接"""
        pass
    
    @abstractmethod
    async def ping(self) -> float:
        """
        测试连接
        
        Returns:
            float: 延迟（毫秒）
        """
        pass
    
    # ========== 工具方法 ==========
    
    def normalize_symbol(self, symbol: str) -> str:
        """
        标准化交易对符号
        
        Args:
            symbol: 原始符号
            
        Returns:
            str: 标准化符号
        """
        # 默认实现：转为大写
        return symbol.upper()
    
    def get_timestamp(self) -> int:
        """获取当前时间戳（毫秒）"""
        import time
        return int(time.time() * 1000)
    
    def get_status(self) -> dict:
        """获取交易所状态"""
        return {
            "name": self.name,
            "type": self.exchange_type.value,
            "is_connected": self._is_connected,
            "testnet": self.testnet,
        }
