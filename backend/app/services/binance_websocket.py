"""
Binance WebSocket 实时数据采集
支持 K 线、深度、Ticker 等实时数据推送
"""
import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from enum import Enum

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from app.core.config import settings
from app.utils.cache import get_cache, CacheKeys

logger = logging.getLogger(__name__)


class KlineInterval(Enum):
    """K 线时间间隔"""
    ONE_MINUTE = "1m"
    THREE_MINUTES = "3m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    TWO_HOURS = "2h"
    FOUR_HOURS = "4h"
    SIX_HOURS = "6h"
    EIGHT_HOURS = "8h"
    TWELVE_HOURS = "12h"
    ONE_DAY = "1d"
    THREE_DAYS = "3d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1M"


class BinanceWebSocket:
    """Binance WebSocket 客户端"""
    
    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        intervals: Optional[List[str]] = None,
        cache_expire: int = 60,
    ):
        """
        初始化 Binance WebSocket
        
        Args:
            symbols: 交易对列表 (如 ["BTCUSDT", "ETHUSDT"])
            intervals: K 线时间间隔列表 (如 ["1m", "5m", "1h"])
            cache_expire: 缓存过期时间 (秒)
        """
        self.symbols = symbols or settings.DEFAULT_SYMBOLS[:3]  # 默认前 3 个
        self.intervals = intervals or ["1m", "5m", "1h"]
        self.cache_expire = cache_expire
        self.cache = get_cache()
        
        # WebSocket 连接
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._reconnect_delay = 5
        self._message_count = 0
        self._last_message_time = 0
        
        # 数据回调
        self._kline_callbacks: List[Callable] = []
        self._ticker_callbacks: List[Callable] = []
        self._depth_callbacks: List[Callable] = []
        
        # 订阅流
        self._streams: List[str] = []
        
        logger.info(f"✅ Binance WebSocket 初始化完成 - 交易对：{self.symbols}")
    
    def _build_streams(self) -> List[str]:
        """构建订阅流列表"""
        streams = []
        
        # K 线流
        for symbol in self.symbols:
            symbol_lower = symbol.lower()
            for interval in self.intervals:
                streams.append(f"{symbol_lower}@kline_{interval}")
            
            # Ticker 流
            streams.append(f"{symbol_lower}@ticker")
            
            # 深度流 (5 档)
            streams.append(f"{symbol_lower}@depth5@100ms")
        
        self._streams = streams
        logger.info(f"📡 构建 {len(streams)} 个订阅流")
        
        return streams
    
    def _get_ws_url(self) -> str:
        """获取 WebSocket URL"""
        streams = self._build_streams()
        stream_str = "/".join(streams)
        return f"wss://stream.binance.com:9443/stream?streams={stream_str}"
    
    def on_kline(self, callback: Callable):
        """注册 K 线数据回调"""
        self._kline_callbacks.append(callback)
        logger.debug(f"📝 注册 K 线回调 - 当前 {len(self._kline_callbacks)} 个")
    
    def on_ticker(self, callback: Callable):
        """注册 Ticker 数据回调"""
        self._ticker_callbacks.append(callback)
        logger.debug(f"📝 注册 Ticker 回调 - 当前 {len(self._ticker_callbacks)} 个")
    
    def on_depth(self, callback: Callable):
        """注册深度数据回调"""
        self._depth_callbacks.append(callback)
        logger.debug(f"📝 注册深度回调 - 当前 {len(self._depth_callbacks)} 个")
    
    async def _handle_kline(self, data: Dict):
        """处理 K 线数据"""
        kline = data.get("k", {})
        
        kline_data = {
            "symbol": data.get("s"),
            "interval": data.get("k", {}).get("x"),  # K 线是否完成
            "open_time": data.get("k", {}).get("t"),
            "close_time": data.get("k", {}).get("T"),
            "open": float(kline.get("o", 0)),
            "high": float(kline.get("h", 0)),
            "low": float(kline.get("l", 0)),
            "close": float(kline.get("c", 0)),
            "volume": float(kline.get("v", 0)),
            "is_closed": kline.get("x", False),
            "timestamp": datetime.now().isoformat(),
        }
        
        # 缓存 K 线数据
        cache_key = CacheKeys.make_key(
            CacheKeys.SYMBOL_KLINE,
            kline_data["symbol"],
            kline_data["interval"],
        )
        self.cache.set(cache_key, kline_data, expire=self.cache_expire)
        
        # 触发回调
        for callback in self._kline_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(kline_data)
                else:
                    callback(kline_data)
            except Exception as e:
                logger.error(f"K 线回调执行失败：{e}")
        
        # 记录日志 (仅完成的 K 线)
        if kline_data["is_closed"]:
            logger.debug(
                f"📊 K 线完成 - {kline_data['symbol']} {kline_data['interval']}: "
                f"${kline_data['close']} (成交量：{kline_data['volume']})"
            )
    
    async def _handle_ticker(self, data: Dict):
        """处理 Ticker 数据"""
        ticker_data = {
            "symbol": data.get("s"),
            "price": float(data.get("c", 0)),
            "price_change": float(data.get("p", 0)),
            "price_change_pct": float(data.get("P", 0)),
            "high_24h": float(data.get("h", 0)),
            "low_24h": float(data.get("l", 0)),
            "volume_24h": float(data.get("v", 0)),
            "timestamp": datetime.now().isoformat(),
        }
        
        # 缓存价格
        cache_key = CacheKeys.make_key(
            CacheKeys.SYMBOL_PRICE,
            ticker_data["symbol"],
        )
        self.cache.set(cache_key, ticker_data, expire=10)  # 10 秒过期
        
        # 触发回调
        for callback in self._ticker_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(ticker_data)
                else:
                    callback(ticker_data)
            except Exception as e:
                logger.error(f"Ticker 回调执行失败：{e}")
    
    async def _handle_depth(self, data: Dict):
        """处理深度数据"""
        depth_data = {
            "symbol": data.get("stream", "").split("@")[0].upper(),
            "bids": data.get("data", {}).get("bids", [])[:5],  # 前 5 档买盘
            "asks": data.get("data", {}).get("asks", [])[:5],  # 前 5 档卖盘
            "timestamp": datetime.now().isoformat(),
        }
        
        # 触发回调
        for callback in self._depth_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(depth_data)
                else:
                    callback(depth_data)
            except Exception as e:
                logger.error(f"深度回调执行失败：{e}")
    
    async def _process_message(self, message: str):
        """处理 WebSocket 消息"""
        try:
            data = json.loads(message)
            self._message_count += 1
            self._last_message_time = time.time()
            
            # 调试日志 (每 100 条打印一次)
            if self._message_count % 100 == 0:
                logger.debug(f"📨 已处理 {self._message_count} 条消息")
            
            stream = data.get("stream", "")
            payload = data.get("data", {})
            
            # 根据流类型处理
            if "@kline_" in stream:
                await self._handle_kline(payload)
            elif "@ticker" in stream:
                await self._handle_ticker(payload)
            elif "@depth" in stream:
                await self._handle_depth(payload)
            else:
                logger.debug(f"未知流类型：{stream}")
                
        except json.JSONDecodeError as e:
            logger.error(f"消息解析失败：{e}")
        except Exception as e:
            logger.error(f"消息处理失败：{e}", exc_info=True)
    
    async def connect(self):
        """连接 WebSocket (带自动重连)"""
        while self._running:
            try:
                url = self._get_ws_url()
                logger.info(f"🔌 连接 Binance WebSocket: {url[:80]}...")
                
                async with websockets.connect(
                    url,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    self._ws = ws
                    logger.info("✅ WebSocket 连接成功")
                    
                    while self._running:
                        try:
                            message = await asyncio.wait_for(
                                ws.recv(),
                                timeout=60.0,
                            )
                            await self._process_message(message)
                        except asyncio.TimeoutError:
                            # 发送心跳
                            await ws.ping()
                
            except ConnectionClosed as e:
                logger.warning(f"⚠️  WebSocket 连接关闭：{e}")
            except WebSocketException as e:
                logger.error(f"❌ WebSocket 错误：{e}")
            except Exception as e:
                logger.error(f"❌ 连接异常：{e}", exc_info=True)
            
            if self._running:
                logger.info(f"🔄 {self._reconnect_delay}s 后重连...")
                await asyncio.sleep(self._reconnect_delay)
    
    def start(self):
        """启动连接"""
        self._running = True
        logger.info("🚀 Binance WebSocket 启动中...")
        
        # 在新线程中运行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.connect())
    
    def stop(self):
        """停止连接"""
        self._running = False
        logger.info("👋 Binance WebSocket 停止中...")
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "running": self._running,
            "message_count": self._message_count,
            "last_message_time": self._last_message_time,
            "symbols": self.symbols,
            "intervals": self.intervals,
            "stream_count": len(self._streams),
            "kline_callbacks": len(self._kline_callbacks),
            "ticker_callbacks": len(self._ticker_callbacks),
            "depth_callbacks": len(self._depth_callbacks),
        }


# 全局实例
_binance_ws: Optional[BinanceWebSocket] = None


def get_binance_ws() -> Optional[BinanceWebSocket]:
    """获取 Binance WebSocket 实例"""
    return _binance_ws


def create_binance_ws(
    symbols: Optional[List[str]] = None,
    intervals: Optional[List[str]] = None,
) -> BinanceWebSocket:
    """创建 Binance WebSocket 实例"""
    global _binance_ws
    _binance_ws = BinanceWebSocket(symbols=symbols, intervals=intervals)
    return _binance_ws
