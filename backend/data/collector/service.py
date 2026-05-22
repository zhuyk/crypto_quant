"""
数据采集服务入口
定期从 Binance 采集K线数据并持久化到数据库

用法: python -m data.collector.service
"""
import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 添加 backend 到 path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.config import settings
from app.core.logging_config import setup_logging
from data.collector.binance_collector import BinanceCollector
from data.persistence.kline_storage import get_kline_storage

setup_logging(log_level=settings.LOG_LEVEL, log_format="text", service_name="data-collector")
logger = logging.getLogger(__name__)


class DataCollectorService:
    """
    数据采集服务
    
    周期性从 Binance 拉取 K 线数据并存入数据库。
    支持增量采集（只拉取数据库中最新时间戳之后的数据）。
    """
    
    def __init__(self):
        self.collector = BinanceCollector(testnet=settings.BINANCE_TESTNET)
        self.storage = get_kline_storage()
        self.symbols = settings.DEFAULT_SYMBOLS
        self.timeframes = settings.DEFAULT_TIMEFRAMES
        self.interval = settings.DATA_COLLECTOR_INTERVAL  # 采集间隔（秒）
        self._running = False
    
    async def collect_once(self):
        """执行一次全量采集"""
        total_new = 0
        
        for symbol in self.symbols:
            # ccxt 使用 BTC/USDT 格式
            ccxt_symbol = symbol.replace("USDT", "/USDT")
            
            for timeframe in self.timeframes:
                try:
                    # 查询数据库中最新时间戳，实现增量采集
                    latest_ts = self.storage.get_latest_timestamp(symbol, timeframe)
                    
                    since = None
                    if latest_ts:
                        # 从最新时间+1ms开始拉取
                        since = int(latest_ts.replace(tzinfo=timezone.utc).timestamp() * 1000) + 1
                    
                    # 拉取数据
                    df = self.collector.fetch_klines(
                        symbol=ccxt_symbol,
                        timeframe=timeframe,
                        limit=500,
                        since=since,
                    )
                    
                    if not df.empty:
                        # 存入数据库（symbol 用原始格式如 BTCUSDT）
                        new_count = self.storage.save_klines(
                            symbol=symbol,
                            timeframe=timeframe,
                            data=df,
                        )
                        total_new += new_count
                        
                except Exception as e:
                    logger.error(f"采集失败 {symbol} {timeframe}: {e}")
                    continue
                
                # 避免 API 限流
                await asyncio.sleep(0.2)
        
        return total_new
    
    async def run(self):
        """启动采集循环"""
        self._running = True
        logger.info(
            f"🚀 数据采集服务启动 | "
            f"交易对: {self.symbols} | "
            f"周期: {self.timeframes} | "
            f"间隔: {self.interval}s"
        )
        
        # 首次启动先做一次全量采集
        try:
            new_count = await self.collect_once()
            logger.info(f"📊 首次采集完成，新增 {new_count} 条记录")
        except Exception as e:
            logger.error(f"首次采集失败: {e}")
        
        # 循环采集
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                
                if not self._running:
                    break
                
                new_count = await self.collect_once()
                if new_count > 0:
                    logger.info(f"📊 增量采集完成，新增 {new_count} 条记录")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"采集循环异常: {e}")
                await asyncio.sleep(10)  # 异常后等待10秒重试
        
        logger.info("👋 数据采集服务已停止")
    
    def stop(self):
        """停止服务"""
        self._running = False


def main():
    """主入口"""
    service = DataCollectorService()
    
    # 优雅关闭
    def signal_handler(sig, frame):
        logger.info(f"收到信号 {sig}，正在停止...")
        service.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 初始化数据库表
    from app.core.database import Base, engine
    Base.metadata.create_all(bind=engine)
    
    # 运行
    asyncio.run(service.run())


if __name__ == "__main__":
    main()
