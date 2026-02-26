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
- Z-Score移动平均平稳化策略 (Z-Score MA Stationary)
- 自适应突破跟踪策略 (Adaptive Breakout Follow)
"""

from .ma_strategy import MAStrategy
from .macd_strategy import MACDStrategy
from .rsi_strategy import RSIStrategy
from .kdj_strategy import KDJStrategy
from .bollinger_strategy import BollingerBandsStrategy
from .dual_ma_strategy import DualMAStrategy
from .turtle_strategy import TurtleStrategy
from .zscore_ma_stationary_strategy import ZScoreMAStationaryStrategy
from .adaptive_breakout_follow_strategy import AdaptiveBreakoutFollowStrategy

# 所有内置策略类
BUILTIN_STRATEGIES = [
    MAStrategy,
    MACDStrategy,
    RSIStrategy,
    KDJStrategy,
    BollingerBandsStrategy,
    DualMAStrategy,
    TurtleStrategy,
    ZScoreMAStationaryStrategy,
    AdaptiveBreakoutFollowStrategy,
]

__all__ = [
    "MAStrategy",
    "MACDStrategy", 
    "RSIStrategy",
    "KDJStrategy",
    "BollingerBandsStrategy",
    "DualMAStrategy",
    "TurtleStrategy",
    "ZScoreMAStationaryStrategy",
    "AdaptiveBreakoutFollowStrategy",
    "BUILTIN_STRATEGIES",
]