"""Pydantic schemas for Realtime Minute module."""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class MarketType(str, Enum):
    """Market type enum."""
    A_STOCK = "a_stock"
    ETF = "etf"
    INDEX = "index"
    HK = "hk"


class FreqType(str, Enum):
    """Frequency type enum."""
    MIN_1 = "1min"
    MIN_5 = "5min"
    MIN_15 = "15min"
    MIN_30 = "30min"
    MIN_60 = "60min"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class MinuteBar(BaseModel):
    """Single minute K-line bar."""
    ts_code: str = Field(..., description="证券代码")
    trade_time: str = Field(..., description="交易时间")
    open: Optional[float] = Field(None, description="开盘价")
    close: Optional[float] = Field(None, description="收盘价")
    high: Optional[float] = Field(None, description="最高价")
    low: Optional[float] = Field(None, description="最低价")
    vol: Optional[float] = Field(None, description="成交量")
    amount: Optional[float] = Field(None, description="成交额")
    pct_chg: Optional[float] = Field(None, description="涨跌幅(%)")
    market_type: Optional[str] = Field(None, description="市场类型")
    freq: Optional[str] = Field(None, description="频率")


class MinuteDataResponse(BaseModel):
    """Response for minute data query."""
    ts_code: Optional[str] = Field(None, description="证券代码")
    freq: str = Field(default="1min", description="频率")
    count: int = Field(default=0, description="数据条数")
    data: List[MinuteBar] = Field(default_factory=list, description="分钟K线数据")


class BatchMinuteDataResponse(BaseModel):
    """Response for batch minute data query."""
    freq: str = Field(default="1min", description="频率")
    total_codes: int = Field(default=0, description="查询代码数")
    total_bars: int = Field(default=0, description="总数据条数")
    data: Dict[str, List[MinuteBar]] = Field(default_factory=dict, description="按代码分组的数据")


class RankItem(BaseModel):
    """Ranking item."""
    ts_code: str = Field(..., description="证券代码")
    name: Optional[str] = Field(None, description="证券名称")
    close: Optional[float] = Field(None, description="最新价")
    pct_chg: Optional[float] = Field(None, description="涨跌幅(%)")
    vol: Optional[float] = Field(None, description="成交量")
    amount: Optional[float] = Field(None, description="成交额")
    trade_time: Optional[str] = Field(None, description="数据时间")
    market_type: Optional[str] = Field(None, description="市场类型")


class RankResponse(BaseModel):
    """Response for ranking queries."""
    rank_type: str = Field(..., description="排行类型")
    freq: str = Field(default="1min", description="频率")
    count: int = Field(default=0, description="数据条数")
    data: List[RankItem] = Field(default_factory=list, description="排行数据")


class MarketOverviewResponse(BaseModel):
    """Response for market overview."""
    freq: str = Field(default="1min", description="频率")
    total: int = Field(default=0, description="总股票数")
    up_count: int = Field(default=0, description="上涨数")
    down_count: int = Field(default=0, description="下跌数")
    flat_count: int = Field(default=0, description="平盘数")
    total_vol: Optional[float] = Field(None, description="总成交量")
    total_amount: Optional[float] = Field(None, description="总成交额")
    avg_pct_chg: Optional[float] = Field(None, description="平均涨跌幅")


class MarketStatsResponse(BaseModel):
    """Response for market stats."""
    total: int = Field(default=0, description="总股票数")
    up_count: int = Field(default=0, description="上涨数")
    down_count: int = Field(default=0, description="下跌数")
    flat_count: int = Field(default=0, description="平盘数")
    limit_up_count: int = Field(default=0, description="涨停数")
    limit_down_count: int = Field(default=0, description="跌停数")
    markets: Dict[str, Dict[str, int]] = Field(default_factory=dict, description="各市场分布")


class CollectStatusResponse(BaseModel):
    """Response for collection status."""
    is_collecting: bool = Field(default=False, description="是否正在采集")
    markets: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="各市场采集状态")
    last_collect_time: Optional[str] = Field(None, description="最后采集时间")
    total_cached_keys: int = Field(default=0, description="Redis缓存Key数")


class TriggerResponse(BaseModel):
    """Response for manual trigger."""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="结果消息")
    markets_collected: Dict[str, int] = Field(default_factory=dict, description="各市场采集数量")


class RefreshCodesResponse(BaseModel):
    """Response for refresh codes."""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="结果消息")
    counts: Dict[str, int] = Field(default_factory=dict, description="各市场代码数量")
