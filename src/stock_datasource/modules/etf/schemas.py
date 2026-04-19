"""Pydantic schemas for ETF module."""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class EtfInfo(BaseModel):
    """ETF basic information matching ods_etf_basic table."""

    ts_code: str = Field(..., description="ETF code")
    csname: str | None = Field(None, description="ETF short name")
    cname: str | None = Field(None, description="ETF full name")
    mgr_name: str | None = Field(None, description="Management company")
    custod_name: str | None = Field(None, description="Custodian bank")
    etf_type: str | None = Field(None, description="ETF type")
    setup_date: date | None = Field(None, description="Setup date")
    list_date: date | None = Field(None, description="List date")
    mgt_fee: float | None = Field(None, description="Management fee rate")
    index_code: str | None = Field(None, description="Tracking index code")
    index_name: str | None = Field(None, description="Tracking index name")
    list_status: str | None = Field(
        None, description="Status (D=delisted, L=listed, P=pending)"
    )
    exchange: str | None = Field(None, description="Exchange (SH/SZ)")

    class Config:
        from_attributes = True


class EtfQuoteItem(BaseModel):
    """ETF item with latest daily quote and basic info."""

    ts_code: str
    trade_date: str | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    pct_chg: float | None = None
    vol: float | None = None
    amount: float | None = None
    csname: str | None = None
    cname: str | None = None
    index_code: str | None = None
    index_name: str | None = None
    exchange: str | None = None
    mgr_name: str | None = None
    custod_name: str | None = None
    list_date: date | None = None
    list_status: str | None = None
    etf_type: str | None = None
    mgt_fee: float | None = None


class EtfListResponse(BaseModel):
    """Paginated ETF list response with latest quotes."""

    items: list[EtfQuoteItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class EtfDailyData(BaseModel):
    """ETF daily trading data."""

    ts_code: str = Field(..., description="ETF code")
    trade_date: str = Field(..., description="Trade date")
    open: float | None = Field(None, description="Open price")
    high: float | None = Field(None, description="High price")
    low: float | None = Field(None, description="Low price")
    close: float | None = Field(None, description="Close price")
    pre_close: float | None = Field(None, description="Previous close")
    change: float | None = Field(None, description="Price change")
    pct_chg: float | None = Field(None, description="Percentage change")
    vol: float | None = Field(None, description="Volume")
    amount: float | None = Field(None, description="Trading amount")


class EtfKLineData(BaseModel):
    """ETF K-line data with adjustment.

    Field name 'date' (not trade_date) for frontend KLineData compatibility.
    """

    ts_code: str = Field(..., description="ETF code")
    date: str = Field(
        ...,
        description="Trade date (renamed from trade_date for frontend compatibility)",
    )
    open: float | None = Field(None, description="Open price")
    high: float | None = Field(None, description="High price")
    low: float | None = Field(None, description="Low price")
    close: float | None = Field(None, description="Close price")
    vol: float | None = Field(None, description="Volume")
    amount: float | None = Field(None, description="Trading amount")
    pct_chg: float | None = Field(None, description="Percentage change")


class EtfKLineResponse(BaseModel):
    """Response for ETF K-line query."""

    ts_code: str = Field(..., description="ETF code")
    code: str = Field(
        ..., description="Alias for ts_code (frontend KLineData compatibility)"
    )
    name: str | None = Field(None, description="ETF name")
    adjust: str = Field(..., description="Adjustment type")
    data: list[EtfKLineData] = Field(..., description="K-line data")


class EtfDailyResponse(BaseModel):
    """Response for ETF daily data query."""

    ts_code: str = Field(..., description="ETF code")
    days: int = Field(..., description="Number of days")
    data: list[EtfDailyData] = Field(..., description="Daily data")


class ExchangeOption(BaseModel):
    """Exchange option for filter."""

    value: str = Field(..., description="Exchange code")
    label: str = Field(..., description="Exchange name")
    count: int = Field(0, description="ETF count")


class EtfTypeOption(BaseModel):
    """ETF type option for filter."""

    value: str = Field(..., description="Type code")
    label: str = Field(..., description="Type name")
    count: int = Field(0, description="ETF count")


class AnalyzeRequest(BaseModel):
    """Request for AI analysis."""

    ts_code: str = Field(..., description="ETF code, e.g., 510300.SH")
    question: str | None = Field(None, description="Optional specific question")
    user_id: str = Field(default="default", description="User ID for session tracking")
    clear_history: bool = Field(default=False, description="Clear conversation history")


class AnalyzeResponse(BaseModel):
    """Response for AI analysis."""

    ts_code: str = Field(..., description="ETF code")
    question: str | None = Field(None, description="Question asked")
    response: str = Field(..., description="AI response")
    success: bool = Field(..., description="Whether analysis succeeded")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    session_id: str = Field(..., description="Session ID")
    history_length: int = Field(..., description="History length")


class QuickAnalysisResponse(BaseModel):
    """Response for quick analysis (without AI)."""

    ts_code: str = Field(..., description="ETF code")
    name: str | None = Field(None, description="ETF name")
    trade_date: str | None = Field(None, description="Latest trade date")
    basic_info: dict[str, Any] = Field(default_factory=dict, description="Basic info")
    price_metrics: dict[str, Any] = Field(
        default_factory=dict, description="Price metrics"
    )
    volume_metrics: dict[str, Any] = Field(
        default_factory=dict, description="Volume metrics"
    )
    tracking_info: dict[str, Any] = Field(
        default_factory=dict, description="Tracking index info"
    )
    risk_metrics: dict[str, Any] = Field(
        default_factory=dict, description="Risk metrics"
    )
    signals: list[str] = Field(default_factory=list, description="Technical signals")
