"""
套利策略模块

包含各类套利策略：
- 资金费率套利
- 期现套利
- 跨交易所套利
- 三角套利
"""

from .funding_rate import FundingRateArbitrage, create_strategy

__all__ = [
    "FundingRateArbitrage",
    "create_strategy",
]
