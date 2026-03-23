"""
策略运行器 - 执行策略交易信号
"""

import logging
from datetime import datetime
from typing import Optional, Dict
from decimal import Decimal

from engine.order.order_manager import OrderManager
from engine.risk.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class StrategyRunner:
    """
    策略运行器
    
    负责执行策略产生的交易信号
    
    功能：
    - 信号验证
    - 仓位计算
    - 订单提交
    - 执行跟踪
    """
    
    def __init__(
        self,
        order_manager: OrderManager,
        risk_manager: RiskManager,
        default_position_size: float = 0.1,
    ):
        """
        Args:
            order_manager: 订单管理器
            risk_manager: 风险管理器
            default_position_size: 默认仓位比例 (0-1)
        """
        self.order_manager = order_manager
        self.risk_manager = risk_manager
        self.default_position_size = default_position_size
        
        # 策略统计
        self._strategy_signals: Dict[str, int] = {}  # strategy_id -> signal count
        self._strategy_pnl: Dict[str, Decimal] = {}  # strategy_id -> pnl
    
    async def execute_signal(
        self,
        strategy_id: str,
        symbol: str,
        side: str,
        signal_strength: float = 1.0,
        price: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
    ) -> bool:
        """
        执行策略信号
        
        Args:
            strategy_id: 策略 ID
            symbol: 交易对
            side: 买卖方向 ('buy' or 'sell')
            signal_strength: 信号强度 (0-1)
            price: 价格（可选，用于计算仓位）
            stop_loss: 止损价
            take_profit: 止盈价
            
        Returns:
            bool: 是否成功执行
        """
        # 记录信号
        self._strategy_signals[strategy_id] = self._strategy_signals.get(strategy_id, 0) + 1
        
        # 1. 风险检查
        risk_result = self.risk_manager.check_trade_permission(
            symbol=symbol,
            order_value=self._calculate_order_value(symbol, signal_strength),
            current_positions={},  # TODO: 从数据库获取
            current_equity=float(self.risk_manager.initial_capital),
        )
        
        if not risk_result.can_trade:
            logger.warning(f"策略 {strategy_id} 信号被风控阻止：{risk_result.reasons}")
            return False
        
        # 2. 计算订单大小
        quantity = self._calculate_quantity(
            symbol=symbol,
            signal_strength=signal_strength,
            price=price,
        )
        
        if quantity <= 0:
            logger.error(f"计算订单数量失败：{symbol}")
            return False
        
        # 3. 确定订单类型
        order_type = "market"  # 默认市价单
        if price and side == 'buy':
            # 买入时使用限价单，价格略高于市价
            order_type = "limit"
        
        # 4. 创建并执行订单
        order = self.order_manager.create_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            strategy_id=strategy_id,
        )
        
        logger.info(
            f"策略 {strategy_id} 执行信号：{side.upper()} {quantity} {symbol} "
            f"@{price or 'MARKET'}"
        )
        
        # TODO: 实际执行需要调用 ExecutionEngine
        # 这里只是记录
        
        return True
    
    def _calculate_order_value(
        self,
        symbol: str,
        signal_strength: float
    ) -> float:
        """
        计算订单价值
        
        Args:
            symbol: 交易对
            signal_strength: 信号强度
            
        Returns:
            float: 订单价值 (USDT)
        """
        base_value = float(self.risk_manager.initial_capital) * self.default_position_size
        return base_value * signal_strength
    
    def _calculate_quantity(
        self,
        symbol: str,
        signal_strength: float,
        price: Optional[Decimal] = None,
    ) -> Decimal:
        """
        计算订单数量
        
        Args:
            symbol: 交易对
            signal_strength: 信号强度
            price: 价格
            
        Returns:
            Decimal: 订单数量
        """
        # 默认价格（如果未提供）
        if price is None:
            # 根据交易对设置默认价格
            default_prices = {
                'BTCUSDT': Decimal('50000'),
                'ETHUSDT': Decimal('3000'),
                'BNBUSDT': Decimal('400'),
            }
            price = default_prices.get(symbol, Decimal('100'))
        
        # 计算订单价值
        order_value = Decimal(str(self._calculate_order_value(symbol, signal_strength)))
        
        # 计算数量
        quantity = order_value / price
        
        # 根据交易对精度调整
        quantity = self._adjust_quantity_precision(symbol, quantity)
        
        return quantity
    
    def _adjust_quantity_precision(
        self,
        symbol: str,
        quantity: Decimal
    ) -> Decimal:
        """
        调整数量精度
        
        Args:
            symbol: 交易对
            quantity: 数量
            
        Returns:
            Decimal: 调整后的数量
        """
        # 不同交易对的精度不同
        precision_map = {
            'BTCUSDT': 6,   # BTC 精确到 0.000001
            'ETHUSDT': 5,   # ETH 精确到 0.00001
            'BNBUSDT': 5,
        }
        
        precision = precision_map.get(symbol, 3)
        quantize_str = '0.' + '0' * precision
        
        return quantity.quantize(Decimal(quantize_str))
    
    def get_strategy_statistics(self, strategy_id: Optional[str] = None) -> dict:
        """
        获取策略统计
        
        Args:
            strategy_id: 策略 ID（可选，不传则返回所有）
            
        Returns:
            dict: 统计数据
        """
        if strategy_id:
            return {
                "strategy_id": strategy_id,
                "signal_count": self._strategy_signals.get(strategy_id, 0),
                "pnl": str(self._strategy_pnl.get(strategy_id, Decimal('0'))),
            }
        else:
            return {
                sid: {
                    "signal_count": count,
                    "pnl": str(self._strategy_pnl.get(sid, Decimal('0'))),
                }
                for sid, count in self._strategy_signals.items()
            }
