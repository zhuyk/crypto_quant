"""
策略对比器 - 多策略对比分析
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class StrategyComparison:
    """策略对比结果"""
    strategies: List[str]
    metrics: Dict[str, dict]
    ranking: List[tuple]
    best_strategy: str
    comparison_time: datetime


class StrategyComparator:
    """
    策略对比器
    
    对比多个策略的表现，生成排名和分析报告
    """
    
    def __init__(self):
        """初始化对比器"""
        self._comparison_history = []
    
    def compare(
        self,
        backtest_results: Dict[str, dict],
        metrics: Optional[List[str]] = None,
    ) -> StrategyComparison:
        """
        对比策略
        
        Args:
            backtest_results: 回测结果 {strategy_name: result}
            metrics: 对比指标列表
            
        Returns:
            StrategyComparison: 对比结果
        """
        if metrics is None:
            metrics = [
                'sharpe_ratio',
                'sortino_ratio',
                'total_return',
                'max_drawdown',
                'win_rate',
                'calmar_ratio',
            ]
        
        # 提取指标
        strategy_metrics = {}
        
        for strategy_name, result in backtest_results.items():
            strategy_metrics[strategy_name] = {
                metric: result.get(metric, 0)
                for metric in metrics
            }
        
        # 计算综合得分
        rankings = self._calculate_ranking(strategy_metrics, metrics)
        
        # 找出最佳策略
        best_strategy = rankings[0][0] if rankings else None
        
        comparison = StrategyComparison(
            strategies=list(backtest_results.keys()),
            metrics=strategy_metrics,
            ranking=rankings,
            best_strategy=best_strategy,
            comparison_time=datetime.utcnow(),
        )
        
        self._comparison_history.append(comparison)
        
        return comparison
    
    def _calculate_ranking(
        self,
        strategy_metrics: Dict[str, dict],
        metrics: List[str],
    ) -> List[tuple]:
        """
        计算排名
        
        Returns:
            List[tuple]: [(strategy_name, score), ...]
        """
        # 指标权重
        weights = {
            'sharpe_ratio': 0.3,
            'sortino_ratio': 0.2,
            'total_return': 0.2,
            'max_drawdown': 0.15,
            'win_rate': 0.1,
            'calmar_ratio': 0.05,
        }
        
        # 归一化指标
        normalized = self._normalize_metrics(strategy_metrics, metrics)
        
        # 计算综合得分
        scores = {}
        
        for strategy, metrics_dict in normalized.items():
            score = 0
            
            for metric in metrics:
                value = metrics_dict.get(metric, 0)
                weight = weights.get(metric, 0)
                
                # 回撤越小越好
                if metric == 'max_drawdown':
                    score += (1 - value) * weight
                else:
                    score += value * weight
            
            scores[strategy] = score
        
        # 排序
        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        return ranking
    
    def _normalize_metrics(
        self,
        strategy_metrics: Dict[str, dict],
        metrics: List[str],
    ) -> Dict[str, dict]:
        """归一化指标"""
        normalized = {}
        
        for metric in metrics:
            values = [
                strategy_metrics[s][metric]
                for s in strategy_metrics
                if metric in strategy_metrics[s]
            ]
            
            if not values:
                continue
            
            min_val = min(values)
            max_val = max(values)
            range_val = max_val - min_val
            
            for strategy in strategy_metrics:
                if strategy not in normalized:
                    normalized[strategy] = {}
                
                value = strategy_metrics[strategy].get(metric, 0)
                
                if range_val > 0:
                    normalized[strategy][metric] = (value - min_val) / range_val
                else:
                    normalized[strategy][metric] = 0.5
        
        return normalized
    
    def generate_report(
        self,
        comparison: StrategyComparison,
        format: str = 'text',
    ) -> str:
        """
        生成对比报告
        
        Args:
            comparison: 对比结果
            format: 输出格式 (text/markdown/html)
            
        Returns:
            str: 报告内容
        """
        if format == 'text':
            return self._generate_text_report(comparison)
        elif format == 'markdown':
            return self._generate_markdown_report(comparison)
        elif format == 'html':
            return self._generate_html_report(comparison)
        else:
            raise ValueError(f"不支持的格式：{format}")
    
    def _generate_text_report(self, comparison: StrategyComparison) -> str:
        """生成文本报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("策略对比报告")
        lines.append("=" * 60)
        lines.append(f"对比时间：{comparison.comparison_time.isoformat()}")
        lines.append(f"策略数量：{len(comparison.strategies)}")
        lines.append("")
        
        lines.append("排名:")
        lines.append("-" * 40)
        for i, (strategy, score) in enumerate(comparison.ranking, 1):
            lines.append(f"{i}. {strategy}: {score:.4f}")
        lines.append("")
        
        lines.append(f"最佳策略：{comparison.best_strategy}")
        lines.append("")
        
        lines.append("详细指标:")
        lines.append("-" * 40)
        for strategy in comparison.strategies:
            lines.append(f"\n{strategy}:")
            metrics = comparison.metrics.get(strategy, {})
            for metric, value in metrics.items():
                lines.append(f"  {metric}: {value:.4f}")
        
        return "\n".join(lines)
    
    def _generate_markdown_report(self, comparison: StrategyComparison) -> str:
        """生成 Markdown 报告"""
        lines = []
        lines.append("# 策略对比报告\n")
        lines.append(f"**对比时间**: {comparison.comparison_time.isoformat()}\n")
        lines.append(f"**策略数量**: {len(comparison.strategies)}\n\n")
        
        lines.append("## 排名\n\n")
        lines.append("| 排名 | 策略 | 综合得分 |")
        lines.append("|------|------|----------|")
        for i, (strategy, score) in enumerate(comparison.ranking, 1):
            lines.append(f"| {i} | {strategy} | {score:.4f} |")
        lines.append("")
        
        lines.append(f"\n**最佳策略**: {comparison.best_strategy}\n\n")
        
        lines.append("## 详细指标\n\n")
        lines.append("| 策略 | " + " | ".join(comparison.metrics.get(comparison.strategies[0], {}).keys()) + " |")
        lines.append("|------|" + "|".join(["---"] * len(comparison.metrics.get(comparison.strategies[0], {}))) + "|")
        
        for strategy in comparison.strategies:
            metrics = comparison.metrics.get(strategy, {})
            values = [f"{v:.4f}" for v in metrics.values()]
            lines.append(f"| {strategy} | " + " | ".join(values) + " |")
        
        return "\n".join(lines)
    
    def _generate_html_report(self, comparison: StrategyComparison) -> str:
        """生成 HTML 报告"""
        html = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { color: #333; }
                table { border-collapse: collapse; width: 100%; margin: 20px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #4CAF50; color: white; }
                tr:nth-child(even) { background-color: #f2f2f2; }
                .best { background-color: #d4edda; }
            </style>
        </head>
        <body>
            <h1>策略对比报告</h1>
            <p><strong>对比时间</strong>: """ + comparison.comparison_time.isoformat() + """</p>
            <p><strong>策略数量</strong>: """ + str(len(comparison.strategies)) + """</p>
            
            <h2>排名</h2>
            <table>
                <tr><th>排名</th><th>策略</th><th>综合得分</th></tr>
        """
        
        for i, (strategy, score) in enumerate(comparison.ranking, 1):
            best_class = 'class="best"' if i == 1 else ''
            html += f"<tr {best_class}><td>{i}</td><td>{strategy}</td><td>{score:.4f}</td></tr>"
        
        html += """
            </table>
            
            <h2>详细指标</h2>
            <table>
                <tr><th>策略</th>
        """
        
        # 添加指标头
        if comparison.strategies:
            sample_metrics = comparison.metrics.get(comparison.strategies[0], {})
            for metric in sample_metrics.keys():
                html += f"<th>{metric}</th>"
        
        html += "</tr>"
        
        # 添加数据行
        for strategy in comparison.strategies:
            html += f"<tr><td>{strategy}</td>"
            metrics = comparison.metrics.get(strategy, {})
            for value in metrics.values():
                html += f"<td>{value:.4f}</td>"
            html += "</tr>"
        
        html += """
            </table>
        </body>
        </html>
        """
        
        return html
