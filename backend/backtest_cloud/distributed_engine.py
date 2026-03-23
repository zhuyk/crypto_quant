"""
分布式回测引擎
"""

import asyncio
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import logging
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class BacktestTask:
    """回测任务"""
    id: str
    strategy_name: str
    symbol: str
    params: dict
    start_time: int
    end_time: int
    timeframe: str
    initial_capital: float
    priority: int = 0
    status: str = "pending"
    result: Optional[dict] = None
    created_at: datetime = None
    completed_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class DistributedBacktestEngine:
    """
    分布式回测引擎
    
    支持:
    - 多节点并行回测
    - 任务队列管理
    - 结果缓存
    - 进度追踪
    """
    
    def __init__(
        self,
        max_concurrent: int = 4,
        cache_enabled: bool = True,
    ):
        """
        Args:
            max_concurrent: 最大并发数
            cache_enabled: 启用缓存
        """
        self.max_concurrent = max_concurrent
        self.cache_enabled = cache_enabled
        
        # 任务队列
        self._task_queue = asyncio.Queue()
        
        # 运行中的任务
        self._running_tasks: Dict[str, BacktestTask] = {}
        
        # 已完成任务
        self._completed_tasks: Dict[str, BacktestTask] = {}
        
        # 结果缓存
        self._result_cache: Dict[str, dict] = {}
        
        # 工作节点
        self._workers = []
        
        # 运行状态
        self._is_running = False
    
    def generate_task_id(self, task: BacktestTask) -> str:
        """生成任务 ID（基于参数哈希）"""
        param_str = f"{task.strategy_name}:{task.symbol}:{task.params}:{task.start_time}:{task.end_time}"
        return hashlib.md5(param_str.encode()).hexdigest()
    
    async def submit_task(
        self,
        strategy_name: str,
        symbol: str,
        params: dict,
        start_time: int,
        end_time: int,
        timeframe: str,
        initial_capital: float = 100000,
        priority: int = 0,
    ) -> str:
        """
        提交回测任务
        
        Args:
            strategy_name: 策略名称
            symbol: 交易对
            params: 策略参数
            start_time: 开始时间
            end_time: 结束时间
            timeframe: 时间周期
            initial_capital: 初始资金
            priority: 优先级
            
        Returns:
            str: 任务 ID
        """
        task = BacktestTask(
            id="",
            strategy_name=strategy_name,
            symbol=symbol,
            params=params,
            start_time=start_time,
            end_time=end_time,
            timeframe=timeframe,
            initial_capital=initial_capital,
            priority=priority,
        )
        
        task.id = self.generate_task_id(task)
        
        # 检查缓存
        if self.cache_enabled and task.id in self._result_cache:
            logger.info(f"使用缓存结果：{task.id}")
            task.status = "completed"
            task.result = self._result_cache[task.id]
            task.completed_at = datetime.utcnow()
            self._completed_tasks[task.id] = task
            return task.id
        
        # 添加到队列
        await self._task_queue.put(task)
        self._running_tasks[task.id] = task
        
        logger.info(f"提交回测任务：{task.id}")
        
        return task.id
    
    async def submit_batch(
        self,
        tasks: List[Dict],
    ) -> List[str]:
        """
        批量提交任务
        
        Args:
            tasks: 任务列表
            
        Returns:
            List[str]: 任务 ID 列表
        """
        task_ids = []
        
        for task_params in tasks:
            task_id = await self.submit_task(**task_params)
            task_ids.append(task_id)
        
        return task_ids
    
    async def get_task_status(self, task_id: str) -> dict:
        """获取任务状态"""
        if task_id in self._completed_tasks:
            task = self._completed_tasks[task_id]
            return {
                'id': task.id,
                'status': task.status,
                'result': task.result,
                'created_at': task.created_at.isoformat(),
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            }
        
        if task_id in self._running_tasks:
            task = self._running_tasks[task_id]
            return {
                'id': task.id,
                'status': task.status,
                'progress': 0,  # TODO: 实现进度追踪
                'created_at': task.created_at.isoformat(),
            }
        
        return {'id': task_id, 'status': 'not_found'}
    
    async def get_result(self, task_id: str) -> Optional[dict]:
        """获取回测结果"""
        if task_id in self._completed_tasks:
            return self._completed_tasks[task_id].result
        
        if task_id in self._result_cache:
            return self._result_cache[task_id]
        
        return None
    
    async def start_workers(self, backtest_func: Callable):
        """
        启动工作节点
        
        Args:
            backtest_func: 回测函数
        """
        if self._is_running:
            return
        
        self._is_running = True
        
        # 创建工作节点
        for i in range(self.max_concurrent):
            worker = asyncio.create_task(self._worker(i, backtest_func))
            self._workers.append(worker)
        
        logger.info(f"启动 {self.max_concurrent} 个工作节点")
    
    async def stop_workers(self):
        """停止工作节点"""
        self._is_running = False
        
        for worker in self._workers:
            worker.cancel()
        
        self._workers.clear()
        
        logger.info("停止工作节点")
    
    async def _worker(self, worker_id: int, backtest_func: Callable):
        """工作节点"""
        while self._is_running:
            try:
                # 获取任务
                task = await asyncio.wait_for(
                    self._task_queue.get(),
                    timeout=1.0
                )
                
                logger.info(f"Worker {worker_id} 开始处理任务：{task.id}")
                
                # 执行回测
                try:
                    result = await backtest_func(
                        strategy_name=task.strategy_name,
                        symbol=task.symbol,
                        params=task.params,
                        start_time=task.start_time,
                        end_time=task.end_time,
                        timeframe=task.timeframe,
                        initial_capital=task.initial_capital,
                    )
                    
                    task.status = "completed"
                    task.result = result
                    task.completed_at = datetime.utcnow()
                    
                    # 缓存结果
                    if self.cache_enabled:
                        self._result_cache[task.id] = result
                    
                    # 移动任务到已完成
                    self._completed_tasks[task.id] = task
                    self._running_tasks.pop(task.id, None)
                    
                    logger.info(f"Worker {worker_id} 完成任务：{task.id}")
                    
                except Exception as e:
                    logger.error(f"Worker {worker_id} 任务失败 {task.id}: {e}")
                    task.status = "failed"
                    task.result = {'error': str(e)}
                
                self._task_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} 错误：{e}")
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        return {
            'is_running': self._is_running,
            'max_concurrent': self.max_concurrent,
            'pending_tasks': self._task_queue.qsize(),
            'running_tasks': len(self._running_tasks),
            'completed_tasks': len(self._completed_tasks),
            'cache_size': len(self._result_cache),
        }
    
    def clear_cache(self):
        """清除缓存"""
        self._result_cache.clear()
        logger.info("清除回测缓存")
