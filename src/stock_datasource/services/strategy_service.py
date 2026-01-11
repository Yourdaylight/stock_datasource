"""
策略管理服务
"""
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date
import pandas as pd

from ..strategies.registry import StrategyRegistry
from ..strategies.base import BaseStrategy
from ..strategies.ai_generator import AIStrategyGenerator
from ..strategies.optimizer import StrategyOptimizer
from ..backtest.engine import IntelligentBacktestEngine
from ..backtest.models import BacktestConfig, BacktestResult
from ..data.stock_data_provider import StockDataProvider


class StrategyService:
    """策略管理服务"""
    
    def __init__(self):
        self.registry = StrategyRegistry()
        self.ai_generator = AIStrategyGenerator()
        self.optimizer = StrategyOptimizer()
        self.backtest_engine = IntelligentBacktestEngine()
        self.data_provider = StockDataProvider()
    
    async def get_available_strategies(self) -> List[Dict[str, Any]]:
        """获取所有可用策略"""
        strategies = []
        
        for name, strategy_class in self.registry.get_all_strategies().items():
            metadata = strategy_class.get_metadata()
            strategies.append({
                "name": name,
                "display_name": metadata.display_name,
                "description": metadata.description,
                "category": metadata.category,
                "parameters": [param.dict() for param in metadata.parameters],
                "risk_level": metadata.risk_level,
                "time_frames": metadata.time_frames
            })
        
        return strategies
    
    async def generate_ai_strategy(
        self,
        description: str,
        market_type: str = "stock",
        risk_level: str = "medium",
        time_frame: str = "daily"
    ) -> str:
        """生成AI策略"""
        return await self.ai_generator.generate_strategy(
            description=description,
            market_type=market_type,
            risk_level=risk_level,
            time_frame=time_frame
        )
    
    async def validate_strategy_code(self, strategy_code: str) -> Dict[str, Any]:
        """验证策略代码"""
        try:
            # 尝试编译代码
            compile(strategy_code, '<string>', 'exec')
            
            # 执行代码并检查是否定义了策略类
            namespace = {}
            exec(strategy_code, namespace)
            
            # 查找继承自BaseStrategy的类
            strategy_classes = []
            for name, obj in namespace.items():
                if (isinstance(obj, type) and 
                    issubclass(obj, BaseStrategy) and 
                    obj != BaseStrategy):
                    strategy_classes.append(name)
            
            if not strategy_classes:
                return {
                    "valid": False,
                    "error": "未找到有效的策略类（必须继承自BaseStrategy）"
                }
            
            return {
                "valid": True,
                "strategy_classes": strategy_classes,
                "message": "策略代码验证通过"
            }
            
        except SyntaxError as e:
            return {
                "valid": False,
                "error": f"语法错误: {str(e)}"
            }
        except Exception as e:
            return {
                "valid": False,
                "error": f"验证失败: {str(e)}"
            }
    
    async def run_backtest(
        self,
        strategy_name: str,
        symbol: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
        parameters: Dict[str, Any] = None
    ) -> BacktestResult:
        """运行策略回测"""
        if parameters is None:
            parameters = {}
        
        # 获取策略类
        strategy_class = self.registry.get_strategy(strategy_name)
        if not strategy_class:
            raise ValueError(f"策略 {strategy_name} 不存在")
        
        # 创建策略实例
        strategy = strategy_class(**parameters)
        
        # 创建回测配置
        config = BacktestConfig(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital
        )
        
        # 运行回测
        return await self.backtest_engine.run_backtest(strategy, config)
    
    async def optimize_strategy(
        self,
        strategy_name: str,
        symbol: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
        optimization_target: str = "total_return",
        max_iterations: int = 100
    ) -> Tuple[Dict[str, Any], Optional[BacktestResult]]:
        """优化策略参数"""
        # 获取策略类
        strategy_class = self.registry.get_strategy(strategy_name)
        if not strategy_class:
            raise ValueError(f"策略 {strategy_name} 不存在")
        
        # 运行优化
        return await self.optimizer.optimize_strategy(
            strategy_class=strategy_class,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            optimization_target=optimization_target,
            max_iterations=max_iterations
        )
    
    async def get_strategy_metadata(self, strategy_name: str) -> Dict[str, Any]:
        """获取策略元数据"""
        strategy_class = self.registry.get_strategy(strategy_name)
        if not strategy_class:
            raise ValueError(f"策略 {strategy_name} 不存在")
        
        metadata = strategy_class.get_metadata()
        return {
            "name": strategy_name,
            "display_name": metadata.display_name,
            "description": metadata.description,
            "category": metadata.category,
            "parameters": [param.dict() for param in metadata.parameters],
            "risk_level": metadata.risk_level,
            "time_frames": metadata.time_frames
        }
    
    async def get_market_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1d"
    ) -> pd.DataFrame:
        """获取市场数据"""
        return await self.data_provider.get_stock_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval
        )
    
    async def register_custom_strategy(
        self,
        name: str,
        strategy_code: str,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """注册自定义策略"""
        try:
            # 验证策略代码
            validation_result = await self.validate_strategy_code(strategy_code)
            if not validation_result["valid"]:
                return validation_result
            
            # 执行代码并获取策略类
            namespace = {}
            exec(strategy_code, namespace)
            
            # 查找策略类
            strategy_class = None
            for obj_name, obj in namespace.items():
                if (isinstance(obj, type) and 
                    issubclass(obj, BaseStrategy) and 
                    obj != BaseStrategy):
                    strategy_class = obj
                    break
            
            if not strategy_class:
                return {
                    "success": False,
                    "error": "未找到有效的策略类"
                }
            
            # 注册策略
            self.registry.register_strategy(name, strategy_class, overwrite=overwrite)
            
            return {
                "success": True,
                "message": f"策略 {name} 注册成功"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"注册失败: {str(e)}"
            }
    
    async def unregister_strategy(self, name: str) -> Dict[str, Any]:
        """注销策略"""
        try:
            self.registry.unregister_strategy(name)
            return {
                "success": True,
                "message": f"策略 {name} 注销成功"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"注销失败: {str(e)}"
            }
    
    async def get_strategy_performance_summary(
        self,
        strategy_name: str,
        symbols: List[str],
        start_date: str,
        end_date: str,
        parameters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """获取策略在多个标的上的表现摘要"""
        if parameters is None:
            parameters = {}
        
        results = {}
        summary_stats = {
            "total_symbols": len(symbols),
            "successful_backtests": 0,
            "failed_backtests": 0,
            "avg_total_return": 0.0,
            "avg_sharpe_ratio": 0.0,
            "avg_max_drawdown": 0.0,
            "best_symbol": None,
            "worst_symbol": None,
            "best_return": float('-inf'),
            "worst_return": float('inf')
        }
        
        for symbol in symbols:
            try:
                result = await self.run_backtest(
                    strategy_name=strategy_name,
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    parameters=parameters
                )
                
                results[symbol] = {
                    "success": True,
                    "result": result.dict()
                }
                
                # 更新统计信息
                summary_stats["successful_backtests"] += 1
                summary_stats["avg_total_return"] += result.total_return
                summary_stats["avg_sharpe_ratio"] += result.sharpe_ratio
                summary_stats["avg_max_drawdown"] += result.max_drawdown
                
                # 更新最佳/最差表现
                if result.total_return > summary_stats["best_return"]:
                    summary_stats["best_return"] = result.total_return
                    summary_stats["best_symbol"] = symbol
                
                if result.total_return < summary_stats["worst_return"]:
                    summary_stats["worst_return"] = result.total_return
                    summary_stats["worst_symbol"] = symbol
                
            except Exception as e:
                results[symbol] = {
                    "success": False,
                    "error": str(e)
                }
                summary_stats["failed_backtests"] += 1
        
        # 计算平均值
        if summary_stats["successful_backtests"] > 0:
            summary_stats["avg_total_return"] /= summary_stats["successful_backtests"]
            summary_stats["avg_sharpe_ratio"] /= summary_stats["successful_backtests"]
            summary_stats["avg_max_drawdown"] /= summary_stats["successful_backtests"]
        
        return {
            "summary": summary_stats,
            "detailed_results": results
        }