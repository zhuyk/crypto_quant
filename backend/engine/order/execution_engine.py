"""
执行引擎 - 订单执行核心
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Callable
from decimal import Decimal

from .order_types import Order, OrderState, OrderSide, OrderType, OrderResult, OrderFill
from .order_manager import OrderManager
from .slippage_control import SlippageController, SlippageConfig

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """
    订单执行引擎
    
    负责订单的实际执行，包括：
    - 订单提交到交易所
    - 执行重试逻辑
    - 超时处理
    - 异常处理
    """
    
    def __init__(
        self,
        order_manager: OrderManager,
        slippage_controller: Optional[SlippageController] = None,
        exchange_client=None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """
        Args:
            order_manager: 订单管理器
            slippage_controller: 滑点控制器
            exchange_client: 交易所客户端（如 Binance）
            timeout: 订单超时时间（秒）
            max_retries: 最大重试次数
        """
        self.order_manager = order_manager
        self.slippage_controller = slippage_controller or SlippageController()
        self.exchange_client = exchange_client
        
        self.timeout = timeout
        self.max_retries = max_retries
        
        # 执行统计
        self._total_executed = 0
        self._total_success = 0
        self._total_failed = 0
        self._total_retries = 0
        
        # 执行队列
        self._execution_queue: asyncio.Queue = asyncio.Queue()
        self._is_running = False
    
    async def start(self):
        """启动执行引擎"""
        self._is_running = True
        asyncio.create_task(self._execution_loop())
        logger.info("执行引擎已启动")
    
    async def stop(self):
        """停止执行引擎"""
        self._is_running = False
        logger.info("执行引擎已停止")
    
    async def _execution_loop(self):
        """执行循环"""
        while self._is_running:
            try:
                # 从队列获取订单
                order = await asyncio.wait_for(
                    self._execution_queue.get(),
                    timeout=1.0
                )
                
                # 执行订单
                await self._execute_order(order)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"执行循环错误：{e}")
                await asyncio.sleep(1.0)
    
    async def execute_order(
        self,
        order: Order,
        priority: bool = False
    ) -> OrderResult:
        """
        执行订单
        
        Args:
            order: 订单对象
            priority: 是否优先执行
            
        Returns:
            OrderResult: 执行结果
        """
        if priority:
            # 高优先级订单插入队列前端
            await self._execution_queue.put(order)
        else:
            await self._execution_queue.put(order)
        
        # 等待执行完成
        while order.is_active:
            await asyncio.sleep(0.1)
        
        return OrderResult(
            success=order.state == OrderState.FILLED,
            order=order,
            message=order.error_message or "执行成功",
            fills=self.order_manager.get_fills(order.client_order_id),
        )
    
    async def _execute_order(self, order: Order):
        """
        实际执行订单（含重试逻辑）
        
        Args:
            order: 订单对象
        """
        self._total_executed += 1
        
        for attempt in range(1, self.max_retries + 1):
            try:
                order.retry_count = attempt
                
                # 提交订单到交易所
                result = await self._submit_to_exchange(order)
                
                if result.success:
                    self._total_success += 1
                    return
                else:
                    logger.warning(f"订单执行失败 (尝试 {attempt}/{self.max_retries}): {result.message}")
                    
            except Exception as e:
                logger.error(f"订单执行异常 (尝试 {attempt}/{self.max_retries}): {e}")
            
            # 重试前等待
            if attempt < self.max_retries:
                self._total_retries += 1
                await asyncio.sleep(1.0 * attempt)  # 指数退避
        
        # 所有重试失败
        order.state = OrderState.FAILED
        order.error_message = f"执行失败：超过最大重试次数 ({self.max_retries})"
        order.updated_at = datetime.utcnow()
        self._total_failed += 1
        
        logger.error(f"订单执行最终失败：{order.client_order_id}")
    
    async def _submit_to_exchange(self, order: Order) -> OrderResult:
        """
        提交订单到交易所
        
        Args:
            order: 订单对象
            
        Returns:
            OrderResult: 执行结果
        """
        if not self.exchange_client:
            # 模拟执行（测试用）
            return await self._simulate_execution(order)
        
        try:
            # 更新订单状态
            self.order_manager.update_order_state(
                order.client_order_id,
                OrderState.SUBMITTED
            )
            
            # 调用交易所 API
            if order.type == OrderType.MARKET:
                response = await self.exchange_client.place_market_order(
                    symbol=order.symbol,
                    side=order.side.value,
                    quantity=float(order.quantity),
                )
            elif order.type == OrderType.LIMIT:
                response = await self.exchange_client.place_limit_order(
                    symbol=order.symbol,
                    side=order.side.value,
                    quantity=float(order.quantity),
                    price=float(order.price),
                    time_in_force=order.time_in_force.value,
                )
            else:
                raise ValueError(f"不支持的订单类型：{order.type}")
            
            # 更新订单 ID
            order.order_id = response.get('order_id')
            
            # 处理成交
            if response.get('status') == 'FILLED':
                fill = OrderFill(
                    fill_id=response.get('fill_id', 'fill_1'),
                    order_id=order.client_order_id,
                    symbol=order.symbol,
                    side=order.side,
                    price=Decimal(str(response.get('price', 0))),
                    quantity=Decimal(str(response.get('quantity', 0))),
                    commission=Decimal(str(response.get('commission', 0))),
                    commission_asset=response.get('commission_asset', 'USDT'),
                    trade_id=response.get('trade_id'),
                    fill_time=datetime.utcnow(),
                )
                self.order_manager.add_fill(order.client_order_id, fill)
            
            return OrderResult(
                success=True,
                order=order,
                message="订单提交成功",
            )
            
        except Exception as e:
            logger.error(f"交易所 API 调用失败：{e}")
            return OrderResult(
                success=False,
                order=order,
                message=str(e),
            )
    
    async def _simulate_execution(self, order: Order) -> OrderResult:
        """
        模拟执行（用于测试）
        
        Args:
            order: 订单对象
            
        Returns:
            OrderResult: 执行结果
        """
        # 模拟网络延迟
        await asyncio.sleep(0.1)
        
        # 模拟价格滑点
        import random
        slippage = Decimal(str(random.uniform(-0.001, 0.001)))
        
        # 模拟成交价格
        if order.price:
            fill_price = order.price * (1 + slippage)
        else:
            fill_price = Decimal('50000') * (1 + slippage)  # 模拟 BTC 价格
        
        # 创建成交记录
        fill = OrderFill(
            fill_id=f"fill_{datetime.utcnow().timestamp()}",
            order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side,
            price=fill_price,
            quantity=order.quantity,
            commission=order.quantity * fill_price * Decimal('0.001'),
            commission_asset='USDT',
            fill_time=datetime.utcnow(),
        )
        
        self.order_manager.add_fill(order.client_order_id, fill)
        
        return OrderResult(
            success=True,
            order=order,
            message="模拟执行成功",
            fills=[fill],
        )
    
    async def cancel_order(self, client_order_id: str) -> bool:
        """
        取消订单
        
        Args:
            client_order_id: 客户端订单 ID
            
        Returns:
            bool: 是否成功取消
        """
        order = self.order_manager.get_order(client_order_id)
        if not order:
            return False
        
        if not self.exchange_client:
            return self.order_manager.cancel_order(client_order_id, "用户取消")
        
        try:
            await self.exchange_client.cancel_order(
                symbol=order.symbol,
                order_id=order.order_id or client_order_id,
            )
            return self.order_manager.cancel_order(client_order_id, "用户取消")
        except Exception as e:
            logger.error(f"取消订单失败：{e}")
            return False
    
    def get_statistics(self) -> dict:
        """获取执行统计"""
        return {
            "total_executed": self._total_executed,
            "total_success": self._total_success,
            "total_failed": self._total_failed,
            "total_retries": self._total_retries,
            "success_rate": self._total_success / self._total_executed if self._total_executed > 0 else 0,
            "avg_retries": self._total_retries / self._total_executed if self._total_executed > 0 else 0,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }
