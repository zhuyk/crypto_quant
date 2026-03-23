"""
OKX 交易所客户端
"""

import base64
import hashlib
import hmac
import time
from typing import Optional, Dict, List
from decimal import Decimal
import aiohttp
import logging

from .base import ExchangeBase, ExchangeType

logger = logging.getLogger(__name__)


class OKXClient(ExchangeBase):
    """
    OKX 交易所客户端
    
    支持现货、合约、期权交易
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        passphrase: str,
        testnet: bool = True,
    ):
        """
        Args:
            api_key: API Key
            api_secret: API Secret
            passphrase: API Passphrase
            testnet: 是否使用测试网
        """
        super().__init__(api_key, api_secret, passphrase=passphrase, testnet=testnet)
        
        # API 端点
        if testnet:
            self.base_url = "https://www.okx.com"
        else:
            self.base_url = "https://www.okx.com"
        
        self._session: Optional[aiohttp.ClientSession] = None
    
    @property
    def name(self) -> str:
        return "OKX"
    
    @property
    def exchange_type(self) -> ExchangeType:
        return ExchangeType.OKX
    
    def _generate_signature(
        self,
        timestamp: str,
        method: str,
        endpoint: str,
        body: str = "",
    ) -> str:
        """生成 OKX 签名"""
        message = timestamp + method + endpoint + body
        mac = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode('utf-8')
    
    def _get_headers(self, method: str, endpoint: str, body: str = "") -> dict:
        """获取请求头"""
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        signature = self._generate_signature(timestamp, method, endpoint, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json',
        }
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        body: Optional[dict] = None,
    ) -> dict:
        """发送 HTTP 请求"""
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(method, endpoint, body or "")
        
        json_body = None
        if body:
            import json
            json_body = json.dumps(body)
        
        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=body,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                data = await response.json()
                
                if data.get('code') != '0':
                    logger.error(f"OKX API 错误：{data}")
                    raise Exception(f"OKX API Error: {data.get('msg')}")
                
                return data.get('data', {})
                
        except Exception as e:
            logger.error(f"OKX 请求失败：{e}")
            raise
    
    # ========== 市场数据 ==========
    
    async def get_ticker(self, symbol: str) -> dict:
        """获取行情"""
        inst_id = self._format_inst_id(symbol)
        data = await self._request('GET', f'/api/v5/market/ticker', {'instId': inst_id})
        
        return {
            'last': Decimal(data.get('last', '0')),
            'bid': Decimal(data.get('bidPx', '0')),
            'ask': Decimal(data.get('askPx', '0')),
            'volume_24h': Decimal(data.get('vol24h', '0')),
            'quote_volume_24h': Decimal(data.get('volCcy24h', '0')),
            'price_change_24h': Decimal(data.get('open24h', '0')),
            'high_24h': Decimal(data.get('high24h', '0')),
            'low_24h': Decimal(data.get('low24h', '0')),
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
        inst_id = self._format_inst_id(symbol)
        
        params = {
            'instId': inst_id,
            'bar': self._convert_interval(interval),
            'limit': limit,
        }
        
        data = await self._request('GET', '/api/v5/market/candles', params)
        
        return [
            {
                'time': int(candle[0]),
                'open': Decimal(candle[1]),
                'high': Decimal(candle[2]),
                'low': Decimal(candle[3]),
                'close': Decimal(candle[4]),
                'volume': Decimal(candle[5]),
            }
            for candle in data
        ]
    
    async def get_orderbook(self, symbol: str, limit: int = 20) -> dict:
        """获取订单簿"""
        inst_id = self._format_inst_id(symbol)
        data = await self._request('GET', '/api/v5/market/books', {'instId': inst_id, 'sz': limit})
        
        return {
            'bids': [[Decimal(b[0]), Decimal(b[1])] for b in data.get('bids', [])],
            'asks': [[Decimal(a[0]), Decimal(a[1])] for a in data.get('asks', [])],
        }
    
    # ========== 账户信息 ==========
    
    async def get_balance(self) -> Dict[str, dict]:
        """获取账户余额"""
        data = await self._request('GET', '/api/v5/account/balance', {'ccy': ''})
        
        balances = {}
        for detail in data[0].get('details', []):
            asset = detail.get('ccy')
            balances[asset] = {
                'free': Decimal(detail.get('availEq', '0')),
                'locked': Decimal(detail.get('frozenBal', '0')),
                'total': Decimal(detail.get('eq', '0')),
            }
        
        return balances
    
    async def get_positions(self) -> List[dict]:
        """获取持仓"""
        data = await self._request('GET', '/api/v5/account/positions', {'instType': 'SWAP'})
        
        return [
            {
                'symbol': pos.get('instId'),
                'side': pos.get('posSide'),
                'size': Decimal(pos.get('pos', '0')),
                'entry_price': Decimal(pos.get('avgPx', '0')),
                'mark_price': Decimal(pos.get('markPx', '0')),
                'unrealized_pnl': Decimal(pos.get('upl', '0')),
                'leverage': int(pos.get('lever', '1')),
            }
            for pos in data
            if Decimal(pos.get('pos', '0')) != 0
        ]
    
    # ========== 订单操作 ==========
    
    async def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
    ) -> dict:
        """市价单"""
        inst_id = self._format_inst_id(symbol)
        
        body = {
            'instId': inst_id,
            'tdMode': 'cash',
            'side': side.lower(),
            'ordType': 'market',
            'sz': str(quantity),
        }
        
        data = await self._request('POST', '/api/v5/trade/order', body=body)
        
        return {
            'order_id': data[0].get('ordId'),
            'client_order_id': data[0].get('clOrdId'),
            'status': data[0].get('smx'),
            'filled_qty': Decimal(data[0].get('accFillSz', '0')),
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
        inst_id = self._format_inst_id(symbol)
        
        body = {
            'instId': inst_id,
            'tdMode': 'cash',
            'side': side.lower(),
            'ordType': 'limit',
            'px': str(price),
            'sz': str(quantity),
        }
        
        data = await self._request('POST', '/api/v5/trade/order', body=body)
        
        return {
            'order_id': data[0].get('ordId'),
            'client_order_id': data[0].get('clOrdId'),
            'status': data[0].get('smx'),
        }
    
    async def cancel_order(self, symbol: str, order_id: str) -> dict:
        """取消订单"""
        inst_id = self._format_inst_id(symbol)
        
        body = {
            'instId': inst_id,
            'ordId': order_id,
        }
        
        data = await self._request('POST', '/api/v5/trade/cancel-order', body=body)
        
        return {
            'success': True,
            'order_id': data[0].get('ordId'),
        }
    
    async def get_order(self, symbol: str, order_id: str) -> dict:
        """查询订单"""
        inst_id = self._format_inst_id(symbol)
        
        data = await self._request(
            'GET',
            '/api/v5/trade/order',
            {'instId': inst_id, 'ordId': order_id}
        )
        
        order = data[0]
        return {
            'order_id': order.get('ordId'),
            'client_order_id': order.get('clOrdId'),
            'symbol': order.get('instId'),
            'side': order.get('side'),
            'type': order.get('ordType'),
            'status': order.get('state'),
            'quantity': Decimal(order.get('sz', '0')),
            'price': Decimal(order.get('px', '0')),
            'filled_qty': Decimal(order.get('accFillSz', '0')),
            'avg_price': Decimal(order.get('avgPx', '0')),
            'time': int(order.get('cTime', 0)),
        }
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[dict]:
        """获取当前委托"""
        params = {'instType': 'SPOT'}
        if symbol:
            params['instId'] = self._format_inst_id(symbol)
        
        data = await self._request('GET', '/api/v5/trade/orders-pending', params)
        
        return [
            {
                'order_id': order.get('ordId'),
                'client_order_id': order.get('clOrdId'),
                'symbol': order.get('instId'),
                'side': order.get('side'),
                'type': order.get('ordType'),
                'quantity': Decimal(order.get('sz', '0')),
                'price': Decimal(order.get('px', '0')),
                'filled_qty': Decimal(order.get('accFillSz', '0')),
                'time': int(order.get('cTime', 0)),
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
        params = {
            'instType': 'SPOT',
            'limit': limit,
        }
        
        if symbol:
            params['instId'] = self._format_inst_id(symbol)
        
        data = await self._request('GET', '/api/v5/trade/fills', params)
        
        return [
            {
                'trade_id': trade.get('tradeId'),
                'order_id': trade.get('ordId'),
                'symbol': trade.get('instId'),
                'side': trade.get('side'),
                'price': Decimal(trade.get('px', '0')),
                'quantity': Decimal(trade.get('sz', '0')),
                'commission': Decimal(trade.get('fee', '0')),
                'commission_asset': trade.get('feeCcy'),
                'time': int(trade.get('ts', 0)),
            }
            for trade in data
        ]
    
    # ========== 连接管理 ==========
    
    async def connect(self) -> bool:
        """建立连接"""
        try:
            await self.ping()
            self._is_connected = True
            logger.info("OKX 连接成功")
            return True
        except Exception as e:
            logger.error(f"OKX 连接失败：{e}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        if self._session:
            await self._session.close()
            self._session = None
        self._is_connected = False
        logger.info("OKX 已断开连接")
    
    async def ping(self) -> float:
        """测试连接"""
        start = time.time()
        await self._request('GET', '/api/v5/public/time')
        return (time.time() - start) * 1000
    
    # ========== 工具方法 ==========
    
    def _format_inst_id(self, symbol: str) -> str:
        """格式化交易对 ID（如 BTC-USDT）"""
        symbol = symbol.upper()
        if '-' in symbol:
            return symbol
        # 尝试拆分
        for quote in ['USDT', 'USD', 'BTC', 'ETH']:
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                return f"{base}-{quote}"
        return symbol
    
    def _convert_interval(self, interval: str) -> str:
        """转换时间间隔"""
        mapping = {
            '1m': '1m',
            '3m': '3m',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '1h': '1H',
            '2h': '2H',
            '4h': '4H',
            '6h': '6H',
            '12h': '12H',
            '1d': '1D',
        }
        return mapping.get(interval, '1m')
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disconnect()
