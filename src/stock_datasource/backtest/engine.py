"""
智能回测引擎

提供完整的策略回测功能，包括：
- 策略执行
- 交易模拟
- 绩效分析
- 智能优化
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date
import pandas as pd
import numpy as np
import asyncio

from .models import (
    BacktestConfig, BacktestResult, IntelligentBacktestConfig, 
    IntelligentBacktestResult, TradingConfig
)
from .simulator import TradingSimulator
from .analyzer import PerformanceAnalyzer
from ..strategies.base import BaseStrategy, TradingSignal
from ..strategies.init import get_strategy_registry

logger = logging.getLogger(__name__)


class DataService:
    """数据服务接口（简化版本）"""
    
    async def get_historical_data(self, 
                                symbols: List[str], 
                                start_date: date, 
                                end_date: date) -> Dict[str, pd.DataFrame]:
        """
        获取历史数据
        
        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            股票历史数据字典
        """
        # 这里应该连接到实际的数据源
        # 暂时返回模拟数据
        data = {}
        
        for symbol in symbols:
            # 生成模拟数据
            date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            
            # 模拟价格走势
            np.random.seed(hash(symbol) % 2**32)  # 确保每个股票的数据一致
            returns = np.random.normal(0.001, 0.02, len(date_range))
            
            prices = [100.0]  # 起始价格
            for ret in returns[1:]:
                prices.append(prices[-1] * (1 + ret))
            
            df = pd.DataFrame({
                'timestamp': date_range,
                'open': prices,
                'high': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
                'low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
                'close': prices,
                'volume': np.random.randint(100000, 1000000, len(date_range)),
                'symbol': symbol
            })
            
            data[symbol] = df
        
        logger.info(f"Retrieved historical data for {len(symbols)} symbols")
        return data


class IntelligentBacktestEngine:
    """智能回测引擎"""
    
    def __init__(self, data_service: Optional[DataService] = None):
        """
        初始化智能回测引擎
        
        Args:
            data_service: 数据服务实例
        """
        self.data_service = data_service or DataService()
        self.performance_analyzer = PerformanceAnalyzer()
        
        logger.info("Intelligent backtest engine initialized")
    
    async def run_backtest(self, config: BacktestConfig) -> BacktestResult:
        """
        执行基础回测
        
        Args:
            config: 回测配置
            
        Returns:
            回测结果
        """
        start_time = datetime.now()
        
        try:
            # 获取策略实例
            strategy = get_strategy_registry().get_strategy(config.strategy_id)
            if strategy is None:
                raise ValueError(f"Strategy not found: {config.strategy_id}")
            
            # 获取历史数据
            historical_data = await self.data_service.get_historical_data(
                config.symbols, config.start_date, config.end_date
            )
            
            # 初始化交易模拟器
            simulator = TradingSimulator(config.trading_config)
            
            # 执行回测
            result = await self._execute_backtest(strategy, historical_data, simulator, config)
            
            # 计算执行时间
            end_time = datetime.now()
            result.start_time = start_time
            result.end_time = end_time
            result.execution_time = (end_time - start_time).total_seconds()
            
            logger.info(f"Backtest completed in {result.execution_time:.2f} seconds")
            return result
            
        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            raise
    
    async def run_intelligent_backtest(self, config: IntelligentBacktestConfig) -> IntelligentBacktestResult:
        """
        执行智能回测
        
        Args:
            config: 智能回测配置
            
        Returns:
            智能回测结果
        """
        try:
            # 执行基础回测
            base_result = await self.run_backtest(config)
            
            # 创建智能回测结果
            intelligent_result = IntelligentBacktestResult(
                strategy_id=base_result.strategy_id,
                config=base_result.config,
                performance_metrics=base_result.performance_metrics,
                risk_metrics=base_result.risk_metrics,
                trades=base_result.trades,
                positions=base_result.positions,
                equity_curve=base_result.equity_curve,
                drawdown_series=base_result.drawdown_series,
                returns_series=base_result.returns_series,
                base_result=base_result
            )
            
            # 参数优化
            if config.enable_optimization and config.optimization_config:
                logger.info("Starting parameter optimization...")
                optimized_result = await self._run_optimization(config)
                intelligent_result.optimized_result = optimized_result
            
            # 鲁棒性测试
            if config.enable_robustness_test and config.robustness_config:
                logger.info("Starting robustness test...")
                robustness_results = await self._run_robustness_test(config)
                intelligent_result.robustness_results = robustness_results
            
            # AI洞察生成
            if config.enable_ai_insights:
                logger.info("Generating AI insights...")
                ai_insights = await self._generate_ai_insights(intelligent_result)
                intelligent_result.ai_insights = ai_insights
            
            logger.info("Intelligent backtest completed successfully")
            return intelligent_result
            
        except Exception as e:
            logger.error(f"Intelligent backtest failed: {e}")
            raise
    
    async def _execute_backtest(self, 
                              strategy: BaseStrategy,
                              historical_data: Dict[str, pd.DataFrame],
                              simulator: TradingSimulator,
                              config: BacktestConfig) -> BacktestResult:
        """执行回测逻辑"""
        
        # 合并所有股票数据，按时间排序
        all_data = []
        for symbol, data in historical_data.items():
            data = data.copy()
            data['symbol'] = symbol
            all_data.append(data)
        
        if not all_data:
            raise ValueError("No historical data available")
        
        # 合并数据并按时间排序
        combined_data = pd.concat(all_data, ignore_index=True)
        combined_data = combined_data.sort_values('timestamp')
        
        # 按时间逐步执行回测
        unique_dates = combined_data['timestamp'].dt.date.unique()
        last_date = unique_dates[-1] if len(unique_dates) > 0 else None
        
        for current_date in unique_dates:
            # 获取当前日期的数据
            daily_data = combined_data[combined_data['timestamp'].dt.date == current_date]
            
            # 为每个股票生成信号
            for symbol in config.symbols:
                symbol_data = historical_data[symbol]
                symbol_daily = symbol_data[symbol_data['timestamp'].dt.date <= current_date]
                
                if len(symbol_daily) < 2:  # 需要足够的历史数据
                    continue
                
                # 生成交易信号
                try:
                    signals = strategy.generate_signals(symbol_daily)
                    
                    # 执行当天的信号
                    for signal in signals:
                        if signal.timestamp.date() == current_date:
                            # 获取当天的市场数据
                            market_data = daily_data[daily_data['symbol'] == symbol]
                            if not market_data.empty:
                                trade = simulator.execute_signal(signal, market_data.iloc[-1])
                                
                except Exception as e:
                    logger.warning(f"Error generating signals for {symbol} on {current_date}: {e}")
                    continue
            
            # 更新持仓市值
            current_market_data = {}
            for symbol in config.symbols:
                symbol_daily = daily_data[daily_data['symbol'] == symbol]
                if not symbol_daily.empty:
                    current_market_data[symbol] = symbol_daily.iloc[-1]
            
            if last_date is not None and current_date == last_date:
                simulator.close_all_positions(
                    current_market_data,
                    timestamp=pd.to_datetime(current_date),
                    reason="回测结束强制平仓"
                )

            simulator.update_positions(current_market_data)
        
        # 分析绩效
        equity_curve = simulator.get_equity_curve()
        if len(equity_curve) == len(unique_dates):
            equity_curve.index = pd.to_datetime(list(unique_dates))
        returns_series = equity_curve.pct_change().fillna(0)

        performance_metrics, risk_metrics = self.performance_analyzer.analyze(
            equity_curve, simulator.trades
        )
        
        # 创建回测结果
        result = BacktestResult(
            strategy_id=config.strategy_id,
            config=config,
            performance_metrics=performance_metrics,
            risk_metrics=risk_metrics,
            trades=simulator.trades,
            positions=simulator.positions,
            equity_curve=equity_curve,
            returns_series=returns_series
        )
        
        # 计算回撤序列
        if len(equity_curve) > 0:
            peak = equity_curve.expanding().max()
            result.drawdown_series = (equity_curve - peak) / peak
        
        return result
    
    async def _run_optimization(self, config: IntelligentBacktestConfig) -> Optional[BacktestResult]:
        """运行参数优化"""
        # 这里应该实现参数优化逻辑
        # 暂时返回None，表示优化功能待实现
        logger.info("Parameter optimization not implemented yet")
        return None
    
    async def _run_robustness_test(self, config: IntelligentBacktestConfig) -> Optional[List[BacktestResult]]:
        """运行鲁棒性测试"""
        # 这里应该实现鲁棒性测试逻辑
        # 暂时返回None，表示鲁棒性测试功能待实现
        logger.info("Robustness test not implemented yet")
        return None
    
    async def _generate_ai_insights(self, result: IntelligentBacktestResult) -> Dict[str, Any]:
        """生成AI洞察"""
        # 这里应该调用AI服务生成洞察
        # 暂时返回基础的统计洞察
        
        insights = {
            'summary': self._generate_performance_summary(result.base_result),
            'risk_analysis': self._generate_risk_analysis(result.base_result),
            'recommendations': self._generate_recommendations(result.base_result)
        }
        
        return insights
    
    def _generate_performance_summary(self, result: BacktestResult) -> str:
        """生成绩效摘要"""
        metrics = result.performance_metrics
        
        summary = f"""
策略在回测期间表现{'优秀' if metrics.sharpe_ratio > 1.0 else '一般' if metrics.sharpe_ratio > 0.5 else '较差'}。

关键指标：
- 总收益率: {metrics.total_return:.2%}
- 年化收益率: {metrics.annualized_return:.2%}
- 最大回撤: {metrics.max_drawdown:.2%}
- 夏普比率: {metrics.sharpe_ratio:.2f}
- 胜率: {metrics.win_rate:.2%}
        """.strip()
        
        return summary
    
    def _generate_risk_analysis(self, result: BacktestResult) -> str:
        """生成风险分析"""
        risk_metrics = result.risk_metrics
        performance_metrics = result.performance_metrics
        
        risk_level = "低"
        if performance_metrics.max_drawdown > 0.2:
            risk_level = "高"
        elif performance_metrics.max_drawdown > 0.1:
            risk_level = "中"
        
        analysis = f"""
策略风险水平: {risk_level}

风险特征：
- 最大回撤: {performance_metrics.max_drawdown:.2%}
- 波动率: {performance_metrics.volatility:.2%}
- VaR(95%): {risk_metrics.var_95:.2%}
- 偏度: {risk_metrics.skewness:.2f}
        """.strip()
        
        return analysis
    
    def _generate_recommendations(self, result: BacktestResult) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        metrics = result.performance_metrics
        
        if metrics.max_drawdown > 0.15:
            recommendations.append("建议加强风险控制，设置更严格的止损条件")
        
        if metrics.win_rate < 0.4:
            recommendations.append("胜率较低，建议优化入场时机或信号过滤条件")
        
        if metrics.sharpe_ratio < 0.5:
            recommendations.append("风险调整收益较低，建议重新评估策略参数")
        
        if metrics.total_trades < 10:
            recommendations.append("交易次数较少，可能错过了一些机会")
        elif metrics.total_trades > 100:
            recommendations.append("交易过于频繁，建议增加信号过滤条件")
        
        if not recommendations:
            recommendations.append("策略表现良好，建议继续监控并适时调整")
        
        return recommendations
    
    def get_supported_strategies(self) -> List[Dict[str, Any]]:
        """获取支持的策略列表"""
        return strategy_registry.list_strategies()
    
    def validate_config(self, config: BacktestConfig) -> List[str]:
        """验证回测配置"""
        errors = []
        
        # 检查策略是否存在
        if not get_strategy_registry().validate_strategy_id(config.strategy_id):
            errors.append(f"Strategy not found: {config.strategy_id}")
        
        # 检查日期范围
        if config.start_date >= config.end_date:
            errors.append("Start date must be before end date")
        
        # 检查股票代码
        if not config.symbols:
            errors.append("At least one symbol is required")
        
        # 检查交易配置
        if config.trading_config.initial_capital <= 0:
            errors.append("Initial capital must be positive")
        
        if config.trading_config.commission_rate < 0:
            errors.append("Commission rate cannot be negative")
        
        return errors