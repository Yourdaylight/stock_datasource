"""Market module schemas."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date


class KLineRequest(BaseModel):
    """K-line data request."""
    code: str = Field(..., description="Stock code, e.g., 000001.SZ")
    start_date: str = Field(..., description="Start date, format: YYYY-MM-DD")
    end_date: str = Field(..., description="End date, format: YYYY-MM-DD")
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


class KLineResponse(BaseModel):
    """K-line data response."""
    code: str
    name: str
    data: List[KLineData]


class IndicatorRequest(BaseModel):
    """Technical indicator request."""
    code: str = Field(..., description="Stock code")
    indicators: List[str] = Field(default=["macd", "rsi", "kdj"], description="Indicator list")
    period: int = Field(default=60, description="Calculation period in days")


class IndicatorData(BaseModel):
    """Indicator data point."""
    date: str
    values: Dict[str, Any]


class IndicatorResponse(BaseModel):
    """Technical indicator response."""
    code: str
    indicators: List[IndicatorData]


class StockSearchResult(BaseModel):
    """Stock search result."""
    code: str
    name: str


class AnalysisRequest(BaseModel):
    """Analysis request."""
    code: str = Field(..., description="Stock code")
    period: int = Field(default=60, description="Analysis period")
