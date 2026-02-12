"""Screener module data models/schemas."""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field


# =============================================================================
# Request Models
# =============================================================================

class ScreenerCondition(BaseModel):
    """筛选条件"""
    field: str
    operator: str  # gt/gte/lt/lte/eq/neq/in/between
    value: Union[float, int, str, List[Any]]


class ScreenerRequest(BaseModel):
    """多条件筛选请求"""
    conditions: List[ScreenerCondition] = Field(default_factory=list)
    sort_by: Optional[str] = None
    sort_order: str = "desc"
    limit: int = 100
    trade_date: Optional[str] = Field(None, description="交易日期，格式 YYYY-MM-DD，默认最新日期")
    market_type: Optional[str] = Field(None, description="市场类型: a_share, hk_stock, all (默认 a_share)")


class NLScreenerRequest(BaseModel):
    """自然语言选股请求"""
    query: str


class BatchProfileRequest(BaseModel):
    """批量画像请求"""
    ts_codes: List[str]


# =============================================================================
# Response Models
# =============================================================================

class StockItem(BaseModel):
    """股票列表项 - 必须同时包含代码和名称"""
    ts_code: str  # 必须
    stock_name: Optional[str] = None  # 股票名称
    trade_date: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    pct_chg: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    ps_ttm: Optional[float] = None
    dv_ratio: Optional[float] = None  # 股息率
    total_mv: Optional[float] = None
    circ_mv: Optional[float] = None
    turnover_rate: Optional[float] = None
    industry: Optional[str] = None


class StockListResponse(BaseModel):
    """分页股票列表响应"""
    items: List[StockItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class NLScreenerResponse(BaseModel):
    """自然语言选股响应"""
    parsed_conditions: List[ScreenerCondition] = Field(default_factory=list)
    items: List[StockItem] = Field(default_factory=list)
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
    indicators: Dict[str, Any] = Field(default_factory=dict)


class StockProfile(BaseModel):
    """股票十维画像"""
    ts_code: str
    stock_name: str  # 必须包含股票名称
    trade_date: str
    
    # 综合评分
    total_score: float
    
    # 十个维度
    dimensions: List[ProfileDimension] = Field(default_factory=list)
    
    # 综合建议
    recommendation: str = ""
    
    # 原始数据
    raw_data: Optional[Dict[str, Any]] = None


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
    profile: Optional[StockProfile] = None


class RecommendationResponse(BaseModel):
    """推荐列表响应"""
    trade_date: str
    categories: Dict[str, List[Recommendation]] = Field(default_factory=dict)


# =============================================================================
# Sector Models (行业板块)
# =============================================================================

class SectorInfo(BaseModel):
    """行业信息"""
    name: str
    stock_count: int


class SectorListResponse(BaseModel):
    """行业列表响应"""
    sectors: List[SectorInfo]
    total: int


# =============================================================================
# Preset Strategy Models
# =============================================================================

class PresetStrategy(BaseModel):
    """预设策略"""
    id: str
    name: str
    description: str
    conditions: List[ScreenerCondition]


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
    signals: Dict[str, List[TechnicalSignal]] = Field(default_factory=dict)


# =============================================================================
# Field Definition
# =============================================================================

class FieldDefinition(BaseModel):
    """筛选字段定义"""
    field: str
    label: str
    type: str  # number/string/select
    options: Optional[List[Dict[str, str]]] = None


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
