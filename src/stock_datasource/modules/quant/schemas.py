"""Pydantic schemas for quant module."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class EngineStage(str, Enum):
    SCREENING = "screening"
    CORE_POOL = "core_pool"
    DEEP_ANALYSIS = "deep_analysis"
    TRADING_SIGNALS = "trading_signals"


class DataStatus(str, Enum):
    READY = "ready"
    MISSING_TABLE = "missing_table"
    MISSING_DATES = "missing_dates"
    INSUFFICIENT_DATA = "insufficient_data"


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    DATA_MISSING = "data_missing"
    ERROR = "error"


class SignalType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    ADD = "add"
    REDUCE = "reduce"


class PoolType(str, Enum):
    CORE = "core"
    RPS_SUPPLEMENT = "rps_supplement"
    WATCHLIST = "watchlist"


# =============================================================================
# Data Readiness Schemas
# =============================================================================

class DataRequirement(BaseModel):
    """Single data requirement declaration."""
    plugin_name: str
    table_name: str
    required_columns: list[str] = Field(default_factory=list)
    date_column: str = "trade_date"
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    min_records: int = 0
    description: str = ""


class PluginTriggerInfo(BaseModel):
    """Info for one plugin that needs triggering (displayed in frontend)."""
    plugin_name: str
    display_name: str
    table_name: str
    missing_dates: list[str] = Field(default_factory=list)
    task_type: str = "incremental"
    description: str = ""


class DataRequirementStatus(BaseModel):
    """Status of a single data requirement."""
    requirement: DataRequirement
    status: DataStatus = DataStatus.READY
    existing_date_range: Optional[list[str]] = None
    missing_dates: list[str] = Field(default_factory=list)
    record_count: int = 0
    suggested_plugins: list[str] = Field(default_factory=list)
    suggested_task_type: str = "incremental"


class MissingDataSummary(BaseModel):
    """Missing data summary for frontend display."""
    total_requirements: int = 0
    ready_count: int = 0
    missing_count: int = 0
    affected_engines: list[str] = Field(default_factory=list)
    plugins_to_trigger: list[PluginTriggerInfo] = Field(default_factory=list)
    estimated_sync_time: str = ""


class DataReadinessResult(BaseModel):
    """Data readiness check result."""
    is_ready: bool = False
    checked_at: str = ""
    stage: str = ""
    requirements: list[DataRequirementStatus] = Field(default_factory=list)
    missing_summary: Optional[MissingDataSummary] = None


# =============================================================================
# Screening Schemas
# =============================================================================

class ScreeningRule(BaseModel):
    """Configurable screening rule."""
    name: str
    category: str = "traditional"  # traditional / custom / benford
    enabled: bool = True
    params: dict[str, Any] = Field(default_factory=dict)
    is_hard_reject: bool = True
    description: str = ""


class RuleExecutionDetail(BaseModel):
    """Per-rule execution detail for frontend display."""
    rule_name: str
    category: str
    enabled: bool = True
    total_checked: int = 0
    passed_count: int = 0
    rejected_count: int = 0
    skipped_count: int = 0
    execution_time_ms: int = 0
    threshold: str = ""
    sample_rejects: list[dict[str, Any]] = Field(default_factory=list)


class ScreeningResultItem(BaseModel):
    """Single stock screening result."""
    ts_code: str
    stock_name: str = ""
    overall_pass: bool = False
    reject_reasons: list[str] = Field(default_factory=list)
    rule_details: list[dict[str, Any]] = Field(default_factory=list)
    roe_3y_avg: Optional[float] = None
    revenue_growth_2y: list[float] = Field(default_factory=list)
    net_profit: Optional[float] = None
    cashflow_sync_ratio: Optional[float] = None
    benford_p_value: Optional[float] = None


class ScreeningResult(BaseModel):
    """Full screening result for frontend display."""
    run_date: str = ""
    run_id: str = ""
    total_stocks: int = 0
    passed_count: int = 0
    rejected_count: int = 0
    passed_stocks: list[ScreeningResultItem] = Field(default_factory=list)
    rejected_stocks: list[ScreeningResultItem] = Field(default_factory=list)
    rule_details: list[RuleExecutionDetail] = Field(default_factory=list)
    data_readiness: Optional[DataReadinessResult] = None
    execution_time_ms: int = 0
    status: str = "success"


class ScreeningRunRequest(BaseModel):
    """Request to run screening."""
    trade_date: Optional[str] = None
    rules: Optional[list[ScreeningRule]] = None


# =============================================================================
# Factor / Core Pool Schemas
# =============================================================================

class FactorWeight(BaseModel):
    """Factor weight configuration."""
    quality: float = 0.30
    growth: float = 0.30
    value: float = 0.20
    momentum: float = 0.20


class FactorScoreDetail(BaseModel):
    """Per-stock factor score detail for frontend."""
    ts_code: str
    stock_name: str = ""
    quality_score: float = 0
    quality_breakdown: dict[str, Any] = Field(default_factory=dict)
    growth_score: float = 0
    growth_breakdown: dict[str, Any] = Field(default_factory=dict)
    value_score: float = 0
    value_breakdown: dict[str, Any] = Field(default_factory=dict)
    momentum_score: float = 0
    momentum_breakdown: dict[str, Any] = Field(default_factory=dict)
    total_score: float = 0
    rank: int = 0
    pool_type: str = ""
    rps_250: float = 0


class PoolChange(BaseModel):
    """Pool entry/exit change record."""
    ts_code: str
    stock_name: str = ""
    change_type: str = ""  # new_entry / exit / rank_change
    change_date: str = ""
    old_rank: Optional[int] = None
    new_rank: Optional[int] = None
    total_score: float = 0
    reason: str = ""


class CorePoolResult(BaseModel):
    """Core pool build result for frontend."""
    update_date: str = ""
    core_stocks: list[FactorScoreDetail] = Field(default_factory=list)
    supplement_stocks: list[FactorScoreDetail] = Field(default_factory=list)
    pool_changes: list[PoolChange] = Field(default_factory=list)
    factor_distribution: dict[str, Any] = Field(default_factory=dict)
    data_readiness: Optional[DataReadinessResult] = None
    execution_time_ms: int = 0


# =============================================================================
# RPS Schemas
# =============================================================================

class RPSRankItem(BaseModel):
    """RPS rank for a stock."""
    ts_code: str
    stock_name: str = ""
    rps_250: float = 0
    rps_120: float = 0
    rps_60: float = 0
    price_chg_250: float = 0
    price_chg_120: float = 0
    price_chg_60: float = 0
    calc_date: str = ""


class RPSResult(BaseModel):
    """RPS calculation result."""
    calc_date: str = ""
    total_stocks: int = 0
    items: list[RPSRankItem] = Field(default_factory=list)
    data_readiness: Optional[DataReadinessResult] = None


# =============================================================================
# Deep Analysis Schemas
# =============================================================================

class TechSnapshot(BaseModel):
    """Technical indicator snapshot for frontend charts."""
    ts_code: str
    stock_name: str = ""
    ma25: Optional[float] = None
    ma120: Optional[float] = None
    ma250: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    rsi_14: Optional[float] = None
    volume_ratio: Optional[float] = None
    close: Optional[float] = None
    pct_chg: Optional[float] = None
    ma_position: str = ""  # above_all / between / below_all


class AiAnalysisCard(BaseModel):
    """AI analysis card for frontend."""
    ts_code: str
    stock_name: str = ""
    credibility_score: float = 0
    optimism_score: float = 0
    key_findings: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    verification_points: list[str] = Field(default_factory=list)
    ai_summary: str = ""


class DeepAnalysisResult(BaseModel):
    """Deep analysis result for a stock."""
    ts_code: str
    stock_name: str = ""
    analysis_date: str = ""
    tech_snapshot: Optional[TechSnapshot] = None
    ai_analysis: Optional[AiAnalysisCard] = None
    tech_score: float = 0
    overall_score: float = 0


class BatchAnalysisStatus(BaseModel):
    """Batch analysis progress for frontend."""
    total: int = 0
    completed: int = 0
    failed: int = 0
    in_progress: str = ""
    results: list[DeepAnalysisResult] = Field(default_factory=list)


# =============================================================================
# Trading Signal Schemas
# =============================================================================

class SignalConfig(BaseModel):
    """Signal generation config."""
    ma_short: int = 25
    ma_long: int = 120
    max_position_pct: float = 0.05
    stop_loss_pct: float = 0.15
    trailing_stop_pct: float = 0.10
    rps_exit_threshold: float = 75
    market_risk_ma: int = 250
    market_risk_position: float = 0.50


class TradingSignal(BaseModel):
    """Trading signal for frontend."""
    signal_date: str = ""
    ts_code: str
    stock_name: str = ""
    signal_type: str = ""  # buy / sell / add / reduce
    signal_source: str = ""  # ma_crossover / stop_loss / stop_profit / risk_control
    price: float = 0
    target_position: float = 0
    confidence: float = 0
    reason: str = ""
    pool_type: str = ""
    ma25: float = 0
    ma120: float = 0
    signal_context: dict[str, Any] = Field(default_factory=dict)


class MarketRiskStatus(BaseModel):
    """Market risk status for frontend."""
    index_code: str = "000300.SH"
    index_name: str = "沪深300"
    index_close: float = 0
    index_ma250: float = 0
    is_above_ma250: bool = True
    risk_level: str = "normal"  # normal / warning / danger
    suggested_position: float = 1.0
    description: str = ""


class SignalResult(BaseModel):
    """Signal generation result."""
    signal_date: str = ""
    signals: list[TradingSignal] = Field(default_factory=list)
    market_risk: Optional[MarketRiskStatus] = None
    data_readiness: Optional[DataReadinessResult] = None
    execution_time_ms: int = 0


# =============================================================================
# Pipeline Schemas
# =============================================================================

class PipelineStageStatus(BaseModel):
    """Status for one pipeline stage."""
    name: str
    stage: str = ""
    status: str = "pending"  # pending / running / completed / data_missing / error
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    result_summary: dict[str, Any] = Field(default_factory=dict)
    data_readiness: Optional[DataReadinessResult] = None
    error_message: str = ""


class PipelineRunStatus(BaseModel):
    """Full pipeline run status for frontend."""
    run_id: str = ""
    run_date: str = ""
    pipeline_type: str = "full"
    overall_status: str = "pending"
    triggered_by: str = "manual"
    stages: list[PipelineStageStatus] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class PipelineRunRequest(BaseModel):
    """Request to run pipeline."""
    pipeline_type: str = "full"  # full / screening_only / signal_only
    trade_date: Optional[str] = None


# =============================================================================
# Config Schemas
# =============================================================================

class QuantConfig(BaseModel):
    """Quant model configuration."""
    config_id: str = ""
    config_name: str = ""
    config_type: str = ""  # screening_rules / factor_weights / signal_params / risk_params
    config_data: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    updated_at: str = ""


class QuantConfigUpdate(BaseModel):
    """Config update request."""
    config_type: str
    config_data: dict[str, Any]
    config_name: Optional[str] = None
