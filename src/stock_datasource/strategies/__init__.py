"""
智能策略系统核心模块

提供统一的策略框架，包括：
- 策略基类和注册中心
- 内置策略库
- AI策略生成
- 策略优化和回测
"""

from .base import BaseStrategy, RiskLevel, StrategyCategory, StrategyMetadata
from .builtin import *

# 延迟导入以避免依赖问题
# from .ai_generator import AIStrategyGenerator
# from .optimizer import StrategyOptimizer
from .init import get_strategy_registry, initialize_builtin_strategies
from .registry import StrategyRegistry


def get_ai_generator():
    """延迟导入AI生成器"""
    from .ai_generator import AIStrategyGenerator

    return AIStrategyGenerator


def get_optimizer():
    """延迟导入优化器"""
    from .optimizer import StrategyOptimizer

    return StrategyOptimizer


__all__ = [
    "BaseStrategy",
    "RiskLevel",
    "StrategyCategory",
    "StrategyMetadata",
    "StrategyRegistry",
    "get_ai_generator",
    "get_optimizer",
    "get_strategy_registry",
    "initialize_builtin_strategies",
]
