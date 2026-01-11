"""
内置策略库

包含经典的技术分析策略实现：
- 移动平均策略 (MA)
- MACD策略
- RSI策略  
- KDJ策略
- 布林带策略 (Bollinger Bands)
- 双均线策略 (Dual MA)
- 海龟交易策略 (Turtle)
"""

from .ma_strategy import MAStrategy
from .macd_strategy import MACDStrategy
from .rsi_strategy import RSIStrategy
from .kdj_strategy import KDJStrategy
from .bollinger_strategy import BollingerBandsStrategy
from .dual_ma_strategy import DualMAStrategy
from .turtle_strategy import TurtleStrategy

# 所有内置策略类
BUILTIN_STRATEGIES = [
    MAStrategy,
    MACDStrategy,
    RSIStrategy,
    KDJStrategy,
    BollingerBandsStrategy,
    DualMAStrategy,
    TurtleStrategy,
]

__all__ = [
    "MAStrategy",
    "MACDStrategy", 
    "RSIStrategy",
    "KDJStrategy",
    "BollingerBandsStrategy",
    "DualMAStrategy",
    "TurtleStrategy",
    "BUILTIN_STRATEGIES",
]