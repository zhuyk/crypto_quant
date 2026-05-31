"""
K线数据持久化服务
将采集到的K线数据写入数据库，支持去重和批量写入
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict

import pandas as pd
from sqlalchemy import and_, text, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.core.database import SessionLocal, engine
from app.core.config import settings
from app.models.trade import Kline

logger = logging.getLogger(__name__)


class KlineStorage:
    """
    K线数据持久化服务
    
    功能:
    - 批量写入K线数据到数据库 (INSERT OR IGNORE / ON CONFLICT DO NOTHING)
    - 自动去重依赖复合唯一索引 ix_kline_composite
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
        批量保存K线数据（使用 UPSERT / INSERT OR IGNORE 去重）
        
        依赖复合唯一索引 ix_kline_composite (exchange, symbol, timeframe, timestamp)
        自动忽略已存在的记录，无需先查询最新时间戳。
        
        Args:
            symbol: 交易对 (如 BTCUSDT)
            timeframe: 时间周期 (1m, 5m, 15m, 1h, 4h, 1d)
            data: K线 DataFrame (index=timestamp, columns=[open, high, low, close, volume])
            exchange: 交易所名称
            
        Returns:
            int: 新写入的记录数
        """
        if data.empty:
            return 0
        
        exchange = exchange or self.exchange
        
        # 构建待插入记录列表 (纯字典，不创建 ORM 对象)
        rows = []
        for ts, row in data.iterrows():
            if isinstance(ts, pd.Timestamp):
                record_ts = ts.to_pydatetime()
            else:
                record_ts = ts
            
            # 统一为 naive UTC
            if hasattr(record_ts, 'tzinfo') and record_ts.tzinfo:
                record_ts = record_ts.replace(tzinfo=None)
            
            rows.append({
                "exchange": exchange,
                "symbol": symbol,
                "timeframe": timeframe,
                "timestamp": record_ts,
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
                "volume": float(row['volume']),
            })
        
        if not rows:
            return 0
        
        db = SessionLocal()
        new_count = 0
        
        try:
            # 使用数据库原生 INSERT OR IGNORE / ON CONFLICT DO NOTHING
            # 分批处理避免单条 SQL 过大
            batch_size = 500
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                
                if settings.is_sqlite:
                    # SQLite: INSERT OR IGNORE
                    stmt = sqlite_insert(Kline).values(batch)
                    stmt = stmt.on_conflict_do_nothing(
                        index_elements=["exchange", "symbol", "timeframe", "timestamp"]
                    )
                elif settings.is_mysql:
                    # MySQL: INSERT IGNORE
                    stmt = mysql_insert(Kline).values(batch)
                    stmt = stmt.on_duplicate_key_update(
                        close=stmt.inserted.close  # no-op update to use INSERT ON DUPLICATE
                    )
                else:
                    # PostgreSQL / fallback: ON CONFLICT DO NOTHING
                    from sqlalchemy.dialects.postgresql import insert as pg_insert
                    stmt = pg_insert(Kline).values(batch)
                    stmt = stmt.on_conflict_do_nothing(
                        index_elements=["exchange", "symbol", "timeframe", "timestamp"]
                    )
                
                result = db.execute(stmt)
                new_count += result.rowcount
            
            db.commit()
            
            self._total_written += new_count
            self._total_duplicates += (len(rows) - new_count)
            
            if new_count > 0:
                logger.info(
                    f"💾 已存储 {new_count} 条K线 (跳过 {len(rows) - new_count} 重复) | "
                    f"{exchange}:{symbol} {timeframe}"
                )
            else:
                logger.debug(f"📊 {symbol} {timeframe} 无新数据需要存储 ({len(rows)} 条均已存在)")
                
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
        从数据库查询K线数据（按时间正序返回）
        
        使用子查询 + ASC 排序避免大结果集的 Python 反转开销。
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            start_time: 起始时间
            end_time: 结束时间
            limit: 最大条数
            exchange: 交易所
            
        Returns:
            pd.DataFrame with OHLCV data, index=timestamp (时间正序)
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
            
            # 直接按 ASC 排序，取最新的 limit 条用子查询
            # 如果有 start_time 限定，直接 ASC + limit 即可
            if start_time:
                query = query.order_by(Kline.timestamp.asc()).limit(limit)
            else:
                # 无 start_time 时取最近 N 条: 先 DESC limit，再外层 ASC
                # 使用 subquery 避免 Python 反转
                from sqlalchemy.orm import aliased
                subq = query.order_by(Kline.timestamp.desc()).limit(limit).subquery()
                query = db.query(Kline).select_entity_from(subq).order_by(subq.c.timestamp.asc())
            
            results = query.all()
            
            if not results:
                return pd.DataFrame()
            
            # 转换为 DataFrame (已按时间正序)
            records = [{
                'timestamp': r.timestamp,
                'open': r.open,
                'high': r.high,
                'low': r.low,
                'close': r.close,
                'volume': r.volume,
            } for r in results]
            
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
            result = db.query(func.max(Kline.timestamp)).filter(
                and_(
                    Kline.exchange == exchange,
                    Kline.symbol == symbol,
                    Kline.timeframe == timeframe,
                )
            ).scalar()
            
            return result
        finally:
            db.close()
    
    def get_stats(self) -> Dict:
        """获取存储统计"""
        db = SessionLocal()
        try:
            total_records = db.query(func.count(Kline.id)).scalar()
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
