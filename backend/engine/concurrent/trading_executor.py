"""
并发交易执行器
支持多线程/异步并发执行交易订单
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading

from loguru import logger

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """任务执行结果"""
    task_id: str
    status: ExecutionStatus
    result: Any = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
            "start_time": datetime.fromtimestamp(self.start_time).isoformat() if self.start_time else None,
            "end_time": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
        }


@dataclass
class Task:
    """执行任务"""
    task_id: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: int = 0  # 优先级，数字越大优先级越高
    timeout: Optional[float] = None  # 超时时间 (秒)
    retry_count: int = 0  # 重试次数
    max_retries: int = 3  # 最大重试次数


class ConcurrentExecutor:
    """并发执行器"""
    
    def __init__(self, max_workers: int = 10):
        """
        初始化并发执行器
        
        Args:
            max_workers: 最大工作线程数
        """
        self.max_workers = max_workers
        self._executor: Optional[ThreadPoolExecutor] = None
        self._futures: Dict[str, Any] = {}
        self._results: Dict[str, TaskResult] = {}
        self._lock = threading.Lock()
        self._running = False
        
        logger.info(f"✅ 并发执行器初始化完成 (最大线程数：{max_workers})")
    
    def start(self):
        """启动执行器"""
        if not self._executor:
            self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
            self._running = True
            logger.info("🚀 并发执行器已启动")
    
    def stop(self, wait: bool = True):
        """停止执行器"""
        self._running = False
        
        if self._executor:
            self._executor.shutdown(wait=wait)
            self._executor = None
            logger.info("👋 并发执行器已停止")
    
    def submit(
        self,
        task_id: str,
        func: Callable,
        *args,
        priority: int = 0,
        timeout: Optional[float] = None,
        max_retries: int = 3,
        **kwargs,
    ) -> str:
        """
        提交任务
        
        Args:
            task_id: 任务 ID
            func: 执行函数
            args: 函数参数
            priority: 优先级
            timeout: 超时时间
            max_retries: 最大重试次数
            kwargs: 函数关键字参数
        
        Returns:
            任务 ID
        """
        if not self._executor:
            self.start()
        
        task = Task(
            task_id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
        )
        
        # 提交到线程池
        future = self._executor.submit(self._execute_with_retry, task)
        
        with self._lock:
            self._futures[task_id] = future
        
        logger.debug(f"📤 任务已提交：{task_id} (优先级：{priority})")
        
        return task_id
    
    def _execute_with_retry(self, task: Task) -> TaskResult:
        """带重试执行任务"""
        result = TaskResult(task_id=task.task_id, status=ExecutionStatus.RUNNING)
        result.start_time = time.time()
        
        last_error = None
        
        for attempt in range(task.max_retries + 1):
            try:
                # 执行任务
                if task.timeout:
                    # 带超时执行
                    future = asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: task.func(*task.args, **task.kwargs),
                    )
                    task_result = asyncio.get_event_loop().run_until_complete(
                        asyncio.wait_for(future, timeout=task.timeout)
                    )
                else:
                    task_result = task.func(*task.args, **task.kwargs)
                
                result.status = ExecutionStatus.COMPLETED
                result.result = task_result
                logger.debug(f"✅ 任务执行成功：{task.task_id}")
                break
                
            except asyncio.TimeoutError:
                last_error = f"任务超时 ({task.timeout}s)"
                logger.warning(f"⏰ 任务超时：{task.task_id} ({task.timeout}s)")
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"❌ 任务执行失败：{task.task_id} - {e}")
                
                if attempt < task.max_retries:
                    wait_time = 2 ** attempt  # 指数退避
                    logger.info(f"🔄 {wait_time}s 后重试 ({attempt + 1}/{task.max_retries})")
                    time.sleep(wait_time)
                    task.retry_count += 1
                else:
                    result.status = ExecutionStatus.FAILED
                    result.error = last_error
        
        result.end_time = time.time()
        result.duration_ms = (result.end_time - result.start_time) * 1000
        
        # 存储结果
        with self._lock:
            self._results[task.task_id] = result
            self._futures.pop(task.task_id, None)
        
        return result
    
    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """获取任务结果"""
        with self._lock:
            return self._results.get(task_id)
    
    def get_all_results(self) -> Dict[str, TaskResult]:
        """获取所有任务结果"""
        with self._lock:
            return dict(self._results)
    
    def cancel(self, task_id: str) -> bool:
        """取消任务"""
        with self._lock:
            future = self._futures.pop(task_id, None)
            if future:
                cancelled = future.cancel()
                if cancelled:
                    self._results[task_id] = TaskResult(
                        task_id=task_id,
                        status=ExecutionStatus.CANCELLED,
                    )
                    logger.info(f"🚫 任务已取消：{task_id}")
                return cancelled
        return False
    
    def wait(self, task_ids: Optional[List[str]] = None, timeout: Optional[float] = None):
        """
        等待任务完成
        
        Args:
            task_ids: 任务 ID 列表 (None 表示等待所有)
            timeout: 超时时间
        """
        with self._lock:
            if task_ids:
                futures = [self._futures[tid] for tid in task_ids if tid in self._futures]
            else:
                futures = list(self._futures.values())
        
        if not futures:
            return
        
        try:
            for future in as_completed(futures, timeout=timeout):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"任务执行异常：{e}")
        except TimeoutError:
            logger.warning(f"⏰ 等待任务超时 ({timeout}s)")
    
    def get_stats(self) -> Dict:
        """获取执行统计"""
        with self._lock:
            total = len(self._results)
            completed = sum(1 for r in self._results.values() if r.status == ExecutionStatus.COMPLETED)
            failed = sum(1 for r in self._results.values() if r.status == ExecutionStatus.FAILED)
            running = len(self._futures)
            
            return {
                "total_tasks": total,
                "completed": completed,
                "failed": failed,
                "running": running,
                "success_rate": completed / total if total > 0 else 0,
            }


class TradingExecutor(ConcurrentExecutor):
    """交易执行器 (专门用于交易订单)"""
    
    def __init__(self, max_workers: int = 5):
        super().__init__(max_workers=max_workers)
        self._order_results: Dict[str, TaskResult] = {}
        
        logger.info("✅ 交易执行器初始化完成")
    
    def submit_order(
        self,
        order_id: str,
        order_func: Callable,
        symbol: str,
        side: str,
        amount: float,
        priority: int = 5,  # 订单默认高优先级
        timeout: float = 30.0,  # 30 秒超时
        **kwargs,
    ) -> str:
        """
        提交订单
        
        Args:
            order_id: 订单 ID
            order_func: 下单函数
            symbol: 交易对
            side: 方向 (buy/sell)
            amount: 数量
            priority: 优先级
            timeout: 超时时间
            kwargs: 其他参数
        
        Returns:
            任务 ID
        """
        task_id = f"order_{order_id}"
        
        return self.submit(
            task_id=task_id,
            func=order_func,
            priority=priority,
            timeout=timeout,
            max_retries=2,  # 订单最多重试 2 次
            symbol=symbol,
            side=side,
            amount=amount,
            **kwargs,
        )
    
    def submit_batch_orders(
        self,
        orders: List[Dict],
        order_func: Callable,
    ) -> List[str]:
        """
        批量提交订单
        
        Args:
            orders: 订单列表 [{order_id, symbol, side, amount, ...}]
            order_func: 下单函数
        
        Returns:
            任务 ID 列表
        """
        task_ids = []
        
        for order in orders:
            order_id = order.pop("order_id")
            task_id = self.submit_order(
                order_id=order_id,
                order_func=order_func,
                **order,
            )
            task_ids.append(task_id)
        
        logger.info(f"📦 批量提交 {len(task_ids)} 个订单")
        
        return task_ids
    
    def get_order_result(self, order_id: str) -> Optional[TaskResult]:
        """获取订单执行结果"""
        task_id = f"order_{order_id}"
        return self.get_result(task_id)
    
    def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        task_id = f"order_{order_id}"
        return self.cancel(task_id)


# 全局交易执行器实例
trading_executor = TradingExecutor(max_workers=5)


def get_trading_executor() -> TradingExecutor:
    """获取交易执行器"""
    return trading_executor
