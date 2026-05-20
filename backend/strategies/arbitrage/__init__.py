"""
套利策略模块

包含各类套利策略：
- 资金费率套利 (单所 + 跨所)
- 三角套利扫描
- 期现基差套利
"""

from .funding_rate import FundingRateArbitrage, create_strategy
from .funding_rate_monitor import FundingRateMonitor, get_funding_rate_monitor
from .triangular_scanner import TriangularArbitrageScanner, get_triangular_scanner
from .basis_arbitrage import BasisArbitrageScanner, get_basis_scanner

__all__ = [
    # 资金费率
    "FundingRateArbitrage",
    "create_strategy",
    "FundingRateMonitor",
    "get_funding_rate_monitor",
    # 三角套利
    "TriangularArbitrageScanner",
    "get_triangular_scanner",
    # 期现基差
    "BasisArbitrageScanner",
    "get_basis_scanner",
]
