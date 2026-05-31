"""
Binance 数据采集器
"""
import asyncio
import ccxt
import pandas as pd
from datetime import datetime, timezone
from typing import List, Optional, Dict
from loguru import logger
import time
import functools


def _retry(max_retries: int = 3, base_delay: float = 1.0, backoff: float = 2.0):
    """
    同步重试装饰器 (指数退避)
    
    适用于网络请求等可能瞬时失败的操作。
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            delay = base_delay
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (ccxt.NetworkError, ccxt.ExchangeNotAvailable, 
                        ccxt.RequestTimeout, ConnectionError, TimeoutError) as e:
                    last_exc = e
                    if attempt == max_retries:
                        break
                    logger.warning(
                        f"⚠️ {func.__name__} 重试 {attempt+1}/{max_retries} "
                        f"(等待 {delay:.1f}s): {e}"
                    )
                    time.sleep(delay)
                    delay *= backoff
            # 所有重试耗尽
            logger.error(f"❌ {func.__name__} 重试 {max_retries} 次后仍失败: {last_exc}")
            raise last_exc
        return wrapper
    return decorator


class BinanceCollector:
    """Binance 数据采集器"""
    
    def __init__(self, testnet: bool = True):
        """
        初始化采集器
        
        Args:
            testnet: 是否使用测试网
        """
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            }
        })
        
        if testnet:
            self.exchange.urls['api'] = {
                'public': 'https://testnet.binance.vision/api/v3',
                'private': 'https://testnet.binance.vision/api/v3',
            }
        
        logger.info(f"✅ Binance 采集器初始化完成 (testnet={testnet})")
    
    @_retry(max_retries=3, base_delay=1.0, backoff=2.0)
    def fetch_klines(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 1000,
        since: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        获取 K 线数据（带自动重试）
        
        Args:
            symbol: 交易对 (如 BTC/USDT)
            timeframe: 时间周期 (1m, 5m, 15m, 1h, 4h, 1d)
            limit: 获取数量 (最多 1000)
            since: 起始时间戳 (毫秒)
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
            
        Raises:
            ccxt.NetworkError: 网络异常（重试耗尽后）
            ccxt.ExchangeError: 交易所返回错误（不重试）
        """
        # 获取 OHLCV 数据
        ohlcv = self.exchange.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            since=since,
            limit=limit,
        )
        
        if not ohlcv:
            return pd.DataFrame()
        
        # 转换为 DataFrame
        df = pd.DataFrame(
            ohlcv,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        
        # 转换时间戳
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('timestamp', inplace=True)
        
        # 数据类型转换
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        df[numeric_cols] = df[numeric_cols].astype(float)
        
        logger.debug(f"📊 获取 {symbol} {timeframe} 数据 {len(df)} 条")
        
        return df
    
    async def fetch_klines_paginated(
        self,
        symbol: str,
        timeframe: str = "1h",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        batch_size: int = 1000,
    ) -> pd.DataFrame:
        """
        分页获取历史 K 线数据（异步，不阻塞事件循环）
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            start_time: 起始时间
            end_time: 结束时间
            batch_size: 每批数量
        
        Returns:
            完整的 K 线数据
        """
        all_data = []
        
        # 计算起始时间戳
        if start_time is None:
            # 默认获取最近 30 天
            start_time = datetime.now(timezone.utc) - pd.Timedelta(days=30)
        
        if end_time is None:
            end_time = datetime.now(timezone.utc)
        
        current_time = int(start_time.timestamp() * 1000)
        end_timestamp = int(end_time.timestamp() * 1000)
        
        logger.info(f"📥 开始获取 {symbol} {timeframe} 历史数据...")
        
        while current_time < end_timestamp:
            # 获取一批数据 (fetch_klines 已有重试)
            try:
                ohlcv = self.exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=current_time,
                    limit=batch_size,
                )
            except Exception as e:
                logger.error(f"❌ 分页获取失败 {symbol} {timeframe} since={current_time}: {e}")
                break
            
            if not ohlcv:
                break
            
            all_data.extend(ohlcv)
            
            # 更新下次起始时间
            current_time = ohlcv[-1][0] + 1
            
            # 使用 asyncio.sleep 避免阻塞事件循环
            await asyncio.sleep(0.1)
            
            logger.debug(f"  已获取 {len(all_data)} 条...")
        
        # 转换为 DataFrame
        if not all_data:
            return pd.DataFrame()
        
        df = pd.DataFrame(
            all_data,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('timestamp', inplace=True)
        
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        df[numeric_cols] = df[numeric_cols].astype(float)
        
        # 过滤时间范围
        df = df[(df.index >= start_time) & (df.index <= end_time)]
        
        logger.info(f"✅ 完成获取 {symbol} {timeframe} 共 {len(df)} 条数据")
        
        return df
    
    def get_symbols(self, quote_currency: str = "USDT") -> List[str]:
        """
        获取可用的交易对列表
        
        Args:
            quote_currency: 计价货币 (如 USDT)
        
        Returns:
            交易对列表
        """
        try:
            markets = self.exchange.load_markets()
            symbols = [
                symbol for symbol in markets.keys()
                if symbol.endswith(f"/{quote_currency}") and markets[symbol]['active']
            ]
            logger.info(f"📋 获取到 {len(symbols)} 个 {quote_currency} 交易对")
            return symbols
        except Exception as e:
            logger.error(f"❌ 获取交易对列表失败：{e}")
            return []
    
    def get_server_time(self) -> datetime:
        """获取服务器时间"""
        try:
            timestamp = self.exchange.fetch_time()
            return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
        except Exception as e:
            logger.error(f"❌ 获取服务器时间失败：{e}")
            return datetime.now(timezone.utc)
    
    def get_ticker(self, symbol: str) -> Dict:
        """
        获取实时行情
        
        Args:
            symbol: 交易对
        
        Returns:
            行情字典
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'last': ticker['last'],
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'high': ticker['high'],
                'low': ticker['low'],
                'volume': ticker['quoteVolume'],
                'change': ticker['percentage'],
                'timestamp': ticker['timestamp'],
            }
        except Exception as e:
            logger.error(f"❌ 获取行情失败：{symbol} - {e}")
            return {}


# 使用示例
if __name__ == "__main__":
    collector = BinanceCollector(testnet=False)
    
    # 获取 BTC/USDT 1 小时 K 线
    df = collector.fetch_klines("BTC/USDT", "1h", limit=100)
    print(df.tail())
    
    # 获取实时价格
    ticker = collector.get_ticker("BTC/USDT")
    print(f"BTC 当前价格：{ticker['last']}")
