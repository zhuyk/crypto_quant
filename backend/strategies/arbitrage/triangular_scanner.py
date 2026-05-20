"""
三角套利扫描器

原理:
  在同一交易所内，利用三个交易对之间的定价不一致获利。
  例如: USDT → BTC → ETH → USDT
  如果 (1/ask_BTC_USDT) * (bid_ETH_BTC) * (bid_ETH_USDT 的倒数) > 1，存在正向套利。

实现:
  1. 拉取交易所所有 ticker (bid/ask)
  2. 构建有向图: 节点=币种, 边=交易对(含手续费)
  3. 检测负权回路 (等价于乘积 > 1 的环)
  4. 按净利润排序输出

性能优化:
  - 只扫描 USDT/BTC/ETH/BNB 为中间节点的三角路径 (覆盖 95%+ 机会)
  - 扣除 taker 手续费后的净利润
  - 考虑最小下单量和深度
"""
import asyncio
import time
import math
import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone

import ccxt.async_support as ccxt_async

logger = logging.getLogger(__name__)


@dataclass
class TriangularPath:
    """三角套利路径"""
    exchange: str
    path: List[str]              # 如 ["USDT", "BTC", "ETH", "USDT"]
    pairs: List[str]             # 如 ["BTC/USDT", "ETH/BTC", "ETH/USDT"]
    actions: List[str]           # 如 ["buy", "buy", "sell"]
    rates: List[float]           # 每步的有效汇率
    gross_profit_pct: float      # 毛利润 %
    net_profit_pct: float        # 扣费后净利润 %
    min_volume_usdt: float       # 最小可执行金额 (USDT)
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "exchange": self.exchange,
            "path": " → ".join(self.path),
            "pairs": self.pairs,
            "actions": self.actions,
            "gross_profit_pct": round(self.gross_profit_pct, 4),
            "net_profit_pct": round(self.net_profit_pct, 4),
            "min_volume_usdt": round(self.min_volume_usdt, 2),
            "timestamp": self.timestamp,
            "profitable": self.net_profit_pct > 0,
        }


class TriangularArbitrageScanner:
    """
    三角套利扫描器

    扫描 Binance / OKX 所内所有可能的三角路径，
    计算扣除 taker 手续费后的净利润。
    """

    # 手续费 (taker)
    FEES = {
        "binance": 0.001,   # 0.1% (BNB 抵扣后约 0.075%)
        "okx": 0.001,       # 0.1%
    }

    # 中间节点 (只扫描经过这些币种的三角)
    INTERMEDIATE_CURRENCIES = {"BTC", "ETH", "BNB", "USDT", "USDC"}

    # 起始/结束币种
    BASE_CURRENCIES = {"USDT", "USDC"}

    def __init__(
        self,
        exchange_name: str = "binance",
        min_net_profit_pct: float = 0.05,   # 最小净利润 0.05%
        min_volume_usdt: float = 100,        # 最小可执行量 $100
        max_results: int = 20,
    ):
        self.exchange_name = exchange_name
        self.min_net_profit_pct = min_net_profit_pct
        self.min_volume_usdt = min_volume_usdt
        self.max_results = max_results

        self._exchange: Optional[ccxt_async.Exchange] = None
        self._tickers: Dict[str, dict] = {}
        self._markets: Dict[str, dict] = {}
        self._last_scan: float = 0

        # 图结构: {from_currency: [(to_currency, pair_symbol, action, rate, volume)]}
        self._graph: Dict[str, List[Tuple]] = {}

    async def _get_exchange(self) -> ccxt_async.Exchange:
        """获取交易所客户端"""
        if self._exchange is None:
            if self.exchange_name == "binance":
                self._exchange = ccxt_async.binance({
                    "enableRateLimit": True,
                    "options": {"defaultType": "spot"},
                })
            elif self.exchange_name == "okx":
                self._exchange = ccxt_async.okx({
                    "enableRateLimit": True,
                    "options": {"defaultType": "spot"},
                })
            else:
                raise ValueError(f"不支持的交易所: {self.exchange_name}")
        return self._exchange

    async def scan(self) -> List[TriangularPath]:
        """
        执行一次完整扫描

        Returns:
            按净利润降序排列的三角套利路径列表
        """
        exchange = await self._get_exchange()

        # 1. 加载市场和行情
        await exchange.load_markets()
        self._markets = exchange.markets
        self._tickers = await exchange.fetch_tickers()

        # 2. 构建有向图
        self._build_graph()

        # 3. 扫描所有三角路径
        opportunities = self._find_triangular_paths()

        # 4. 排序
        opportunities.sort(key=lambda x: x.net_profit_pct, reverse=True)

        self._last_scan = time.time()
        logger.info(
            f"🔺 三角套利扫描完成 [{self.exchange_name}] | "
            f"交易对: {len(self._tickers)} | "
            f"发现机会: {len(opportunities)}"
        )

        return opportunities[:self.max_results]

    def _build_graph(self):
        """
        从 ticker 数据构建有向图

        每条边表示一个可执行的交易:
        - buy: 用 quote 买 base → edge: quote → base, rate = 1/ask
        - sell: 卖 base 得 quote → edge: base → quote, rate = bid
        """
        self._graph.clear()

        for symbol, ticker in self._tickers.items():
            if symbol not in self._markets:
                continue

            market = self._markets[symbol]
            base = market.get("base", "")
            quote = market.get("quote", "")

            if not base or not quote:
                continue

            # 过滤: 至少一端是中间节点
            if base not in self.INTERMEDIATE_CURRENCIES and quote not in self.INTERMEDIATE_CURRENCIES:
                continue

            bid = ticker.get("bid")
            ask = ticker.get("ask")
            bid_volume = ticker.get("bidVolume", 0) or 0
            ask_volume = ticker.get("askVolume", 0) or 0
            base_volume = ticker.get("baseVolume", 0) or 0

            if not bid or not ask or bid <= 0 or ask <= 0:
                continue

            # 估算可用深度 (USDT 计价)
            price_mid = (bid + ask) / 2
            # 保守估计: 盘口量 * 价格
            volume_usdt = min(bid_volume, ask_volume) * price_mid if bid_volume and ask_volume else base_volume * price_mid * 0.01

            # Buy edge: quote → base (用 quote 买 base, 花费 ask 价格)
            buy_rate = 1.0 / ask
            if quote not in self._graph:
                self._graph[quote] = []
            self._graph[quote].append((base, symbol, "buy", buy_rate, volume_usdt))

            # Sell edge: base → quote (卖 base 得 quote, 得到 bid 价格)
            sell_rate = bid
            if base not in self._graph:
                self._graph[base] = []
            self._graph[base].append((quote, symbol, "sell", sell_rate, volume_usdt))

    def _find_triangular_paths(self) -> List[TriangularPath]:
        """
        遍历所有三步路径: start → mid → end → start
        只搜索以 USDT/USDC 为起点和终点的三角
        """
        opportunities: List[TriangularPath] = []
        fee_multiplier = (1 - self.FEES[self.exchange_name]) ** 3  # 三次交易手续费

        for start_currency in self.BASE_CURRENCIES:
            if start_currency not in self._graph:
                continue

            # 第一步: start → mid1
            for mid1, pair1, action1, rate1, vol1 in self._graph[start_currency]:
                if mid1 == start_currency:
                    continue

                # 第二步: mid1 → mid2
                if mid1 not in self._graph:
                    continue

                for mid2, pair2, action2, rate2, vol2 in self._graph[mid1]:
                    if mid2 == start_currency or mid2 == mid1:
                        continue

                    # 第三步: mid2 → start (回到起点)
                    if mid2 not in self._graph:
                        continue

                    for end, pair3, action3, rate3, vol3 in self._graph[mid2]:
                        if end != start_currency:
                            continue

                        # 避免重复对 (同一个 pair 用两次)
                        pairs = [pair1, pair2, pair3]
                        if len(set(pairs)) < 3:
                            continue

                        # 计算总乘积
                        gross_product = rate1 * rate2 * rate3
                        net_product = gross_product * fee_multiplier

                        gross_profit_pct = (gross_product - 1) * 100
                        net_profit_pct = (net_product - 1) * 100

                        # 只保留净利润为正的
                        if net_profit_pct < self.min_net_profit_pct:
                            continue

                        # 估算最小可执行量
                        min_vol = min(vol1, vol2, vol3)
                        if min_vol < self.min_volume_usdt:
                            continue

                        path = TriangularPath(
                            exchange=self.exchange_name,
                            path=[start_currency, mid1, mid2, start_currency],
                            pairs=pairs,
                            actions=[action1, action2, action3],
                            rates=[rate1, rate2, rate3],
                            gross_profit_pct=gross_profit_pct,
                            net_profit_pct=net_profit_pct,
                            min_volume_usdt=min_vol,
                            timestamp=time.time(),
                        )
                        opportunities.append(path)

        return opportunities

    async def get_summary(self) -> dict:
        """获取扫描摘要"""
        opportunities = await self.scan()

        profitable = [o for o in opportunities if o.net_profit_pct > 0]
        high_profit = [o for o in opportunities if o.net_profit_pct > 0.1]

        return {
            "exchange": self.exchange_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_pairs_scanned": len(self._tickers),
            "total_opportunities": len(opportunities),
            "profitable_paths": len(profitable),
            "high_profit_paths": len(high_profit),
            "best_opportunity": opportunities[0].to_dict() if opportunities else None,
            "top_opportunities": [o.to_dict() for o in opportunities[:10]],
            "fee_rate_pct": self.FEES[self.exchange_name] * 100,
            "scan_time": self._last_scan,
        }

    async def close(self):
        """关闭交易所连接"""
        if self._exchange:
            await self._exchange.close()
            self._exchange = None


# 全局实例
_scanners: Dict[str, TriangularArbitrageScanner] = {}


def get_triangular_scanner(exchange: str = "binance") -> TriangularArbitrageScanner:
    """获取全局三角套利扫描器"""
    global _scanners
    if exchange not in _scanners:
        _scanners[exchange] = TriangularArbitrageScanner(
            exchange_name=exchange,
            min_net_profit_pct=0.02,  # 0.02% 最小净利润
        )
    return _scanners[exchange]
