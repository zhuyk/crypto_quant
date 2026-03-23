"""
Binance 交易所客户端
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


class BinanceClient(ExchangeBase):
    """
    Binance 交易所客户端
    
    支持现货和合约交易
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
        futures: bool = False,
    ):
        """
        Args:
            api_key: API Key
            api_secret: API Secret
            testnet: 是否使用测试网
            futures: 是否使用合约
        """
        super().__init__(api_key, api_secret, testnet=testnet)
        
        self.futures = futures
        
        # API 端点
        if testnet:
            self.base_url = "https://testnet.binance.vision"
            self.futures_url = "https://testnet.binancefuture.com"
        else:
            self.base_url = "https://api.binance.com"
            self.futures_url = "https://fapi.binance.com"
        
        self._session: Optional[aiohttp.ClientSession] = None
    
    @property
    def name(self) -> str:
        return "Binance"
    
    @property
    def exchange_type(self) -> ExchangeType:
        return ExchangeType.BINANCE
    
    def _get_base_url(self) -> str:
        """获取基础 URL"""
        return self.futures_url if self.futures else self.base_url
    
    def _generate_signature(self, params: dict) -> str:
        """生成签名"""
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _get_headers(self) -> dict:
        """获取请求头"""
        return {
            'X-MBX-APIKEY': self.api_key,
            'Content-Type': 'application/json',
        }
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        signed: bool = False,
    ) -> dict:
        """
        发送 HTTP 请求
        
        Args:
            method: HTTP 方法
            endpoint: 端点
            params: 请求参数
            signed: 是否需要签名
            
        Returns:
            dict: 响应数据
        """
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        url = f"{self._get_base_url()}{endpoint}"
        headers = self._get_headers()
        
        if params is None:
            params = {}
        
        # 添加时间戳
        params['timestamp'] = self.get_timestamp()
        
        # 添加签名
        if signed:
            params['signature'] = self._generate_signature(params)
        
        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                data = await response.json()
                
                if response.status != 200:
                    logger.error(f"Binance API 错误：{data}")
                    raise Exception(f"Binance API Error: {data}")
                
                return data
                
        except Exception as e:
            logger.error(f"Binance 请求失败：{e}")
            raise
    
    # ========== 市场数据 ==========
    
    async def get_ticker(self, symbol: str) -> dict:
        """获取行情"""
        symbol = self.normalize_symbol(symbol)
        data = await self._request('GET', '/api/v3/ticker/24hr', {'symbol': symbol})
        
        return {
            'last': Decimal(data['lastPrice']),
            'bid': Decimal(data['bidPrice']),
            'ask': Decimal(data['askPrice']),
            'volume_24h': Decimal(data['volume']),
            'quote_volume_24h': Decimal(data['quoteVolume']),
            'price_change_24h': Decimal(data['priceChange']),
            'price_change_percent_24h': Decimal(data['priceChangePercent']),
            'high_24h': Decimal(data['highPrice']),
            'low_24h': Decimal(data['lowPrice']),
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
        
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        
        data = await self._request('GET', '/api/v3/klines', params)
        
        return [
            {
                'time': kline[0],
                'open': Decimal(kline[1]),
                'high': Decimal(kline[2]),
                'low': Decimal(kline[3]),
                'close': Decimal(kline[4]),
                'volume': Decimal(kline[5]),
                'close_time': kline[6],
                'quote_volume': Decimal(kline[7]),
                'trades_count': kline[8],
            }
            for kline in data
        ]
    
    async def get_orderbook(self, symbol: str, limit: int = 20) -> dict:
        """获取订单簿"""
        symbol = self.normalize_symbol(symbol)
        data = await self._request('GET', '/api/v3/depth', {'symbol': symbol, 'limit': limit})
        
        return {
            'bids': [[Decimal(b[0]), Decimal(b[1])] for b in data['bids']],
            'asks': [[Decimal(a[0]), Decimal(a[1])] for a in data['asks']],
        }
    
    # ========== 账户信息 ==========
    
    async def get_balance(self) -> Dict[str, dict]:
        """获取账户余额"""
        data = await self._request('GET', '/api/v3/account', signed=True)
        
        return {
            balance['asset']: {
                'free': Decimal(balance['free']),
                'locked': Decimal(balance['locked']),
                'total': Decimal(balance['free']) + Decimal(balance['locked']),
            }
            for balance in data['balances']
            if Decimal(balance['free']) > 0 or Decimal(balance['locked']) > 0
        }
    
    async def get_positions(self) -> List[dict]:
        """获取持仓（合约）"""
        if not self.futures:
            return []
        
        data = await self._request('GET', '/fapi/v2/positionRisk', signed=True)
        
        return [
            {
                'symbol': pos['symbol'],
                'side': pos['positionSide'],
                'size': Decimal(pos['positionAmt']),
                'entry_price': Decimal(pos['entryPrice']),
                'mark_price': Decimal(pos['markPrice']),
                'unrealized_pnl': Decimal(pos['unRealizedProfit']),
                'leverage': int(pos['leverage']),
            }
            for pos in data
            if Decimal(pos['positionAmt']) != 0
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
            'symbol': symbol,
            'side': side.upper(),
            'type': 'MARKET',
            'quantity': quantity,
        }
        
        data = await self._request('POST', '/api/v3/order', params, signed=True)
        
        return {
            'order_id': str(data['orderId']),
            'client_order_id': data['clientOrderId'],
            'status': data['status'],
            'filled_qty': Decimal(data['executedQty']),
            'avg_price': Decimal(data['cummulativeQuoteQty']) / Decimal(data['executedQty']) if Decimal(data['executedQty']) > 0 else Decimal('0'),
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
            'symbol': symbol,
            'side': side.upper(),
            'type': 'LIMIT',
            'quantity': quantity,
            'price': price,
            'timeInForce': time_in_force,
        }
        
        data = await self._request('POST', '/api/v3/order', params, signed=True)
        
        return {
            'order_id': str(data['orderId']),
            'client_order_id': data['clientOrderId'],
            'status': data['status'],
            'filled_qty': Decimal(data['executedQty']),
            'avg_price': Decimal(data['cummulativeQuoteQty']) / Decimal(data['executedQty']) if Decimal(data['executedQty']) > 0 else Decimal('0'),
        }
    
    async def cancel_order(self, symbol: str, order_id: str) -> dict:
        """取消订单"""
        symbol = self.normalize_symbol(symbol)
        
        data = await self._request(
            'DELETE',
            '/api/v3/order',
            {'symbol': symbol, 'orderId': order_id},
            signed=True
        )
        
        return {
            'success': True,
            'order_id': str(data['orderId']),
            'status': data['status'],
        }
    
    async def get_order(self, symbol: str, order_id: str) -> dict:
        """查询订单"""
        symbol = self.normalize_symbol(symbol)
        
        data = await self._request(
            'GET',
            '/api/v3/order',
            {'symbol': symbol, 'orderId': order_id},
            signed=True
        )
        
        return {
            'order_id': str(data['orderId']),
            'client_order_id': data['clientOrderId'],
            'symbol': data['symbol'],
            'side': data['side'],
            'type': data['type'],
            'status': data['status'],
            'quantity': Decimal(data['origQty']),
            'price': Decimal(data['price']),
            'filled_qty': Decimal(data['executedQty']),
            'avg_price': Decimal(data['cummulativeQuoteQty']) / Decimal(data['executedQty']) if Decimal(data['executedQty']) > 0 else Decimal('0'),
            'time': data['time'],
        }
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[dict]:
        """获取当前委托"""
        params = {}
        if symbol:
            params['symbol'] = self.normalize_symbol(symbol)
        
        data = await self._request('GET', '/api/v3/openOrders', params, signed=True)
        
        return [
            {
                'order_id': str(order['orderId']),
                'client_order_id': order['clientOrderId'],
                'symbol': order['symbol'],
                'side': order['side'],
                'type': order['type'],
                'quantity': Decimal(order['origQty']),
                'price': Decimal(order['price']),
                'filled_qty': Decimal(order['executedQty']),
                'time': order['time'],
            }
            for order in data
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
        
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        
        data = await self._request('GET', '/api/v3/myTrades', params, signed=True)
        
        return [
            {
                'trade_id': str(trade['id']),
                'order_id': str(trade['orderId']),
                'symbol': trade['symbol'],
                'side': trade['isBuyer'] and 'buy' or 'sell',
                'price': Decimal(trade['price']),
                'quantity': Decimal(trade['qty']),
                'commission': Decimal(trade['commission']),
                'commission_asset': trade['commissionAsset'],
                'time': trade['time'],
            }
            for trade in data
        ]
    
    # ========== 连接管理 ==========
    
    async def connect(self) -> bool:
        """建立连接"""
        try:
            await self.ping()
            self._is_connected = True
            logger.info("Binance 连接成功")
            return True
        except Exception as e:
            logger.error(f"Binance 连接失败：{e}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        if self._session:
            await self._session.close()
            self._session = None
        self._is_connected = False
        logger.info("Binance 已断开连接")
    
    async def ping(self) -> float:
        """测试连接"""
        start = time.time()
        await self._request('GET', '/api/v3/ping')
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
