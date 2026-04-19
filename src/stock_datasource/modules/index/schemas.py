"""Pydantic schemas for Index module."""

from typing import Any

from pydantic import BaseModel, Field


class IndexInfo(BaseModel):
    """Index basic information."""

    ts_code: str = Field(..., description="Index code")
    name: str | None = Field(None, description="Index name")
    fullname: str | None = Field(None, description="Full name")
    market: str | None = Field(None, description="Market (SSE/SZSE/CSI)")
    publisher: str | None = Field(None, description="Publisher")
    index_type: str | None = Field(None, description="Index type")
    category: str | None = Field(None, description="Category")
    base_date: str | None = Field(None, description="Base date")
    base_point: float | None = Field(None, description="Base point")
    list_date: str | None = Field(None, description="List date")
    weight_rule: str | None = Field(None, description="Weight rule")
    desc: str | None = Field(None, description="Description")


class IndexQuoteItem(BaseModel):
    """Index with daily quote data."""

    ts_code: str = Field(..., description="Index code")
    name: str | None = Field(None, description="Index name")
    fullname: str | None = Field(None, description="Full name")
    market: str | None = Field(None, description="Market (SSE/SZSE/CSI)")
    publisher: str | None = Field(None, description="Publisher")
    index_type: str | None = Field(None, description="Index type")
    category: str | None = Field(None, description="Category")
    base_date: str | None = Field(None, description="Base date")
    base_point: float | None = Field(None, description="Base point")
    list_date: str | None = Field(None, description="List date")
    weight_rule: str | None = Field(None, description="Weight rule")
    desc: str | None = Field(None, description="Description")
    # Daily quote fields
    trade_date: str | None = Field(None, description="Trade date")
    open: float | None = Field(None, description="Open price")
    high: float | None = Field(None, description="High price")
    low: float | None = Field(None, description="Low price")
    close: float | None = Field(None, description="Close price")
    pre_close: float | None = Field(None, description="Previous close")
    pct_chg: float | None = Field(None, description="Price change %")
    vol: float | None = Field(None, description="Volume")
    amount: float | None = Field(None, description="Amount")


class IndexListResponse(BaseModel):
    """Response for index list query."""

    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Page size")
    data: list[IndexQuoteItem] = Field(..., description="Index list")
    trade_date: str | None = Field(None, description="Trade date for query")


class Constituent(BaseModel):
    """Index constituent stock."""

    index_code: str = Field(..., description="Index code")
    con_code: str = Field(..., description="Constituent stock code")
    trade_date: str | None = Field(None, description="Trade date")
    weight: float | None = Field(None, description="Weight percentage")


class ConstituentResponse(BaseModel):
    """Response for constituent query."""

    index_code: str = Field(..., description="Index code")
    trade_date: str | None = Field(None, description="Trade date")
    constituent_count: int = Field(..., description="Number of constituents")
    total_weight: float = Field(..., description="Total weight")
    constituents: list[Constituent] = Field(..., description="Constituent list")


class FactorData(BaseModel):
    """Technical factor data."""

    ts_code: str = Field(..., description="Index code")
    trade_date: str = Field(..., description="Trade date")
    close: float | None = Field(None, description="Close price")
    # Add more fields as needed


class FactorResponse(BaseModel):
    """Response for factor query."""

    ts_code: str = Field(..., description="Index code")
    days: int = Field(..., description="Number of days")
    data: list[dict[str, Any]] = Field(..., description="Factor data")


class AnalyzeRequest(BaseModel):
    """Request for AI analysis."""

    ts_code: str = Field(..., description="Index code, e.g., 000300.SH")
    question: str | None = Field(None, description="Optional specific question")
    user_id: str = Field(default="default", description="User ID for session tracking")
    clear_history: bool = Field(
        default=False, description="Clear conversation history before this request"
    )


class AnalyzeResponse(BaseModel):
    """Response for AI analysis."""

    ts_code: str = Field(..., description="Index code")
    question: str | None = Field(None, description="Question asked")
    response: str = Field(..., description="AI response")
    success: bool = Field(..., description="Whether analysis succeeded")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    session_id: str = Field(..., description="Session ID for conversation tracking")
    history_length: int = Field(..., description="Number of messages in history")


class AnalysisResult(BaseModel):
    """AI analysis result."""

    ts_code: str = Field(..., description="Index code")
    index_name: str | None = Field(None, description="Index name")
    trade_date: str | None = Field(None, description="Analysis date")
    overall_score: int = Field(..., description="Overall score (0-100)")
    suggestion: str = Field(..., description="Suggestion")
    suggestion_detail: str = Field(..., description="Detailed suggestion")
    risks: list[str] = Field(..., description="Risk factors")
    dimension_scores: dict[str, Any] = Field(..., description="Scores by dimension")
    concentration: dict[str, Any] | None = Field(
        None, description="Concentration analysis"
    )
    disclaimer: str = Field(..., description="Disclaimer")


class ConcentrationAnalysis(BaseModel):
    """Concentration analysis result."""

    ts_code: str = Field(..., description="Index code")
    trade_date: str | None = Field(None, description="Trade date")
    constituent_count: int = Field(..., description="Number of constituents")
    cr10: float = Field(..., description="Top 10 concentration ratio")
    hhi: float = Field(..., description="HHI index")
    risk_level: str = Field(..., description="Risk level")
    risk_description: str = Field(..., description="Risk description")
    top10_constituents: list[dict[str, Any]] = Field(
        ..., description="Top 10 constituents"
    )


class TrendAnalysis(BaseModel):
    """Trend analysis result."""

    ts_code: str = Field(..., description="Index code")
    trade_date: str | None = Field(None, description="Trade date")
    trend_direction: str = Field(..., description="Trend direction")
    trend_score: int = Field(..., description="Trend score")
    ma_analysis: dict[str, Any] = Field(..., description="MA analysis")
    macd_analysis: dict[str, Any] = Field(..., description="MACD analysis")
    dmi_analysis: dict[str, Any] = Field(..., description="DMI analysis")
