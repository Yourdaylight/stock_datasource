"""Pydantic schemas for ETF module."""

from typing import List, Optional, Dict, Any
from datetime import date
from pydantic import BaseModel, Field


class EtfInfo(BaseModel):
    """ETF basic information matching ods_etf_basic table."""
    ts_code: str = Field(..., description="ETF code")
    csname: Optional[str] = Field(None, description="ETF short name")
    cname: Optional[str] = Field(None, description="ETF full name")
    mgr_name: Optional[str] = Field(None, description="Management company")
    custod_name: Optional[str] = Field(None, description="Custodian bank")
    etf_type: Optional[str] = Field(None, description="ETF type")
    setup_date: Optional[date] = Field(None, description="Setup date")
    list_date: Optional[date] = Field(None, description="List date")
    mgt_fee: Optional[float] = Field(None, description="Management fee rate")
    index_code: Optional[str] = Field(None, description="Tracking index code")
    index_name: Optional[str] = Field(None, description="Tracking index name")
    list_status: Optional[str] = Field(None, description="Status (D=delisted, L=listed, P=pending)")
    exchange: Optional[str] = Field(None, description="Exchange (SH/SZ)")

    class Config:
        from_attributes = True


class EtfQuoteItem(BaseModel):
    """ETF item with latest daily quote and basic info."""
    ts_code: str
    trade_date: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    pct_chg: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None
    csname: Optional[str] = None
    cname: Optional[str] = None
    index_code: Optional[str] = None
    index_name: Optional[str] = None
    exchange: Optional[str] = None
    mgr_name: Optional[str] = None
    custod_name: Optional[str] = None
    list_date: Optional[date] = None
    list_status: Optional[str] = None
    etf_type: Optional[str] = None
    mgt_fee: Optional[float] = None


class EtfListResponse(BaseModel):
    """Paginated ETF list response with latest quotes."""
    items: List[EtfQuoteItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class EtfDailyData(BaseModel):
    """ETF daily trading data."""
    ts_code: str = Field(..., description="ETF code")
    trade_date: str = Field(..., description="Trade date")
    open: Optional[float] = Field(None, description="Open price")
    high: Optional[float] = Field(None, description="High price")
    low: Optional[float] = Field(None, description="Low price")
    close: Optional[float] = Field(None, description="Close price")
    pre_close: Optional[float] = Field(None, description="Previous close")
    change: Optional[float] = Field(None, description="Price change")
    pct_chg: Optional[float] = Field(None, description="Percentage change")
    vol: Optional[float] = Field(None, description="Volume")
    amount: Optional[float] = Field(None, description="Trading amount")


class EtfKLineData(BaseModel):
    """ETF K-line data with adjustment."""
    ts_code: str = Field(..., description="ETF code")
    trade_date: str = Field(..., description="Trade date")
    open: float = Field(..., description="Open price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Close price")
    vol: Optional[float] = Field(None, description="Volume")
    amount: Optional[float] = Field(None, description="Trading amount")
    pct_chg: Optional[float] = Field(None, description="Percentage change")


class EtfKLineResponse(BaseModel):
    """Response for ETF K-line query."""
    ts_code: str = Field(..., description="ETF code")
    name: Optional[str] = Field(None, description="ETF name")
    adjust: str = Field(..., description="Adjustment type")
    data: List[EtfKLineData] = Field(..., description="K-line data")


class EtfDailyResponse(BaseModel):
    """Response for ETF daily data query."""
    ts_code: str = Field(..., description="ETF code")
    days: int = Field(..., description="Number of days")
    data: List[EtfDailyData] = Field(..., description="Daily data")


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
    question: Optional[str] = Field(None, description="Optional specific question")
    user_id: str = Field(default="default", description="User ID for session tracking")
    clear_history: bool = Field(default=False, description="Clear conversation history")


class AnalyzeResponse(BaseModel):
    """Response for AI analysis."""
    ts_code: str = Field(..., description="ETF code")
    question: Optional[str] = Field(None, description="Question asked")
    response: str = Field(..., description="AI response")
    success: bool = Field(..., description="Whether analysis succeeded")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    session_id: str = Field(..., description="Session ID")
    history_length: int = Field(..., description="History length")


class QuickAnalysisResponse(BaseModel):
    """Response for quick analysis (without AI)."""
    ts_code: str = Field(..., description="ETF code")
    name: Optional[str] = Field(None, description="ETF name")
    trade_date: Optional[str] = Field(None, description="Latest trade date")
    basic_info: Dict[str, Any] = Field(default_factory=dict, description="Basic info")
    price_metrics: Dict[str, Any] = Field(default_factory=dict, description="Price metrics")
    volume_metrics: Dict[str, Any] = Field(default_factory=dict, description="Volume metrics")
    tracking_info: Dict[str, Any] = Field(default_factory=dict, description="Tracking index info")
    risk_metrics: Dict[str, Any] = Field(default_factory=dict, description="Risk metrics")
    signals: List[str] = Field(default_factory=list, description="Technical signals")
