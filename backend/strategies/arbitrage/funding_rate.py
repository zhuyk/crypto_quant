"""
资金费率套利策略

资金费率套利原理：
1. 永续合约通过资金费率机制锚定现货价格
2. 当费率为正时：多头支付空头 → 做空合约 + 做多现货赚取费率
3. 当费率为负时：空头支付多头 → 做多合约 + 做空现货赚取费率
4. 风险对冲：现货和合约方向相反，对冲价格波动风险

策略类型：
- 单交易所资金费率套利
- 跨交易所资金费率套利
- 三角资金费率套利
"""

from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import asyncio
from datetime import datetime, timedelta

from strategies.base import BaseStrategy, Signal, SignalType
from app.core.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class FundingRateArbitrage(BaseStrategy):
    """
    资金费率套利策略
    
    核心逻辑：
    1. 监控多个交易对的资金费率
    2. 当费率超过阈值时开仓
    3. 现货和合约对冲，赚取费率收益
    4. 定期结算并重新平衡
    """
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        
        self.strategy_id = "funding_rate_arbitrage"
        self.strategy_name = "资金费率套利"
        self.description = "通过永续合约资金费率进行套利，对冲价格风险"
        
        # 策略参数
        self.params = config or {
            "min_funding_rate": 0.0001,  # 最小费率阈值 (0.01%)
            "max_funding_rate": 0.001,   # 最大费率阈值 (0.1%)
            "position_size_usdt": 1000,  # 单笔仓位大小 (USDT)
            "max_positions": 5,          # 最大同时持仓数
            "rebalance_interval_hours": 8,  # 重新平衡间隔
            "stop_loss_funding_rate": -0.0005,  # 止损费率
            "exchanges": ["binance", "bybit", "okx"],  # 支持的交易所
        }
        
        # 状态
        self.positions = {}  # 当前持仓
        self.funding_rates = {}  # 最新费率
        self.last_rebalance = None
        
    async def initialize(self):
        """初始化策略"""
        logger.info(f"初始化 {self.strategy_name} 策略")
        await self._load_funding_rates()
        
    async def _load_funding_rates(self):
        """加载所有交易对的资金费率"""
        try:
            # 从交易所获取资金费率
            for exchange in self.params["exchanges"]:
                rates = await self._fetch_funding_rates(exchange)
                self.funding_rates[exchange] = rates
                logger.debug(f"交易所 {exchange} 费率数据：{len(rates)} 个交易对")
        except Exception as e:
            logger.error(f"加载资金费率失败：{e}")
    
    async def _fetch_funding_rates(self, exchange: str) -> Dict:
        """
        获取交易所资金费率
        
        Args:
            exchange: 交易所名称
            
        Returns:
            {symbol: {funding_rate, next_funding_time, mark_price, index_price}}
        """
        # TODO: 实现交易所 API 调用
        # 这里使用模拟数据
        return {
            "BTCUSDT": {
                "funding_rate": 0.0001,
                "next_funding_time": datetime.now() + timedelta(hours=8),
                "mark_price": 68800,
                "index_price": 68795,
            },
            "ETHUSDT": {
                "funding_rate": 0.00015,
                "next_funding_time": datetime.now() + timedelta(hours=8),
                "mark_price": 3450,
                "index_price": 3448,
            },
        }
    
    async def generate_signals(self) -> List[Signal]:
        """
        生成交易信号
        
        Returns:
            交易信号列表
        """
        signals = []
        
        # 扫描所有交易对
        for exchange, rates in self.funding_rates.items():
            for symbol, data in rates.items():
                funding_rate = Decimal(str(data["funding_rate"]))
                
                # 检查是否超过阈值
                if funding_rate >= Decimal(str(self.params["min_funding_rate"])):
                    # 正费率：做空合约 + 做多现货
                    signal = self._create_signal(
                        symbol=symbol,
                        exchange=exchange,
                        signal_type=SignalType.SHORT,
                        funding_rate=funding_rate,
                        reason=f"正费率套利：{funding_rate:.4%}"
                    )
                    signals.append(signal)
                    
                elif funding_rate <= Decimal(str(self.params["stop_loss_funding_rate"])):
                    # 负费率：做多合约 + 做空现货
                    signal = self._create_signal(
                        symbol=symbol,
                        exchange=exchange,
                        signal_type=SignalType.LONG,
                        funding_rate=funding_rate,
                        reason=f"负费率套利：{funding_rate:.4%}"
                    )
                    signals.append(signal)
        
        return signals
    
    def _create_signal(self, symbol: str, exchange: str, signal_type: SignalType, 
                      funding_rate: Decimal, reason: str) -> Signal:
        """创建交易信号"""
        return Signal(
            strategy_id=self.strategy_id,
            symbol=symbol,
            exchange=exchange,
            signal_type=signal_type,
            entry_price=Decimal(str(self.funding_rates[exchange][symbol]["mark_price"])),
            quantity=Decimal(str(self.params["position_size_usdt"])) / Decimal(str(self.funding_rates[exchange][symbol]["mark_price"])),
            stop_loss=None,  # 对冲策略，无需传统止损
            take_profit=None,
            metadata={
                "funding_rate": float(funding_rate),
                "annual_return": float(funding_rate * 3 * 365),  # 年化收益率估算
                "reason": reason,
                "hedge_type": "spot_perp",  # 现货 - 永续对冲
            }
        )
    
    async def execute_signal(self, signal: Signal) -> bool:
        """
        执行交易信号
        
        Args:
            signal: 交易信号
            
        Returns:
            执行是否成功
        """
        try:
            logger.info(f"执行资金费率套利信号：{signal.symbol} {signal.signal_type.name}")
            
            # 1. 开现货仓位
            spot_success = await self._open_spot_position(signal)
            if not spot_success:
                logger.error("现货开仓失败")
                return False
            
            # 2. 开合约仓位（反向）
            perp_success = await self._open_perp_position(signal)
            if not perp_success:
                logger.error("合约开仓失败，需平掉现货仓位")
                await self._close_spot_position(signal)
                return False
            
            # 3. 记录持仓
            self.positions[signal.symbol] = {
                "signal": signal,
                "spot_position": "long" if signal.signal_type == SignalType.SHORT else "short",
                "perp_position": "short" if signal.signal_type == SignalType.SHORT else "long",
                "open_time": datetime.now(),
                "total_funding_earned": Decimal("0"),
            }
            
            logger.info(f"资金费率套利开仓成功：{signal.symbol}")
            return True
            
        except Exception as e:
            logger.error(f"执行信号失败：{e}")
            return False
    
    async def _open_spot_position(self, signal: Signal) -> bool:
        """开现货仓位"""
        # TODO: 实现现货交易
        logger.debug(f"现货开仓：{signal.symbol} {signal.signal_type.name}")
        return True
    
    async def _open_perp_position(self, signal: Signal) -> bool:
        """开合约仓位"""
        # TODO: 实现合约交易
        logger.debug(f"合约开仓：{signal.symbol} {'SHORT' if signal.signal_type == SignalType.SHORT else 'LONG'}")
        return True
    
    async def _close_spot_position(self, signal: Signal) -> bool:
        """平现货仓位"""
        # TODO: 实现现货平仓
        return True
    
    async def _close_perp_position(self, signal: Signal) -> bool:
        """平合约仓位"""
        # TODO: 实现合约平仓
        return True
    
    async def monitor_positions(self):
        """监控持仓，处理资金费率和重新平衡"""
        for symbol, position in self.positions.items():
            try:
                # 1. 检查当前费率是否反转
                current_rate = await self._get_current_funding_rate(symbol)
                
                # 2. 如果费率不利，考虑平仓
                if self._should_close_position(position, current_rate):
                    await self.close_position(symbol)
                    continue
                
                # 3. 累计资金费
                funding_payment = self._calculate_funding_payment(position, current_rate)
                position["total_funding_earned"] += funding_payment
                
                # 4. 检查是否需要重新平衡
                if self._should_rebalance(position):
                    await self.rebalance_position(symbol)
                    
            except Exception as e:
                logger.error(f"监控持仓 {symbol} 失败：{e}")
    
    def _should_close_position(self, position: Dict, current_rate: Decimal) -> bool:
        """判断是否应该平仓"""
        signal = position["signal"]
        
        # 费率反转且超过止损阈值
        if signal.signal_type == SignalType.SHORT and current_rate < Decimal(str(self.params["stop_loss_funding_rate"])):
            return True
        if signal.signal_type == SignalType.LONG and current_rate > Decimal(str(self.params["stop_loss_funding_rate"])):
            return True
        
        return False
    
    def _calculate_funding_payment(self, position: Dict, funding_rate: Decimal) -> Decimal:
        """计算资金费收入"""
        signal = position["signal"]
        position_value = signal.quantity * signal.entry_price
        
        # 多头支付空头
        if position["perp_position"] == "short":
            return position_value * funding_rate
        else:
            return -position_value * funding_rate
    
    def _should_rebalance(self, position: Dict) -> bool:
        """判断是否需要重新平衡"""
        # 检查时间间隔
        if self.last_rebalance is None:
            return True
        
        time_since_rebalance = datetime.now() - self.last_rebalance
        return time_since_rebalance >= timedelta(hours=self.params["rebalance_interval_hours"])
    
    async def rebalance_position(self, symbol: str):
        """重新平衡仓位"""
        logger.info(f"重新平衡仓位：{symbol}")
        # TODO: 实现重新平衡逻辑
        self.last_rebalance = datetime.now()
    
    async def close_position(self, symbol: str) -> bool:
        """平仓"""
        if symbol not in self.positions:
            return False
        
        position = self.positions[symbol]
        signal = position["signal"]
        
        logger.info(f"平仓资金费率套利：{symbol}, 累计费率收益：{position['total_funding_earned']}")
        
        # 1. 平合约仓位
        await self._close_perp_position(signal)
        
        # 2. 平现货仓位
        await self._close_spot_position(signal)
        
        # 3. 移除持仓记录
        del self.positions[symbol]
        
        return True
    
    async def get_status(self) -> Dict:
        """获取策略状态"""
        total_pnl = sum(pos["total_funding_earned"] for pos in self.positions.values())
        
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "active_positions": len(self.positions),
            "max_positions": self.params["max_positions"],
            "total_funding_earned": float(total_pnl),
            "positions": [
                {
                    "symbol": symbol,
                    "side": pos["signal"].signal_type.name,
                    "funding_rate": pos["signal"].metadata["funding_rate"],
                    "earned": float(pos["total_funding_earned"]),
                }
                for symbol, pos in self.positions.items()
            ],
        }
    
    def get_risk_metrics(self) -> Dict:
        """获取风险指标"""
        return {
            "strategy_type": "market_neutral",  # 市场中性
            "delta_exposure": 0,  # Delta 对冲
            "funding_rate_risk": "medium",
            "liquidation_risk": "low",  # 对冲策略，清算风险低
            "basis_risk": "low",  # 基差风险
        }


# 策略工厂
def create_strategy(config: Dict = None) -> FundingRateArbitrage:
    """创建资金费率套利策略实例"""
    return FundingRateArbitrage(config)
