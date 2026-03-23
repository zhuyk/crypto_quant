"""
交易对账引擎 - 确保订单状态一致性
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from decimal import Decimal
from dataclasses import dataclass, field

from .order_types import Order, OrderState, OrderFill
from .order_manager import OrderManager

logger = logging.getLogger(__name__)


@dataclass
class ReconciliationResult:
    """
    对账结果
    
    Attributes:
        is_matched: 是否匹配
        discrepancies: 差异列表
        local_order: 本地订单
        remote_order: 远程订单（交易所）
    """
    is_matched: bool
    discrepancies: List[str] = field(default_factory=list)
    local_order: Optional[Order] = None
    remote_order: Optional[dict] = None


class ReconciliationEngine:
    """
    交易对账引擎
    
    定期对比本地订单状态和交易所订单状态，确保一致性
    
    功能：
    - 定时对账
    - 差异检测
    - 自动修复
    - 对账报告
    """
    
    def __init__(
        self,
        order_manager: OrderManager,
        exchange_client=None,
        check_interval: int = 60,
        auto_fix: bool = True,
    ):
        """
        Args:
            order_manager: 订单管理器
            exchange_client: 交易所客户端
            check_interval: 对账间隔（秒）
            auto_fix: 是否自动修复差异
        """
        self.order_manager = order_manager
        self.exchange_client = exchange_client
        self.check_interval = check_interval
        self.auto_fix = auto_fix
        
        # 对账统计
        self._total_checks = 0
        self._total_matched = 0
        self._total_discrepancies = 0
        self._total_fixed = 0
        
        # 对账历史
        self._reconciliation_history: List[ReconciliationResult] = []
        
        # 运行状态
        self._is_running = False
    
    async def start(self):
        """启动对账引擎"""
        self._is_running = True
        asyncio.create_task(self._reconciliation_loop())
        logger.info("对账引擎已启动")
    
    async def stop(self):
        """停止对账引擎"""
        self._is_running = False
        logger.info("对账引擎已停止")
    
    async def _reconciliation_loop(self):
        """对账循环"""
        while self._is_running:
            try:
                await self._run_reconciliation()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"对账循环错误：{e}")
                await asyncio.sleep(10)
    
    async def _run_reconciliation(self):
        """执行一次完整对账"""
        self._total_checks += 1
        
        # 获取所有活跃订单
        active_orders = self.order_manager.get_active_orders()
        
        logger.info(f"开始对账，检查 {len(active_orders)} 个活跃订单")
        
        results = []
        
        for order in active_orders:
            result = await self._check_order(order)
            results.append(result)
            
            if not result.is_matched:
                self._total_discrepancies += 1
                logger.warning(
                    f"订单对账不匹配：{order.client_order_id} "
                    f"差异：{result.discrepancies}"
                )
                
                # 自动修复
                if self.auto_fix:
                    await self._fix_discrepancy(order, result)
            else:
                self._total_matched += 1
        
        # 保存历史记录
        self._reconciliation_history.extend(results)
        
        # 清理旧记录（保留最近 100 条）
        if len(self._reconciliation_history) > 100:
            self._reconciliation_history = self._reconciliation_history[-100:]
        
        logger.info(
            f"对账完成：匹配 {self._total_matched}, "
            f"差异 {self._total_discrepancies}"
        )
    
    async def _check_order(self, order: Order) -> ReconciliationResult:
        """
        检查单个订单
        
        Args:
            order: 本地订单
            
        Returns:
            ReconciliationResult: 对账结果
        """
        discrepancies = []
        
        if not self.exchange_client:
            # 无交易所客户端，假设匹配
            return ReconciliationResult(
                is_matched=True,
                local_order=order,
            )
        
        try:
            # 从交易所获取订单状态
            remote_order = await self.exchange_client.get_order(
                symbol=order.symbol,
                order_id=order.order_id or order.client_order_id,
            )
            
            if not remote_order:
                discrepancies.append("交易所无此订单记录")
                return ReconciliationResult(
                    is_matched=False,
                    discrepancies=discrepancies,
                    local_order=order,
                    remote_order=None,
                )
            
            # 对比状态
            remote_state = self._map_remote_state(remote_order.get('status'))
            if remote_state != order.state:
                discrepancies.append(
                    f"状态不匹配：本地={order.state.value}, "
                    f"远程={remote_state.value}"
                )
            
            # 对比成交数量
            remote_filled = Decimal(str(remote_order.get('filled_quantity', 0)))
            if remote_filled != order.filled_quantity:
                discrepancies.append(
                    f"成交数量不匹配：本地={order.filled_quantity}, "
                    f"远程={remote_filled}"
                )
            
            # 对比成交价格
            remote_avg_price = Decimal(str(remote_order.get('avg_fill_price', 0)))
            if remote_avg_price != order.avg_fill_price and remote_filled > 0:
                discrepancies.append(
                    f"平均价格不匹配：本地={order.avg_fill_price}, "
                    f"远程={remote_avg_price}"
                )
            
            return ReconciliationResult(
                is_matched=len(discrepancies) == 0,
                discrepancies=discrepancies,
                local_order=order,
                remote_order=remote_order,
            )
            
        except Exception as e:
            logger.error(f"检查订单失败：{order.client_order_id} - {e}")
            return ReconciliationResult(
                is_matched=False,
                discrepancies=[f"检查失败：{str(e)}"],
                local_order=order,
            )
    
    def _map_remote_state(self, remote_status: str) -> OrderState:
        """
        映射交易所状态到本地状态
        
        Args:
            remote_status: 交易所状态
            
        Returns:
            OrderState: 本地订单状态
        """
        mapping = {
            'NEW': OrderState.SUBMITTED,
            'PARTIALLY_FILLED': OrderState.PARTIALLY_FILLED,
            'FILLED': OrderState.FILLED,
            'CANCELED': OrderState.CANCELLED,
            'REJECTED': OrderState.REJECTED,
            'EXPIRED': OrderState.EXPIRED,
        }
        return mapping.get(remote_status, OrderState.PENDING)
    
    async def _fix_discrepancy(self, order: Order, result: ReconciliationResult):
        """
        修复对账差异
        
        Args:
            order: 本地订单
            result: 对账结果
        """
        if not result.remote_order:
            logger.warning(f"无法修复：无远程订单数据 {order.client_order_id}")
            return
        
        try:
            # 以交易所状态为准，更新本地订单
            remote_state = self._map_remote_state(result.remote_order.get('status'))
            
            if remote_state != order.state:
                logger.info(
                    f"修复订单状态：{order.client_order_id} "
                    f"{order.state.value} -> {remote_state.value}"
                )
                self.order_manager.update_order_state(
                    order.client_order_id,
                    remote_state,
                )
            
            # 更新成交信息
            remote_filled = Decimal(str(result.remote_order.get('filled_quantity', 0)))
            if remote_filled != order.filled_quantity:
                logger.info(
                    f"修复成交数量：{order.client_order_id} "
                    f"{order.filled_quantity} -> {remote_filled}"
                )
                order.filled_quantity = remote_filled
                order.updated_at = datetime.utcnow()
            
            self._total_fixed += 1
            
        except Exception as e:
            logger.error(f"修复对账差异失败：{e}")
    
    def get_statistics(self) -> dict:
        """获取对账统计"""
        return {
            "total_checks": self._total_checks,
            "total_matched": self._total_matched,
            "total_discrepancies": self._total_discrepancies,
            "total_fixed": self._total_fixed,
            "match_rate": self._total_matched / (self._total_matched + self._total_discrepancies) if (self._total_matched + self._total_discrepancies) > 0 else 0,
            "check_interval": self.check_interval,
            "auto_fix_enabled": self.auto_fix,
        }
    
    def get_reconciliation_history(self, limit: int = 10) -> List[dict]:
        """
        获取对账历史
        
        Args:
            limit: 返回记录数
            
        Returns:
            List[dict]: 对账历史记录
        """
        history = self._reconciliation_history[-limit:]
        return [
            {
                "is_matched": r.is_matched,
                "discrepancies": r.discrepancies,
                "order_id": r.local_order.client_order_id if r.local_order else None,
                "timestamp": datetime.utcnow().isoformat(),
            }
            for r in history
        ]
