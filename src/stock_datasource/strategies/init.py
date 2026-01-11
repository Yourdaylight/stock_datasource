"""
策略系统初始化模块
"""
from .registry import StrategyRegistry
from .builtin.ma_strategy import MAStrategy
from .builtin.macd_strategy import MACDStrategy
from .builtin.rsi_strategy import RSIStrategy
from .builtin.kdj_strategy import KDJStrategy
from .builtin.bollinger_strategy import BollingerBandsStrategy
from .builtin.dual_ma_strategy import DualMAStrategy
from .builtin.turtle_strategy import TurtleStrategy


def initialize_builtin_strategies():
    """初始化所有内置策略"""
    registry = StrategyRegistry()
    
    # 注册所有内置策略
    strategies = [
        ("ma_strategy", MAStrategy),
        ("macd_strategy", MACDStrategy),
        ("rsi_strategy", RSIStrategy),
        ("kdj_strategy", KDJStrategy),
        ("bollinger_strategy", BollingerBandsStrategy),
        ("dual_ma_strategy", DualMAStrategy),
        ("turtle_strategy", TurtleStrategy),
    ]
    
    for name, strategy_class in strategies:
        try:
            registry.register_strategy(name, strategy_class, overwrite=True)
            print(f"✓ 已注册策略: {name}")
        except Exception as e:
            print(f"✗ 注册策略失败 {name}: {e}")
    
    print(f"策略初始化完成，共注册 {len(strategies)} 个内置策略")
    return registry


def get_strategy_registry():
    """获取策略注册中心实例"""
    return _registry


# 在模块导入时自动初始化
_registry = initialize_builtin_strategies()