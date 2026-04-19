"""Signal aggregator schemas - 信号聚合数据模型."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 维度信号输入
# ---------------------------------------------------------------------------


class NewsSignalInput(BaseModel):
    """消息面信号输入."""

    ts_code: str
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    average_score: float = Field(default=0.0, ge=-1.0, le=1.0, description="情绪均分 -1~1")
    high_impact_count: int = Field(default=0, description="重大影响新闻数")
    top_headlines: list[str] = Field(default_factory=list, description="重要新闻标题(最多3条)")


class CapitalFlowSignalInput(BaseModel):
    """资金面信号输入."""

    ts_code: str
    net_institutional_flow: float = Field(default=0.0, description="机构净流入(元)")
    hot_money_count: int = Field(default=0, description="游资参与席位数")
    seat_hhi: float = Field(default=0.0, ge=0.0, le=1.0, description="席位集中度HHI")
    northbound_net_flow: float = Field(default=0.0, description="北向净流入(元)")
    sector_flow_rank: int | None = Field(default=None, description="板块资金流向排名")


class TechSignalInput(BaseModel):
    """技术面信号输入."""

    ts_code: str
    signal_type: Literal["buy", "sell", "reduce", "hold"] = "hold"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    target_position: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""
    ma_short: float | None = None
    ma_long: float | None = None


# ---------------------------------------------------------------------------
# 评分结果
# ---------------------------------------------------------------------------


class DimensionScore(BaseModel):
    """单维度评分."""

    score: float = Field(default=50.0, ge=0.0, le=100.0, description="0-100评分")
    direction: Literal["bullish", "bearish", "neutral"] = "neutral"
    detail: dict[str, Any] = Field(default_factory=dict, description="评分细节")


class StockObservationScore(BaseModel):
    """股票可观测综合评分."""

    ts_code: str
    stock_name: str = ""
    signal_date: str = ""
    news_score: DimensionScore = Field(default_factory=DimensionScore)
    capital_score: DimensionScore = Field(default_factory=DimensionScore)
    tech_score: DimensionScore = Field(default_factory=DimensionScore)
    composite_score: float = Field(default=50.0, ge=0.0, le=100.0)
    composite_direction: Literal["bullish", "bearish", "neutral"] = "neutral"
    updated_at: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# 时序快照
# ---------------------------------------------------------------------------


class SignalSnapshot(BaseModel):
    """信号快照(存ClickHouse)."""

    ts_code: str
    signal_date: str
    news_score: float = 50.0
    capital_score: float = 50.0
    tech_score: float = 50.0
    composite_score: float = 50.0
    news_detail: dict[str, Any] = Field(default_factory=dict)
    capital_detail: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# API 响应
# ---------------------------------------------------------------------------


class StockSignalSummary(BaseModel):
    """单股票信号汇总(前端用)."""

    ts_code: str
    stock_name: str = ""
    composite_score: float = 50.0
    composite_direction: Literal["bullish", "bearish", "neutral"] = "neutral"
    news_score: float = 50.0
    capital_score: float = 50.0
    tech_score: float = 50.0
    news_detail: dict[str, Any] = Field(default_factory=dict)
    capital_detail: dict[str, Any] = Field(default_factory=dict)
    tech_detail: dict[str, Any] = Field(default_factory=dict)
    signal_date: str = ""


class SignalAggregationResponse(BaseModel):
    """信号聚合API响应."""

    stocks: list[StockSignalSummary] = Field(default_factory=list)
    trade_date: str = ""
    total_count: int = 0


class SignalTimelineResponse(BaseModel):
    """信号时序追踪响应."""

    ts_code: str
    stock_name: str = ""
    snapshots: list[SignalSnapshot] = Field(default_factory=list)


class SignalWeightsConfig(BaseModel):
    """信号权重配置."""

    news_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    capital_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    tech_weight: float = Field(default=0.3, ge=0.0, le=1.0)

    def normalized(self) -> tuple[float, float, float]:
        """Return normalized weights that sum to 1.0."""
        total = self.news_weight + self.capital_weight + self.tech_weight
        if total == 0:
            return 0.33, 0.34, 0.33
        return (
            self.news_weight / total,
            self.capital_weight / total,
            self.tech_weight / total,
        )
