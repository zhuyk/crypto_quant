"""
期现基差套利 (Spot-Futures Basis Arbitrage)

原理:
  当交割合约价格 > 现货价格（正溢价/contango）时：
  - 现货买入 + 交割合约做空
  - 到期时两者价格收敛，无风险获利 = 基差
  
  当交割合约价格 < 现货价格（负溢价/backwardation）时：
  - 反向操作（较少见）

关键指标:
  - Basis = 期货价格 - 现货价格
  - Basis Rate = Basis / 现货价格
  - Annualized Basis = Basis Rate * (365 / 剩余天数)

适用:
  - Binance 季度交割合约 (BTCUSD_250627 等)
  - OKX 交割合约
  
风险:
  - 极低（到期收敛是确定性事件）
  - 主要风险: 保证金不足导致强平、交易所风险
"""
import asyncio
import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import ccxt.async_support as ccxt_async

logger = logging.getLogger(__name__)


@dataclass
class BasisOpportunity:
    """期现基差套利机会"""
    symbol: str                   # 基础币种 (如 BTC)
    exchange: str
    spot_price: float             # 现货价格
    futures_price: float          # 期货价格
    futures_symbol: str           # 期货合约代码
    expiry_date: str              # 到期日 (ISO format)
    days_to_expiry: int           # 剩余天数
    basis: float                  # 基差 (期货 - 现货)
    basis_rate: float             # 基差率 (basis / spot)
    annualized_rate: float        # 年化基差率
    net_annualized_rate: float    # 扣费后年化
    direction: str                # "contango" (正溢价) / "backwardation" (负溢价)
    risk_score: float             # 风险评分 0-1
    recommended_size_pct: float   # 建议仓位占比
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "spot_price": round(self.spot_price, 2),
            "futures_price": round(self.futures_price, 2),
            "futures_symbol": self.futures_symbol,
            "expiry_date": self.expiry_date,
            "days_to_expiry": self.days_to_expiry,
            "basis": round(self.basis, 4),
            "basis_rate_pct": round(self.basis_rate * 100, 4),
            "annualized_rate_pct": round(self.annualized_rate * 100, 2),
            "net_annualized_rate_pct": round(self.net_annualized_rate * 100, 2),
            "direction": self.direction,
            "risk_score": round(self.risk_score, 2),
            "recommended_size_pct": round(self.recommended_size_pct, 1),
            "timestamp": self.timestamp,
            "profitable": self.net_annualized_rate > 0.05,  # 年化 > 5% 视为可行
        }


class BasisArbitrageScanner:
    """
    期现基差套利扫描器
    
    功能:
    - 扫描 Binance/OKX 所有交割合约
    - 计算基差、基差率、年化收益
    - 扣除手续费后的净收益
    - 风险评估和仓位建议
    """

    # 手续费假设
    FEES = {
        "binance": {
            "spot_taker": 0.001,      # 现货 taker 0.1%
            "futures_taker": 0.0004,  # 交割合约 taker 0.04%
            "futures_maker": 0.0002,  # 交割合约 maker 0.02%
        },
        "okx": {
            "spot_taker": 0.001,
            "futures_taker": 0.0005,
            "futures_maker": 0.0002,
        },
    }

    # 最小年化阈值 (低于此值不报告)
    MIN_ANNUALIZED_RATE = 0.03  # 3%

    def __init__(
        self,
        exchanges: Optional[List[str]] = None,
        min_annualized_rate: float = 0.05,   # 5% 最小年化
        max_days_to_expiry: int = 120,        # 最大 120 天到期
        min_days_to_expiry: int = 3,          # 最少 3 天到期 (避免临近交割)
        symbols_filter: Optional[List[str]] = None,
        max_results: int = 20,
    ):
        self.exchange_names = exchanges or ["binance", "okx"]
        self.min_annualized_rate = min_annualized_rate
        self.max_days_to_expiry = max_days_to_expiry
        self.min_days_to_expiry = min_days_to_expiry
        self.symbols_filter = symbols_filter
        self.max_results = max_results

        self._exchanges: Dict[str, ccxt_async.Exchange] = {}
        self._last_scan: float = 0

    async def _get_exchange(self, name: str) -> ccxt_async.Exchange:
        """获取交易所客户端"""
        if name not in self._exchanges:
            if name == "binance":
                self._exchanges[name] = ccxt_async.binance({
                    "enableRateLimit": True,
                    "options": {"defaultType": "delivery"},  # 交割合约
                })
            elif name == "okx":
                self._exchanges[name] = ccxt_async.okx({
                    "enableRateLimit": True,
                    "options": {"defaultType": "future"},  # OKX 交割
                })
            else:
                raise ValueError(f"不支持的交易所: {name}")
        return self._exchanges[name]

    async def scan(self) -> List[BasisOpportunity]:
        """
        扫描所有交割合约的基差套利机会
        
        Returns:
            按年化收益降序排列的机会列表
        """
        all_opportunities: List[BasisOpportunity] = []

        tasks = [self._scan_exchange(name) for name in self.exchange_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"扫描 {self.exchange_names[i]} 失败: {result}")
            else:
                all_opportunities.extend(result)

        # 按净年化收益排序
        all_opportunities.sort(key=lambda x: x.net_annualized_rate, reverse=True)

        self._last_scan = time.time()
        logger.info(
            f"📈 期现基差扫描完成 | 交易所: {self.exchange_names} | "
            f"发现机会: {len(all_opportunities)}"
        )

        return all_opportunities[:self.max_results]

    async def _scan_exchange(self, exchange_name: str) -> List[BasisOpportunity]:
        """扫描单个交易所的交割合约"""
        opportunities: List[BasisOpportunity] = []

        try:
            exchange = await self._get_exchange(exchange_name)
            await exchange.load_markets()

            # 分离现货和交割合约市场
            spot_markets = {}
            delivery_markets = {}

            for symbol, market in exchange.markets.items():
                if market.get("spot"):
                    base = market.get("base", "")
                    if base and market.get("quote") == "USDT":
                        spot_markets[base] = symbol
                elif market.get("future") and not market.get("swap"):
                    # 交割合约 (非永续)
                    base = market.get("base", "")
                    expiry = market.get("expiry")
                    if base and expiry:
                        if base not in delivery_markets:
                            delivery_markets[base] = []
                        delivery_markets[base].append({
                            "symbol": symbol,
                            "expiry": expiry,
                            "market": market,
                        })

            # 对每个有交割合约的币种，获取现货和期货价格
            for base_currency, futures_list in delivery_markets.items():
                if base_currency not in spot_markets:
                    continue

                # 过滤币种
                if self.symbols_filter and base_currency not in self.symbols_filter:
                    continue

                try:
                    # 获取现货价格
                    spot_symbol = spot_markets[base_currency]
                    spot_ticker = await exchange.fetch_ticker(spot_symbol)
                    spot_price = spot_ticker.get("last", 0)

                    if not spot_price or spot_price <= 0:
                        continue

                    # 检查每个交割合约
                    for futures_info in futures_list:
                        try:
                            opp = await self._analyze_basis(
                                exchange=exchange,
                                exchange_name=exchange_name,
                                base_currency=base_currency,
                                spot_price=spot_price,
                                futures_info=futures_info,
                            )
                            if opp:
                                opportunities.append(opp)
                        except Exception as e:
                            logger.debug(f"分析 {futures_info['symbol']} 失败: {e}")

                except Exception as e:
                    logger.debug(f"获取 {base_currency} 价格失败: {e}")

                # 限流
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"扫描 {exchange_name} 交割合约失败: {e}")
            raise

        return opportunities

    async def _analyze_basis(
        self,
        exchange: ccxt_async.Exchange,
        exchange_name: str,
        base_currency: str,
        spot_price: float,
        futures_info: dict,
    ) -> Optional[BasisOpportunity]:
        """分析单个交割合约的基差"""

        futures_symbol = futures_info["symbol"]
        expiry_ts = futures_info["expiry"]

        # 计算到期天数
        if isinstance(expiry_ts, (int, float)):
            expiry_dt = datetime.fromtimestamp(expiry_ts / 1000, tz=timezone.utc)
        else:
            expiry_dt = datetime.fromisoformat(str(expiry_ts).replace("Z", "+00:00"))

        now = datetime.now(timezone.utc)
        days_to_expiry = (expiry_dt - now).days

        # 过滤: 太近或太远的不要
        if days_to_expiry < self.min_days_to_expiry:
            return None
        if days_to_expiry > self.max_days_to_expiry:
            return None

        # 获取期货价格
        futures_ticker = await exchange.fetch_ticker(futures_symbol)
        futures_price = futures_ticker.get("last", 0)

        if not futures_price or futures_price <= 0:
            return None

        # 计算基差
        basis = futures_price - spot_price
        basis_rate = basis / spot_price

        # 方向
        if basis > 0:
            direction = "contango"
        elif basis < 0:
            direction = "backwardation"
        else:
            return None

        # 年化
        if days_to_expiry > 0:
            annualized_rate = basis_rate * (365 / days_to_expiry)
        else:
            return None

        # 扣除手续费
        fees = self.FEES.get(exchange_name, self.FEES["binance"])
        # 开仓: 现货 taker + 合约 taker
        # 平仓: 到期自动交割 (通常免手续费或极低)
        total_fee = fees["spot_taker"] + fees["futures_taker"]
        fee_annualized = total_fee * (365 / days_to_expiry)  # 摊到年化

        net_annualized_rate = abs(annualized_rate) - fee_annualized

        # 过滤低收益
        if net_annualized_rate < self.min_annualized_rate:
            return None

        # 风险评分
        risk_score = self._calculate_risk(
            base_currency, days_to_expiry, abs(basis_rate), spot_price
        )

        # 建议仓位 (风险越低允许越大仓位)
        recommended_size = max(5, min(30, (1 - risk_score) * 30))

        return BasisOpportunity(
            symbol=base_currency,
            exchange=exchange_name,
            spot_price=spot_price,
            futures_price=futures_price,
            futures_symbol=futures_symbol,
            expiry_date=expiry_dt.strftime("%Y-%m-%d"),
            days_to_expiry=days_to_expiry,
            basis=basis,
            basis_rate=basis_rate,
            annualized_rate=annualized_rate,
            net_annualized_rate=net_annualized_rate,
            direction=direction,
            risk_score=risk_score,
            recommended_size_pct=recommended_size,
            timestamp=time.time(),
        )

    def _calculate_risk(
        self,
        symbol: str,
        days_to_expiry: int,
        basis_rate: float,
        spot_price: float,
    ) -> float:
        """
        计算风险评分 (0-1, 越低越安全)
        
        因素:
        - 到期时间 (越短越安全，但 <7 天有交割风险)
        - 基差率 (过大可能说明市场极端)
        - 币种 (主流币更安全)
        - 价格级别 (高价格 = 流动性好)
        """
        risk = 0.0

        # 到期时间风险
        if days_to_expiry < 7:
            risk += 0.2  # 临近交割有意外风险
        elif days_to_expiry > 90:
            risk += 0.15  # 资金占用时间长

        # 基差率极端 (> 5% 的基差率可能说明市场定价有问题)
        if basis_rate > 0.05:
            risk += 0.3
        elif basis_rate > 0.02:
            risk += 0.1

        # 币种风险
        major_coins = {"BTC", "ETH", "BNB", "SOL"}
        mid_coins = {"XRP", "ADA", "DOGE", "AVAX", "DOT"}
        if symbol in major_coins:
            risk += 0.0
        elif symbol in mid_coins:
            risk += 0.1
        else:
            risk += 0.25

        # 流动性 (价格越高通常流动性越好)
        if spot_price < 0.1:
            risk += 0.15

        return min(risk, 1.0)

    async def get_summary(self) -> dict:
        """获取扫描摘要"""
        opportunities = await self.scan()

        contango = [o for o in opportunities if o.direction == "contango"]
        backwardation = [o for o in opportunities if o.direction == "backwardation"]

        avg_annualized = (
            sum(o.net_annualized_rate for o in opportunities) / len(opportunities)
            if opportunities else 0
        )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "exchanges": self.exchange_names,
            "total_opportunities": len(opportunities),
            "contango_count": len(contango),
            "backwardation_count": len(backwardation),
            "avg_net_annualized_pct": round(avg_annualized * 100, 2),
            "best_opportunity": opportunities[0].to_dict() if opportunities else None,
            "top_opportunities": [o.to_dict() for o in opportunities[:10]],
            "scan_time": self._last_scan,
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
_scanner: Optional[BasisArbitrageScanner] = None


def get_basis_scanner() -> BasisArbitrageScanner:
    """获取全局期现基差扫描器"""
    global _scanner
    if _scanner is None:
        _scanner = BasisArbitrageScanner(
            exchanges=["binance", "okx"],
            min_annualized_rate=0.05,
            symbols_filter=None,  # 扫描所有
        )
    return _scanner
