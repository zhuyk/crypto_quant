"""
K线数据持久化服务
将采集到的K线数据写入数据库，支持去重和批量写入
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict

import pandas as pd
from sqlalchemy import and_, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.database import SessionLocal, engine
from app.models.trade import Kline

logger = logging.getLogger(__name__)


class KlineStorage:
    """
    K线数据持久化服务
    
    功能:
    - 批量写入K线数据到数据库
    - 自动去重 (基于 exchange+symbol+timeframe+timestamp)
    - 支持增量更新
    - 查询历史数据
    """
    
    def __init__(self, exchange: str = "binance"):
        self.exchange = exchange
        self._total_written = 0
        self._total_duplicates = 0
    
    def save_klines(
        self,
        symbol: str,
        timeframe: str,
        data: pd.DataFrame,
        exchange: Optional[str] = None,
    ) -> int:
        """
        批量保存K线数据
        
        Args:
            symbol: 交易对 (如 BTC/USDT)
            timeframe: 时间周期 (1m, 5m, 15m, 1h, 4h, 1d)
            data: K线 DataFrame (index=timestamp, columns=[open, high, low, close, volume])
            exchange: 交易所名称
            
        Returns:
            int: 新写入的记录数
        """
        if data.empty:
            return 0
        
        exchange = exchange or self.exchange
        db = SessionLocal()
        new_count = 0
        
        try:
            # 获取该symbol+timeframe已有的最新时间戳
            existing_latest = db.query(Kline.timestamp).filter(
                and_(
                    Kline.exchange == exchange,
                    Kline.symbol == symbol,
                    Kline.timeframe == timeframe,
                )
            ).order_by(Kline.timestamp.desc()).first()
            
            latest_ts = existing_latest[0] if existing_latest else None
            
            # 过滤出新数据
            records = []
            for ts, row in data.iterrows():
                # ts 可能是 DatetimeIndex 或列值
                if isinstance(ts, pd.Timestamp):
                    record_ts = ts.to_pydatetime()
                else:
                    record_ts = ts
                
                # 如果有时区信息，转为 naive UTC
                if hasattr(record_ts, 'tzinfo') and record_ts.tzinfo:
                    record_ts = record_ts.replace(tzinfo=None)
                
                # 跳过已存在的数据
                if latest_ts and record_ts <= latest_ts:
                    self._total_duplicates += 1
                    continue
                
                records.append(Kline(
                    exchange=exchange,
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=record_ts,
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=float(row['volume']),
                ))
            
            # 批量写入
            if records:
                db.bulk_save_objects(records)
                db.commit()
                new_count = len(records)
                self._total_written += new_count
                logger.info(
                    f"💾 已存储 {new_count} 条K线 | "
                    f"{exchange}:{symbol} {timeframe} | "
                    f"最新: {records[-1].timestamp}"
                )
            else:
                logger.debug(f"📊 {symbol} {timeframe} 无新数据需要存储")
                
        except Exception as e:
            db.rollback()
            logger.error(f"❌ K线数据存储失败: {symbol} {timeframe} - {e}")
            raise
        finally:
            db.close()
        
        return new_count
    
    def get_klines(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
        exchange: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        从数据库查询K线数据
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            start_time: 起始时间
            end_time: 结束时间
            limit: 最大条数
            exchange: 交易所
            
        Returns:
            pd.DataFrame with OHLCV data
        """
        exchange = exchange or self.exchange
        db = SessionLocal()
        
        try:
            query = db.query(Kline).filter(
                and_(
                    Kline.exchange == exchange,
                    Kline.symbol == symbol,
                    Kline.timeframe == timeframe,
                )
            )
            
            if start_time:
                query = query.filter(Kline.timestamp >= start_time)
            if end_time:
                query = query.filter(Kline.timestamp <= end_time)
            
            query = query.order_by(Kline.timestamp.desc()).limit(limit)
            results = query.all()
            
            if not results:
                return pd.DataFrame()
            
            # 转换为 DataFrame
            records = [{
                'timestamp': r.timestamp,
                'open': r.open,
                'high': r.high,
                'low': r.low,
                'close': r.close,
                'volume': r.volume,
            } for r in reversed(results)]  # 反转为时间正序
            
            df = pd.DataFrame(records)
            df.set_index('timestamp', inplace=True)
            return df
            
        except Exception as e:
            logger.error(f"❌ 查询K线数据失败: {symbol} {timeframe} - {e}")
            return pd.DataFrame()
        finally:
            db.close()
    
    def get_latest_timestamp(
        self,
        symbol: str,
        timeframe: str,
        exchange: Optional[str] = None,
    ) -> Optional[datetime]:
        """获取某交易对某周期的最新时间戳"""
        exchange = exchange or self.exchange
        db = SessionLocal()
        
        try:
            result = db.query(Kline.timestamp).filter(
                and_(
                    Kline.exchange == exchange,
                    Kline.symbol == symbol,
                    Kline.timeframe == timeframe,
                )
            ).order_by(Kline.timestamp.desc()).first()
            
            return result[0] if result else None
        finally:
            db.close()
    
    def get_stats(self) -> Dict:
        """获取存储统计"""
        db = SessionLocal()
        try:
            total_records = db.query(Kline).count()
            return {
                "total_records": total_records,
                "total_written_session": self._total_written,
                "total_duplicates_session": self._total_duplicates,
                "exchange": self.exchange,
            }
        finally:
            db.close()


# 全局实例
_kline_storage: Optional[KlineStorage] = None


def get_kline_storage() -> KlineStorage:
    """获取K线存储服务实例"""
    global _kline_storage
    if _kline_storage is None:
        _kline_storage = KlineStorage()
    return _kline_storage
