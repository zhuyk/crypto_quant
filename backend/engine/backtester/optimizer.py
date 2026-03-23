"""
参数优化器 - 网格搜索 + 遗传算法
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple, Optional, Callable
from itertools import product
import logging
import random

from strategies.base import Strategy
from .core import Backtester
from .report import BacktestReport

logger = logging.getLogger(__name__)


class ParameterOptimizer:
    """
    策略参数优化器
    
    支持：
    - 网格搜索 (Grid Search)
    - 随机搜索 (Random Search)
    - 遗传算法 (Genetic Algorithm)
    """
    
    def __init__(
        self,
        backtester: Backtester,
        data: pd.DataFrame,
        strategy_class: type,
        metric: str = "sharpe_ratio",
    ):
        """
        初始化优化器
        
        Args:
            backtester: 回测引擎实例
            data: K 线数据
            strategy_class: 策略类
            metric: 优化目标指标 (sharpe_ratio, total_return, max_drawdown 等)
        """
        self.backtester = backtester
        self.data = data
        self.strategy_class = strategy_class
        self.metric = metric
        self.results: List[Dict[str, Any]] = []
    
    def grid_search(
        self,
        param_grid: Dict[str, List[Any]],
        max_workers: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        网格搜索
        
        Args:
            param_grid: 参数网格，例如 {"fast_period": [10, 20, 30], "slow_period": [50, 60, 70]}
            max_workers: 并行工作线程数 (暂未实现并行)
        
        Returns:
            所有参数组合的结果列表
        """
        logger.info(f"开始网格搜索 - 参数组合数：{self._count_combinations(param_grid)}")
        
        self.results = []
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        
        # 生成所有参数组合
        combinations = list(product(*values))
        
        for i, combo in enumerate(combinations):
            params = dict(zip(keys, combo))
            
            # 跳过无效参数组合
            if not self._validate_params(params):
                continue
            
            # 执行回测
            try:
                strategy = self.strategy_class(params)
                report = self.backtester.run(strategy, self.data, params)
                
                result = {
                    "params": params,
                    "metric_value": getattr(report, self.metric, 0),
                    "report": report,
                }
                self.results.append(result)
                
                if (i + 1) % 10 == 0:
                    logger.info(f"进度：{i+1}/{len(combinations)}")
                
            except Exception as e:
                logger.warning(f"参数组合 {params} 回测失败：{e}")
        
        # 按指标排序
        self.results.sort(key=lambda x: x["metric_value"], reverse=True)
        
        logger.info(f"网格搜索完成 - 最佳指标：{self.results[0]['metric_value']:.4f}" if self.results else "网格搜索完成 - 无有效结果")
        
        return self.results
    
    def random_search(
        self,
        param_ranges: Dict[str, Tuple[Any, Any]],
        n_iterations: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        随机搜索
        
        Args:
            param_ranges: 参数范围，例如 {"fast_period": (10, 50), "slow_period": (50, 200)}
            n_iterations: 迭代次数
        
        Returns:
            所有参数组合的结果列表
        """
        logger.info(f"开始随机搜索 - 迭代次数：{n_iterations}")
        
        self.results = []
        
        for i in range(n_iterations):
            # 随机生成参数
            params = {}
            for param_name, (min_val, max_val) in param_ranges.items():
                if isinstance(min_val, int):
                    params[param_name] = random.randint(min_val, max_val)
                else:
                    params[param_name] = random.uniform(min_val, max_val)
            
            # 跳过无效参数组合
            if not self._validate_params(params):
                continue
            
            # 执行回测
            try:
                strategy = self.strategy_class(params)
                report = self.backtester.run(strategy, self.data, params)
                
                result = {
                    "params": params,
                    "metric_value": getattr(report, self.metric, 0),
                    "report": report,
                }
                self.results.append(result)
                
            except Exception as e:
                logger.warning(f"参数组合 {params} 回测失败：{e}")
        
        # 按指标排序
        self.results.sort(key=lambda x: x["metric_value"], reverse=True)
        
        logger.info(f"随机搜索完成 - 最佳指标：{self.results[0]['metric_value']:.4f}" if self.results else "随机搜索完成 - 无有效结果")
        
        return self.results
    
    def genetic_algorithm(
        self,
        param_ranges: Dict[str, Tuple[Any, Any]],
        population_size: int = 50,
        generations: int = 20,
        mutation_rate: float = 0.1,
        elite_size: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        遗传算法优化
        
        Args:
            param_ranges: 参数范围
            population_size: 种群大小
            generations: 迭代代数
            mutation_rate: 变异率
            elite_size: 精英保留数量
        
        Returns:
            最佳参数组合
        """
        logger.info(f"开始遗传算法 - 种群：{population_size}, 代数：{generations}")
        
        # 初始化种群
        population = self._create_population(param_ranges, population_size)
        
        for generation in range(generations):
            # 评估适应度
            fitness_scores = []
            for params in population:
                try:
                    strategy = self.strategy_class(params)
                    report = self.backtester.run(strategy, self.data, params)
                    fitness = getattr(report, self.metric, 0)
                    fitness_scores.append(fitness)
                except Exception as e:
                    fitness_scores.append(0)
                    logger.debug(f"参数 {params} 评估失败：{e}")
            
            # 选择精英
            elite_indices = np.argsort(fitness_scores)[-elite_size:]
            elite = [population[i] for i in elite_indices]
            
            # 生成新一代
            new_population = elite.copy()
            
            while len(new_population) < population_size:
                # 选择父代 (锦标赛选择)
                parent1 = self._tournament_selection(population, fitness_scores)
                parent2 = self._tournament_selection(population, fitness_scores)
                
                # 交叉
                child = self._crossover(parent1, parent2)
                
                # 变异
                child = self._mutate(child, param_ranges, mutation_rate)
                
                if self._validate_params(child):
                    new_population.append(child)
            
            population = new_population
            
            best_fitness = max(fitness_scores)
            logger.info(f"代数 {generation+1}/{generations} - 最佳适应度：{best_fitness:.4f}")
        
        # 最终评估
        self.results = []
        for params in population:
            try:
                strategy = self.strategy_class(params)
                report = self.backtester.run(strategy, self.data, params)
                result = {
                    "params": params,
                    "metric_value": getattr(report, self.metric, 0),
                    "report": report,
                }
                self.results.append(result)
            except Exception as e:
                logger.warning(f"参数组合 {params} 回测失败：{e}")
        
        self.results.sort(key=lambda x: x["metric_value"], reverse=True)
        
        logger.info(f"遗传算法完成 - 最佳指标：{self.results[0]['metric_value']:.4f}" if self.results else "遗传算法完成 - 无有效结果")
        
        return self.results
    
    def get_best_params(self) -> Optional[Dict[str, Any]]:
        """获取最佳参数"""
        if not self.results:
            return None
        return self.results[0]["params"]
    
    def get_best_report(self) -> Optional[BacktestReport]:
        """获取最佳回测报告"""
        if not self.results:
            return None
        return self.results[0]["report"]
    
    def _count_combinations(self, param_grid: Dict[str, List[Any]]) -> int:
        """计算参数组合数"""
        count = 1
        for values in param_grid.values():
            count *= len(values)
        return count
    
    def _validate_params(self, params: Dict[str, Any]) -> bool:
        """验证参数组合是否有效"""
        # 示例：确保快周期 < 慢周期
        if "fast_period" in params and "slow_period" in params:
            if params["fast_period"] >= params["slow_period"]:
                return False
        
        # 可以添加更多验证逻辑
        return True
    
    def _create_population(
        self,
        param_ranges: Dict[str, Tuple[Any, Any]],
        size: int,
    ) -> List[Dict[str, Any]]:
        """创建初始种群"""
        population = []
        for _ in range(size):
            params = {}
            for param_name, (min_val, max_val) in param_ranges.items():
                if isinstance(min_val, int):
                    params[param_name] = random.randint(min_val, max_val)
                else:
                    params[param_name] = random.uniform(min_val, max_val)
            population.append(params)
        return population
    
    def _tournament_selection(
        self,
        population: List[Dict[str, Any]],
        fitness_scores: List[float],
        tournament_size: int = 5,
    ) -> Dict[str, Any]:
        """锦标赛选择"""
        indices = random.sample(range(len(population)), min(tournament_size, len(population)))
        best_idx = max(indices, key=lambda i: fitness_scores[i])
        return population[best_idx].copy()
    
    def _crossover(
        self,
        parent1: Dict[str, Any],
        parent2: Dict[str, Any],
    ) -> Dict[str, Any]:
        """交叉操作"""
        child = {}
        for key in parent1.keys():
            if random.random() < 0.5:
                child[key] = parent1[key]
            else:
                child[key] = parent2[key]
        return child
    
    def _mutate(
        self,
        params: Dict[str, Any],
        param_ranges: Dict[str, Tuple[Any, Any]],
        rate: float,
    ) -> Dict[str, Any]:
        """变异操作"""
        mutated = params.copy()
        for key in mutated.keys():
            if random.random() < rate:
                min_val, max_val = param_ranges[key]
                if isinstance(min_val, int):
                    mutated[key] = random.randint(min_val, max_val)
                else:
                    mutated[key] = random.uniform(min_val, max_val)
        return mutated
