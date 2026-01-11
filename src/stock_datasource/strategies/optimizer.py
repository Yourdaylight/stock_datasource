"""
策略优化器

提供多种优化算法来优化策略参数，包括：
- 网格搜索
- 随机搜索  
- 贝叶斯优化
- 遗传算法
"""

import logging
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import itertools
from dataclasses import dataclass

from .base import BaseStrategy
from ..backtest.models import OptimizationResult

logger = logging.getLogger(__name__)


@dataclass
class OptimizationObjective:
    """优化目标"""
    name: str
    type: str  # maximize, minimize
    weight: float = 1.0
    target_value: Optional[float] = None


@dataclass
class OptimizationConfig:
    """优化配置"""
    objectives: List[OptimizationObjective]
    algorithm: str = "grid_search"  # grid_search, random_search, bayesian, genetic
    max_iterations: int = 100
    convergence_threshold: float = 1e-6
    constraints: Dict[str, Any] = None
    parallel: bool = True
    max_workers: int = 4


class OptimizationAlgorithm:
    """优化算法基类"""
    
    def __init__(self, config: OptimizationConfig):
        self.config = config
        self.iteration_count = 0
        self.best_score = float('-inf')
        self.convergence_history = []
    
    async def optimize(self, 
                     param_space: Dict[str, Dict[str, Any]],
                     objective_function: Callable,
                     constraints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行优化"""
        raise NotImplementedError
    
    def _evaluate_objectives(self, result: Any) -> float:
        """评估目标函数"""
        total_score = 0.0
        
        for objective in self.config.objectives:
            if hasattr(result, objective.name):
                value = getattr(result, objective.name)
            elif hasattr(result, 'performance_metrics') and hasattr(result.performance_metrics, objective.name):
                value = getattr(result.performance_metrics, objective.name)
            else:
                logger.warning(f"Objective {objective.name} not found in result")
                continue
            
            if objective.type == "maximize":
                score = value * objective.weight
            else:  # minimize
                score = -value * objective.weight
            
            total_score += score
        
        return total_score
    
    def _check_convergence(self, current_score: float) -> bool:
        """检查收敛条件"""
        if len(self.convergence_history) < 2:
            return False
        
        improvement = abs(current_score - self.convergence_history[-1])
        return improvement < self.config.convergence_threshold


class GridSearchOptimizer(OptimizationAlgorithm):
    """网格搜索优化器"""
    
    async def optimize(self, 
                     param_space: Dict[str, Dict[str, Any]],
                     objective_function: Callable,
                     constraints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行网格搜索优化"""
        
        logger.info("Starting grid search optimization")
        
        # 生成参数网格
        param_grid = self._generate_param_grid(param_space)
        
        best_params = None
        best_score = float('-inf')
        
        # 并行评估参数组合
        if self.config.parallel:
            results = await self._parallel_evaluate(param_grid, objective_function)
        else:
            results = await self._sequential_evaluate(param_grid, objective_function)
        
        # 找到最佳参数
        for params, result in results:
            if result is not None:
                score = self._evaluate_objectives(result)
                
                if score > best_score:
                    best_score = score
                    best_params = params
                
                self.convergence_history.append(score)
        
        logger.info(f"Grid search completed. Best score: {best_score}")
        
        return best_params or {}
    
    def _generate_param_grid(self, param_space: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成参数网格"""
        param_names = list(param_space.keys())
        param_values = []
        
        for param_name, param_config in param_space.items():
            param_type = param_config['type']
            min_val = param_config['min']
            max_val = param_config['max']
            
            # 生成参数值序列
            if param_type == 'int':
                step = max(1, (max_val - min_val) // 10)  # 最多10个值
                values = list(range(min_val, max_val + 1, step))
            else:  # float
                values = np.linspace(min_val, max_val, 10).tolist()
            
            param_values.append(values)
        
        # 生成所有参数组合
        param_combinations = list(itertools.product(*param_values))
        
        param_grid = []
        for combination in param_combinations:
            param_dict = dict(zip(param_names, combination))
            param_grid.append(param_dict)
        
        logger.info(f"Generated {len(param_grid)} parameter combinations")
        return param_grid
    
    async def _parallel_evaluate(self, 
                                param_grid: List[Dict[str, Any]], 
                                objective_function: Callable) -> List[Tuple[Dict[str, Any], Any]]:
        """并行评估参数组合"""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # 提交任务
            future_to_params = {
                executor.submit(objective_function, params): params 
                for params in param_grid
            }
            
            # 收集结果
            for future in as_completed(future_to_params):
                params = future_to_params[future]
                try:
                    result = future.result()
                    results.append((params, result))
                except Exception as e:
                    logger.error(f"Error evaluating params {params}: {e}")
                    results.append((params, None))
        
        return results
    
    async def _sequential_evaluate(self, 
                                  param_grid: List[Dict[str, Any]], 
                                  objective_function: Callable) -> List[Tuple[Dict[str, Any], Any]]:
        """顺序评估参数组合"""
        results = []
        
        for params in param_grid:
            try:
                result = objective_function(params)
                results.append((params, result))
            except Exception as e:
                logger.error(f"Error evaluating params {params}: {e}")
                results.append((params, None))
        
        return results


class RandomSearchOptimizer(OptimizationAlgorithm):
    """随机搜索优化器"""
    
    async def optimize(self, 
                     param_space: Dict[str, Dict[str, Any]],
                     objective_function: Callable,
                     constraints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行随机搜索优化"""
        
        logger.info("Starting random search optimization")
        
        best_params = None
        best_score = float('-inf')
        
        for iteration in range(self.config.max_iterations):
            # 随机生成参数
            params = self._sample_random_params(param_space)
            
            try:
                # 评估参数
                result = objective_function(params)
                score = self._evaluate_objectives(result)
                
                # 更新最佳结果
                if score > best_score:
                    best_score = score
                    best_params = params
                
                self.convergence_history.append(score)
                
                # 检查收敛
                if self._check_convergence(score):
                    logger.info(f"Converged at iteration {iteration}")
                    break
                
            except Exception as e:
                logger.error(f"Error evaluating params {params}: {e}")
                continue
        
        logger.info(f"Random search completed. Best score: {best_score}")
        
        return best_params or {}
    
    def _sample_random_params(self, param_space: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """随机采样参数"""
        params = {}
        
        for param_name, param_config in param_space.items():
            param_type = param_config['type']
            min_val = param_config['min']
            max_val = param_config['max']
            
            if param_type == 'int':
                value = np.random.randint(min_val, max_val + 1)
            else:  # float
                value = np.random.uniform(min_val, max_val)
            
            params[param_name] = value
        
        return params


class BayesianOptimizer(OptimizationAlgorithm):
    """贝叶斯优化器（简化版本）"""
    
    async def optimize(self, 
                     param_space: Dict[str, Dict[str, Any]],
                     objective_function: Callable,
                     constraints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行贝叶斯优化"""
        
        logger.info("Starting Bayesian optimization (simplified)")
        
        # 简化实现：使用随机搜索 + 高斯过程近似
        best_params = None
        best_score = float('-inf')
        
        # 初始随机采样
        n_initial = min(10, self.config.max_iterations // 2)
        
        for iteration in range(self.config.max_iterations):
            if iteration < n_initial:
                # 初始随机采样
                params = self._sample_random_params(param_space)
            else:
                # 基于历史结果的智能采样（简化版本）
                params = self._intelligent_sample(param_space)
            
            try:
                result = objective_function(params)
                score = self._evaluate_objectives(result)
                
                if score > best_score:
                    best_score = score
                    best_params = params
                
                self.convergence_history.append(score)
                
                if self._check_convergence(score):
                    break
                
            except Exception as e:
                logger.error(f"Error evaluating params {params}: {e}")
                continue
        
        logger.info(f"Bayesian optimization completed. Best score: {best_score}")
        
        return best_params or {}
    
    def _sample_random_params(self, param_space: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """随机采样参数"""
        params = {}
        
        for param_name, param_config in param_space.items():
            param_type = param_config['type']
            min_val = param_config['min']
            max_val = param_config['max']
            
            if param_type == 'int':
                value = np.random.randint(min_val, max_val + 1)
            else:  # float
                value = np.random.uniform(min_val, max_val)
            
            params[param_name] = value
        
        return params
    
    def _intelligent_sample(self, param_space: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """智能采样（简化版本）"""
        # 简化实现：在历史最佳参数附近采样
        if not hasattr(self, '_best_params_history'):
            return self._sample_random_params(param_space)
        
        # 基于历史最佳参数进行扰动
        base_params = self._best_params_history[-1] if self._best_params_history else {}
        params = {}
        
        for param_name, param_config in param_space.items():
            param_type = param_config['type']
            min_val = param_config['min']
            max_val = param_config['max']
            
            if param_name in base_params:
                base_value = base_params[param_name]
                # 在基础值附近添加噪声
                noise_scale = (max_val - min_val) * 0.1
                
                if param_type == 'int':
                    noise = int(np.random.normal(0, noise_scale))
                    value = np.clip(base_value + noise, min_val, max_val)
                else:  # float
                    noise = np.random.normal(0, noise_scale)
                    value = np.clip(base_value + noise, min_val, max_val)
            else:
                # 如果没有历史值，随机采样
                if param_type == 'int':
                    value = np.random.randint(min_val, max_val + 1)
                else:  # float
                    value = np.random.uniform(min_val, max_val)
            
            params[param_name] = value
        
        return params


class StrategyOptimizer:
    """策略优化器"""
    
    def __init__(self):
        """初始化策略优化器"""
        self.algorithms = {
            'grid_search': GridSearchOptimizer,
            'random_search': RandomSearchOptimizer,
            'bayesian': BayesianOptimizer,
        }
        
        logger.info("Strategy optimizer initialized")
    
    async def optimize(self, 
                     strategy: BaseStrategy, 
                     config: OptimizationConfig,
                     backtest_function: Callable) -> Tuple[BaseStrategy, OptimizationResult]:
        """
        优化策略参数
        
        Args:
            strategy: 待优化的策略
            config: 优化配置
            backtest_function: 回测函数
            
        Returns:
            优化后的策略和优化结果
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"Starting strategy optimization with {config.algorithm}")
            
            # 获取参数空间
            param_space = strategy.get_parameter_space()
            
            if not param_space:
                logger.warning("No parameter space defined for strategy")
                return strategy, OptimizationResult({}, {}, [], 0.0, 0)
            
            # 选择优化算法
            algorithm_class = self.algorithms.get(config.algorithm)
            if algorithm_class is None:
                raise ValueError(f"Unknown optimization algorithm: {config.algorithm}")
            
            algorithm = algorithm_class(config)
            
            # 定义目标函数
            def objective_function(params: Dict[str, Any]) -> Any:
                # 创建带有新参数的策略实例
                optimized_strategy = strategy.create_optimized_version(params)
                
                # 执行回测
                result = backtest_function(optimized_strategy)
                
                return result
            
            # 执行优化
            optimal_params = await algorithm.optimize(param_space, objective_function, config.constraints)
            
            # 创建优化后的策略
            optimized_strategy = strategy.create_optimized_version(optimal_params)
            
            # 计算目标值
            objective_values = {}
            if optimal_params:
                final_result = objective_function(optimal_params)
                for objective in config.objectives:
                    if hasattr(final_result, objective.name):
                        objective_values[objective.name] = getattr(final_result, objective.name)
                    elif hasattr(final_result, 'performance_metrics'):
                        if hasattr(final_result.performance_metrics, objective.name):
                            objective_values[objective.name] = getattr(final_result.performance_metrics, objective.name)
            
            # 创建优化结果
            end_time = datetime.now()
            computation_time = (end_time - start_time).total_seconds()
            
            optimization_result = OptimizationResult(
                optimal_parameters=optimal_params,
                objective_values=objective_values,
                convergence_history=algorithm.convergence_history,
                computation_time=computation_time,
                iterations_count=algorithm.iteration_count
            )
            
            logger.info(f"Optimization completed in {computation_time:.2f} seconds")
            
            return optimized_strategy, optimization_result
            
        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            raise
    
    def create_optimization_config(self, 
                                 objectives: List[str],
                                 algorithm: str = "grid_search",
                                 max_iterations: int = 100) -> OptimizationConfig:
        """
        创建优化配置
        
        Args:
            objectives: 优化目标列表
            algorithm: 优化算法
            max_iterations: 最大迭代次数
            
        Returns:
            优化配置
        """
        objective_objects = []
        
        for obj_name in objectives:
            if obj_name in ['total_return', 'annualized_return', 'sharpe_ratio', 'calmar_ratio']:
                obj_type = 'maximize'
            elif obj_name in ['max_drawdown', 'volatility']:
                obj_type = 'minimize'
            else:
                obj_type = 'maximize'  # 默认最大化
            
            objective_objects.append(OptimizationObjective(
                name=obj_name,
                type=obj_type,
                weight=1.0
            ))
        
        return OptimizationConfig(
            objectives=objective_objects,
            algorithm=algorithm,
            max_iterations=max_iterations
        )
    
    def get_supported_algorithms(self) -> List[str]:
        """获取支持的优化算法"""
        return list(self.algorithms.keys())
    
    def get_common_objectives(self) -> List[str]:
        """获取常用的优化目标"""
        return [
            'total_return',
            'annualized_return', 
            'sharpe_ratio',
            'calmar_ratio',
            'max_drawdown',
            'volatility',
            'win_rate',
            'profit_factor'
        ]