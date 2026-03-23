"""
表现图表 - 策略表现可视化
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class PerformanceChart:
    """
    表现图表生成器
    
    生成各种策略表现图表
    """
    
    def __init__(self):
        """初始化表现图表"""
        self._metrics = {}
    
    def add_metric(self, name: str, value: float, label: str = ""):
        """添加指标"""
        self._metrics[name] = {
            'value': value,
            'label': label or name,
        }
    
    def generate_metrics_chart(
        self,
        backtest_result: dict,
        chart_type: str = "radar",
    ) -> dict:
        """
        生成表现指标图表
        
        Args:
            backtest_result: 回测结果
            chart_type: 图表类型 (radar/bar)
            
        Returns:
            dict: 图表配置
        """
        metrics = {
            'Sharpe Ratio': backtest_result.get('sharpe_ratio', 0),
            'Sortino Ratio': backtest_result.get('sortino_ratio', 0),
            'Win Rate': backtest_result.get('win_rate', 0) * 100,
            'Profit Factor': backtest_result.get('profit_factor', 0),
            'Calmar Ratio': backtest_result.get('calmar_ratio', 0),
            'Recovery Factor': backtest_result.get('recovery_factor', 0),
        }
        
        # 归一化到 0-10
        normalized = {}
        for name, value in metrics.items():
            if name in ['Win Rate']:
                normalized[name] = value  # 已经是百分比
            elif name in ['Profit Factor', 'Recovery Factor']:
                normalized[name] = min(value * 10, 100)  # 放大
            else:
                normalized[name] = min(value * 20, 100)  # 放大
        
        return {
            'type': chart_type,
            'title': '策略表现指标',
            'data': {
                'labels': list(normalized.keys()),
                'values': list(normalized.values()),
            },
            'options': {
                'maxValue': 100,
                'showLegend': True,
            },
        }
    
    def generate_monthly_return_chart(
        self,
        monthly_returns: List[dict],
    ) -> dict:
        """
        生成月度收益图表
        
        Args:
            monthly_returns: 月度收益数据 [{month, return}]
            
        Returns:
            dict: 图表配置
        """
        return {
            'type': 'bar',
            'title': '月度收益',
            'data': {
                'labels': [m['month'] for m in monthly_returns],
                'values': [m['return'] * 100 for m in monthly_returns],
            },
            'options': {
                'colorPositive': '#28a745',
                'colorNegative': '#dc3545',
                'showGrid': True,
            },
        }
    
    def generate_drawdown_chart(
        self,
        drawdowns: List[dict],
    ) -> dict:
        """
        生成回撤图表
        
        Args:
            drawdowns: 回撤数据 [{time, drawdown}]
            
        Returns:
            dict: 图表配置
        """
        return {
            'type': 'area',
            'title': '回撤曲线',
            'data': {
                'timestamps': [d['time'] for d in drawdowns],
                'values': [d['drawdown'] * 100 for d in drawdowns],
            },
            'options': {
                'color': '#dc3545',
                'fillColor': 'rgba(220, 53, 69, 0.2)',
                'showGrid': True,
            },
        }
    
    def generate_distribution_chart(
        self,
        returns: List[float],
        bins: int = 20,
    ) -> dict:
        """
        生成收益分布图
        
        Args:
            returns: 收益数据
            bins: 分组数
            
        Returns:
            dict: 图表配置
        """
        import numpy as np
        
        # 计算直方图
        hist, bin_edges = np.histogram(returns, bins=bins)
        
        return {
            'type': 'histogram',
            'title': '收益分布',
            'data': {
                'bins': [f"{(bin_edges[i] + bin_edges[i+1]) / 2:.4f}" for i in range(len(hist))],
                'counts': hist.tolist(),
            },
            'options': {
                'color': '#007bff',
                'showGrid': True,
            },
        }
    
    def generate_comparison_chart(
        self,
        strategies: List[dict],
        metric: str = "equity_curve",
    ) -> dict:
        """
        生成策略对比图
        
        Args:
            strategies: 策略数据列表
            metric: 对比指标
            
        Returns:
            dict: 图表配置
        """
        datasets = []
        
        for strategy in strategies:
            datasets.append({
                'label': strategy.get('name', 'Unknown'),
                'data': strategy.get(metric, []),
                'borderColor': strategy.get('color', '#000000'),
            })
        
        return {
            'type': 'line',
            'title': f'策略对比 - {metric}',
            'data': {
                'datasets': datasets,
            },
            'options': {
                'showLegend': True,
                'showGrid': True,
            },
        }
