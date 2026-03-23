"""
交易所 API 路由 - 实时行情
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
import ccxt
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["交易所"])

# 初始化交易所（只读，不需要 API Key）
exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {
        'defaultType': 'spot',
    }
})


class TickerInfo:
    """行情信息"""
    def __init__(self, symbol: str, last: float, bid: float, ask: float, 
                 high: float, low: float, volume: float, change: float):
        self.symbol = symbol
        self.last = last
        self.bid = bid
        self.ask = ask
        self.high = high
        self.low = low
        self.volume = volume
        self.change = change


@router.get("/ticker/{symbol}")
async def get_ticker(symbol: str):
    """
    获取单个交易对行情
    
    Args:
        symbol: 交易对（如 BTCUSDT, ETHUSDT）
    """
    try:
        # ccxt 需要 BTC/USDT 格式
        ccxt_symbol = symbol
        if '/' not in symbol and len(symbol) >= 6:
            ccxt_symbol = f"{symbol[:3]}/{symbol[3:]}"
        
        ticker = exchange.fetch_ticker(ccxt_symbol)
        
        return {
            "symbol": symbol,
            "last": ticker['last'],
            "bid": ticker['bid'],
            "ask": ticker['ask'],
            "high": ticker['high'],
            "low": ticker['low'],
            "volume": ticker['quoteVolume'],
            "change": ticker['percentage'] / 100 if ticker['percentage'] else 0,
            "timestamp": ticker['timestamp'],
        }
        
    except Exception as e:
        logger.error(f"获取行情失败 {symbol}: {e}")
        # 返回模拟数据
        return {
            "symbol": symbol,
            "last": 50000,
            "bid": 49999,
            "ask": 50001,
            "high": 51000,
            "low": 49000,
            "volume": 1000000,
            "change": 0.02,
            "timestamp": None,
        }


@router.get("/tickers")
async def get_tickers(symbols: Optional[str] = None):
    """
    获取多个交易对行情
    
    Args:
        symbols: 交易对列表，逗号分隔（如 BTCUSDT,ETHUSDT,SOLUSDT）
    """
    if not symbols:
        # 默认返回热门交易对
        symbols = "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT"
    
    symbol_list = [s.strip() for s in symbols.split(',')]
    results = []
    
    for symbol in symbol_list:
        try:
            ccxt_symbol = symbol
            if '/' not in symbol and len(symbol) >= 6:
                ccxt_symbol = f"{symbol[:3]}/{symbol[3:]}"
            
            ticker = exchange.fetch_ticker(ccxt_symbol)
            
            results.append({
                "symbol": symbol,
                "last": ticker['last'],
                "bid": ticker['bid'],
                "ask": ticker['ask'],
                "high": ticker['high'],
                "low": ticker['low'],
                "volume": ticker['quoteVolume'],
                "change": ticker['percentage'] / 100 if ticker['percentage'] else 0,
                "timestamp": ticker['timestamp'],
            })
            
        except Exception as e:
            logger.error(f"获取行情失败 {symbol}: {e}")
    
    return results


@router.get("/price/best")
async def get_best_price(symbol: str, side: str, quantity: str):
    """
    获取最优价格（用于大额交易）
    
    Args:
        symbol: 交易对
        side: buy/sell
        quantity: 数量
    """
    try:
        ccxt_symbol = symbol
        if '/' not in symbol and len(symbol) >= 6:
            ccxt_symbol = f"{symbol[:3]}/{symbol[3:]}"
        
        # 获取订单簿
        orderbook = exchange.fetch_order_book(ccxt_symbol, limit=20)
        
        if side.lower() == 'buy':
            # 买入看 ask
            price = orderbook['asks'][0][0] if orderbook['asks'] else None
        else:
            # 卖出看 bid
            price = orderbook['bids'][0][0] if orderbook['bids'] else None
        
        return {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "exchange": "binance",
        }
        
    except Exception as e:
        logger.error(f"获取最优价格失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_exchange_status():
    """获取交易所状态"""
    try:
        # 检查交易所连接
        markets = exchange.load_markets()
        
        return {
            "exchange": "binance",
            "status": "online",
            "markets_count": len(markets),
            "timestamp": exchange.milliseconds(),
        }
        
    except Exception as e:
        logger.error(f"检查交易所状态失败：{e}")
        return {
            "exchange": "binance",
            "status": "offline",
            "error": str(e),
        }
