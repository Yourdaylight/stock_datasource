"""Pydantic schemas for ETF module."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class IndexInfo(BaseModel):
    """Index basic information."""
    ts_code: str = Field(..., description="Index code")
    name: Optional[str] = Field(None, description="Index name")
    fullname: Optional[str] = Field(None, description="Full name")
    market: Optional[str] = Field(None, description="Market (SSE/SZSE/CSI)")
    publisher: Optional[str] = Field(None, description="Publisher")
    index_type: Optional[str] = Field(None, description="Index type")
    category: Optional[str] = Field(None, description="Category")
    base_date: Optional[str] = Field(None, description="Base date")
    base_point: Optional[float] = Field(None, description="Base point")
    list_date: Optional[str] = Field(None, description="List date")
    weight_rule: Optional[str] = Field(None, description="Weight rule")
    desc: Optional[str] = Field(None, description="Description")


class IndexListResponse(BaseModel):
    """Response for index list query."""
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Page size")
    data: List[IndexInfo] = Field(..., description="Index list")


class Constituent(BaseModel):
    """Index constituent stock."""
    index_code: str = Field(..., description="Index code")
    con_code: str = Field(..., description="Constituent stock code")
    trade_date: Optional[str] = Field(None, description="Trade date")
    weight: Optional[float] = Field(None, description="Weight percentage")


class ConstituentResponse(BaseModel):
    """Response for constituent query."""
    index_code: str = Field(..., description="Index code")
    trade_date: Optional[str] = Field(None, description="Trade date")
    constituent_count: int = Field(..., description="Number of constituents")
    total_weight: float = Field(..., description="Total weight")
    constituents: List[Constituent] = Field(..., description="Constituent list")


class FactorData(BaseModel):
    """Technical factor data."""
    ts_code: str = Field(..., description="Index code")
    trade_date: str = Field(..., description="Trade date")
    close: Optional[float] = Field(None, description="Close price")
    # Add more fields as needed


class FactorResponse(BaseModel):
    """Response for factor query."""
    ts_code: str = Field(..., description="Index code")
    days: int = Field(..., description="Number of days")
    data: List[Dict[str, Any]] = Field(..., description="Factor data")


class AnalyzeRequest(BaseModel):
    """Request for AI analysis."""
    ts_code: str = Field(..., description="Index code, e.g., 000300.SH")
    question: Optional[str] = Field(None, description="Optional specific question")
    user_id: str = Field(default="default", description="User ID for session tracking")
    clear_history: bool = Field(default=False, description="Clear conversation history before this request")


class AnalyzeResponse(BaseModel):
    """Response for AI analysis."""
    ts_code: str = Field(..., description="Index code")
    question: Optional[str] = Field(None, description="Question asked")
    response: str = Field(..., description="AI response")
    success: bool = Field(..., description="Whether analysis succeeded")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    session_id: str = Field(..., description="Session ID for conversation tracking")
    history_length: int = Field(..., description="Number of messages in history")


class AnalysisResult(BaseModel):
    """AI analysis result."""
    ts_code: str = Field(..., description="Index code")
    index_name: Optional[str] = Field(None, description="Index name")
    trade_date: Optional[str] = Field(None, description="Analysis date")
    overall_score: int = Field(..., description="Overall score (0-100)")
    suggestion: str = Field(..., description="Suggestion")
    suggestion_detail: str = Field(..., description="Detailed suggestion")
    risks: List[str] = Field(..., description="Risk factors")
    dimension_scores: Dict[str, Any] = Field(..., description="Scores by dimension")
    concentration: Optional[Dict[str, Any]] = Field(None, description="Concentration analysis")
    disclaimer: str = Field(..., description="Disclaimer")


class ConcentrationAnalysis(BaseModel):
    """Concentration analysis result."""
    ts_code: str = Field(..., description="Index code")
    trade_date: Optional[str] = Field(None, description="Trade date")
    constituent_count: int = Field(..., description="Number of constituents")
    cr10: float = Field(..., description="Top 10 concentration ratio")
    hhi: float = Field(..., description="HHI index")
    risk_level: str = Field(..., description="Risk level")
    risk_description: str = Field(..., description="Risk description")
    top10_constituents: List[Dict[str, Any]] = Field(..., description="Top 10 constituents")


class TrendAnalysis(BaseModel):
    """Trend analysis result."""
    ts_code: str = Field(..., description="Index code")
    trade_date: Optional[str] = Field(None, description="Trade date")
    trend_direction: str = Field(..., description="Trend direction")
    trend_score: int = Field(..., description="Trend score")
    ma_analysis: Dict[str, Any] = Field(..., description="MA analysis")
    macd_analysis: Dict[str, Any] = Field(..., description="MACD analysis")
    dmi_analysis: Dict[str, Any] = Field(..., description="DMI analysis")
