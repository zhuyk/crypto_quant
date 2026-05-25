#!/usr/bin/env python3
"""
BTC MA120 突破/跌破策略回测 + 可视化

功能:
- 使用 BTC 历史日线数据
- 价格突破 MA120 买入，跌破 MA120 卖出
- 生成独立 HTML 文件，包含交互式图表

使用方式:
    python scripts/backtest_ma120_btc.py

输出:
    scripts/output/btc_ma120_backtest.html
"""
import json
import os
import math
from datetime import datetime, timedelta
from pathlib import Path


# ============================================================
# 1. 生成 BTC 模拟历史日线数据 (2020-01 ~ 2025-05)
#    真实场景应从数据库/文件读取，这里用种子生成近似走势
# ============================================================

def generate_btc_daily_data(start_date: str = "2020-01-01", days: int = 1970, seed: int = 42):
    """
    生成近似 BTC 日线数据 (用确定性随机游走模拟真实走势)
    返回: list of dict {date, open, high, low, close, volume}
    
    价格锚点 (近似真实):
    2020-01: ~7200 → 2020-12: ~29000
    2021-04: ~64000 → 2021-07: ~30000 → 2021-11: ~69000
    2022-06: ~20000 → 2022-11: ~16000
    2023-01: ~16800 → 2023-12: ~44000
    2024-03: ~73000 → 2024-12: ~95000
    2025-05: ~105000
    """
    import random
    random.seed(seed)
    
    data = []
    price = 7200.0  # BTC 2020-01-01 实际价格
    
    # (天数, 日漂移, 日波动率) — 调参让终点贴近真实价格
    phases = [
        (365, 0.0038, 0.032),   # 2020: 7200 → ~29000
        (120, 0.0045, 0.035),   # 2021 Q1-Q2: → ~64000
        (90, -0.0075, 0.04),    # 2021 Q3: → ~30000
        (90, 0.009, 0.038),     # 2021 Q4: → ~69000
        (210, -0.005, 0.033),   # 2022 H1: → ~20000
        (155, -0.0015, 0.028),  # 2022 H2: → ~16000
        (365, 0.0028, 0.025),   # 2023: → ~44000
        (180, 0.0035, 0.028),   # 2024 H1: → ~73000
        (185, 0.0015, 0.025),   # 2024 H2: → ~95000
        (190, 0.0008, 0.022),   # 2025: → ~105000
    ]
    
    dt = datetime.strptime(start_date, "%Y-%m-%d")
    day_idx = 0
    
    for phase_days, drift, vol in phases:
        for _ in range(phase_days):
            if day_idx >= days:
                break
            
            # 日收益率
            ret = drift + vol * random.gauss(0, 1)
            price *= (1 + ret)
            price = max(price, 3000)
            
            # 生成 OHLCV
            intra_vol = abs(random.gauss(0, vol * 0.5))
            high = price * (1 + intra_vol)
            low = price * (1 - intra_vol)
            open_price = price * (1 + random.uniform(-vol * 0.25, vol * 0.25))
            volume = random.uniform(15_000, 60_000) * (price / 50_000)
            
            data.append({
                "date": dt.strftime("%Y-%m-%d"),
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(price, 2),
                "volume": round(volume, 0),
            })
            
            dt += timedelta(days=1)
            day_idx += 1
        
        if day_idx >= days:
            break
    
    return data


# ============================================================
# 2. 计算 MA120
# ============================================================

def compute_ma(closes: list, period: int) -> list:
    """计算简单移动平均线，前 period-1 个值为 None"""
    ma = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        ma[i] = sum(closes[i - period + 1: i + 1]) / period
    return ma


# ============================================================
# 3. 回测引擎
# ============================================================

def run_backtest(data: list, ma_period: int = 120, initial_capital: float = 100000.0):
    """
    执行回测
    
    规则:
    - 价格从下方突破 MA120 → 全仓买入
    - 价格从上方跌破 MA120 → 全仓卖出
    
    返回: trades, equity_curve, signals
    """
    closes = [d["close"] for d in data]
    ma = compute_ma(closes, ma_period)
    
    capital = initial_capital
    position = 0.0  # BTC 持仓数量
    entry_price = 0.0
    
    trades = []       # {date, side, price, capital_after, pnl}
    equity = []       # 每日净值
    signals = []      # {index, side, price, date}
    
    in_position = False
    
    for i in range(1, len(data)):
        if ma[i] is None or ma[i - 1] is None:
            # MA 未就绪
            current_equity = capital + position * closes[i]
            equity.append(current_equity)
            continue
        
        prev_above = closes[i - 1] > ma[i - 1]
        curr_above = closes[i] > ma[i]
        
        # 向上突破 → 买入
        if not prev_above and curr_above and not in_position:
            # 全仓买入 (扣 0.1% 手续费)
            buy_price = closes[i]
            fee = capital * 0.001
            position = (capital - fee) / buy_price
            entry_price = buy_price
            capital = 0.0
            in_position = True
            
            signals.append({"index": i, "side": "buy", "price": buy_price, "date": data[i]["date"]})
            trades.append({
                "date": data[i]["date"],
                "side": "buy",
                "price": buy_price,
                "quantity": round(position, 6),
                "fee": round(fee, 2),
            })
        
        # 向下跌破 → 卖出
        elif prev_above and not curr_above and in_position:
            sell_price = closes[i]
            proceeds = position * sell_price
            fee = proceeds * 0.001
            pnl = (sell_price - entry_price) * position - fee
            capital = proceeds - fee
            
            signals.append({"index": i, "side": "sell", "price": sell_price, "date": data[i]["date"]})
            trades.append({
                "date": data[i]["date"],
                "side": "sell",
                "price": sell_price,
                "quantity": round(position, 6),
                "fee": round(fee, 2),
                "pnl": round(pnl, 2),
                "return_pct": round((sell_price / entry_price - 1) * 100, 2),
            })
            
            position = 0.0
            entry_price = 0.0
            in_position = False
        
        # 记录当日净值
        current_equity = capital + position * closes[i]
        equity.append(current_equity)
    
    # 统计
    total_trades = len([t for t in trades if t["side"] == "sell"])
    winning_trades = len([t for t in trades if t["side"] == "sell" and t.get("pnl", 0) > 0])
    final_equity = equity[-1] if equity else initial_capital
    total_return = (final_equity / initial_capital - 1) * 100
    
    # 最大回撤
    peak = initial_capital
    max_dd = 0
    for eq in equity:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak
        if dd > max_dd:
            max_dd = dd
    
    stats = {
        "initial_capital": initial_capital,
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "win_rate_pct": round(winning_trades / total_trades * 100, 2) if total_trades > 0 else 0,
        "still_in_position": in_position,
    }
    
    return {
        "trades": trades,
        "equity": equity,
        "signals": signals,
        "ma": ma,
        "stats": stats,
    }


# ============================================================
# 4. 生成 HTML 可视化
# ============================================================

def generate_html(data: list, result: dict, ma_period: int = 120) -> str:
    """生成包含交互式图表的 HTML 文件"""
    
    dates = [d["date"] for d in data]
    closes = [d["close"] for d in data]
    ma_values = result["ma"]
    equity = result["equity"]
    signals = result["signals"]
    stats = result["stats"]
    trades = result["trades"]
    
    # 准备 JSON 数据
    chart_data = {
        "dates": dates,
        "closes": closes,
        "ma": [v if v is not None else None for v in ma_values],
        "equity": [round(e, 2) for e in equity],
        "signals": signals,
    }
    
    # 交易记录表格 HTML
    trades_html = ""
    for t in trades:
        if t["side"] == "sell":
            pnl = t.get("pnl", 0)
            color = "#22c55e" if pnl > 0 else "#ef4444"
            trades_html += f"""
            <tr>
                <td>{t['date']}</td>
                <td style="color:{color}">{t.get('return_pct', 0):+.2f}%</td>
                <td style="color:{color}">${pnl:,.2f}</td>
                <td>${t['price']:,.2f}</td>
            </tr>"""
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BTC MA{ma_period} 突破/跌破策略回测</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f1419; color: #e7e9ea; padding: 20px; }}
.container {{ max-width: 1400px; margin: 0 auto; }}
h1 {{ text-align: center; margin-bottom: 8px; font-size: 24px; color: #f7931a; }}
.subtitle {{ text-align: center; color: #71767b; margin-bottom: 24px; font-size: 14px; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 24px; }}
.stat-card {{ background: #1e2732; border-radius: 12px; padding: 16px; text-align: center; }}
.stat-card .label {{ color: #71767b; font-size: 12px; margin-bottom: 4px; }}
.stat-card .value {{ font-size: 20px; font-weight: bold; }}
.stat-card .value.positive {{ color: #22c55e; }}
.stat-card .value.negative {{ color: #ef4444; }}
.chart-container {{ background: #1e2732; border-radius: 12px; padding: 20px; margin-bottom: 24px; }}
.chart-title {{ font-size: 14px; color: #71767b; margin-bottom: 12px; }}
canvas {{ width: 100%; height: 400px; display: block; }}
.trades-section {{ background: #1e2732; border-radius: 12px; padding: 20px; }}
.trades-section h3 {{ margin-bottom: 12px; font-size: 16px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ text-align: left; padding: 8px; color: #71767b; border-bottom: 1px solid #2f3336; }}
td {{ padding: 8px; border-bottom: 1px solid #2f3336; }}
.legend {{ display: flex; gap: 16px; margin-bottom: 8px; font-size: 12px; }}
.legend span {{ display: flex; align-items: center; gap: 4px; }}
.legend .dot {{ width: 10px; height: 10px; border-radius: 50%; }}
</style>
</head>
<body>
<div class="container">
    <h1>BTC MA{ma_period} 突破/跌破策略回测</h1>
    <p class="subtitle">数据范围: {dates[0]} ~ {dates[-1]} | 初始资金: $100,000</p>
    
    <div class="stats-grid">
        <div class="stat-card">
            <div class="label">最终净值</div>
            <div class="value {'positive' if stats['total_return_pct'] > 0 else 'negative'}">${stats['final_equity']:,.0f}</div>
        </div>
        <div class="stat-card">
            <div class="label">总收益率</div>
            <div class="value {'positive' if stats['total_return_pct'] > 0 else 'negative'}">{stats['total_return_pct']:+.2f}%</div>
        </div>
        <div class="stat-card">
            <div class="label">最大回撤</div>
            <div class="value negative">-{stats['max_drawdown_pct']:.2f}%</div>
        </div>
        <div class="stat-card">
            <div class="label">交易次数</div>
            <div class="value">{stats['total_trades']}</div>
        </div>
        <div class="stat-card">
            <div class="label">胜率</div>
            <div class="value {'positive' if stats['win_rate_pct'] >= 50 else 'negative'}">{stats['win_rate_pct']:.1f}%</div>
        </div>
        <div class="stat-card">
            <div class="label">当前状态</div>
            <div class="value">{'持仓中' if stats['still_in_position'] else '空仓'}</div>
        </div>
    </div>
    
    <div class="chart-container">
        <div class="chart-title">BTC 价格 & MA{ma_period}</div>
        <div class="legend">
            <span><span class="dot" style="background:#3b82f6"></span>BTC 价格</span>
            <span><span class="dot" style="background:#f59e0b"></span>MA{ma_period}</span>
            <span><span class="dot" style="background:#22c55e"></span>买入</span>
            <span><span class="dot" style="background:#ef4444"></span>卖出</span>
        </div>
        <canvas id="priceChart"></canvas>
    </div>
    
    <div class="chart-container">
        <div class="chart-title">账户净值曲线</div>
        <canvas id="equityChart"></canvas>
    </div>
    
    <div class="trades-section">
        <h3>交易记录 (卖出)</h3>
        <table>
            <thead><tr><th>日期</th><th>收益率</th><th>盈亏</th><th>卖出价</th></tr></thead>
            <tbody>{trades_html}</tbody>
        </table>
    </div>
</div>

<script>
const DATA = {json.dumps(chart_data)};

function drawChart(canvasId, config) {{
    const canvas = document.getElementById(canvasId);
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    
    const W = rect.width;
    const H = rect.height;
    const pad = {{ top: 20, right: 60, bottom: 30, left: 80 }};
    const cW = W - pad.left - pad.right;
    const cH = H - pad.top - pad.bottom;
    
    const {{ series, signals, yLabel }} = config;
    
    // 计算 Y 范围
    let yMin = Infinity, yMax = -Infinity;
    for (const s of series) {{
        for (const v of s.data) {{
            if (v !== null && v !== undefined) {{
                if (v < yMin) yMin = v;
                if (v > yMax) yMax = v;
            }}
        }}
    }}
    const yPad = (yMax - yMin) * 0.05;
    yMin -= yPad; yMax += yPad;
    
    const n = series[0].data.length;
    const xScale = (i) => pad.left + (i / (n - 1)) * cW;
    const yScale = (v) => pad.top + (1 - (v - yMin) / (yMax - yMin)) * cH;
    
    // 背景
    ctx.fillStyle = '#1e2732';
    ctx.fillRect(0, 0, W, H);
    
    // 网格
    ctx.strokeStyle = '#2f3336';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 5; i++) {{
        const y = pad.top + (i / 5) * cH;
        ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
        const val = yMax - (i / 5) * (yMax - yMin);
        ctx.fillStyle = '#71767b'; ctx.font = '11px sans-serif'; ctx.textAlign = 'right';
        ctx.fillText(val >= 1000 ? '$' + (val/1000).toFixed(1) + 'k' : '$' + val.toFixed(0), pad.left - 8, y + 4);
    }}
    
    // 画线
    for (const s of series) {{
        ctx.strokeStyle = s.color;
        ctx.lineWidth = s.width || 1.5;
        ctx.beginPath();
        let started = false;
        for (let i = 0; i < n; i++) {{
            if (s.data[i] === null || s.data[i] === undefined) continue;
            const x = xScale(i), y = yScale(s.data[i]);
            if (!started) {{ ctx.moveTo(x, y); started = true; }}
            else ctx.lineTo(x, y);
        }}
        ctx.stroke();
    }}
    
    // 信号标记
    if (signals) {{
        for (const sig of signals) {{
            const x = xScale(sig.index);
            const y = yScale(sig.price);
            ctx.beginPath();
            if (sig.side === 'buy') {{
                ctx.fillStyle = '#22c55e';
                ctx.moveTo(x, y + 8); ctx.lineTo(x - 5, y + 15); ctx.lineTo(x + 5, y + 15);
            }} else {{
                ctx.fillStyle = '#ef4444';
                ctx.moveTo(x, y - 8); ctx.lineTo(x - 5, y - 15); ctx.lineTo(x + 5, y - 15);
            }}
            ctx.closePath(); ctx.fill();
        }}
    }}
    
    // X 轴日期
    ctx.fillStyle = '#71767b'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center';
    const step = Math.floor(n / 8);
    for (let i = 0; i < n; i += step) {{
        const x = xScale(i);
        ctx.fillText(DATA.dates[i].slice(0, 7), x, H - 8);
    }}
}}

// 价格图
drawChart('priceChart', {{
    series: [
        {{ data: DATA.closes, color: '#3b82f6', width: 1.5 }},
        {{ data: DATA.ma, color: '#f59e0b', width: 2 }},
    ],
    signals: DATA.signals,
}});

// 净值图
drawChart('equityChart', {{
    series: [
        {{ data: DATA.equity, color: '#a78bfa', width: 2 }},
    ],
}});
</script>
</body>
</html>"""
    return html


# ============================================================
# 5. 主函数
# ============================================================

def main():
    print("=" * 60)
    print("  BTC MA120 突破/跌破策略 - 回测 + 可视化")
    print("=" * 60)
    
    # 生成数据
    print("\n[1/4] 生成 BTC 日线数据 (2020-01 ~ 2025-05)...")
    data = generate_btc_daily_data()
    print(f"      共 {len(data)} 根日线, 起止: {data[0]['date']} ~ {data[-1]['date']}")
    print(f"      价格范围: ${min(d['close'] for d in data):,.0f} ~ ${max(d['close'] for d in data):,.0f}")
    
    # 执行回测
    print("\n[2/4] 执行回测 (MA120 突破买入 / 跌破卖出)...")
    result = run_backtest(data, ma_period=120)
    stats = result["stats"]
    
    print(f"      初始资金: ${stats['initial_capital']:,.0f}")
    print(f"      最终净值: ${stats['final_equity']:,.0f}")
    print(f"      总收益率: {stats['total_return_pct']:+.2f}%")
    print(f"      最大回撤: -{stats['max_drawdown_pct']:.2f}%")
    print(f"      交易次数: {stats['total_trades']}")
    print(f"      胜率:     {stats['win_rate_pct']:.1f}%")
    print(f"      当前状态: {'持仓中' if stats['still_in_position'] else '空仓'}")
    
    # 生成 HTML
    print("\n[3/4] 生成可视化 HTML...")
    html_content = generate_html(data, result, ma_period=120)
    
    # 输出文件
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "btc_ma120_backtest.html"
    output_path.write_text(html_content, encoding="utf-8")
    
    print(f"      输出文件: {output_path}")
    print(f"      文件大小: {output_path.stat().st_size / 1024:.1f} KB")
    
    # 输出交易详情
    print("\n[4/4] 交易详情:")
    print(f"{'日期':<12} {'方向':<6} {'价格':>12} {'收益率':>10} {'盈亏':>12}")
    print("-" * 56)
    for t in result["trades"]:
        side_str = "买入" if t["side"] == "buy" else "卖出"
        pnl_str = f"${t.get('pnl', 0):+,.0f}" if t["side"] == "sell" else ""
        ret_str = f"{t.get('return_pct', 0):+.1f}%" if t["side"] == "sell" else ""
        print(f"{t['date']:<12} {side_str:<6} ${t['price']:>10,.2f} {ret_str:>10} {pnl_str:>12}")
    
    print("\n" + "=" * 60)
    print(f"  回测完成! HTML 报告: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
