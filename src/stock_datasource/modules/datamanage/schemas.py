"""Data management module schemas."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    """Sync task status enum."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Sync task type enum."""
    FULL = "full"
    INCREMENTAL = "incremental"
    BACKFILL = "backfill"


class ScheduleFrequency(str, Enum):
    """Plugin schedule frequency enum."""
    DAILY = "daily"
    WEEKLY = "weekly"


# Request Models
class TriggerSyncRequest(BaseModel):
    """Request model for triggering sync."""
    plugin_name: str
    task_type: TaskType = TaskType.INCREMENTAL
    trade_dates: Optional[List[str]] = None  # For backfill
    force_overwrite: bool = False  # Whether to overwrite existing data


class ManualDetectRequest(BaseModel):
    """Request model for manual missing data detection."""
    days: int = Field(default=30, ge=1, le=365)


class CheckDataExistsRequest(BaseModel):
    """Request model for checking if data exists for specific dates."""
    dates: List[str] = Field(..., min_length=1, description="List of dates to check (YYYY-MM-DD format)")


# Response Models
class DataSource(BaseModel):
    """Data source info."""
    id: str
    source_name: str
    source_type: str
    provider: str
    is_enabled: bool = True
    last_sync_at: Optional[str] = None


class SyncTask(BaseModel):
    """Sync task info."""
    task_id: str
    plugin_name: str
    task_type: str
    status: TaskStatus
    progress: float = 0
    records_processed: int = 0
    total_records: int = 0
    error_message: Optional[str] = None
    trade_dates: List[str] = []
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class PluginSchedule(BaseModel):
    """Plugin schedule configuration."""
    frequency: ScheduleFrequency
    time: str = "18:00"
    day_of_week: Optional[str] = None


class PluginStatus(BaseModel):
    """Plugin data status."""
    latest_date: Optional[str] = None
    missing_count: int = 0
    missing_dates: List[str] = []
    total_records: int = 0


class PluginColumn(BaseModel):
    """Plugin schema column definition."""
    name: str
    data_type: str
    nullable: bool = True
    comment: Optional[str] = None
    default: Optional[str] = None


class PluginSchema(BaseModel):
    """Plugin schema definition."""
    table_name: str
    table_type: str = "ods"
    columns: List[PluginColumn] = []
    partition_by: Optional[str] = None
    order_by: List[str] = []
    engine: str = "ReplacingMergeTree"
    engine_params: List[str] = []
    comment: Optional[str] = None


class PluginConfig(BaseModel):
    """Plugin configuration."""
    enabled: bool = True
    rate_limit: int = 120
    timeout: int = 30
    retry_attempts: int = 3
    description: Optional[str] = None
    schedule: Optional[PluginSchedule] = None
    parameters_schema: Dict[str, Any] = {}


class PluginInfo(BaseModel):
    """Basic plugin info for list view."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    type: str = "data_source"
    is_enabled: bool = True
    schedule_frequency: Optional[str] = None
    schedule_time: Optional[str] = None
    latest_date: Optional[str] = None
    missing_count: int = 0
    last_run_at: Optional[str] = None
    last_run_status: Optional[str] = None


class PluginDetail(BaseModel):
    """Detailed plugin info including config and schema."""
    plugin_name: str
    version: str = "1.0.0"
    description: str = ""
    config: PluginConfig
    table_schema: PluginSchema
    status: PluginStatus


class PluginDataPreview(BaseModel):
    """Plugin data preview response."""
    plugin_name: str
    table_name: str
    columns: List[str]
    data: List[Dict[str, Any]]
    total_count: int
    page: int = 1
    page_size: int = 100


class MissingDataInfo(BaseModel):
    """Missing data info for a plugin."""
    plugin_name: str
    table_name: str
    schedule_frequency: str
    latest_date: Optional[str] = None
    missing_dates: List[str] = []
    missing_count: int = 0


class MissingDataSummary(BaseModel):
    """Summary of missing data across all plugins."""
    check_time: datetime
    total_plugins: int
    plugins_with_missing: int
    plugins: List[MissingDataInfo]


class QualityMetrics(BaseModel):
    """Data quality metrics."""
    table_name: str
    completeness_score: float
    consistency_score: float
    timeliness_score: float
    overall_score: float
    record_count: int
    latest_update: Optional[str] = None


class SyncHistory(BaseModel):
    """Sync task history record."""
    task_id: str
    plugin_name: str
    task_type: str
    status: str
    records_processed: int
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None


# AI Diagnosis Models
class DiagnosisRequest(BaseModel):
    """Request model for AI diagnosis."""
    log_lines: int = Field(default=100, ge=10, le=500, description="Number of log lines to analyze")
    include_errors_only: bool = Field(default=False, description="Only include error logs")
    context: Optional[str] = Field(default=None, description="Additional context for diagnosis")


class DiagnosisSuggestion(BaseModel):
    """A single diagnosis suggestion."""
    severity: str  # 'critical', 'warning', 'info'
    category: str  # 'config', 'data', 'connection', 'plugin', 'system'
    title: str
    description: str
    suggestion: str
    related_logs: List[str] = []


class DiagnosisResult(BaseModel):
    """AI diagnosis result."""
    diagnosis_time: datetime
    log_lines_analyzed: int
    error_count: int
    warning_count: int
    summary: str
    suggestions: List[DiagnosisSuggestion]
    raw_errors: List[str] = []


class DataExistsCheckResult(BaseModel):
    """Result of checking if data exists for specific dates."""
    plugin_name: str
    dates_checked: List[str]
    existing_dates: List[str]
    non_existing_dates: List[str]
    record_counts: Dict[str, int] = {}  # date -> record count
