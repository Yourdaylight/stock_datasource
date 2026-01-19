"""Pydantic schemas for THS Index module."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class THSIndexItem(BaseModel):
    """THS sector index item."""
    ts_code: str = Field(..., description="Index code, e.g., 885001.TI")
    name: str = Field(..., description="Index name")
    count: Optional[int] = Field(None, description="Number of constituent stocks")
    exchange: Optional[str] = Field(None, description="Market: A/HK/US")
    type: Optional[str] = Field(None, description="Index type: N-概念/I-行业/R-地域/S-特色/ST-风格/TH-主题/BB-宽基")
    list_date: Optional[str] = Field(None, description="Listing date")


class THSIndexListResponse(BaseModel):
    """Response for THS index list."""
    data: List[THSIndexItem] = Field(default_factory=list, description="Index list")
    total: int = Field(0, description="Total count")
    exchange: Optional[str] = Field(None, description="Filtered exchange")
    index_type: Optional[str] = Field(None, description="Filtered type")


class THSDailyItem(BaseModel):
    """THS daily data item."""
    ts_code: str = Field(..., description="Index code")
    trade_date: str = Field(..., description="Trade date")
    open: Optional[float] = Field(None, description="Open price")
    high: Optional[float] = Field(None, description="High price")
    low: Optional[float] = Field(None, description="Low price")
    close: Optional[float] = Field(None, description="Close price")
    pre_close: Optional[float] = Field(None, description="Previous close")
    pct_change: Optional[float] = Field(None, description="Percentage change")
    vol: Optional[float] = Field(None, description="Volume")
    turnover_rate: Optional[float] = Field(None, description="Turnover rate")
    total_mv: Optional[float] = Field(None, description="Total market value")
    float_mv: Optional[float] = Field(None, description="Float market value")


class THSDailyResponse(BaseModel):
    """Response for THS daily data."""
    ts_code: str = Field(..., description="Index code")
    name: Optional[str] = Field(None, description="Index name")
    data: List[THSDailyItem] = Field(default_factory=list, description="Daily data")


class THSRankingItem(BaseModel):
    """THS ranking item with daily data."""
    ts_code: str = Field(..., description="Index code")
    name: str = Field(..., description="Index name")
    type: Optional[str] = Field(None, description="Index type")
    count: Optional[int] = Field(None, description="Constituent count")
    close: Optional[float] = Field(None, description="Close price")
    pct_change: Optional[float] = Field(None, description="Percentage change")
    vol: Optional[float] = Field(None, description="Volume")
    turnover_rate: Optional[float] = Field(None, description="Turnover rate")


class THSRankingResponse(BaseModel):
    """Response for THS ranking."""
    trade_date: Optional[str] = Field(None, description="Trade date")
    sort_by: str = Field(..., description="Sort field")
    order: str = Field(..., description="Sort order")
    index_type: Optional[str] = Field(None, description="Filtered type")
    data: List[THSRankingItem] = Field(default_factory=list, description="Ranking list")


class THSSearchResponse(BaseModel):
    """Response for THS index search."""
    keyword: str = Field(..., description="Search keyword")
    data: List[THSIndexItem] = Field(default_factory=list, description="Search results")


class THSStatsItem(BaseModel):
    """THS index statistics item."""
    type: Optional[str] = Field(None, description="Index type")
    exchange: Optional[str] = Field(None, description="Market")
    index_count: int = Field(0, description="Number of indices")
    total_constituents: Optional[int] = Field(None, description="Total constituents")
    avg_constituents: Optional[float] = Field(None, description="Average constituents")


class THSStatsResponse(BaseModel):
    """Response for THS index statistics."""
    data: List[THSStatsItem] = Field(default_factory=list, description="Statistics")
