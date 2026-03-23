"""
订单管理器 - 管理订单生命周期
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from collections import defaultdict

from .order_types import Order, OrderState, OrderSide, OrderType, TimeInForce, OrderFill, OrderResult
from decimal import Decimal

logger = logging.getLogger(__name__)


class OrderManager:
    """
    订单管理器
    
    负责订单的创建、跟踪、更新、取消等生命周期管理
    """
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Args:
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # 订单存储
        self._orders: Dict[str, Order] = {}  # order_id -> Order
        self._client_orders: Dict[str, Order] = {}  # client_order_id -> Order
        self._fills: Dict[str, List[OrderFill]] = defaultdict(list)  # order_id -> fills
        
        # 回调函数
        self._on_order_update: Optional[Callable] = None
        self._on_order_fill: Optional[Callable] = None
        
        # 统计
        self._total_submitted = 0
        self._total_filled = 0
        self._total_cancelled = 0
        self._total_failed = 0
    
    def set_callbacks(
        self,
        on_order_update: Optional[Callable] = None,
        on_order_fill: Optional[Callable] = None
    ):
        """
        设置回调函数
        
        Args:
            on_order_update: 订单状态更新回调
            on_order_fill: 订单成交回调
        """
        self._on_order_update = on_order_update
        self._on_order_fill = on_order_fill
    
    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        strategy_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> Order:
        """
        创建订单
        
        Args:
            symbol: 交易对
            side: 买卖方向
            order_type: 订单类型
            quantity: 数量
            price: 价格（限价单）
            stop_price: 触发价格（止损/止盈）
            time_in_force: 有效期
            strategy_id: 策略 ID
            client_order_id: 客户端订单 ID
            
        Returns:
            Order: 订单对象
        """
        order = Order(
            symbol=symbol,
            side=side,
            type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            strategy_id=strategy_id,
            client_order_id=client_order_id or f"order_{datetime.utcnow().timestamp()}",
        )
        
        # 存储订单
        self._orders[order.client_order_id] = order
        self._client_orders[order.client_order_id] = order
        
        logger.info(f"订单创建：{order.client_order_id} {side.value} {quantity} {symbol}")
        
        return order
    
    def update_order_state(
        self,
        client_order_id: str,
        new_state: OrderState,
        order_id: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """
        更新订单状态
        
        Args:
            client_order_id: 客户端订单 ID
            new_state: 新状态
            order_id: 交易所订单 ID
            error_message: 错误信息
        """
        order = self._client_orders.get(client_order_id)
        if not order:
            logger.error(f"订单不存在：{client_order_id}")
            return
        
        old_state = order.state
        order.state = new_state
        order.updated_at = datetime.utcnow()
        
        if order_id:
            order.order_id = order_id
        
        if error_message:
            order.error_message = error_message
        
        # 更新统计
        if new_state == OrderState.SUBMITTED:
            self._total_submitted += 1
        elif new_state == OrderState.FILLED:
            self._total_filled += 1
        elif new_state == OrderState.CANCELLED:
            self._total_cancelled += 1
        elif new_state in [OrderState.REJECTED, OrderState.FAILED]:
            self._total_failed += 1
        
        logger.info(f"订单状态更新：{client_order_id} {old_state.value} -> {new_state.value}")
        
        # 触发回调
        if self._on_order_update:
            asyncio.create_task(self._on_order_update(order))
    
    def add_fill(self, client_order_id: str, fill: OrderFill):
        """
        添加成交记录
        
        Args:
            client_order_id: 客户端订单 ID
            fill: 成交记录
        """
        order = self._client_orders.get(client_order_id)
        if not order:
            logger.error(f"订单不存在：{client_order_id}")
            return
        
        # 更新订单成交信息
        order.filled_quantity += fill.quantity
        
        # 计算平均成交价格
        total_value = order.avg_fill_price * (order.filled_quantity - fill.quantity) + fill.price * fill.quantity
        order.avg_fill_price = total_value / order.filled_quantity
        
        # 更新状态
        if order.filled_quantity >= order.quantity:
            order.state = OrderState.FILLED
        elif order.filled_quantity > 0:
            order.state = OrderState.PARTIALLY_FILLED
        
        order.updated_at = datetime.utcnow()
        
        # 存储成交记录
        self._fills[client_order_id].append(fill)
        
        logger.info(f"订单成交：{client_order_id} {fill.quantity}@{fill.price}")
        
        # 触发回调
        if self._on_order_fill:
            asyncio.create_task(self._on_order_fill(order, fill))
    
    def cancel_order(self, client_order_id: str, reason: str = "用户取消") -> bool:
        """
        取消订单
        
        Args:
            client_order_id: 客户端订单 ID
            reason: 取消原因
            
        Returns:
            bool: 是否成功取消
        """
        order = self._client_orders.get(client_order_id)
        if not order:
            logger.error(f"订单不存在：{client_order_id}")
            return False
        
        if order.is_terminal:
            logger.warning(f"订单已是终态，无法取消：{client_order_id} {order.state.value}")
            return False
        
        order.state = OrderState.CANCELLED
        order.updated_at = datetime.utcnow()
        order.error_message = reason
        
        self._total_cancelled += 1
        
        logger.info(f"订单取消：{client_order_id} 原因：{reason}")
        
        # 触发回调
        if self._on_order_update:
            asyncio.create_task(self._on_order_update(order))
        
        return True
    
    def get_order(self, client_order_id: str) -> Optional[Order]:
        """获取订单"""
        return self._client_orders.get(client_order_id)
    
    def get_active_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        获取活跃订单
        
        Args:
            symbol: 交易对过滤（可选）
            
        Returns:
            List[Order]: 活跃订单列表
        """
        orders = [o for o in self._client_orders.values() if o.is_active]
        
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        
        return orders
    
    def get_fills(self, client_order_id: str) -> List[OrderFill]:
        """获取订单成交记录"""
        return self._fills.get(client_order_id, [])
    
    def get_statistics(self) -> dict:
        """获取订单统计"""
        return {
            "total_orders": len(self._client_orders),
            "active_orders": len(self.get_active_orders()),
            "total_submitted": self._total_submitted,
            "total_filled": self._total_filled,
            "total_cancelled": self._total_cancelled,
            "total_failed": self._total_failed,
            "fill_rate": self._total_filled / self._total_submitted if self._total_submitted > 0 else 0,
        }
    
    def cleanup_old_orders(self, max_age_hours: int = 24):
        """
        清理旧订单
        
        Args:
            max_age_hours: 最大保留时间（小时）
        """
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        to_remove = [
            cid for cid, order in self._client_orders.items()
            if order.updated_at < cutoff and order.is_terminal
        ]
        
        for cid in to_remove:
            del self._client_orders[cid]
            if cid in self._orders:
                del self._orders[cid]
            if cid in self._fills:
                del self._fills[cid]
        
        logger.info(f"清理 {len(to_remove)} 个旧订单")
