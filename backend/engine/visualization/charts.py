#!/usr/bin/env python3
"""
数据可视化模块
生成交易图表、资金曲线、策略表现等
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger


def create_equity_curve_data(
    initial_capital: float,
    trades: List[Dict],
    daily: bool = True,
) -> List[Dict]:
    """
    创建资金曲线数据
    
    Args:
        initial_capital: 初始资金
        trades: 交易历史列表
        daily: 是否按日聚合
    
    Returns:
        资金曲线数据点列表
    """
    if not trades:
        return [
            {"timestamp": datetime.now().isoformat(), "equity": initial_capital, "pnl": 0}
        ]
    
    # 按时间排序
    sorted_trades = sorted(trades, key=lambda x: x.get("closed_at", ""))
    
    equity = initial_capital
    curve = []
    
    # 初始点
    curve.append({
        "timestamp": sorted_trades[0].get("opened_at", datetime.now().isoformat()),
        "equity": initial_capital,
        "pnl": 0,
        "drawdown": 0,
    })
    
    peak = initial_capital
    
    for trade in sorted_trades:
        equity += trade.get("pnl", 0)
        peak = max(peak, equity)
        drawdown = (peak - equity) / peak * 100
        
        curve.append({
            "timestamp": trade.get("closed_at", datetime.now().isoformat()),
            "equity": equity,
            "pnl": equity - initial_capital,
            "pnl_pct": (equity - initial_capital) / initial_capital * 100,
            "drawdown": drawdown,
        })
    
    return curve


def create_position_chart_data(positions: List[Dict]) -> List[Dict]:
    """
    创建持仓分布数据
    
    Returns:
        持仓分布数据
    """
    if not positions:
        return []
    
    chart_data = []
    for pos in positions:
        chart_data.append({
            "symbol": pos.get("symbol", "Unknown"),
            "value": pos.get("amount", 0) * pos.get("current_price", pos.get("entry_price", 0)),
            "pnl": pos.get("unrealized_pnl", 0),
            "pnl_pct": pos.get("unrealized_pnl_pct", 0),
            "side": pos.get("side", "unknown"),
        })
    
    return chart_data


def calculate_strategy_metrics(trades: List[Dict]) -> Dict:
    """
    计算策略表现指标
    
    Args:
        trades: 交易历史
    
    Returns:
        指标字典
    """
    if not trades:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "avg_pnl": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "profit_factor": 0,
            "largest_win": 0,
            "largest_loss": 0,
            "avg_holding_period": 0,
        }
    
    pnls = [t.get("pnl", 0) for t in trades]
    winning_pnls = [p for p in pnls if p > 0]
    losing_pnls = [p for p in pnls if p < 0]
    
    total_trades = len(trades)
    winning_trades = len(winning_pnls)
    losing_trades = len(losing_pnls)
    
    win_rate = winning_trades / total_trades if total_trades > 0 else 0
    
    total_pnl = sum(pnls)
    avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
    
    avg_win = sum(winning_pnls) / len(winning_pnls) if winning_pnls else 0
    avg_loss = sum(losing_pnls) / len(losing_pnls) if losing_pnls else 0
    
    total_wins = sum(winning_pnls)
    total_losses = abs(sum(losing_pnls))
    profit_factor = total_wins / total_losses if total_losses > 0 else 0
    
    largest_win = max(winning_pnls) if winning_pnls else 0
    largest_loss = min(losing_pnls) if losing_pnls else 0
    
    # 计算平均持仓时间
    holding_periods = []
    for trade in trades:
        opened = trade.get("opened_at")
        closed = trade.get("closed_at")
        if opened and closed:
            try:
                open_time = datetime.fromisoformat(opened.replace("Z", "+00:00"))
                close_time = datetime.fromisoformat(closed.replace("Z", "+00:00"))
                holding_periods.append((close_time - open_time).total_seconds() / 3600)  # 小时
            except:
                pass
    
    avg_holding_period = sum(holding_periods) / len(holding_periods) if holding_periods else 0
    
    return {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": round(win_rate * 100, 2),
        "total_pnl": round(total_pnl, 2),
        "avg_pnl": round(avg_pnl, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2),
        "largest_win": round(largest_win, 2),
        "largest_loss": round(largest_loss, 2),
        "avg_holding_period": round(avg_holding_period, 2),
    }


def calculate_sharpe_ratio(
    returns: List[float],
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252,
) -> float:
    """
    计算夏普比率
    
    Args:
        returns: 收益率序列 (小数形式，如 0.01 表示 1%)
        risk_free_rate: 无风险利率
        periods_per_year: 年化因子 (日线 252, 小时线 8760)
    
    Returns:
        夏普比率
    """
    if not returns or len(returns) < 2:
        return 0.0
    
    returns_series = pd.Series(returns)
    
    # 超额收益
    excess_returns = returns_series - risk_free_rate / periods_per_year
    
    # 夏普比率
    if returns_series.std() == 0:
        return 0.0
    
    sharpe = excess_returns.mean() / returns_series.std() * np.sqrt(periods_per_year)
    
    return round(sharpe, 2)


def calculate_max_drawdown(equity_curve: List[Dict]) -> Dict:
    """
    计算最大回撤
    
    Args:
        equity_curve: 资金曲线数据
    
    Returns:
        回撤信息
    """
    if not equity_curve:
        return {
            "max_drawdown": 0,
            "max_drawdown_pct": 0,
            "start_date": None,
            "end_date": None,
            "recovery_date": None,
        }
    
    equities = [point.get("equity", 0) for point in equity_curve]
    timestamps = [point.get("timestamp", "") for point in equity_curve]
    
    peak = equities[0]
    peak_idx = 0
    max_dd = 0
    max_dd_pct = 0
    start_idx = 0
    end_idx = 0
    
    for i, equity in enumerate(equities):
        if equity > peak:
            peak = equity
            peak_idx = i
        
        dd = peak - equity
        dd_pct = dd / peak * 100 if peak > 0 else 0
        
        if dd_pct > max_dd_pct:
            max_dd = dd
            max_dd_pct = dd_pct
            start_idx = peak_idx
            end_idx = i
    
    # 寻找恢复日期
    recovery_idx = None
    if end_idx < len(equities) - 1:
        peak_value = equities[start_idx]
        for i in range(end_idx + 1, len(equities)):
            if equities[i] >= peak_value:
                recovery_idx = i
                break
    
    return {
        "max_drawdown": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "start_date": timestamps[start_idx] if start_idx < len(timestamps) else None,
        "end_date": timestamps[end_idx] if end_idx < len(timestamps) else None,
        "recovery_date": timestamps[recovery_idx] if recovery_idx else None,
    }


def generate_trade_analysis_report(
    trades: List[Dict],
    equity_curve: List[Dict],
    initial_capital: float,
) -> Dict:
    """
    生成交易分析报告
    
    Args:
        trades: 交易历史
        equity_curve: 资金曲线
        initial_capital: 初始资金
    
    Returns:
        分析报告
    """
    # 策略指标
    strategy_metrics = calculate_strategy_metrics(trades)
    
    # 回撤分析
    drawdown_analysis = calculate_max_drawdown(equity_curve)
    
    # 计算收益率序列
    if len(equity_curve) >= 2:
        returns = []
        for i in range(1, len(equity_curve)):
            prev_equity = equity_curve[i-1].get("equity", initial_capital)
            curr_equity = equity_curve[i].get("equity", initial_capital)
            if prev_equity > 0:
                returns.append((curr_equity - prev_equity) / prev_equity)
        
        sharpe = calculate_sharpe_ratio(returns)
    else:
        sharpe = 0.0
    
    # 当前状态
    current_equity = equity_curve[-1].get("equity", initial_capital) if equity_curve else initial_capital
    total_pnl = current_equity - initial_capital
    total_pnl_pct = total_pnl / initial_capital * 100
    
    return {
        "summary": {
            "initial_capital": initial_capital,
            "current_equity": current_equity,
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
        },
        "performance": {
            "sharpe_ratio": sharpe,
            "max_drawdown": drawdown_analysis["max_drawdown_pct"],
            "win_rate": strategy_metrics["win_rate"],
            "profit_factor": strategy_metrics["profit_factor"],
        },
        "trades": strategy_metrics,
        "drawdown": drawdown_analysis,
        "generated_at": datetime.now().isoformat(),
    }


def create_kline_chart_data(df: pd.DataFrame, indicators: List[str] = None) -> Dict:
    """
    创建 K 线图表数据
    
    Args:
        df: K 线数据 (OHLCV)
        indicators: 需要包含的指标
    
    Returns:
        图表数据
    """
    if df.empty:
        return {"candles": [], "indicators": {}}
    
    # K 线数据
    candles = []
    for idx, row in df.iterrows():
        candles.append({
            "timestamp": idx.isoformat() if hasattr(idx, 'isoformat') else str(idx),
            "open": float(row.get("open", 0)),
            "high": float(row.get("high", 0)),
            "low": float(row.get("low", 0)),
            "close": float(row.get("close", 0)),
            "volume": float(row.get("volume", 0)),
        })
    
    # 指标数据
    indicator_data = {}
    
    if indicators:
        for indicator in indicators:
            if indicator in df.columns:
                indicator_data[indicator] = df[indicator].tolist()
    
    return {
        "candles": candles,
        "indicators": indicator_data,
        "symbol": df.get("symbol", ["Unknown"])[0] if "symbol" in df.columns else "Unknown",
        "timeframe": "1h",  # TODO: 从数据中获取
    }
