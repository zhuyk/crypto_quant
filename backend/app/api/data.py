"""
历史数据管理 API
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import logging
import os
import json
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(tags=["data"])


class SymbolData(BaseModel):
    """交易对数据信息"""
    symbol: str
    timeframe: str
    candle_count: int
    start_time: int
    end_time: int
    size: int
    updated_at: int


class DownloadRequest(BaseModel):
    """下载请求"""
    symbols: List[str]
    timeframe: str
    start_time: Optional[int] = None
    end_time: Optional[int] = None


@router.get("/symbols", response_model=List[SymbolData])
async def get_symbols():
    """获取所有已下载的交易对数据"""
    # 使用绝对路径
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(base_dir, "data", "klines")
    
    if not os.path.exists(data_dir):
        return []
    
    symbols = []
    
    # 遍历所有子目录（支持 BTC/USDT 这种嵌套结构）
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            if not file.endswith('.json'):
                continue
            
            # 获取相对路径
            rel_path = os.path.relpath(root, data_dir)
            symbol = rel_path  # 例如：BTC/USDT 或 ETHUSDT
            
            timeframe = file.replace('.json', '')
            file_path = os.path.join(root, file)
            
            try:
                with open(file_path, 'r') as f:
                    klines = json.load(f)
                
                if not klines:
                    continue
                
                file_size = os.path.getsize(file_path)
                start_time = min(k[0] for k in klines)
                end_time = max(k[0] for k in klines)
                mtime = os.path.getmtime(file_path)
                
                symbols.append(SymbolData(
                    symbol=symbol,
                    timeframe=timeframe,
                    candle_count=len(klines),
                    start_time=start_time,
                    end_time=end_time,
                    size=file_size,
                    updated_at=int(mtime * 1000),
                ))
                
            except Exception as e:
                logger.error(f"读取数据失败 {file_path}: {e}")
    
    logger.info(f"📊 找到 {len(symbols)} 个已下载的交易对数据")
    return symbols


@router.get("/klines")
async def get_klines(
    symbol: str,
    timeframe: str = Query(default="1h"),
    limit: int = Query(default=1000, ge=1, le=10000),
):
    """获取 K 线数据"""
    file_path = f"data/klines/{symbol}/{timeframe}.json"
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="数据不存在")
    
    try:
        with open(file_path, 'r') as f:
            klines = json.load(f)
        
        # 返回最新的 limit 条数据
        klines = klines[-limit:]
        
        # 转换为字典格式
        result = [
            {
                "time": k[0],
                "open": k[1],
                "high": k[2],
                "low": k[3],
                "close": k[4],
                "volume": k[5],
            }
            for k in klines
        ]
        
        return {"klines": result}
        
    except Exception as e:
        logger.error(f"读取 K 线数据失败 {file_path}: {e}")
        raise HTTPException(status_code=500, detail="读取数据失败")


@router.post("/download")
async def download_data(request: DownloadRequest):
    """下载历史数据"""
    from data.collector.binance_collector import BinanceCollector
    from datetime import datetime, timezone
    
    collector = BinanceCollector(testnet=False)
    
    results = []
    
    for symbol in request.symbols:
        try:
            # 统一格式：BTCUSDT → BTC/USDT，ETHUSDT → ETH/USDT
            if '/' not in symbol and len(symbol) >= 6:
                ccxt_symbol = f"{symbol[:3]}/{symbol[3:]}"  # BTCUSDT → BTC/USDT
                storage_symbol = ccxt_symbol  # 存储也用 BTC/USDT 格式
            else:
                ccxt_symbol = symbol
                storage_symbol = symbol
            
            # 使用简单方式获取数据（最近 1000 条）
            df = collector.fetch_klines(
                symbol=ccxt_symbol,
                timeframe=request.timeframe,
                limit=1000,
            )
            
            if df.empty:
                results.append({
                    "symbol": symbol,
                    "success": False,
                    "error": "未获取到数据",
                })
                continue
            
            # 转换为列表格式 [timestamp, open, high, low, close, volume]
            klines = []
            for idx, row in df.iterrows():
                klines.append([
                    int(idx.timestamp() * 1000),  # 毫秒时间戳
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    float(row['volume']),
                ])
            
            # 保存到文件（创建 BTC/USDT 这样的目录结构）
            data_dir = f"data/klines/{storage_symbol}"
            os.makedirs(data_dir, exist_ok=True)
            
            file_path = f"{data_dir}/{request.timeframe}.json"
            
            with open(file_path, 'w') as f:
                json.dump(klines, f, indent=2)
            
            results.append({
                "symbol": storage_symbol,
                "success": True,
                "count": len(klines),
            })
            
            logger.info(f"✅ 下载 {storage_symbol} {request.timeframe} 共 {len(klines)} 条数据")
            
        except Exception as e:
            logger.error(f"❌ 下载数据失败 {symbol}: {e}")
            results.append({
                "symbol": symbol,
                "success": False,
                "error": str(e),
            })
    
    return {"results": results}


@router.delete("/symbols/{symbol}")
async def delete_symbol_data(
    symbol: str,
    timeframe: Optional[str] = Query(default=None),
):
    """删除交易对数据"""
    if timeframe:
        # 删除特定时期的数据
        file_path = f"data/klines/{symbol}/{timeframe}.json"
        if os.path.exists(file_path):
            os.remove(file_path)
            return {"success": True, "message": f"已删除 {symbol} {timeframe} 数据"}
        else:
            raise HTTPException(status_code=404, detail="数据不存在")
    else:
        # 删除所有数据
        symbol_path = f"data/klines/{symbol}"
        if os.path.exists(symbol_path):
            import shutil
            shutil.rmtree(symbol_path)
            return {"success": True, "message": f"已删除 {symbol} 所有数据"}
        else:
            raise HTTPException(status_code=404, detail="数据不存在")
