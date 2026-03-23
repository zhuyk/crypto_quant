"""
资金曲线 - 权益变化可视化
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class EquityPoint:
    """权益点"""
    timestamp: int
    value: float
    pnl: float = 0.0
    drawdown: float = 0.0


class EquityCurve:
    """
    资金曲线生成器
    
    生成权益曲线、回撤曲线等
    """
    
    def __init__(self):
        """初始化资金曲线"""
        self._data_points: List[EquityPoint] = []
    
    def add_point(
        self,
        timestamp: int,
        value: float,
        pnl: float = 0.0,
        drawdown: float = 0.0,
    ):
        """添加数据点"""
        self._data_points.append(
            EquityPoint(
                timestamp=timestamp,
                value=value,
                pnl=pnl,
                drawdown=drawdown,
            )
        )
    
    def add_points(self, points: List[dict]):
        """批量添加数据点"""
        for p in points:
            self.add_point(
                timestamp=p.get('time', int(datetime.utcnow().timestamp() * 1000)),
                value=p.get('value', 0),
                pnl=p.get('pnl', 0),
                drawdown=p.get('drawdown', 0),
            )
    
    def calculate_drawdown(self) -> List[float]:
        """计算回撤"""
        if not self._data_points:
            return []
        
        drawdowns = []
        peak = self._data_points[0].value
        
        for point in self._data_points:
            if point.value > peak:
                peak = point.value
            
            dd = (peak - point.value) / peak if peak > 0 else 0
            drawdowns.append(dd)
        
        return drawdowns
    
    def get_chart_data(self) -> dict:
        """获取图表数据"""
        return {
            'timestamps': [p.timestamp for p in self._data_points],
            'values': [p.value for p in self._data_points],
            'pnl': [p.pnl for p in self._data_points],
            'drawdowns': self.calculate_drawdown(),
        }
    
    def generate_config(self, title: str = "资金曲线") -> dict:
        """生成图表配置"""
        return {
            'title': title,
            'type': 'line',
            'data': self.get_chart_data(),
            'options': {
                'responsive': True,
                'showLegend': True,
                'showGrid': True,
            },
        }
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        if not self._data_points:
            return {}
        
        values = [p.value for p in self._data_points]
        pnl = [p.pnl for p in self._data_points]
        drawdowns = self.calculate_drawdown()
        
        return {
            'initial_value': values[0] if values else 0,
            'final_value': values[-1] if values else 0,
            'total_return': (values[-1] - values[0]) / values[0] if values and values[0] > 0 else 0,
            'max_value': max(values),
            'min_value': min(values),
            'max_drawdown': max(drawdowns) if drawdowns else 0,
            'avg_drawdown': sum(drawdowns) / len(drawdowns) if drawdowns else 0,
            'total_pnl': sum(pnl),
            'avg_pnl': sum(pnl) / len(pnl) if pnl else 0,
            'data_points': len(self._data_points),
        }
    
    def clear(self):
        """清空数据"""
        self._data_points.clear()
