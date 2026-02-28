"""Backtest module router."""

from fastapi import APIRouter, Query, HTTPException
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel
from datetime import datetime
import logging

from ...backtest.models import TradeType, TradeStatus

logger = logging.getLogger(__name__)

router = APIRouter()

_BACKTEST_HISTORY: List["BacktestResult"] = []
_MAX_HISTORY_SIZE = 100


def _calculate_trade_stats(trades: List[Any]) -> Tuple[int, int, int, float, float, float, float]:
    """计算已完成交易的统计指标"""
    filled_trades = [t for t in trades if t.status == TradeStatus.FILLED]
    pnls: List[float] = []
    positions: Dict[str, Tuple[int, float]] = {}

    for trade in filled_trades:
        symbol = trade.symbol
        if symbol not in positions:
            positions[symbol] = (0, 0.0)

        current_qty, current_avg_price = positions[symbol]

        if trade.trade_type == TradeType.BUY:
            new_qty = current_qty + trade.quantity
            if new_qty > 0:
                new_avg_price = ((current_qty * current_avg_price) + (trade.quantity * trade.price)) / new_qty
            else:
                new_avg_price = trade.price
            positions[symbol] = (new_qty, new_avg_price)

        elif trade.trade_type == TradeType.SELL:
            if current_qty >= trade.quantity:
                cost_basis = trade.quantity * current_avg_price
                proceeds = trade.quantity * trade.price - trade.commission
                pnl = float(proceeds - cost_basis)
                pnls.append(pnl)

                new_qty = current_qty - trade.quantity
                positions[symbol] = (new_qty, current_avg_price)

    if not pnls:
        return 0, 0, 0, 0.0, 0.0, 0.0, 0.0

    winning_trades = [pnl for pnl in pnls if pnl > 0]
    losing_trades = [pnl for pnl in pnls if pnl < 0]

    total_trades = len(pnls)
    win_count = len(winning_trades)
    loss_count = len(losing_trades)
    win_rate = win_count / total_trades if total_trades > 0 else 0.0
    avg_win = float(sum(winning_trades) / len(winning_trades)) if winning_trades else 0.0
    avg_loss = float(abs(sum(losing_trades) / len(losing_trades))) if losing_trades else 0.0
    profit_factor = (sum(winning_trades) / abs(sum(losing_trades))) if losing_trades else 0.0

    return total_trades, win_count, loss_count, win_rate, avg_win, avg_loss, float(profit_factor)


class StrategyParam(BaseModel):
    name: str
    type: str
    default: Any
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: str


class Strategy(BaseModel):
    id: str
    name: str
    description: str
    category: str
    params: List[StrategyParam]


class BacktestRequest(BaseModel):
    strategy_id: str
    ts_codes: List[str]
    start_date: str
    end_date: str
    initial_capital: float = 100000
    params: Dict[str, Any] = {}


class Trade(BaseModel):
    date: str
    direction: str
    price: float
    quantity: int
    amount: float
    signal_reason: str


class EquityPoint(BaseModel):
    date: str
    value: float


class BacktestResult(BaseModel):
    task_id: str
    strategy_name: str
    ts_codes: List[str]
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    annual_return: float
    excess_return: float = 0.0
    volatility: float = 0.0
    max_drawdown: float
    max_drawdown_duration: int = 0
    sharpe_ratio: float
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    information_ratio: float = 0.0
    alpha: float = 0.0
    beta: float = 0.0
    win_rate: float
    trade_count: int
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0
    var_99: float = 0.0
    cvar_99: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0
    trades: List[Trade] = []
    equity_curve: List[EquityPoint] = []
    drawdown_series: Dict[str, float] = {}
    daily_returns: Dict[str, float] = {}
    benchmark_curve: Dict[str, float] = {}
    created_at: str


@router.get("/strategies", response_model=List[Strategy])
async def get_strategies():
    """Get available strategies."""
    try:
        # 导入策略注册表
        from ...strategies.init import get_strategy_registry
        
        registry = get_strategy_registry()
        strategies = []
        
        for strategy_id, strategy_info in registry._strategies.items():
            metadata = strategy_info.metadata
            
            # 获取策略参数
            strategy_class = registry.get_strategy_class(strategy_id)
            if strategy_class:
                param_schema = strategy_class().get_parameter_schema()
                params = [
                    StrategyParam(
                        name=param.name,
                        type=param.type,
                        default=param.default,
                        min_value=param.min_value,
                        max_value=param.max_value,
                        description=param.description
                    )
                    for param in param_schema
                ]
            else:
                params = []
            
            strategies.append(Strategy(
                id=metadata.id,
                name=metadata.name,
                description=metadata.description,
                category=metadata.category.value,
                params=params
            ))
        
        logger.info(f"返回 {len(strategies)} 个策略给回测模块")
        return strategies
        
    except Exception as e:
        logger.error(f"获取策略列表失败: {e}")
        # 如果出错，返回备用的硬编码策略
        return [
            Strategy(
                id="ma_strategy",
                name="均线策略",
                description="基于短期和长期均线交叉的趋势跟踪策略",
                category="trend",
                params=[
                    StrategyParam(name="short_period", type="int", default=5, min_value=2, max_value=30, description="短期均线周期"),
                    StrategyParam(name="long_period", type="int", default=20, min_value=10, max_value=120, description="长期均线周期")
                ]
            ),
            Strategy(
                id="macd_strategy",
                name="MACD策略",
                description="基于MACD指标的趋势策略",
                category="trend",
                params=[
                    StrategyParam(name="fast", type="int", default=12, min_value=5, max_value=20, description="快线周期"),
                    StrategyParam(name="slow", type="int", default=26, min_value=20, max_value=40, description="慢线周期"),
                    StrategyParam(name="signal", type="int", default=9, min_value=5, max_value=15, description="信号线周期")
                ]
            ),
            Strategy(
                id="rsi_strategy",
                name="RSI策略",
                description="基于RSI超买超卖的震荡策略",
                category="momentum",
                params=[
                    StrategyParam(name="period", type="int", default=14, min_value=5, max_value=30, description="RSI周期"),
                    StrategyParam(name="oversold", type="int", default=30, min_value=10, max_value=40, description="超卖阈值"),
                    StrategyParam(name="overbought", type="int", default=70, min_value=60, max_value=90, description="超买阈值")
                ]
            )
        ]


@router.get("/strategies/{strategy_id}", response_model=Strategy)
async def get_strategy(strategy_id: str):
    """Get strategy details."""
    strategies = await get_strategies()
    for s in strategies:
        if s.id == strategy_id:
            return s
    return strategies[0]


@router.post("/run", response_model=BacktestResult)
async def run_backtest(request: BacktestRequest):
    """Run backtest."""
    if not request.ts_codes:
        raise HTTPException(status_code=400, detail="回测标的不能为空")

    try:
        from ...backtest.engine import IntelligentBacktestEngine
        from ...backtest.models import BacktestConfig, TradingConfig
        from ...backtest.simulator import TradingSimulator
        from ...strategies.init import get_strategy_registry

        engine = IntelligentBacktestEngine()
        registry = get_strategy_registry()
        strategy = registry.get_strategy(request.strategy_id, request.params)
        if strategy is None:
            raise HTTPException(status_code=404, detail=f"策略不存在: {request.strategy_id}")

        config = BacktestConfig(
            strategy_id=request.strategy_id,
            symbols=request.ts_codes,
            start_date=request.start_date,
            end_date=request.end_date,
            trading_config=TradingConfig(initial_capital=request.initial_capital)
        )

        errors = engine.validate_config(config)
        if errors:
            raise HTTPException(status_code=400, detail="; ".join(errors))

        historical_data = await engine.data_service.get_historical_data(
            config.symbols,
            config.start_date,
            config.end_date
        )
        simulator = TradingSimulator(config.trading_config)
        result = await engine._execute_backtest(strategy, historical_data, simulator, config)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"回测执行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    performance = result.performance_metrics
    total_trades, win_count, loss_count, win_rate, avg_win, avg_loss, profit_factor = _calculate_trade_stats(result.trades)
    trades = [
        Trade(
            date=trade.timestamp.date().isoformat(),
            direction=trade.trade_type.value,
            price=float(trade.price),
            quantity=int(trade.quantity),
            amount=float(trade.trade_value),
            signal_reason=trade.signal_reason or ""
        )
        for trade in result.trades
    ]

    equity_curve = []
    if result.equity_curve is not None and len(result.equity_curve) > 0:
        equity_curve = [
            EquityPoint(
                date=(idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)),
                value=float(value)
            )
            for idx, value in result.equity_curve.items()
        ]

    drawdown_series = {}
    if result.drawdown_series is not None and len(result.drawdown_series) > 0:
        drawdown_series = {
            (idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)): float(value)
            for idx, value in result.drawdown_series.items()
        }

    daily_returns = {}
    if result.returns_series is not None and len(result.returns_series) > 0:
        daily_returns = {
            (idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)): float(value)
            for idx, value in result.returns_series.items()
        }

    risk = result.risk_metrics

    backtest_result = BacktestResult(
        task_id=f"bt_{request.strategy_id}_{request.start_date}",
        strategy_name=request.strategy_id,
        ts_codes=request.ts_codes,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        final_capital=float(result.final_portfolio_value),
        total_return=float(performance.total_return * 100),
        annual_return=float(performance.annualized_return * 100),
        excess_return=float(performance.excess_return * 100),
        volatility=float(performance.volatility * 100),
        max_drawdown=float(performance.max_drawdown * 100),
        max_drawdown_duration=int(performance.max_drawdown_duration),
        sharpe_ratio=float(performance.sharpe_ratio),
        sortino_ratio=float(performance.sortino_ratio),
        calmar_ratio=float(performance.calmar_ratio),
        information_ratio=float(performance.information_ratio),
        alpha=float(performance.alpha),
        beta=float(performance.beta),
        win_rate=float(win_rate * 100),
        trade_count=int(total_trades),
        winning_trades=int(win_count),
        losing_trades=int(loss_count),
        avg_win=float(avg_win),
        avg_loss=float(avg_loss),
        profit_factor=float(profit_factor),
        var_95=float(risk.var_95 * 100),
        cvar_95=float(risk.cvar_95 * 100),
        var_99=float(risk.var_99 * 100),
        cvar_99=float(risk.cvar_99 * 100),
        skewness=float(risk.skewness),
        kurtosis=float(risk.kurtosis),
        trades=trades,
        equity_curve=equity_curve,
        drawdown_series=drawdown_series,
        daily_returns=daily_returns,
        created_at=datetime.utcnow().isoformat()
    )

    _BACKTEST_HISTORY.insert(0, backtest_result)
    if len(_BACKTEST_HISTORY) > _MAX_HISTORY_SIZE:
        _BACKTEST_HISTORY.pop()

    return backtest_result


@router.get("/results", response_model=List[BacktestResult])
async def get_results(limit: int = Query(default=20)):
    """Get backtest history."""
    safe_limit = max(1, min(limit, _MAX_HISTORY_SIZE))
    return _BACKTEST_HISTORY[:safe_limit]


@router.get("/results/{task_id}", response_model=BacktestResult)
async def get_result(task_id: str):
    """Get backtest result details."""
    for item in _BACKTEST_HISTORY:
        if item.task_id == task_id:
            return item
    raise HTTPException(status_code=404, detail="回测结果不存在")
