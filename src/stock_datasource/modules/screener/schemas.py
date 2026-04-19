"""Screener module data models/schemas."""

from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# Request Models
# =============================================================================


class ScreenerCondition(BaseModel):
    """筛选条件"""

    field: str
    operator: str  # gt/gte/lt/lte/eq/neq/in/between
    value: float | int | str | list[Any]


class ScreenerRequest(BaseModel):
    """多条件筛选请求"""

    conditions: list[ScreenerCondition] = Field(default_factory=list)
    sort_by: str | None = None
    sort_order: str = "desc"
    limit: int = 100
    trade_date: str | None = Field(
        None, description="交易日期，格式 YYYY-MM-DD，默认最新日期"
    )
    market_type: str | None = Field(
        None, description="市场类型: a_share, hk_stock, all (默认 a_share)"
    )
    search: str | None = Field(None, description="按名称/代码模糊搜索")


class NLScreenerRequest(BaseModel):
    """自然语言选股请求"""

    query: str


class BatchProfileRequest(BaseModel):
    """批量画像请求"""

    ts_codes: list[str]


# =============================================================================
# Response Models
# =============================================================================


class StockItem(BaseModel):
    """股票列表项 - 必须同时包含代码和名称"""

    ts_code: str  # 必须
    stock_name: str | None = None  # 股票名称
    trade_date: str | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    pct_chg: float | None = None
    vol: float | None = None
    amount: float | None = None
    pe_ttm: float | None = None
    pb: float | None = None
    ps_ttm: float | None = None
    dv_ratio: float | None = None  # 股息率
    total_mv: float | None = None
    circ_mv: float | None = None
    turnover_rate: float | None = None
    industry: str | None = None


class StockListResponse(BaseModel):
    """分页股票列表响应"""

    items: list[StockItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class NLScreenerResponse(BaseModel):
    """自然语言选股响应"""

    parsed_conditions: list[ScreenerCondition] = Field(default_factory=list)
    items: list[StockItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
    explanation: str = ""


# =============================================================================
# Profile Models (十维画像)
# =============================================================================


class ProfileDimension(BaseModel):
    """画像维度"""

    name: str
    score: float  # 0-100
    level: str  # 优秀/良好/中等/较差
    weight: float  # 权重
    indicators: dict[str, Any] = Field(default_factory=dict)


class StockProfile(BaseModel):
    """股票十维画像"""

    ts_code: str
    stock_name: str  # 必须包含股票名称
    trade_date: str

    # 综合评分
    total_score: float

    # 十个维度
    dimensions: list[ProfileDimension] = Field(default_factory=list)

    # 综合建议
    recommendation: str = ""

    # 原始数据
    raw_data: dict[str, Any] | None = None


# =============================================================================
# Recommendation Models (AI推荐)
# =============================================================================


class Recommendation(BaseModel):
    """AI推荐结果"""

    ts_code: str
    stock_name: str  # 必须包含股票名称
    reason: str
    score: float
    category: str  # 低估值/高成长/技术突破等
    profile: StockProfile | None = None


class RecommendationResponse(BaseModel):
    """推荐列表响应"""

    trade_date: str
    categories: dict[str, list[Recommendation]] = Field(default_factory=dict)


# =============================================================================
# Sector Models (行业板块)
# =============================================================================


class SectorInfo(BaseModel):
    """行业信息"""

    name: str
    stock_count: int


class SectorListResponse(BaseModel):
    """行业列表响应"""

    sectors: list[SectorInfo]
    total: int


# =============================================================================
# Preset Strategy Models
# =============================================================================


class PresetStrategy(BaseModel):
    """预设策略"""

    id: str
    name: str
    description: str
    conditions: list[ScreenerCondition]


# =============================================================================
# Technical Signal Models
# =============================================================================


class TechnicalSignal(BaseModel):
    """技术信号"""

    ts_code: str
    stock_name: str
    signal_type: str  # macd_golden/ma_bullish/volume_breakout/rsi_oversold
    signal_name: str
    strength: float  # 信号强度 0-100
    description: str


class TechnicalSignalResponse(BaseModel):
    """技术信号响应"""

    trade_date: str
    signals: dict[str, list[TechnicalSignal]] = Field(default_factory=dict)


# =============================================================================
# Field Definition
# =============================================================================


class FieldDefinition(BaseModel):
    """筛选字段定义"""

    field: str
    label: str
    type: str  # number/string/select
    options: list[dict[str, str]] | None = None


# =============================================================================
# Market Summary
# =============================================================================


class MarketSummary(BaseModel):
    """市场概况"""

    trade_date: str
    total_stocks: int
    up_count: int
    down_count: int
    flat_count: int
    limit_up: int
    limit_down: int
    avg_change: float
    # 交易日历信息
    is_trading_day: bool | None = None  # 今天是否交易日
    prev_trading_day: str | None = None  # 上一个交易日
    next_trading_day: str | None = None  # 下一个交易日
    market_label: str | None = None  # 市场标签 (A股/港股)
