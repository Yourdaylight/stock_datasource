"""Pydantic schemas for THS Index module."""

from pydantic import BaseModel, Field


class THSIndexItem(BaseModel):
    """THS sector index item."""

    ts_code: str = Field(..., description="Index code, e.g., 885001.TI")
    name: str = Field(..., description="Index name")
    count: int | None = Field(None, description="Number of constituent stocks")
    exchange: str | None = Field(None, description="Market: A/HK/US")
    type: str | None = Field(
        None,
        description="Index type: N-概念/I-行业/R-地域/S-特色/ST-风格/TH-主题/BB-宽基",
    )
    list_date: str | None = Field(None, description="Listing date")


class THSIndexListResponse(BaseModel):
    """Response for THS index list."""

    data: list[THSIndexItem] = Field(default_factory=list, description="Index list")
    total: int = Field(0, description="Total count")
    exchange: str | None = Field(None, description="Filtered exchange")
    index_type: str | None = Field(None, description="Filtered type")


class THSDailyItem(BaseModel):
    """THS daily data item."""

    ts_code: str = Field(..., description="Index code")
    trade_date: str = Field(..., description="Trade date")
    open: float | None = Field(None, description="Open price")
    high: float | None = Field(None, description="High price")
    low: float | None = Field(None, description="Low price")
    close: float | None = Field(None, description="Close price")
    pre_close: float | None = Field(None, description="Previous close")
    pct_change: float | None = Field(None, description="Percentage change")
    vol: float | None = Field(None, description="Volume")
    turnover_rate: float | None = Field(None, description="Turnover rate")
    total_mv: float | None = Field(None, description="Total market value")
    float_mv: float | None = Field(None, description="Float market value")


class THSDailyResponse(BaseModel):
    """Response for THS daily data."""

    ts_code: str = Field(..., description="Index code")
    name: str | None = Field(None, description="Index name")
    data: list[THSDailyItem] = Field(default_factory=list, description="Daily data")


class THSRankingItem(BaseModel):
    """THS ranking item with daily data."""

    ts_code: str = Field(..., description="Index code")
    name: str = Field(..., description="Index name")
    type: str | None = Field(None, description="Index type")
    count: int | None = Field(None, description="Constituent count")
    close: float | None = Field(None, description="Close price")
    pct_change: float | None = Field(None, description="Percentage change")
    vol: float | None = Field(None, description="Volume")
    turnover_rate: float | None = Field(None, description="Turnover rate")


class THSRankingResponse(BaseModel):
    """Response for THS ranking."""

    trade_date: str | None = Field(None, description="Trade date")
    sort_by: str = Field(..., description="Sort field")
    order: str = Field(..., description="Sort order")
    index_type: str | None = Field(None, description="Filtered type")
    data: list[THSRankingItem] = Field(default_factory=list, description="Ranking list")


class THSSearchResponse(BaseModel):
    """Response for THS index search."""

    keyword: str = Field(..., description="Search keyword")
    data: list[THSIndexItem] = Field(default_factory=list, description="Search results")


class THSStatsItem(BaseModel):
    """THS index statistics item."""

    type: str | None = Field(None, description="Index type")
    exchange: str | None = Field(None, description="Market")
    index_count: int = Field(0, description="Number of indices")
    total_constituents: int | None = Field(None, description="Total constituents")
    avg_constituents: float | None = Field(None, description="Average constituents")


class THSStatsResponse(BaseModel):
    """Response for THS index statistics."""

    data: list[THSStatsItem] = Field(default_factory=list, description="Statistics")
