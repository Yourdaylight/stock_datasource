"""
智能回测引擎模块

提供完整的策略回测功能，包括：
- 智能回测引擎
- 绩效分析器
- 风险指标计算
- 交易模拟器
"""

from .engine import IntelligentBacktestEngine
from .models import (
    BacktestConfig, BacktestResult, PerformanceMetrics, 
    RiskMetrics, Trade, TradeType, TradeStatus
)
from .analyzer import PerformanceAnalyzer
from .simulator import TradingSimulator

__all__ = [
    "IntelligentBacktestEngine",
    "BacktestConfig",
    "BacktestResult", 
    "PerformanceMetrics",
    "RiskMetrics",
    "Trade",
    "TradeType",
    "TradeStatus",
    "PerformanceAnalyzer",
    "TradingSimulator",
]