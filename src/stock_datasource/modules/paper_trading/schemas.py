"""Paper Trading schemas — Pydantic 数据模型"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Request models
# ------------------------------------------------------------------


class CreateAccountRequest(BaseModel):
    """创建模拟账户"""

    account_name: str = "默认模拟盘"
    initial_capital: float = Field(default=1000000.0, gt=0)
    strategy_id: str = "stock_timing"


class ExecuteSignalRequest(BaseModel):
    """手动执行信号"""

    ts_code: str
    direction: str  # buy / sell
    price: float = Field(gt=0)
    quantity: int | None = None  # None = 自动计算
    reason: str = ""


# ------------------------------------------------------------------
# Response models
# ------------------------------------------------------------------


class AccountSummary(BaseModel):
    """账户摘要"""

    account_id: str
    account_name: str
    initial_capital: float
    current_cash: float
    total_value: float = 0.0
    total_return_pct: float = 0.0
    position_count: int = 0
    status: str = "active"
    created_at: str = ""


class Position(BaseModel):
    """持仓"""

    ts_code: str
    stock_name: str = ""
    quantity: int
    avg_cost: float
    current_price: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    first_buy_date: str = ""


class TradeRecord(BaseModel):
    """交易记录"""

    trade_id: str
    ts_code: str
    direction: str
    quantity: int
    price: float
    amount: float
    commission: float = 0.0
    signal_reason: str = ""
    signal_confidence: float = 0.0
    regime_state: str = ""
    trade_date: str = ""


class EquityPoint(BaseModel):
    """净值曲线点"""

    date: str
    total_value: float
    cash: float
    positions_value: float
    daily_pnl: float = 0.0
    total_return_pct: float = 0.0


class PerformanceMetrics(BaseModel):
    """绩效指标"""

    total_return_pct: float = 0.0
    annual_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_holding_days: float = 0.0
    profit_factor: float = 0.0


class TradeResult(BaseModel):
    """交易执行结果"""

    success: bool
    trade_id: str = ""
    message: str = ""
    executed_quantity: int = 0
    executed_price: float = 0.0
    commission: float = 0.0
