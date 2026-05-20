"""
多交易所资金费率实时对比监控

功能:
- 同时拉取 Binance / OKX 的永续合约资金费率
- 计算跨所费率差值，识别套利机会
- 按年化收益率排序，筛选高收益品种
- 支持实时推送信号到前端
"""
import asyncio
import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone

import ccxt.async_support as ccxt_async

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class FundingRateInfo:
    """单个品种的资金费率信息"""
    symbol: str
    exchange: str
    funding_rate: float           # 当前费率 (如 0.0001 = 0.01%)
    predicted_rate: Optional[float] = None  # 预测下期费率
    next_funding_time: Optional[str] = None
    mark_price: float = 0.0
    index_price: float = 0.0
    annual_rate: float = 0.0      # 年化收益率
    funding_interval_hours: int = 8  # 结算周期 (小时)
    timestamp: float = 0.0


@dataclass
class CrossExchangeOpportunity:
    """跨所费率套利机会"""
    symbol: str
    long_exchange: str            # 做多的交易所 (费率低/负)
    short_exchange: str           # 做空的交易所 (费率高/正)
    long_rate: float              # 做多所的费率
    short_rate: float             # 做空所的费率
    rate_spread: float            # 费率差
    annual_spread: float          # 年化差值
    estimated_daily_profit_pct: float  # 估计日收益率
    mark_price: float = 0.0
    risk_score: float = 0.0       # 风险评分 0-1 (越低越安全)
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "long_exchange": self.long_exchange,
            "short_exchange": self.short_exchange,
            "long_rate": round(self.long_rate * 100, 4),  # 转为百分比
            "short_rate": round(self.short_rate * 100, 4),
            "rate_spread": round(self.rate_spread * 100, 4),
            "annual_spread_pct": round(self.annual_spread * 100, 2),
            "estimated_daily_profit_pct": round(self.estimated_daily_profit_pct * 100, 4),
            "mark_price": self.mark_price,
            "risk_score": round(self.risk_score, 2),
            "timestamp": self.timestamp,
        }


@dataclass
class SingleExchangeOpportunity:
    """单所期现费率套利机会 (现货买入 + 永续做空)"""
    symbol: str
    exchange: str
    funding_rate: float
    annual_rate: float
    mark_price: float
    funding_interval_hours: int
    risk_score: float = 0.0
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "funding_rate_pct": round(self.funding_rate * 100, 4),
            "annual_rate_pct": round(self.annual_rate * 100, 2),
            "mark_price": self.mark_price,
            "funding_interval_hours": self.funding_interval_hours,
            "risk_score": round(self.risk_score, 2),
            "timestamp": self.timestamp,
        }


class FundingRateMonitor:
    """
    多交易所资金费率监控器
    
    支持交易所: Binance, OKX
    功能:
    - 实时拉取所有永续合约的 funding rate
    - 计算年化收益率
    - 识别跨所套利机会 (rate spread)
    - 识别单所高费率套利机会
    """

    # 费用假设 (用于计算净收益)
    FEES = {
        "binance": {"maker": 0.0002, "taker": 0.0005, "funding_fee": 0},
        "okx": {"maker": 0.0002, "taker": 0.0005, "funding_fee": 0},
    }

    def __init__(
        self,
        min_funding_rate: float = 0.0003,     # 单所最低费率阈值 (0.03%)
        min_cross_spread: float = 0.0005,     # 跨所最低价差阈值 (0.05%)
        symbols_filter: Optional[List[str]] = None,  # 只监控指定币种
        max_results: int = 20,                # 最多返回结果数
    ):
        self.min_funding_rate = min_funding_rate
        self.min_cross_spread = min_cross_spread
        self.symbols_filter = symbols_filter
        self.max_results = max_results

        # 缓存
        self._rates: Dict[str, Dict[str, FundingRateInfo]] = {}  # {exchange: {symbol: info}}
        self._last_update: float = 0
        self._update_interval = 60  # 最小更新间隔 (秒)

        # 交易所客户端 (延迟初始化)
        self._exchanges: Dict[str, ccxt_async.Exchange] = {}

    async def _get_exchange(self, name: str) -> ccxt_async.Exchange:
        """获取或创建交易所客户端"""
        if name not in self._exchanges:
            if name == "binance":
                self._exchanges[name] = ccxt_async.binance({
                    "enableRateLimit": True,
                    "options": {"defaultType": "swap"},
                })
            elif name == "okx":
                self._exchanges[name] = ccxt_async.okx({
                    "enableRateLimit": True,
                    "options": {"defaultType": "swap"},
                })
            else:
                raise ValueError(f"不支持的交易所: {name}")
        return self._exchanges[name]

    async def fetch_all_rates(self) -> Dict[str, Dict[str, FundingRateInfo]]:
        """
        并行拉取所有交易所的 funding rate
        
        Returns:
            {exchange_name: {symbol: FundingRateInfo}}
        """
        now = time.time()
        if now - self._last_update < self._update_interval and self._rates:
            return self._rates

        tasks = [
            self._fetch_exchange_rates("binance"),
            self._fetch_exchange_rates("okx"),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, exchange_name in enumerate(["binance", "okx"]):
            if isinstance(results[i], Exception):
                logger.error(f"拉取 {exchange_name} funding rates 失败: {results[i]}")
            else:
                self._rates[exchange_name] = results[i]

        self._last_update = now
        return self._rates

    async def _fetch_exchange_rates(self, exchange_name: str) -> Dict[str, FundingRateInfo]:
        """从单个交易所拉取所有永续合约 funding rate"""
        exchange = await self._get_exchange(exchange_name)
        rates_map: Dict[str, FundingRateInfo] = {}

        try:
            # 加载市场信息
            await exchange.load_markets()

            # 获取所有永续合约的 funding rates
            funding_rates = await exchange.fetch_funding_rates()

            for symbol, data in funding_rates.items():
                # 标准化 symbol (转为 BTC/USDT:USDT 格式)
                base_symbol = symbol.split(":")[0] if ":" in symbol else symbol

                # 过滤 USDT 结算的
                if not base_symbol.endswith("/USDT"):
                    continue

                # 只保留指定币种
                clean_symbol = base_symbol.replace("/USDT", "USDT")
                if self.symbols_filter and clean_symbol not in self.symbols_filter:
                    continue

                funding_rate = data.get("fundingRate", 0) or 0
                predicted_rate = data.get("nextFundingRate") or data.get("fundingRate", 0)
                mark_price = data.get("markPrice", 0) or 0
                index_price = data.get("indexPrice", 0) or 0

                # 确定结算周期
                interval_hours = 8  # 默认 8h
                if exchange_name == "binance":
                    # 部分品种是 4h 结算
                    funding_timestamp = data.get("fundingTimestamp", 0)
                    info = data.get("info", {})
                    if isinstance(info, dict) and info.get("fundingIntervalHours"):
                        interval_hours = int(info["fundingIntervalHours"])

                # 年化计算
                settlements_per_year = 365 * 24 / interval_hours
                annual_rate = funding_rate * settlements_per_year

                rates_map[clean_symbol] = FundingRateInfo(
                    symbol=clean_symbol,
                    exchange=exchange_name,
                    funding_rate=funding_rate,
                    predicted_rate=predicted_rate,
                    next_funding_time=data.get("fundingDatetime"),
                    mark_price=mark_price,
                    index_price=index_price,
                    annual_rate=annual_rate,
                    funding_interval_hours=interval_hours,
                    timestamp=time.time(),
                )

            logger.info(f"📊 {exchange_name}: 获取 {len(rates_map)} 个品种 funding rate")

        except Exception as e:
            logger.error(f"拉取 {exchange_name} 费率失败: {e}")
            raise

        return rates_map

    async def find_cross_exchange_opportunities(self) -> List[CrossExchangeOpportunity]:
        """
        发现跨所费率套利机会
        
        逻辑: 同一品种在两个交易所的 funding rate 不同
        - A 所费率高 → 在 A 所做空永续 (收费率)
        - B 所费率低/负 → 在 B 所做多永续 (少付/收费率)
        - 净收益 = |A_rate - B_rate| (扣除手续费后)
        """
        rates = await self.fetch_all_rates()

        if len(rates) < 2:
            return []

        opportunities: List[CrossExchangeOpportunity] = []
        exchanges = list(rates.keys())

        # 找到两所都有的品种
        for symbol in rates.get(exchanges[0], {}):
            if symbol not in rates.get(exchanges[1], {}):
                continue

            rate_a = rates[exchanges[0]][symbol]
            rate_b = rates[exchanges[1]][symbol]

            # 计算费率差
            spread = rate_a.funding_rate - rate_b.funding_rate

            if abs(spread) < self.min_cross_spread:
                continue

            # 确定方向: 在费率高的所做空，费率低的所做多
            if spread > 0:
                short_ex, long_ex = exchanges[0], exchanges[1]
                short_rate, long_rate = rate_a.funding_rate, rate_b.funding_rate
                mark_price = rate_a.mark_price
            else:
                short_ex, long_ex = exchanges[1], exchanges[0]
                short_rate, long_rate = rate_b.funding_rate, rate_a.funding_rate
                mark_price = rate_b.mark_price

            # 计算净收益 (扣除开仓手续费)
            total_fees = (
                self.FEES[short_ex]["taker"] +  # 做空开仓
                self.FEES[long_ex]["taker"]     # 做多开仓
            )

            net_spread = abs(spread)
            # 年化
            avg_interval = (rate_a.funding_interval_hours + rate_b.funding_interval_hours) / 2
            settlements_per_year = 365 * 24 / avg_interval
            annual_spread = net_spread * settlements_per_year

            # 日收益
            settlements_per_day = 24 / avg_interval
            daily_profit = net_spread * settlements_per_day - total_fees / 30  # 摊薄开仓费

            # 风险评分 (越低越安全)
            risk = self._calculate_risk(symbol, net_spread, mark_price)

            opportunities.append(CrossExchangeOpportunity(
                symbol=symbol,
                long_exchange=long_ex,
                short_exchange=short_ex,
                long_rate=long_rate,
                short_rate=short_rate,
                rate_spread=net_spread,
                annual_spread=annual_spread,
                estimated_daily_profit_pct=daily_profit,
                mark_price=mark_price,
                risk_score=risk,
                timestamp=time.time(),
            ))

        # 按年化收益排序
        opportunities.sort(key=lambda x: x.annual_spread, reverse=True)
        return opportunities[:self.max_results]

    async def find_single_exchange_opportunities(self) -> List[SingleExchangeOpportunity]:
        """
        发现单所资金费率套利机会
        
        逻辑: 费率为正且足够高 → 现货买入 + 永续做空 → 收取费率
        """
        rates = await self.fetch_all_rates()
        opportunities: List[SingleExchangeOpportunity] = []

        for exchange_name, exchange_rates in rates.items():
            for symbol, info in exchange_rates.items():
                if info.funding_rate < self.min_funding_rate:
                    continue

                # 扣除手续费后的净收益
                open_fee = self.FEES[exchange_name]["taker"] * 2  # 现货+合约开仓
                net_rate = info.funding_rate - open_fee / (365 * 24 / info.funding_interval_hours)

                if net_rate <= 0:
                    continue

                risk = self._calculate_risk(symbol, info.funding_rate, info.mark_price)

                opportunities.append(SingleExchangeOpportunity(
                    symbol=symbol,
                    exchange=exchange_name,
                    funding_rate=info.funding_rate,
                    annual_rate=info.annual_rate,
                    mark_price=info.mark_price,
                    funding_interval_hours=info.funding_interval_hours,
                    risk_score=risk,
                    timestamp=time.time(),
                ))

        # 按年化排序
        opportunities.sort(key=lambda x: x.annual_rate, reverse=True)
        return opportunities[:self.max_results]

    def _calculate_risk(self, symbol: str, rate: float, price: float) -> float:
        """
        计算风险评分 (0-1, 越低越安全)
        
        考虑因素:
        - 费率极端程度 (过高的费率不可持续)
        - 币种流动性 (主流币更安全)
        - 价格级别
        """
        risk = 0.0

        # 费率极端 (> 0.1% 很可能快速反转)
        if abs(rate) > 0.001:
            risk += 0.4
        elif abs(rate) > 0.0005:
            risk += 0.2

        # 小币种风险更高
        major_coins = {"BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"}
        if symbol not in major_coins:
            risk += 0.3

        # 低价格 (可能流动性差)
        if price < 1:
            risk += 0.2

        return min(risk, 1.0)

    async def get_summary(self) -> dict:
        """获取监控摘要"""
        rates = await self.fetch_all_rates()

        total_symbols = set()
        for ex_rates in rates.values():
            total_symbols.update(ex_rates.keys())

        cross_opps = await self.find_cross_exchange_opportunities()
        single_opps = await self.find_single_exchange_opportunities()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "exchanges_monitored": list(rates.keys()),
            "total_symbols": len(total_symbols),
            "cross_exchange_opportunities": len(cross_opps),
            "single_exchange_opportunities": len(single_opps),
            "top_cross_exchange": [o.to_dict() for o in cross_opps[:5]],
            "top_single_exchange": [o.to_dict() for o in single_opps[:10]],
        }

    async def close(self):
        """关闭所有交易所连接"""
        for exchange in self._exchanges.values():
            try:
                await exchange.close()
            except Exception:
                pass
        self._exchanges.clear()


# 全局实例
_monitor: Optional[FundingRateMonitor] = None


def get_funding_rate_monitor() -> FundingRateMonitor:
    """获取全局监控器实例"""
    global _monitor
    if _monitor is None:
        _monitor = FundingRateMonitor(
            symbols_filter=None,  # 监控所有品种
            min_funding_rate=0.0003,
            min_cross_spread=0.0004,
        )
    return _monitor
