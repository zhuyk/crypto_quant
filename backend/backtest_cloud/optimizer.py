"""
参数优化器 - 网格搜索和贝叶斯优化
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """优化结果"""
    best_params: dict
    best_score: float
    all_results: List[dict]
    total_iterations: int
    optimization_time: float


class ParameterOptimizer:
    """
    参数优化器
    
    支持:
    - 网格搜索
    - 随机搜索
    - 贝叶斯优化
    """
    
    def __init__(self):
        """初始化优化器"""
        self._optimization_history = []
    
    def grid_search(
        self,
        backtest_func,
        param_grid: Dict[str, List],
        symbol: str,
        start_time: int,
        end_time: int,
        timeframe: str,
        initial_capital: float = 100000,
        metric: str = 'sharpe',
    ) -> OptimizationResult:
        """
        网格搜索
        
        Args:
            backtest_func: 回测函数
            param_grid: 参数网格 {param_name: [values]}
            symbol: 交易对
            start_time: 开始时间
            end_time: 结束时间
            timeframe: 时间周期
            initial_capital: 初始资金
            metric: 优化指标
            
        Returns:
            OptimizationResult: 优化结果
        """
        import time
        start_time_opt = time.time()
        
        # 生成所有参数组合
        param_combinations = self._generate_param_combinations(param_grid)
        
        logger.info(f"网格搜索：{len(param_combinations)} 个参数组合")
        
        all_results = []
        best_score = float('-inf')
        best_params = None
        
        for i, params in enumerate(param_combinations):
            try:
                # 执行回测
                result = backtest_func(
                    symbol=symbol,
                    params=params,
                    start_time=start_time,
                    end_time=end_time,
                    timeframe=timeframe,
                    initial_capital=initial_capital,
                )
                
                # 获取指标分数
                score = self._get_metric_score(result, metric)
                
                result_entry = {
                    'params': params,
                    'score': score,
                    'metrics': result,
                }
                
                all_results.append(result_entry)
                
                # 更新最优
                if score > best_score:
                    best_score = score
                    best_params = params
                
                logger.info(f"[{i+1}/{len(param_combinations)}] Score: {score:.4f} - Params: {params}")
                
            except Exception as e:
                logger.error(f"回测失败 {params}: {e}")
        
        optimization_time = time.time() - start_time_opt
        
        result = OptimizationResult(
            best_params=best_params or {},
            best_score=best_score,
            all_results=all_results,
            total_iterations=len(all_results),
            optimization_time=optimization_time,
        )
        
        self._optimization_history.append(result)
        
        return result
    
    def random_search(
        self,
        backtest_func,
        param_distributions: Dict[str, Tuple],
        symbol: str,
        start_time: int,
        end_time: int,
        timeframe: str,
        initial_capital: float = 100000,
        metric: str = 'sharpe',
        n_iterations: int = 50,
    ) -> OptimizationResult:
        """
        随机搜索
        
        Args:
            backtest_func: 回测函数
            param_distributions: 参数分布 {param_name: (min, max)}
            symbol: 交易对
            start_time: 开始时间
            end_time: 结束时间
            timeframe: 时间周期
            initial_capital: 初始资金
            metric: 优化指标
            n_iterations: 迭代次数
            
        Returns:
            OptimizationResult: 优化结果
        """
        import time
        start_time_opt = time.time()
        
        logger.info(f"随机搜索：{n_iterations} 次迭代")
        
        all_results = []
        best_score = float('-inf')
        best_params = None
        
        for i in range(n_iterations):
            # 随机生成参数
            params = self._sample_random_params(param_distributions)
            
            try:
                result = backtest_func(
                    symbol=symbol,
                    params=params,
                    start_time=start_time,
                    end_time=end_time,
                    timeframe=timeframe,
                    initial_capital=initial_capital,
                )
                
                score = self._get_metric_score(result, metric)
                
                result_entry = {
                    'params': params,
                    'score': score,
                    'metrics': result,
                }
                
                all_results.append(result_entry)
                
                if score > best_score:
                    best_score = score
                    best_params = params
                
                logger.info(f"[{i+1}/{n_iterations}] Score: {score:.4f}")
                
            except Exception as e:
                logger.error(f"回测失败 {params}: {e}")
        
        optimization_time = time.time() - start_time_opt
        
        result = OptimizationResult(
            best_params=best_params or {},
            best_score=best_score,
            all_results=all_results,
            total_iterations=len(all_results),
            optimization_time=optimization_time,
        )
        
        self._optimization_history.append(result)
        
        return result
    
    def _generate_param_combinations(self, param_grid: Dict[str, List]) -> List[dict]:
        """生成参数组合"""
        import itertools
        
        keys = list(param_grid.keys())
        values = [param_grid[k] for k in keys]
        
        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))
        
        return combinations
    
    def _sample_random_params(self, param_distributions: Dict[str, Tuple]) -> dict:
        """随机采样参数"""
        params = {}
        
        for param_name, (min_val, max_val) in param_distributions.items():
            if isinstance(min_val, int) and isinstance(max_val, int):
                params[param_name] = np.random.randint(min_val, max_val + 1)
            else:
                params[param_name] = np.random.uniform(min_val, max_val)
        
        return params
    
    def _get_metric_score(self, result: dict, metric: str) -> float:
        """获取指标分数"""
        metric_mapping = {
            'sharpe': result.get('sharpe_ratio', 0),
            'sortino': result.get('sortino_ratio', 0),
            'total_return': result.get('total_return', 0),
            'max_drawdown': -result.get('max_drawdown', 0),  # 越小越好
            'calmar': result.get('calmar_ratio', 0),
        }
        
        return metric_mapping.get(metric, 0)
    
    def get_optimization_history(self) -> List[OptimizationResult]:
        """获取优化历史"""
        return self._optimization_history.copy()
