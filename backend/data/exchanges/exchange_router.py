"""
交易所路由 - 统一多交易所访问
"""

import logging
from typing import Optional, Dict, List, Type
from decimal import Decimal

from .base import ExchangeBase, ExchangeType
from .binance_client import BinanceClient
from .okx_client import OKXClient
from .bybit_client import BybitClient

logger = logging.getLogger(__name__)


class ExchangeRouter:
    """
    交易所路由器
    
    统一管理多个交易所客户端，提供：
    - 交易所注册
    - 智能路由（最佳价格）
    - 故障转移
    - 负载均衡
    """
    
    def __init__(self):
        """初始化路由器"""
        self._exchanges: Dict[ExchangeType, ExchangeBase] = {}
        self._default_exchange: Optional[ExchangeType] = None
        self._exchange_priorities: List[ExchangeType] = []
    
    def register_exchange(
        self,
        exchange_type: ExchangeType,
        client: ExchangeBase,
        priority: int = 0,
    ):
        """
        注册交易所
        
        Args:
            exchange_type: 交易所类型
            client: 交易所客户端
            priority: 优先级（数字越小优先级越高）
        """
        self._exchanges[exchange_type] = client
        
        if exchange_type not in self._exchange_priorities:
            self._exchange_priorities.insert(priority, exchange_type)
        
        logger.info(f"注册交易所：{exchange_type.value} (priority={priority})")
    
    def unregister_exchange(self, exchange_type: ExchangeType):
        """注销交易所"""
        if exchange_type in self._exchanges:
            del self._exchanges[exchange_type]
        
        if exchange_type in self._exchange_priorities:
            self._exchange_priorities.remove(exchange_type)
        
        logger.info(f"注销交易所：{exchange_type.value}")
    
    def set_default_exchange(self, exchange_type: ExchangeType):
        """设置默认交易所"""
        if exchange_type not in self._exchanges:
            raise ValueError(f"交易所未注册：{exchange_type.value}")
        
        self._default_exchange = exchange_type
        logger.info(f"设置默认交易所：{exchange_type.value}")
    
    def get_exchange(self, exchange_type: Optional[ExchangeType] = None) -> ExchangeBase:
        """
        获取交易所客户端
        
        Args:
            exchange_type: 交易所类型（可选，默认使用默认交易所）
            
        Returns:
            ExchangeBase: 交易所客户端
        """
        if exchange_type is None:
            if self._default_exchange is None:
                raise ValueError("未设置默认交易所")
            exchange_type = self._default_exchange
        
        if exchange_type not in self._exchanges:
            raise ValueError(f"交易所未注册：{exchange_type.value}")
        
        return self._exchanges[exchange_type]
    
    def get_all_exchanges(self) -> Dict[ExchangeType, ExchangeBase]:
        """获取所有已注册的交易所"""
        return self._exchanges.copy()
    
    # ========== 智能路由 ==========
    
    async def get_best_price(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
    ) -> Dict[str, any]:
        """
        获取最优价格
        
        比较所有交易所的价格，返回最优的
        
        Args:
            symbol: 交易对
            side: 买卖方向
            quantity: 数量
            
        Returns:
            dict: {exchange, price, total_cost, ...}
        """
        prices = []
        
        for exchange_type, client in self._exchanges.items():
            try:
                ticker = await client.get_ticker(symbol)
                
                if side == 'buy':
                    price = ticker['ask']
                    total_cost = price * quantity
                else:
                    price = ticker['bid']
                    total_cost = price * quantity
                
                prices.append({
                    'exchange': exchange_type,
                    'exchange_name': client.name,
                    'price': price,
                    'total_cost': total_cost,
                    'bid': ticker['bid'],
                    'ask': ticker['ask'],
                    'volume_24h': ticker.get('volume_24h'),
                })
                
            except Exception as e:
                logger.warning(f"{client.name} 获取价格失败：{e}")
        
        if not prices:
            raise Exception("所有交易所获取价格失败")
        
        # 排序：买入选最便宜的，卖出选最贵的
        if side == 'buy':
            best = min(prices, key=lambda x: x['total_cost'])
        else:
            best = max(prices, key=lambda x: x['total_cost'])
        
        return {
            'best': best,
            'all_prices': sorted(
                prices,
                key=lambda x: x['total_cost'],
                reverse=(side == 'sell')
            ),
        }
    
    async def execute_with_failover(
        self,
        method: str,
        symbol: str,
        *args,
        **kwargs,
    ) -> any:
        """
        执行订单（带故障转移）
        
        按优先级尝试各个交易所，直到成功
        
        Args:
            method: 方法名（如 place_market_order）
            symbol: 交易对
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            any: 执行结果
        """
        last_error = None
        
        # 按优先级尝试
        exchanges_to_try = (
            [self._default_exchange] +
            [e for e in self._exchange_priorities if e != self._default_exchange]
        ) if self._default_exchange else self._exchange_priorities
        
        for exchange_type in exchanges_to_try:
            client = self._exchanges.get(exchange_type)
            if not client:
                continue
            
            try:
                method_func = getattr(client, method)
                result = await method_func(symbol, *args, **kwargs)
                
                logger.info(f"{client.name} 执行成功")
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"{client.name} 执行失败：{e}")
                continue
        
        # 所有交易所都失败
        raise Exception(f"所有交易所执行失败：{last_error}")
    
    async def place_smart_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        split_orders: bool = False,
    ) -> List[dict]:
        """
        智能下单
        
        Args:
            symbol: 交易对
            side: 买卖方向
            quantity: 数量
            split_orders: 是否拆分订单到多个交易所
            
        Returns:
            List[dict]: 订单结果列表
        """
        if not split_orders:
            # 单交易所执行
            best_price = await self.get_best_price(symbol, side, quantity)
            best_exchange = best_price['best']['exchange']
            
            client = self._exchanges[best_exchange]
            result = await client.place_market_order(symbol, side, float(quantity))
            result['exchange'] = best_exchange.value
            result['reference_price'] = str(best_price['best']['price'])
            
            return [result]
        
        else:
            # 拆分到多个交易所
            results = []
            num_exchanges = len(self._exchanges)
            qty_per_exchange = quantity / num_exchanges
            
            for exchange_type, client in self._exchanges.items():
                try:
                    result = await client.place_market_order(
                        symbol, side, float(qty_per_exchange)
                    )
                    result['exchange'] = exchange_type.value
                    results.append(result)
                except Exception as e:
                    logger.error(f"{client.name} 下单失败：{e}")
            
            return results
    
    # ========== 状态管理 ==========
    
    def get_status(self) -> dict:
        """获取路由器状态"""
        return {
            'default_exchange': self._default_exchange.value if self._default_exchange else None,
            'registered_exchanges': [e.value for e in self._exchange_priorities],
            'exchanges': {
                e_type.value: client.get_status()
                for e_type, client in self._exchanges.items()
            },
        }
    
    async def check_all_connections(self) -> Dict[str, bool]:
        """检查所有交易所连接状态"""
        results = {}
        
        for exchange_type, client in self._exchanges.items():
            try:
                await client.ping()
                results[exchange_type.value] = True
            except Exception:
                results[exchange_type.value] = False
        
        return results
    
    async def connect_all(self) -> Dict[str, bool]:
        """连接所有交易所"""
        results = {}
        
        for exchange_type, client in self._exchanges.items():
            success = await client.connect()
            results[exchange_type.value] = success
        
        return results
    
    async def disconnect_all(self):
        """断开所有交易所连接"""
        for client in self._exchanges.values():
            await client.disconnect()
    
    # ========== 工厂方法 ==========
    
    @classmethod
    def create_client(
        cls,
        exchange_type: ExchangeType,
        api_key: str,
        api_secret: str,
        passphrase: Optional[str] = None,
        testnet: bool = True,
    ) -> ExchangeBase:
        """
        创建交易所客户端
        
        Args:
            exchange_type: 交易所类型
            api_key: API Key
            api_secret: API Secret
            passphrase: API Passphrase
            testnet: 是否测试网
            
        Returns:
            ExchangeBase: 交易所客户端
        """
        if exchange_type == ExchangeType.BINANCE:
            return BinanceClient(api_key, api_secret, testnet=testnet)
        elif exchange_type == ExchangeType.OKX:
            if not passphrase:
                raise ValueError("OKX requires passphrase")
            return OKXClient(api_key, api_secret, passphrase, testnet=testnet)
        elif exchange_type == ExchangeType.BYBIT:
            return BybitClient(api_key, api_secret, testnet=testnet)
        else:
            raise ValueError(f"Unsupported exchange: {exchange_type.value}")
