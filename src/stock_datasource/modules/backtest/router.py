"""Backtest module router."""

from fastapi import APIRouter, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class StrategyParam(BaseModel):
    name: str
    type: str
    default: Any
    min_value: float = None
    max_value: float = None
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
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    trade_count: int
    trades: List[Trade] = []
    equity_curve: List[EquityPoint] = []


@router.get("/strategies", response_model=List[Strategy])
async def get_strategies():
    """Get available strategies."""
    return [
        Strategy(
            id="ma",
            name="均线策略",
            description="基于短期和长期均线交叉的趋势跟踪策略",
            category="trend",
            params=[
                StrategyParam(name="short_period", type="int", default=5, min_value=2, max_value=30, description="短期均线周期"),
                StrategyParam(name="long_period", type="int", default=20, min_value=10, max_value=120, description="长期均线周期")
            ]
        ),
        Strategy(
            id="macd",
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
            id="rsi",
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
    # Mock implementation
    return BacktestResult(
        task_id=f"bt_{request.strategy_id}_{request.start_date}",
        strategy_name="均线策略",
        ts_codes=request.ts_codes,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        final_capital=request.initial_capital * 1.15,
        total_return=15.0,
        annual_return=12.5,
        max_drawdown=8.5,
        sharpe_ratio=1.2,
        win_rate=55.0,
        trade_count=20,
        trades=[
            Trade(date="2024-01-15", direction="buy", price=100.0, quantity=1000, amount=100000, signal_reason="金叉"),
            Trade(date="2024-02-20", direction="sell", price=110.0, quantity=1000, amount=110000, signal_reason="死叉")
        ]
    )


@router.get("/results", response_model=List[BacktestResult])
async def get_results(limit: int = Query(default=20)):
    """Get backtest history."""
    return []


@router.get("/results/{task_id}", response_model=BacktestResult)
async def get_result(task_id: str):
    """Get backtest result details."""
    return BacktestResult(
        task_id=task_id,
        strategy_name="均线策略",
        ts_codes=["600519.SH"],
        start_date="2023-01-01",
        end_date="2024-01-01",
        initial_capital=100000,
        final_capital=115000,
        total_return=15.0,
        annual_return=15.0,
        max_drawdown=8.5,
        sharpe_ratio=1.2,
        win_rate=55.0,
        trade_count=20
    )
