"""
回测可视化 API

提供 /backtest/chart 端点，执行回测并返回交互式 HTML 图表页面。
"""
import json
import logging
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import async_get_db
from app.core.exceptions import DataNotAvailableError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["回测可视化"])


class ChartRequest(BaseModel):
    """回测图表请求"""
    strategy_name: str = Field(..., description="策略名称")
    symbol: str = Field("BTCUSDT", description="交易对")
    timeframe: str = Field("1d", description="时间周期")
    params: Dict[str, Any] = Field(default_factory=dict, description="策略参数")
    initial_capital: float = Field(100000.0, description="初始资金")
    start_time: Optional[int] = Field(None, description="开始时间 (毫秒时间戳)")
    end_time: Optional[int] = Field(None, description="结束时间 (毫秒时间戳)")


@router.post("/chart", response_class=HTMLResponse)
async def backtest_chart(request: ChartRequest):
    """
    执行回测并返回交互式 HTML 图表

    图表包含：
    - 价格走势 + 策略指标（如均线）
    - 买入/卖出信号标记
    - 账户净值曲线
    - 绩效统计卡片
    - 交易记录表格

    示例请求：
    ```json
    {
        "strategy_name": "ma_single",
        "symbol": "BTCUSDT",
        "timeframe": "1d",
        "params": {"ma_period": 120}
    }
    ```
    """
    from app.api.backtest import _load_data, _create_strategy
    from engine.backtester import Backtester

    try:
        # 1. 加载数据
        data = await _load_data(
            request.symbol, request.timeframe,
            request.start_time, request.end_time,
        )

        if data.empty:
            raise HTTPException(status_code=404, detail="未找到数据")

        # 2. 执行回测
        strategy = _create_strategy(request.strategy_name, request.params)
        backtester = Backtester(
            initial_capital=request.initial_capital,
            commission_rate=0.001,
            slippage=0.0005,
            timeframe=request.timeframe,
        )
        report = backtester.run(strategy, data)

        # 3. 提取图表所需数据
        dates = [ts.strftime("%Y-%m-%d") if hasattr(ts, 'strftime') else str(ts) for ts in data.index]
        closes = [float(v) for v in data["close"].tolist()]

        # 计算策略使用的均线（从 params 推断）
        ma_period = request.params.get("ma_period") or request.params.get("slow_period") or 120
        ma_values = _compute_ma(closes, int(ma_period))

        # 提取交易信号
        signals = []
        for t in backtester.trades:
            bar_idx = t.get("bar", 0)
            if t.get("action") == "open":
                signals.append({
                    "index": bar_idx,
                    "side": "buy" if t.get("side") == "long" else "sell",
                    "price": float(t.get("price", 0)),
                    "date": dates[bar_idx] if bar_idx < len(dates) else "",
                })
            elif t.get("action") == "close" or "pnl" in t:
                signals.append({
                    "index": bar_idx,
                    "side": "sell",
                    "price": float(t.get("price", t.get("exit_price", 0))),
                    "date": dates[bar_idx] if bar_idx < len(dates) else "",
                })

        # 权益曲线
        equity = [float(v) for v in backtester.equity_curve]

        # 统计数据
        report_dict = report.to_dict()

        # 4. 生成 HTML
        html = _render_chart_html(
            symbol=request.symbol,
            strategy_name=request.strategy_name,
            ma_period=ma_period,
            dates=dates,
            closes=closes,
            ma_values=ma_values,
            equity=equity,
            signals=signals,
            stats=report_dict,
            trades=report_dict.get("trades_summary", []),
        )

        return HTMLResponse(content=html)

    except DataNotAvailableError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("回测图表生成失败")
        raise HTTPException(status_code=500, detail=f"回测图表生成失败: {str(e)}")


# ============================================================
# 辅助函数
# ============================================================

def _compute_ma(closes: List[float], period: int) -> List[Optional[float]]:
    """计算简单移动平均线"""
    ma: List[Optional[float]] = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        ma[i] = sum(closes[i - period + 1: i + 1]) / period
    return ma


def _render_chart_html(
    symbol: str,
    strategy_name: str,
    ma_period: int,
    dates: List[str],
    closes: List[float],
    ma_values: List[Optional[float]],
    equity: List[float],
    signals: List[Dict],
    stats: Dict[str, Any],
    trades: List[Dict],
) -> str:
    """渲染完整的 HTML 图表页面"""

    chart_data = {
        "dates": dates,
        "closes": closes,
        "ma": ma_values,
        "equity": equity,
        "signals": signals,
    }

    # 统计数据
    total_return = stats.get("total_return", 0)
    max_drawdown = stats.get("max_drawdown", 0)
    total_trades = stats.get("total_trades", 0)
    win_rate = stats.get("win_rate", 0)
    final_capital = stats.get("final_capital", 0)
    sharpe = stats.get("sharpe_ratio", 0)

    # 交易记录 HTML
    trades_html = ""
    for t in trades:
        pnl = t.get("pnl", 0)
        color = "#22c55e" if pnl > 0 else "#ef4444"
        pnl_pct = t.get("pnl_pct", 0)
        trades_html += f"""
        <tr>
            <td>{t.get('symbol', symbol)}</td>
            <td>{t.get('side', '')}</td>
            <td>${t.get('entry_price', 0):,.2f}</td>
            <td>${t.get('exit_price', 0):,.2f}</td>
            <td style="color:{color}">{pnl_pct*100 if abs(pnl_pct) < 1 else pnl_pct:+.2f}%</td>
            <td style="color:{color}">${pnl:,.2f}</td>
            <td>{t.get('exit_reason', '')}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{symbol} {strategy_name} 回测图表</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f1419; color: #e7e9ea; padding: 20px; }}
.container {{ max-width: 1400px; margin: 0 auto; }}
h1 {{ text-align: center; margin-bottom: 8px; font-size: 24px; color: #f7931a; }}
.subtitle {{ text-align: center; color: #71767b; margin-bottom: 24px; font-size: 14px; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }}
.stat-card {{ background: #1e2732; border-radius: 12px; padding: 16px; text-align: center; }}
.stat-card .label {{ color: #71767b; font-size: 12px; margin-bottom: 4px; }}
.stat-card .value {{ font-size: 20px; font-weight: bold; }}
.stat-card .value.positive {{ color: #22c55e; }}
.stat-card .value.negative {{ color: #ef4444; }}
.chart-container {{ background: #1e2732; border-radius: 12px; padding: 20px; margin-bottom: 24px; position: relative; }}
.chart-title {{ font-size: 14px; color: #71767b; margin-bottom: 12px; }}
canvas {{ width: 100%; height: 400px; display: block; }}
.trades-section {{ background: #1e2732; border-radius: 12px; padding: 20px; overflow-x: auto; }}
.trades-section h3 {{ margin-bottom: 12px; font-size: 16px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ text-align: left; padding: 8px 12px; color: #71767b; border-bottom: 1px solid #2f3336; white-space: nowrap; }}
td {{ padding: 8px 12px; border-bottom: 1px solid #2f3336; white-space: nowrap; }}
.legend {{ display: flex; gap: 16px; margin-bottom: 8px; font-size: 12px; flex-wrap: wrap; }}
.legend span {{ display: flex; align-items: center; gap: 4px; }}
.legend .dot {{ width: 10px; height: 10px; border-radius: 50%; }}
.tooltip {{ position: absolute; background: #2f3336; color: #e7e9ea; padding: 8px 12px; border-radius: 6px; font-size: 12px; pointer-events: none; display: none; z-index: 10; }}
</style>
</head>
<body>
<div class="container">
    <h1>{symbol} — {strategy_name} (MA{ma_period})</h1>
    <p class="subtitle">数据: {dates[0]} ~ {dates[-1]} | 周期: {ma_period} | 初始资金: ${stats.get('initial_capital', 100000):,.0f}</p>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="label">最终净值</div>
            <div class="value {'positive' if total_return > 0 else 'negative'}">${final_capital:,.0f}</div>
        </div>
        <div class="stat-card">
            <div class="label">总收益率</div>
            <div class="value {'positive' if total_return > 0 else 'negative'}">{total_return*100 if abs(total_return) < 2 else total_return:+.2f}%</div>
        </div>
        <div class="stat-card">
            <div class="label">夏普比率</div>
            <div class="value {'positive' if sharpe > 0 else 'negative'}">{sharpe:.2f}</div>
        </div>
        <div class="stat-card">
            <div class="label">最大回撤</div>
            <div class="value negative">{max_drawdown*100 if abs(max_drawdown) < 2 else max_drawdown:-.2f}%</div>
        </div>
        <div class="stat-card">
            <div class="label">交易次数</div>
            <div class="value">{total_trades}</div>
        </div>
        <div class="stat-card">
            <div class="label">胜率</div>
            <div class="value {'positive' if win_rate >= 0.5 else 'negative'}">{win_rate*100 if abs(win_rate) < 2 else win_rate:.1f}%</div>
        </div>
    </div>

    <div class="chart-container">
        <div class="chart-title">{symbol} 价格 & MA{ma_period}</div>
        <div class="legend">
            <span><span class="dot" style="background:#3b82f6"></span>价格</span>
            <span><span class="dot" style="background:#f59e0b"></span>MA{ma_period}</span>
            <span><span class="dot" style="background:#22c55e"></span>买入</span>
            <span><span class="dot" style="background:#ef4444"></span>卖出</span>
        </div>
        <canvas id="priceChart"></canvas>
        <div class="tooltip" id="tooltip"></div>
    </div>

    <div class="chart-container">
        <div class="chart-title">账户净值曲线</div>
        <canvas id="equityChart"></canvas>
    </div>

    <div class="trades-section">
        <h3>交易记录</h3>
        <table>
            <thead><tr><th>交易对</th><th>方向</th><th>入场价</th><th>出场价</th><th>收益率</th><th>盈亏</th><th>原因</th></tr></thead>
            <tbody>{trades_html if trades_html else '<tr><td colspan="7" style="text-align:center;color:#71767b">暂无交易记录</td></tr>'}</tbody>
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

    const W = rect.width, H = rect.height;
    const pad = {{ top: 20, right: 70, bottom: 30, left: 80 }};
    const cW = W - pad.left - pad.right;
    const cH = H - pad.top - pad.bottom;

    const {{ series, signals }} = config;

    // Y 范围
    let yMin = Infinity, yMax = -Infinity;
    for (const s of series) {{
        for (const v of s.data) {{
            if (v !== null && v !== undefined) {{
                if (v < yMin) yMin = v;
                if (v > yMax) yMax = v;
            }}
        }}
    }}
    const yPad = (yMax - yMin) * 0.06;
    yMin -= yPad; yMax += yPad;

    const n = series[0].data.length;
    const xScale = (i) => pad.left + (i / Math.max(n - 1, 1)) * cW;
    const yScale = (v) => pad.top + (1 - (v - yMin) / (yMax - yMin)) * cH;

    // 背景
    ctx.fillStyle = '#1e2732';
    ctx.fillRect(0, 0, W, H);

    // 网格 + Y 轴标签
    ctx.strokeStyle = '#2f3336'; ctx.lineWidth = 0.5;
    for (let i = 0; i <= 5; i++) {{
        const y = pad.top + (i / 5) * cH;
        ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
        const val = yMax - (i / 5) * (yMax - yMin);
        ctx.fillStyle = '#71767b'; ctx.font = '11px sans-serif'; ctx.textAlign = 'right';
        if (val >= 1000000) ctx.fillText('$' + (val/1000000).toFixed(2) + 'M', pad.left - 8, y + 4);
        else if (val >= 1000) ctx.fillText('$' + (val/1000).toFixed(1) + 'k', pad.left - 8, y + 4);
        else ctx.fillText('$' + val.toFixed(0), pad.left - 8, y + 4);
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
                ctx.moveTo(x, y + 6); ctx.lineTo(x - 4, y + 12); ctx.lineTo(x + 4, y + 12);
            }} else {{
                ctx.fillStyle = '#ef4444';
                ctx.moveTo(x, y - 6); ctx.lineTo(x - 4, y - 12); ctx.lineTo(x + 4, y - 12);
            }}
            ctx.closePath(); ctx.fill();
        }}
    }}

    // X 轴日期
    ctx.fillStyle = '#71767b'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center';
    const step = Math.max(1, Math.floor(n / 8));
    for (let i = 0; i < n; i += step) {{
        ctx.fillText(DATA.dates[i] ? DATA.dates[i].slice(0, 7) : '', xScale(i), H - 8);
    }}

    // 鼠标悬停 tooltip
    canvas.addEventListener('mousemove', function(e) {{
        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const idx = Math.round((mx - pad.left) / cW * (n - 1));
        if (idx >= 0 && idx < n && DATA.dates[idx]) {{
            const tip = document.getElementById('tooltip');
            const price = DATA.closes[idx];
            const maVal = DATA.ma[idx];
            tip.innerHTML = `${{DATA.dates[idx]}}<br>价格: $${{price ? price.toLocaleString() : '-'}}<br>MA: $${{maVal ? maVal.toLocaleString(undefined, {{maximumFractionDigits:0}}) : '-'}}`;
            tip.style.display = 'block';
            tip.style.left = (mx + 12) + 'px';
            tip.style.top = (e.clientY - rect.top - 60) + 'px';
        }}
    }});
    canvas.addEventListener('mouseleave', () => {{ document.getElementById('tooltip').style.display = 'none'; }});
}}

drawChart('priceChart', {{
    series: [
        {{ data: DATA.closes, color: '#3b82f6', width: 1.5 }},
        {{ data: DATA.ma, color: '#f59e0b', width: 2 }},
    ],
    signals: DATA.signals,
}});

drawChart('equityChart', {{
    series: [{{ data: DATA.equity, color: '#a78bfa', width: 2 }}],
}});
</script>
</body>
</html>"""
    return html
