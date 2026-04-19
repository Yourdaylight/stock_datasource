"""Market module schemas."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# Enums
# =============================================================================


class IndicatorType(str, Enum):
    """Available technical indicators."""

    MA = "MA"
    EMA = "EMA"
    MACD = "MACD"
    RSI = "RSI"
    KDJ = "KDJ"
    BOLL = "BOLL"
    ATR = "ATR"
    OBV = "OBV"
    DMI = "DMI"
    CCI = "CCI"


class TrendType(str, Enum):
    """Trend types."""

    UP = "上涨趋势"
    DOWN = "下跌趋势"
    SIDEWAYS = "震荡"


class SignalType(str, Enum):
    """Signal types."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


# =============================================================================
# K-Line Schemas
# =============================================================================


class KLineRequest(BaseModel):
    """K-line data request."""

    code: str = Field(..., description="Stock code, e.g., 000001.SZ")
    start_date: str = Field(
        ..., description="Start date, format: YYYY-MM-DD or YYYYMMDD"
    )
    end_date: str = Field(..., description="End date, format: YYYY-MM-DD or YYYYMMDD")
    adjust: str = Field(default="qfq", description="Adjust type: qfq/hfq/none")


class KLineData(BaseModel):
    """K-line data point."""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    pct_chg: float | None = None  # Daily change percentage


class KLineResponse(BaseModel):
    """K-line data response."""

    code: str
    name: str
    data: list[KLineData]


# =============================================================================
# Indicator Schemas
# =============================================================================


class IndicatorParams(BaseModel):
    """Parameters for indicator calculation."""

    MA: dict[str, Any] | None = Field(
        default=None, description="MA params: {periods: [5,10,20]}"
    )
    EMA: dict[str, Any] | None = Field(
        default=None, description="EMA params: {periods: [12,26]}"
    )
    MACD: dict[str, Any] | None = Field(
        default=None, description="MACD params: {fast:12, slow:26, signal:9}"
    )
    RSI: dict[str, Any] | None = Field(
        default=None, description="RSI params: {period: 14}"
    )
    KDJ: dict[str, Any] | None = Field(
        default=None, description="KDJ params: {n:9, m1:3, m2:3}"
    )
    BOLL: dict[str, Any] | None = Field(
        default=None, description="BOLL params: {period:20, std_dev:2}"
    )
    ATR: dict[str, Any] | None = Field(
        default=None, description="ATR params: {period: 14}"
    )
    DMI: dict[str, Any] | None = Field(
        default=None, description="DMI params: {period: 14}"
    )
    CCI: dict[str, Any] | None = Field(
        default=None, description="CCI params: {period: 14}"
    )


class IndicatorRequest(BaseModel):
    """Technical indicator request."""

    code: str = Field(..., description="Stock code")
    indicators: list[str] = Field(
        default=["MACD", "RSI", "KDJ"], description="Indicator list"
    )
    period: int = Field(
        default=60, ge=10, le=500, description="Calculation period in days"
    )
    params: IndicatorParams | None = Field(
        default=None, description="Custom indicator parameters"
    )


class IndicatorData(BaseModel):
    """Indicator data point (legacy format)."""

    date: str
    values: dict[str, Any]


class IndicatorDataV2(BaseModel):
    """Indicator data with dates array."""

    dates: list[str]
    values: dict[str, list[float | None]]


class IndicatorResponse(BaseModel):
    """Technical indicator response (legacy format for backward compatibility)."""

    code: str
    indicators: list[IndicatorData]


class IndicatorResponseV2(BaseModel):
    """Technical indicator response V2 with better structure."""

    code: str
    name: str
    dates: list[str]
    indicators: dict[str, list[float | None]]
    signals: list[dict[str, Any]] | None = Field(
        default=None, description="Detected trading signals"
    )


# =============================================================================
# Search Schemas
# =============================================================================


class StockSearchResult(BaseModel):
    """Stock search result."""

    code: str
    name: str
    market: str | None = None
    industry: str | None = None


# =============================================================================
# Market Overview Schemas
# =============================================================================


class IndexData(BaseModel):
    """Index data point."""

    code: str
    name: str
    close: float
    pct_chg: float
    volume: float | None = None
    amount: float | None = None


class MarketStats(BaseModel):
    """Market statistics."""

    up_count: int = Field(description="Number of stocks with positive change")
    down_count: int = Field(description="Number of stocks with negative change")
    flat_count: int = Field(description="Number of stocks unchanged")
    limit_up_count: int = Field(default=0, description="Number of stocks at limit up")
    limit_down_count: int = Field(
        default=0, description="Number of stocks at limit down"
    )
    total_amount: float = Field(description="Total trading amount (亿元)")


class MarketOverviewResponse(BaseModel):
    """Market overview response."""

    date: str
    indices: list[IndexData]
    stats: MarketStats


class HotSector(BaseModel):
    """Hot sector data."""

    name: str
    pct_chg: float
    leading_stock: str | None = None
    leading_stock_code: str | None = None


class HotSectorsResponse(BaseModel):
    """Hot sectors response."""

    date: str
    sectors: list[HotSector]


# =============================================================================
# Analysis Schemas
# =============================================================================


class AnalysisRequest(BaseModel):
    """Analysis request."""

    code: str = Field(..., description="Stock code")
    period: int = Field(default=60, description="Analysis period in days")


class TechnicalSignal(BaseModel):
    """Technical signal."""

    type: SignalType
    indicator: str
    signal: str
    description: str


class TrendAnalysisResponse(BaseModel):
    """AI trend analysis response."""

    code: str
    name: str
    trend: str = Field(description="Trend: 上涨趋势/下跌趋势/震荡")
    support: float = Field(description="Support level")
    resistance: float = Field(description="Resistance level")
    signals: list[TechnicalSignal] = Field(
        default_factory=list, description="Technical signals"
    )
    summary: str = Field(description="AI analysis summary")
    disclaimer: str = Field(
        default="以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。",
        description="Risk disclaimer",
    )


# =============================================================================
# Pattern Recognition Schemas
# =============================================================================


class PatternRequest(BaseModel):
    """Pattern recognition request."""

    code: str = Field(..., description="Stock code")
    period: int = Field(default=60, description="Analysis period")


class PatternResult(BaseModel):
    """Pattern recognition result."""

    pattern: str
    confidence: float = Field(ge=0, le=1)
    description: str
    implication: str = Field(description="Bullish/Bearish implication")
