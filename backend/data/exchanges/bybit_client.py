"""
Bybit 交易所客户端
"""

import hashlib
import hmac
import time
from typing import Optional, Dict, List
from decimal import Decimal
import aiohttp
import logging

from .base import ExchangeBase, ExchangeType

logger = logging.getLogger(__name__)


class BybitClient(ExchangeBase):
    """
    Bybit 交易所客户端
    
    支持现货和合约交易
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
    ):
        """
        Args:
            api_key: API Key
            api_secret: API Secret
            testnet: 是否使用测试网
        """
        super().__init__(api_key, api_secret, testnet=testnet)
        
        # API 端点
        if testnet:
            self.base_url = "https://api-testnet.bybit.com"
        else:
            self.base_url = "https://api.bybit.com"
        
        self._session: Optional[aiohttp.ClientSession] = None
    
    @property
    def name(self) -> str:
        return "Bybit"
    
    @property
    def exchange_type(self) -> ExchangeType:
        return ExchangeType.BYBIT
    
    def _generate_signature(self, params: dict, recv_window: int = 5000) -> str:
        """生成 Bybit 签名"""
        params['api_key'] = self.api_key
        params['recv_window'] = recv_window
        params['timestamp'] = self.get_timestamp()
        
        param_str = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _get_headers(self) -> dict:
        """获取请求头"""
        return {
            'Content-Type': 'application/json',
        }
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        signed: bool = False,
    ) -> dict:
        """发送 HTTP 请求"""
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        
        if params is None:
            params = {}
        
        if signed:
            params['api_key'] = self.api_key
            params['recv_window'] = 5000
            params['timestamp'] = self.get_timestamp()
            params['sign'] = self._generate_signature(params, params['recv_window'])
        
        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=params if method == 'GET' else None,
                json=params if method == 'POST' else None,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                data = await response.json()
                
                if data.get('ret_code') != 0:
                    logger.error(f"Bybit API 错误：{data}")
                    raise Exception(f"Bybit API Error: {data.get('ret_msg')}")
                
                return data.get('result', {})
                
        except Exception as e:
            logger.error(f"Bybit 请求失败：{e}")
            raise
    
    # ========== 市场数据 ==========
    
    async def get_ticker(self, symbol: str) -> dict:
        """获取行情"""
        symbol = self.normalize_symbol(symbol)
        data = await self._request('GET', '/v2/public/tickers', {'symbol': symbol})
        
        if isinstance(data, list):
            data = data[0]
        
        return {
            'last': Decimal(data.get('last_price', '0')),
            'bid': Decimal(data.get('bid_price', '0')),
            'ask': Decimal(data.get('ask_price', '0')),
            'volume_24h': Decimal(data.get('volume_24h', '0')),
            'quote_volume_24h': Decimal(data.get('turnover_24h', '0')),
            'price_change_24h': Decimal(data.get('price_24h_pcnt', '0')),
            'high_24h': Decimal(data.get('high_price_24h', '0')),
            'low_24h': Decimal(data.get('low_price_24h', '0')),
        }
    
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[dict]:
        """获取 K 线数据"""
        symbol = self.normalize_symbol(symbol)
        
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit,
        }
        
        data = await self._request('GET', '/v2/public/kline/list', params)
        
        return [
            {
                'time': kline['at'],
                'open': Decimal(kline['open']),
                'high': Decimal(kline['high']),
                'low': Decimal(kline['low']),
                'close': Decimal(kline['close']),
                'volume': Decimal(kline['volume']),
            }
            for kline in data
        ]
    
    async def get_orderbook(self, symbol: str, limit: int = 20) -> dict:
        """获取订单簿"""
        symbol = self.normalize_symbol(symbol)
        data = await self._request('GET', '/v2/public/orderBook/L2', {'symbol': symbol})
        
        bids = [[Decimal(b['price']), Decimal(b['size'])] for b in data if b['side'] == 'Buy']
        asks = [[Decimal(a['price']), Decimal(a['size'])] for a in data if a['side'] == 'Sell']
        
        return {
            'bids': sorted(bids, key=lambda x: x[0], reverse=True)[:limit],
            'asks': sorted(asks, key=lambda x: x[0])[:limit],
        }
    
    # ========== 账户信息 ==========
    
    async def get_balance(self) -> Dict[str, dict]:
        """获取账户余额"""
        data = await self._request('GET', '/v2/private/wallet/balance', {'coin': 'All'}, signed=True)
        
        balances = {}
        for coin_data in data.get('list', []):
            asset = coin_data.get('coin')
            balances[asset] = {
                'free': Decimal(coin_data.get('availableToWithdraw', '0')),
                'locked': Decimal(coin_data.get('locked', '0')),
                'total': Decimal(coin_data.get('walletBalance', '0')),
            }
        
        return balances
    
    async def get_positions(self) -> List[dict]:
        """获取持仓"""
        data = await self._request('GET', '/v2/private/position/list', {}, signed=True)
        
        return [
            {
                'symbol': pos.get('symbol'),
                'side': pos.get('side'),
                'size': Decimal(pos.get('size', '0')),
                'entry_price': Decimal(pos.get('avg_price', '0')),
                'mark_price': Decimal(pos.get('mark_price', '0')),
                'unrealized_pnl': Decimal(pos.get('unrealised_pnl', '0')),
                'leverage': pos.get('leverage', 1),
            }
            for pos in data.get('list', [])
            if Decimal(pos.get('size', '0')) != 0
        ]
    
    # ========== 订单操作 ==========
    
    async def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
    ) -> dict:
        """市价单"""
        symbol = self.normalize_symbol(symbol)
        
        params = {
            'side': side.capitalize(),
            'symbol': symbol,
            'order_type': 'Market',
            'qty': quantity,
            'time_in_force': 'GoodTillCancel',
        }
        
        data = await self._request('POST', '/v2/private/order/create', params, signed=True)
        
        return {
            'order_id': str(data.get('order_id')),
            'client_order_id': data.get('order_link_id'),
            'status': data.get('order_status'),
            'filled_qty': Decimal(data.get('cum_exec_qty', '0')),
        }
    
    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        time_in_force: str = "GTC",
    ) -> dict:
        """限价单"""
        symbol = self.normalize_symbol(symbol)
        
        params = {
            'side': side.capitalize(),
            'symbol': symbol,
            'order_type': 'Limit',
            'qty': quantity,
            'price': price,
            'time_in_force': 'GoodTillCancel',
        }
        
        data = await self._request('POST', '/v2/private/order/create', params, signed=True)
        
        return {
            'order_id': str(data.get('order_id')),
            'client_order_id': data.get('order_link_id'),
            'status': data.get('order_status'),
        }
    
    async def cancel_order(self, symbol: str, order_id: str) -> dict:
        """取消订单"""
        symbol = self.normalize_symbol(symbol)
        
        params = {
            'symbol': symbol,
            'order_id': order_id,
        }
        
        data = await self._request('POST', '/v2/private/order/cancel', params, signed=True)
        
        return {
            'success': True,
            'order_id': str(data.get('order_id')),
        }
    
    async def get_order(self, symbol: str, order_id: str) -> dict:
        """查询订单"""
        symbol = self.normalize_symbol(symbol)
        
        params = {
            'symbol': symbol,
            'order_id': order_id,
        }
        
        data = await self._request('GET', '/v2/private/order', params, signed=True)
        
        order = data.get('list', [{}])[0]
        return {
            'order_id': str(order.get('order_id')),
            'client_order_id': order.get('order_link_id'),
            'symbol': order.get('symbol'),
            'side': order.get('side'),
            'type': order.get('order_type'),
            'status': order.get('order_status'),
            'quantity': Decimal(order.get('qty', '0')),
            'price': Decimal(order.get('price', '0')),
            'filled_qty': Decimal(order.get('cum_exec_qty', '0')),
            'avg_price': Decimal(order.get('avg_price', '0')),
            'time': order.get('created_time'),
        }
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[dict]:
        """获取当前委托"""
        params = {}
        if symbol:
            params['symbol'] = self.normalize_symbol(symbol)
        
        data = await self._request('GET', '/v2/private/order/realtime', params, signed=True)
        
        return [
            {
                'order_id': str(order.get('order_id')),
                'client_order_id': order.get('order_link_id'),
                'symbol': order.get('symbol'),
                'side': order.get('side'),
                'type': order.get('order_type'),
                'quantity': Decimal(order.get('qty', '0')),
                'price': Decimal(order.get('price', '0')),
                'filled_qty': Decimal(order.get('cum_exec_qty', '0')),
                'time': order.get('created_time'),
            }
            for order in data.get('list', [])
        ]
    
    # ========== 交易历史 ==========
    
    async def get_trades(
        self,
        symbol: str,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[dict]:
        """获取成交历史"""
        symbol = self.normalize_symbol(symbol)
        
        params = {
            'symbol': symbol,
            'limit': limit,
        }
        
        data = await self._request('GET', '/v2/private/execution/list', params, signed=True)
        
        return [
            {
                'trade_id': str(trade.get('id')),
                'order_id': str(trade.get('order_id')),
                'symbol': trade.get('symbol'),
                'side': trade.get('side'),
                'price': Decimal(trade.get('price', '0')),
                'quantity': Decimal(trade.get('qty', '0')),
                'commission': Decimal(trade.get('exec_fee', '0')),
                'commission_asset': trade.get('fee_rate', ''),
                'time': trade.get('trade_time_ms'),
            }
            for trade in data.get('list', [])
        ]
    
    # ========== 连接管理 ==========
    
    async def connect(self) -> bool:
        """建立连接"""
        try:
            await self.ping()
            self._is_connected = True
            logger.info("Bybit 连接成功")
            return True
        except Exception as e:
            logger.error(f"Bybit 连接失败：{e}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        if self._session:
            await self._session.close()
            self._session = None
        self._is_connected = False
        logger.info("Bybit 已断开连接")
    
    async def ping(self) -> float:
        """测试连接"""
        start = time.time()
        await self._request('GET', '/v2/public/time')
        return (time.time() - start) * 1000
    
    # ========== 工具方法 ==========
    
    def normalize_symbol(self, symbol: str) -> str:
        """标准化交易对符号"""
        return symbol.upper().replace('-', '').replace('_', '')
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disconnect()
