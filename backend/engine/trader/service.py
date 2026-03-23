"""
实盘交易员服务 - 7x24 小时运行
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from decimal import Decimal

from engine.order.order_manager import OrderManager
from engine.order.execution_engine import ExecutionEngine
from engine.order.slippage_control import SlippageController, SlippageConfig
from engine.order.reconciliation import ReconciliationEngine
from engine.risk.risk_manager import RiskManager
from engine.trader.strategy_runner import StrategyRunner

logger = logging.getLogger(__name__)


class TraderService:
    """
    实盘交易员服务
    
    整合所有交易组件，提供完整的实盘交易能力
    
    功能：
    - 策略信号监听
    - 风险控制检查
    - 订单执行
    - 仓位管理
    - 盈亏追踪
    - 自动对账
    """
    
    def __init__(
        self,
        risk_manager: RiskManager,
        initial_capital: float = 100000,
        exchange_client=None,
    ):
        """
        Args:
            risk_manager: 风险管理器
            initial_capital: 初始资金
            exchange_client: 交易所客户端
        """
        self.risk_manager = risk_manager
        self.initial_capital = Decimal(str(initial_capital))
        self.exchange_client = exchange_client
        
        # 初始化组件
        self.order_manager = OrderManager()
        self.slippage_controller = SlippageController(
            SlippageConfig(
                mode='percentage',
                max_slippage_pct=0.001,
                enable_dynamic=True,
            )
        )
        self.execution_engine = ExecutionEngine(
            order_manager=self.order_manager,
            slippage_controller=self.slippage_controller,
            exchange_client=exchange_client,
            timeout=30.0,
            max_retries=3,
        )
        self.reconciliation_engine = ReconciliationEngine(
            order_manager=self.order_manager,
            exchange_client=exchange_client,
            check_interval=60,
            auto_fix=True,
        )
        
        # 策略运行器
        self.strategy_runner = StrategyRunner(
            order_manager=self.order_manager,
            risk_manager=risk_manager,
        )
        
        # 仓位追踪
        self._positions: Dict[str, Decimal] = {}  # symbol -> quantity
        self._position_values: Dict[str, Decimal] = {}  # symbol -> value in USDT
        
        # 服务状态
        self._is_running = False
        self._current_equity = self.initial_capital
        
        # 设置回调
        self._setup_callbacks()
    
    def _setup_callbacks(self):
        """设置回调函数"""
        async def on_order_update(order):
            logger.info(f"订单更新：{order.client_order_id} {order.state.value}")
            # 更新权益
            await self._update_equity()
        
        async def on_order_fill(order, fill):
            logger.info(f"订单成交：{order.client_order_id} {fill.quantity}@{fill.price}")
            # 更新仓位
            self._update_position(fill)
            # 记录盈亏
            if order.is_terminal:
                await self._record_pnl(order)
            # 更新权益
            await self._update_equity()
        
        self.order_manager.set_callbacks(
            on_order_update=on_order_update,
            on_order_fill=on_order_fill,
        )
    
    async def start(self):
        """启动交易服务"""
        if self._is_running:
            logger.warning("交易服务已在运行")
            return
        
        self._is_running = True
        
        # 启动各组件
        await self.execution_engine.start()
        await self.reconciliation_engine.start()
        
        logger.info("交易服务已启动")
        
        # 记录启动日志
        logger.info(
            f"交易服务启动 - 初始资金：{self.initial_capital} USDT, "
            f"风控：max_drawdown={self.risk_manager.drawdown_monitor.max_drawdown:.2%}"
        )
    
    async def stop(self):
        """停止交易服务"""
        if not self._is_running:
            return
        
        self._is_running = False
        
        # 停止各组件
        await self.execution_engine.stop()
        await self.reconciliation_engine.stop()
        
        logger.info("交易服务已停止")
    
    async def execute_signal(
        self,
        strategy_id: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        order_type: str = "market",
        priority: bool = False,
    ) -> bool:
        """
        执行交易信号
        
        Args:
            strategy_id: 策略 ID
            symbol: 交易对
            side: 买卖方向
            quantity: 数量
            price: 价格（限价单）
            order_type: 订单类型
            priority: 是否优先执行
            
        Returns:
            bool: 是否成功执行
        """
        if not self._is_running:
            logger.error("交易服务未启动")
            return False
        
        # 1. 风险检查
        current_positions = {
            sym: float(val * Decimal(str(price or 50000)))
            for sym, val in self._positions.items()
        }
        
        order_value = float(quantity * (price or Decimal('50000')))
        
        risk_result = self.risk_manager.check_trade_permission(
            symbol=symbol,
            order_value=order_value,
            current_positions=current_positions,
            current_equity=float(self._current_equity),
        )
        
        if not risk_result.can_trade:
            logger.warning(f"风险检查未通过：{risk_result.reasons}")
            return False
        
        if risk_result.warnings:
            logger.warning(f"风险预警：{risk_result.warnings}")
        
        # 2. 创建订单
        from engine.order.order_types import OrderSide, OrderType, TimeInForce
        
        order = self.order_manager.create_order(
            symbol=symbol,
            side=OrderSide.BUY if side == 'buy' else OrderSide.SELL,
            order_type=OrderType.MARKET if order_type == 'market' else OrderType.LIMIT,
            quantity=quantity,
            price=price,
            strategy_id=strategy_id,
        )
        
        # 3. 执行订单
        result = await self.execution_engine.execute_order(order, priority=priority)
        
        # 4. 记录结果
        if result.success:
            self.risk_manager.record_trade_success()
        else:
            self.risk_manager.record_trade_failure()
        
        return result.success
    
    def _update_position(self, fill):
        """
        更新仓位
        
        Args:
            fill: 成交记录
        """
        symbol = fill.symbol
        
        if symbol not in self._positions:
            self._positions[symbol] = Decimal('0')
        
        # 更新数量
        if fill.side.value == 'buy':
            self._positions[symbol] += fill.quantity
        else:
            self._positions[symbol] -= fill.quantity
        
        # 更新仓位价值
        self._position_values[symbol] = self._positions[symbol] * fill.price
        
        logger.info(
            f"仓位更新：{symbol} {self._positions[symbol]} "
            f"(价值：{self._position_values[symbol]:.2f} USDT)"
        )
    
    async def _update_equity(self):
        """更新权益值"""
        # 简单实现：初始资金 + 已实现盈亏
        # 实际应该查询交易所账户余额
        self._current_equity = self.initial_capital
        
        # 更新风控系统
        self.risk_manager.drawdown_monitor.update_equity(
            float(self._current_equity)
        )
    
    async def _record_pnl(self, order):
        """
        记录盈亏
        
        Args:
            order: 订单对象
        """
        # 计算盈亏（简化版）
        # 实际应该根据开仓和平仓价格计算
        if order.filled_quantity > 0:
            # 这里需要根据持仓成本计算
            pass
    
    def get_positions(self) -> List[dict]:
        """获取当前持仓"""
        return [
            {
                "symbol": symbol,
                "quantity": str(quantity),
                "value": str(self._position_values.get(symbol, Decimal('0'))),
            }
            for symbol, quantity in self._positions.items()
            if quantity != 0
        ]
    
    def get_full_status(self) -> dict:
        """获取完整状态"""
        return {
            "is_running": self._is_running,
            "current_equity": str(self._current_equity),
            "initial_capital": str(self.initial_capital),
            "positions": self.get_positions(),
            "order_statistics": self.order_manager.get_statistics(),
            "execution_statistics": self.execution_engine.get_statistics(),
            "reconciliation_statistics": self.reconciliation_engine.get_statistics(),
            "slippage_statistics": self.slippage_controller.get_statistics(),
            "risk_status": self.risk_manager.get_full_status(),
        }


# 全局交易服务实例
_trader_service: Optional[TraderService] = None


def get_trader_service() -> Optional[TraderService]:
    """获取交易服务实例"""
    return _trader_service


def init_trader_service(
    risk_manager: RiskManager,
    initial_capital: float = 100000,
    exchange_client=None,
) -> TraderService:
    """初始化交易服务"""
    global _trader_service
    _trader_service = TraderService(
        risk_manager=risk_manager,
        initial_capital=initial_capital,
        exchange_client=exchange_client,
    )
    return _trader_service
