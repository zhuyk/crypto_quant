"""
历史数据管理 API

改进:
- 统一使用数据库存储 (废弃 JSON 文件)
- 增量下载 + 断点续传
- 异步非阻塞下载 (后台任务)
- 正确的 symbol 解析 (支持 DOGE/MATIC 等 4+ 字符币种)
- 下载进度跟踪
- 使用 Depends(async_get_db) 统一 session 管理
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.core.database import async_get_db
from app.models.trade import Kline
from data.persistence.kline_storage import get_kline_storage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["data"])

# 下载进度 (内存)
_download_tasks: Dict[str, dict] = {}


# ============================================================
# Models
# ============================================================

class DownloadRequest(BaseModel):
    symbols: List[str] = Field(..., description="交易对列表")
    timeframe: str = Field("1h", description="时间周期")
    start_time: Optional[int] = Field(None, description="开始时间 (ms)")
    end_time: Optional[int] = Field(None, description="结束时间 (ms)")


# ============================================================
# 工具
# ============================================================

def normalize_symbol(symbol: str) -> tuple:
    """标准化 symbol → (ccxt_format, storage_format)"""
    symbol = symbol.strip().upper()
    if "/" in symbol:
        return symbol, symbol.replace("/", "")
    quotes = ["USDT", "USDC", "BUSD", "USD", "BTC", "ETH", "BNB"]
    for q in quotes:
        if symbol.endswith(q) and len(symbol) > len(q):
            return f"{symbol[:-len(q)]}/{q}", symbol
    return symbol, symbol


# ============================================================
# 端点
# ============================================================

@router.get("/symbols")
async def get_symbols(db: Session = Depends(async_get_db)):
    """获取已存储的数据概览 (从数据库)"""
    stats = db.query(
        Kline.symbol, Kline.timeframe, Kline.exchange,
        func.count(Kline.id).label("count"),
        func.min(Kline.timestamp).label("earliest"),
        func.max(Kline.timestamp).label("latest"),
    ).group_by(Kline.symbol, Kline.timeframe, Kline.exchange).all()

    return [
        {
            "symbol": r.symbol, "timeframe": r.timeframe, "exchange": r.exchange,
            "candle_count": r.count,
            "start_time": int(r.earliest.timestamp() * 1000) if r.earliest else None,
            "end_time": int(r.latest.timestamp() * 1000) if r.latest else None,
        }
        for r in stats
    ]


@router.get("/klines")
async def get_klines(
    symbol: str = Query(...),
    timeframe: str = Query("1h"),
    limit: int = Query(500, ge=1, le=5000),
    start_time: Optional[int] = Query(None),
    end_time: Optional[int] = Query(None),
):
    """获取 K 线数据 (从数据库)"""
    storage = get_kline_storage()
    _, stor_sym = normalize_symbol(symbol)
    start_dt = datetime.fromtimestamp(start_time / 1000, tz=timezone.utc).replace(tzinfo=None) if start_time else None
    end_dt = datetime.fromtimestamp(end_time / 1000, tz=timezone.utc).replace(tzinfo=None) if end_time else None

    df = storage.get_klines(symbol=stor_sym, timeframe=timeframe, start_time=start_dt, end_time=end_dt, limit=limit)
    if df.empty:
        return {"klines": [], "count": 0}

    klines = [
        {"time": int(row.name.timestamp() * 1000), "open": row["open"], "high": row["high"],
         "low": row["low"], "close": row["close"], "volume": row["volume"]}
        for _, row in df.iterrows()
    ]
    return {"klines": klines, "count": len(klines)}


@router.post("/download")
async def download_data(request: DownloadRequest, background_tasks: BackgroundTasks):
    """下载历史数据 (后台异步, 增量续传)"""
    task_id = f"{','.join(sorted(request.symbols))}:{request.timeframe}"

    if task_id in _download_tasks and _download_tasks[task_id].get("status") == "running":
        return {"success": False, "message": "任务正在运行", "task_id": task_id, "progress": _download_tasks[task_id]}

    _download_tasks[task_id] = {
        "status": "running", "symbols": request.symbols, "timeframe": request.timeframe,
        "total_symbols": len(request.symbols), "completed_symbols": 0,
        "total_records": 0, "errors": [],
        "started_at": datetime.now(timezone.utc).isoformat(), "completed_at": None,
    }

    background_tasks.add_task(_bg_download, task_id, request.symbols, request.timeframe, request.start_time, request.end_time)
    return {"success": True, "message": f"下载已启动 ({len(request.symbols)} 个交易对)", "task_id": task_id}


@router.get("/download/status")
async def get_download_status(task_id: Optional[str] = Query(None)):
    """获取下载进度"""
    if task_id:
        return _download_tasks.get(task_id, {"status": "not_found"})
    return {"tasks": _download_tasks}


@router.get("/timeframes")
async def get_timeframes():
    """支持的时间周期"""
    return {"timeframes": [
        {"value": "1m", "label": "1 分钟"}, {"value": "5m", "label": "5 分钟"},
        {"value": "15m", "label": "15 分钟"}, {"value": "30m", "label": "30 分钟"},
        {"value": "1h", "label": "1 小时"}, {"value": "4h", "label": "4 小时"},
        {"value": "1d", "label": "1 天"}, {"value": "1w", "label": "1 周"},
    ]}


@router.delete("/klines")
async def delete_klines(
    symbol: str = Query(...),
    timeframe: str = Query(...),
    db: Session = Depends(async_get_db),
):
    """删除指定数据"""
    _, stor_sym = normalize_symbol(symbol)
    deleted = db.query(Kline).filter(
        and_(Kline.symbol == stor_sym, Kline.timeframe == timeframe)
    ).delete(synchronize_session=False)
    db.commit()
    return {"success": True, "deleted_count": deleted}


# ============================================================
# 后台下载
# ============================================================

async def _bg_download(task_id: str, symbols: List[str], timeframe: str, start_time, end_time):
    """后台非阻塞下载"""
    from data.collector.binance_collector import BinanceCollector

    storage = get_kline_storage()
    collector = BinanceCollector(testnet=False)
    task = _download_tasks[task_id]

    try:
        for i, symbol in enumerate(symbols):
            ccxt_sym, stor_sym = normalize_symbol(symbol)
            try:
                since = start_time
                if not since:
                    latest_ts = storage.get_latest_timestamp(stor_sym, timeframe)
                    if latest_ts:
                        since = int(latest_ts.replace(tzinfo=timezone.utc).timestamp() * 1000) + 1

                end_ts = end_time or int(datetime.now(timezone.utc).timestamp() * 1000)
                total_new = 0

                for _ in range(500):
                    try:
                        df = collector.fetch_klines(symbol=ccxt_sym, timeframe=timeframe, limit=1000, since=since)
                    except Exception as e:
                        logger.warning(f"拉取失败 {ccxt_sym}: {e}")
                        await asyncio.sleep(2)
                        continue

                    if df.empty:
                        break

                    new_count = storage.save_klines(symbol=stor_sym, timeframe=timeframe, data=df)
                    total_new += new_count

                    last_ts = df.index[-1]
                    since = int(last_ts.timestamp() * 1000) + 1 if hasattr(last_ts, 'timestamp') else None
                    if not since or since >= end_ts or len(df) < 1000:
                        break

                    await asyncio.sleep(0.15)

                task["completed_symbols"] = i + 1
                task["total_records"] += total_new

            except Exception as e:
                task["errors"].append({"symbol": symbol, "error": str(e)})

            await asyncio.sleep(0.5)

        task["status"] = "completed"
        task["completed_at"] = datetime.now(timezone.utc).isoformat()

    except Exception as e:
        task["status"] = "failed"
        task["errors"].append({"error": str(e)})
