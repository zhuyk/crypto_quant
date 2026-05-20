#!/usr/bin/env python3
"""
批量下载历史数据脚本
下载 5 个交易对 x 3 个周期的完整历史数据（从 2020-01-01 开始）
"""

import requests
import time
import sys
from datetime import datetime

# 配置
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'SOL/USDT', 'BNB/USDT']
TIMEFRAMES = ['15m', '30m', '1h']
START_DATE = '2020-01-01'
API_BASE = 'http://localhost:8000'

def log(msg):
    """打印日志并刷新"""
    print(msg, flush=True)

def download_data(symbol, timeframe, start_date):
    """下载数据"""
    url = f"{API_BASE}/api/v1/data/download"
    
    # 转换日期为毫秒时间戳
    start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
    
    payload = {
        "symbols": [symbol],
        "timeframe": timeframe,
        "start_time": start_ts
    }
    
    try:
        log(f"   📡 请求: {symbol} {timeframe} from {start_date}")
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"error": str(e)}

def main():
    log("=" * 70)
    log("📥 批量下载历史数据")
    log("=" * 70)
    log(f"交易对: {', '.join(SYMBOLS)}")
    log(f"周期: {', '.join(TIMEFRAMES)}")
    log(f"开始日期: {START_DATE}")
    log(f"总计: {len(SYMBOLS) * len(TIMEFRAMES)} 次下载")
    log("=" * 70)
    log("")
    
    success_count = 0
    failed_count = 0
    total = len(SYMBOLS) * len(TIMEFRAMES)
    current = 0
    
    for timeframe in TIMEFRAMES:
        log(f"\n{'=' * 70}")
        log(f"📊 下载周期: {timeframe}")
        log(f"{'=' * 70}")
        
        for symbol in SYMBOLS:
            current += 1
            log(f"\n[{current}/{total}] ⏳ 下载 {symbol} {timeframe}...")
            
            result = download_data(symbol, timeframe, START_DATE)
            
            if "error" in result:
                log(f"   ❌ 失败: {result['error']}")
                failed_count += 1
            elif result.get("success"):
                results = result.get("results", [])
                for item in results:
                    if item.get("success"):
                        count = item.get("count", 0)
                        log(f"   ✅ 成功: {count} 条 K 线")
                        success_count += 1
                    else:
                        error = item.get("error", "Unknown error")
                        log(f"   ❌ 失败: {error}")
                        failed_count += 1
            else:
                error = result.get("error", "Unknown error")
                log(f"   ❌ 失败: {error}")
                failed_count += 1
            
            # 避免请求过快
            time.sleep(2)
    
    log("\n" + "=" * 70)
    log("📊 下载完成！")
    log("=" * 70)
    log(f"✅ 成功: {success_count}")
    log(f"❌ 失败: {failed_count}")
    if success_count + failed_count > 0:
        log(f"📈 成功率: {success_count / (success_count + failed_count) * 100:.1f}%")
    log("=" * 70)

if __name__ == "__main__":
    main()
