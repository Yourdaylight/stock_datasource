"""Pydantic schemas for Overview module."""

from typing import Any

from pydantic import BaseModel, Field


class IndexStatus(BaseModel):
    """Index status in daily overview."""

    ts_code: str = Field(..., description="Index code")
    name: str | None = Field(None, description="Index name")
    close: float | None = Field(None, description="Close price")
    pct_chg: float | None = Field(None, description="Percentage change")
    vol: float | None = Field(None, description="Volume")
    amount: float | None = Field(None, description="Trading amount")


class MarketStats(BaseModel):
    """Market statistics."""

    trade_date: str | None = Field(None, description="Trade date")
    up_count: int = Field(0, description="Number of stocks up")
    down_count: int = Field(0, description="Number of stocks down")
    flat_count: int = Field(0, description="Number of stocks flat")
    limit_up_count: int = Field(0, description="Number of limit up")
    limit_down_count: int = Field(0, description="Number of limit down")
    total_amount: float | None = Field(None, description="Total trading amount")
    total_vol: float | None = Field(None, description="Total volume")


class HotEtf(BaseModel):
    """Hot ETF item."""

    ts_code: str = Field(..., description="ETF code")
    name: str | None = Field(None, description="ETF name")
    close: float | None = Field(None, description="Close price")
    pct_chg: float | None = Field(None, description="Percentage change")
    amount: float | None = Field(None, description="Trading amount")
    vol: float | None = Field(None, description="Volume")


class DailyOverviewResponse(BaseModel):
    """Response for daily overview."""

    trade_date: str | None = Field(None, description="Trade date")
    major_indices: list[IndexStatus] = Field(
        default_factory=list, description="Major indices"
    )
    market_stats: MarketStats | None = Field(None, description="Market statistics")
    hot_etfs_by_amount: list[HotEtf] = Field(
        default_factory=list, description="Hot ETFs by amount"
    )
    hot_etfs_by_change: list[HotEtf] = Field(
        default_factory=list, description="Hot ETFs by change"
    )


class HotEtfResponse(BaseModel):
    """Response for hot ETFs."""

    trade_date: str | None = Field(None, description="Trade date")
    sort_by: str = Field(..., description="Sort field")
    data: list[HotEtf] = Field(default_factory=list, description="Hot ETF list")


class AnalyzeRequest(BaseModel):
    """Request for AI analysis."""

    question: str = Field(..., description="User question")
    user_id: str = Field(default="default", description="User ID for session tracking")
    date: str | None = Field(
        None, description="Analysis date (YYYYMMDD), defaults to latest"
    )
    clear_history: bool = Field(default=False, description="Clear conversation history")


class AnalyzeResponse(BaseModel):
    """Response for AI analysis."""

    date: str = Field(..., description="Analysis date")
    question: str = Field(..., description="Question asked")
    response: str = Field(..., description="AI response")
    success: bool = Field(..., description="Whether analysis succeeded")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    session_id: str = Field(..., description="Session ID")
    history_length: int = Field(..., description="History length")


class QuickAnalysisResponse(BaseModel):
    """Response for quick market analysis."""

    trade_date: str | None = Field(None, description="Trade date")
    market_summary: str = Field(default="暂无数据", description="Market summary text")
    indices_summary: dict[str, Any] = Field(
        default_factory=dict, description="Indices summary"
    )
    market_breadth: dict[str, Any] = Field(
        default_factory=dict, description="Market breadth"
    )
    sentiment: dict[str, Any] = Field(
        default_factory=dict, description="Market sentiment"
    )
    hot_etfs: list[dict[str, Any]] = Field(default_factory=list, description="Hot ETFs")
    signals: list[str] = Field(default_factory=list, description="Market signals")
