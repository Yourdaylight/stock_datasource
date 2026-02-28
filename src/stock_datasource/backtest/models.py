"""
回测相关数据模型

定义回测配置、结果、交易记录等核心数据结构。
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Dict, List, Optional, Any, Union
import pandas as pd
import numpy as np


class TradeType(Enum):
    """交易类型"""
    BUY = "buy"
    SELL = "sell"
    SHORT = "short"
    COVER = "cover"


class TradeStatus(Enum):
    """交易状态"""
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


@dataclass
class TradingConfig:
    """交易配置"""
    initial_capital: float = 1000000.0  # 初始资金
    commission_rate: float = 0.0003  # 手续费率
    slippage_rate: float = 0.001  # 滑点率
    min_commission: float = 5.0  # 最小手续费
    max_position_size: float = 0.95  # 最大仓位比例
    allow_short: bool = False  # 是否允许做空
    margin_rate: float = 1.0  # 保证金比例


@dataclass
class BacktestConfig:
    """回测配置"""
    strategy_id: str
    symbols: List[str]
    start_date: Union[str, date, datetime]
    end_date: Union[str, date, datetime]
    trading_config: TradingConfig = field(default_factory=TradingConfig)
    benchmark: Optional[str] = None  # 基准指数
    rebalance_frequency: str = "daily"  # 再平衡频率
    
    def __post_init__(self):
        """后处理：确保日期格式正确"""
        if isinstance(self.start_date, str):
            self.start_date = pd.to_datetime(self.start_date).date()
        elif isinstance(self.start_date, datetime):
            self.start_date = self.start_date.date()
            
        if isinstance(self.end_date, str):
            self.end_date = pd.to_datetime(self.end_date).date()
        elif isinstance(self.end_date, datetime):
            self.end_date = self.end_date.date()


@dataclass
class Trade:
    """交易记录"""
    trade_id: str
    symbol: str
    trade_type: TradeType
    quantity: int
    price: float
    timestamp: datetime
    commission: float = 0.0
    slippage: float = 0.0
    status: TradeStatus = TradeStatus.PENDING
    signal_reason: str = ""
    
    @property
    def trade_value(self) -> float:
        """交易金额"""
        return abs(self.quantity * self.price)
    
    @property
    def total_cost(self) -> float:
        """总成本（包含手续费和滑点）"""
        return self.trade_value + self.commission + abs(self.slippage * self.trade_value)


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    quantity: int = 0
    avg_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    @property
    def is_long(self) -> bool:
        """是否持有多头仓位"""
        return self.quantity > 0
    
    @property
    def is_short(self) -> bool:
        """是否持有空头仓位"""
        return self.quantity < 0
    
    @property
    def is_flat(self) -> bool:
        """是否空仓"""
        return self.quantity == 0


@dataclass
class PerformanceMetrics:
    """绩效指标"""
    # 收益指标
    total_return: float = 0.0  # 总收益率
    annualized_return: float = 0.0  # 年化收益率
    excess_return: float = 0.0  # 超额收益率
    
    # 风险指标
    volatility: float = 0.0  # 波动率
    max_drawdown: float = 0.0  # 最大回撤
    max_drawdown_duration: int = 0  # 最大回撤持续期
    
    # 风险调整收益
    sharpe_ratio: float = 0.0  # 夏普比率
    sortino_ratio: float = 0.0  # 索提诺比率
    calmar_ratio: float = 0.0  # 卡玛比率
    
    # 交易统计
    total_trades: int = 0  # 总交易次数
    winning_trades: int = 0  # 盈利交易次数
    losing_trades: int = 0  # 亏损交易次数
    win_rate: float = 0.0  # 胜率
    
    # 盈亏统计
    avg_win: float = 0.0  # 平均盈利
    avg_loss: float = 0.0  # 平均亏损
    profit_factor: float = 0.0  # 盈利因子
    
    # 其他指标
    beta: float = 0.0  # 贝塔系数
    alpha: float = 0.0  # 阿尔法系数
    information_ratio: float = 0.0  # 信息比率
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'total_return': self.total_return,
            'annualized_return': self.annualized_return,
            'excess_return': self.excess_return,
            'volatility': self.volatility,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_duration': self.max_drawdown_duration,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'calmar_ratio': self.calmar_ratio,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'profit_factor': self.profit_factor,
            'beta': self.beta,
            'alpha': self.alpha,
            'information_ratio': self.information_ratio
        }


@dataclass
class RiskMetrics:
    """风险指标"""
    var_95: float = 0.0  # 95% VaR
    var_99: float = 0.0  # 99% VaR
    cvar_95: float = 0.0  # 95% CVaR
    cvar_99: float = 0.0  # 99% CVaR
    
    # 尾部风险
    skewness: float = 0.0  # 偏度
    kurtosis: float = 0.0  # 峰度
    tail_ratio: float = 0.0  # 尾部比率
    
    # 下行风险
    downside_deviation: float = 0.0  # 下行标准差
    upside_deviation: float = 0.0  # 上行标准差
    
    # 回撤分析
    avg_drawdown: float = 0.0  # 平均回撤
    drawdown_frequency: float = 0.0  # 回撤频率
    recovery_factor: float = 0.0  # 恢复因子
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'var_95': self.var_95,
            'var_99': self.var_99,
            'cvar_95': self.cvar_95,
            'cvar_99': self.cvar_99,
            'skewness': self.skewness,
            'kurtosis': self.kurtosis,
            'tail_ratio': self.tail_ratio,
            'downside_deviation': self.downside_deviation,
            'upside_deviation': self.upside_deviation,
            'avg_drawdown': self.avg_drawdown,
            'drawdown_frequency': self.drawdown_frequency,
            'recovery_factor': self.recovery_factor
        }


@dataclass
class BacktestResult:
    """回测结果"""
    strategy_id: str
    config: BacktestConfig
    performance_metrics: PerformanceMetrics
    risk_metrics: RiskMetrics
    trades: List[Trade]
    positions: Dict[str, Position]
    
    # 时间序列数据
    equity_curve: pd.Series = field(default_factory=pd.Series)
    drawdown_series: pd.Series = field(default_factory=pd.Series)
    returns_series: pd.Series = field(default_factory=pd.Series)
    
    # 基准对比
    benchmark_returns: Optional[pd.Series] = None
    
    # 执行信息
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    execution_time: float = 0.0  # 执行时间（秒）
    
    def __post_init__(self):
        """后处理"""
        if self.end_time is None:
            self.end_time = datetime.now()
            self.execution_time = (self.end_time - self.start_time).total_seconds()
    
    @property
    def total_pnl(self) -> float:
        """总盈亏"""
        return sum(pos.realized_pnl + pos.unrealized_pnl for pos in self.positions.values())
    
    @property
    def final_portfolio_value(self) -> float:
        """最终组合价值"""
        if len(self.equity_curve) > 0:
            return self.equity_curve.iloc[-1]
        return self.config.trading_config.initial_capital
    
    def get_trade_summary(self) -> Dict[str, Any]:
        """获取交易摘要"""
        if not self.trades:
            return {}
        
        filled_trades = [t for t in self.trades if t.status == TradeStatus.FILLED]
        
        return {
            'total_trades': len(filled_trades),
            'buy_trades': len([t for t in filled_trades if t.trade_type == TradeType.BUY]),
            'sell_trades': len([t for t in filled_trades if t.trade_type == TradeType.SELL]),
            'total_commission': sum(t.commission for t in filled_trades),
            'total_slippage': sum(abs(t.slippage * t.trade_value) for t in filled_trades),
            'avg_trade_size': np.mean([t.trade_value for t in filled_trades]) if filled_trades else 0
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            'strategy_id': self.strategy_id,
            'config': {
                'symbols': self.config.symbols,
                'start_date': self.config.start_date.isoformat(),
                'end_date': self.config.end_date.isoformat(),
                'initial_capital': self.config.trading_config.initial_capital
            },
            'performance_metrics': self.performance_metrics.to_dict(),
            'risk_metrics': self.risk_metrics.to_dict(),
            'trade_summary': self.get_trade_summary(),
            'final_portfolio_value': self.final_portfolio_value,
            'total_pnl': self.total_pnl,
            'execution_time': self.execution_time,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            
            # 交易记录
            'trades': [
                {
                    'trade_id': trade.trade_id,
                    'symbol': trade.symbol,
                    'side': trade.trade_type.value,
                    'quantity': trade.quantity,
                    'price': trade.price,
                    'amount': trade.trade_value,
                    'commission': trade.commission,
                    'timestamp': trade.timestamp.isoformat(),
                    'signal_reason': trade.signal_reason
                }
                for trade in self.trades
            ]
        }
        
        # 时间序列数据 - 转换为图表友好的格式
        if not self.equity_curve.empty:
            result['equity_curve'] = {
                date.strftime('%Y-%m-%d'): float(value)
                for date, value in self.equity_curve.items()
            }
        else:
            result['equity_curve'] = {}
            
        if not self.drawdown_series.empty:
            result['drawdown_series'] = {
                date.strftime('%Y-%m-%d'): float(value)
                for date, value in self.drawdown_series.items()
            }
        else:
            result['drawdown_series'] = {}
            
        if not self.returns_series.empty:
            result['daily_returns'] = {
                date.strftime('%Y-%m-%d'): float(value)
                for date, value in self.returns_series.items()
            }
        else:
            result['daily_returns'] = {}
            
        # 基准数据
        if self.benchmark_returns is not None and not self.benchmark_returns.empty:
            result['benchmark_curve'] = {
                date.strftime('%Y-%m-%d'): float(value)
                for date, value in self.benchmark_returns.items()
            }
        else:
            result['benchmark_curve'] = {}
            
        return result


@dataclass
class IntelligentBacktestConfig(BacktestConfig):
    """智能回测配置"""
    enable_optimization: bool = False  # 是否启用参数优化
    enable_robustness_test: bool = False  # 是否启用鲁棒性测试
    enable_ai_insights: bool = True  # 是否启用AI洞察
    
    # 优化配置
    optimization_config: Optional[Dict[str, Any]] = None
    
    # 鲁棒性测试配置
    robustness_config: Optional[Dict[str, Any]] = None


@dataclass
class OptimizationResult:
    """优化结果"""
    optimal_parameters: Dict[str, Any]
    objective_values: Dict[str, float]
    convergence_history: List[Dict[str, float]]
    computation_time: float
    iterations_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'optimal_parameters': self.optimal_parameters,
            'objective_values': self.objective_values,
            'convergence_history': self.convergence_history,
            'computation_time': self.computation_time,
            'iterations_count': self.iterations_count
        }


@dataclass
class IntelligentBacktestResult(BacktestResult):
    """智能回测结果"""
    optimized_result: Optional[BacktestResult] = None
    robustness_results: Optional[List[BacktestResult]] = None
    ai_insights: Optional[Dict[str, Any]] = None
    optimization_result: Optional[OptimizationResult] = None
    
    def get_best_result(self) -> BacktestResult:
        """获取最佳回测结果"""
        if self.optimized_result and self.optimized_result.performance_metrics.sharpe_ratio > self.performance_metrics.sharpe_ratio:
            return self.optimized_result
        return self