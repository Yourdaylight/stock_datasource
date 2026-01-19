"""Pydantic schemas for Overview module."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class IndexStatus(BaseModel):
    """Index status in daily overview."""
    ts_code: str = Field(..., description="Index code")
    name: Optional[str] = Field(None, description="Index name")
    close: Optional[float] = Field(None, description="Close price")
    pct_chg: Optional[float] = Field(None, description="Percentage change")
    vol: Optional[float] = Field(None, description="Volume")
    amount: Optional[float] = Field(None, description="Trading amount")


class MarketStats(BaseModel):
    """Market statistics."""
    trade_date: Optional[str] = Field(None, description="Trade date")
    up_count: int = Field(0, description="Number of stocks up")
    down_count: int = Field(0, description="Number of stocks down")
    flat_count: int = Field(0, description="Number of stocks flat")
    limit_up_count: int = Field(0, description="Number of limit up")
    limit_down_count: int = Field(0, description="Number of limit down")
    total_amount: Optional[float] = Field(None, description="Total trading amount")
    total_vol: Optional[float] = Field(None, description="Total volume")


class HotEtf(BaseModel):
    """Hot ETF item."""
    ts_code: str = Field(..., description="ETF code")
    name: Optional[str] = Field(None, description="ETF name")
    close: Optional[float] = Field(None, description="Close price")
    pct_chg: Optional[float] = Field(None, description="Percentage change")
    amount: Optional[float] = Field(None, description="Trading amount")
    vol: Optional[float] = Field(None, description="Volume")


class DailyOverviewResponse(BaseModel):
    """Response for daily overview."""
    trade_date: Optional[str] = Field(None, description="Trade date")
    major_indices: List[IndexStatus] = Field(default_factory=list, description="Major indices")
    market_stats: Optional[MarketStats] = Field(None, description="Market statistics")
    hot_etfs_by_amount: List[HotEtf] = Field(default_factory=list, description="Hot ETFs by amount")
    hot_etfs_by_change: List[HotEtf] = Field(default_factory=list, description="Hot ETFs by change")


class HotEtfResponse(BaseModel):
    """Response for hot ETFs."""
    trade_date: Optional[str] = Field(None, description="Trade date")
    sort_by: str = Field(..., description="Sort field")
    data: List[HotEtf] = Field(default_factory=list, description="Hot ETF list")


class AnalyzeRequest(BaseModel):
    """Request for AI analysis."""
    question: str = Field(..., description="User question")
    user_id: str = Field(default="default", description="User ID for session tracking")
    date: Optional[str] = Field(None, description="Analysis date (YYYYMMDD), defaults to latest")
    clear_history: bool = Field(default=False, description="Clear conversation history")


class AnalyzeResponse(BaseModel):
    """Response for AI analysis."""
    date: str = Field(..., description="Analysis date")
    question: str = Field(..., description="Question asked")
    response: str = Field(..., description="AI response")
    success: bool = Field(..., description="Whether analysis succeeded")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    session_id: str = Field(..., description="Session ID")
    history_length: int = Field(..., description="History length")


class QuickAnalysisResponse(BaseModel):
    """Response for quick market analysis."""
    trade_date: Optional[str] = Field(None, description="Trade date")
    market_summary: str = Field(..., description="Market summary text")
    indices_summary: Dict[str, Any] = Field(default_factory=dict, description="Indices summary")
    market_breadth: Dict[str, Any] = Field(default_factory=dict, description="Market breadth")
    hot_sectors: List[Dict[str, Any]] = Field(default_factory=list, description="Hot sectors")
    signals: List[str] = Field(default_factory=list, description="Market signals")
