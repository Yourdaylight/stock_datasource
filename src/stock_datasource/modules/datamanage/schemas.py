"""Data management module schemas."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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
    MONTHLY = "monthly"


class PluginCategoryEnum(str, Enum):
    """Plugin category enum."""

    CN_STOCK = "cn_stock"  # A股相关
    HK_STOCK = "hk_stock"  # 港股相关
    INDEX = "index"  # 指数相关
    ETF_FUND = "etf_fund"  # ETF/基金相关
    SYSTEM = "system"  # 系统数据
    STOCK = "stock"  # 兼容旧值


class PluginRoleEnum(str, Enum):
    """Plugin role enum."""

    PRIMARY = "primary"
    BASIC = "basic"
    DERIVED = "derived"
    AUXILIARY = "auxiliary"


# Request Models
class TriggerSyncRequest(BaseModel):
    """Request model for triggering sync."""

    plugin_name: str
    task_type: TaskType = TaskType.INCREMENTAL
    trade_dates: list[str] | None = None  # For backfill
    force_overwrite: bool = False  # Whether to overwrite existing data
    include_optional: bool = True  # Whether to include optional dependencies
    # Parallelism settings (optional, use global settings if not provided)
    max_concurrent_tasks: int | None = Field(
        None, ge=1, le=10, description="Max parallel tasks (1-10)"
    )
    max_date_threads: int | None = Field(
        None, ge=1, le=20, description="Max threads per task for multi-date (1-20)"
    )


class ManualDetectRequest(BaseModel):
    """Request model for manual missing data detection."""

    days: int = Field(default=1825, ge=1, le=3650)  # Default 5 years, max 10 years


class CheckDataExistsRequest(BaseModel):
    """Request model for checking if data exists for specific dates."""

    dates: list[str] = Field(
        ..., min_length=1, description="List of dates to check (YYYY-MM-DD format)"
    )


class SyncConfigRequest(BaseModel):
    """Request model for updating sync configuration."""

    max_concurrent_tasks: int | None = Field(
        None, ge=1, le=10, description="Max parallel tasks (1-10)"
    )
    max_date_threads: int | None = Field(
        None, ge=1, le=20, description="Max threads per task for multi-date (1-20)"
    )


class SyncConfig(BaseModel):
    """Sync configuration response."""

    max_concurrent_tasks: int = Field(description="Current max parallel tasks")
    max_date_threads: int = Field(description="Current max threads per task")
    running_tasks_count: int = Field(description="Currently running tasks")
    pending_tasks_count: int = Field(description="Pending tasks in queue")
    running_plugins: list[str] = Field(description="Plugins currently running")


# Response Models
class DataSource(BaseModel):
    """Data source info."""

    id: str
    source_name: str
    source_type: str
    provider: str
    is_enabled: bool = True
    last_sync_at: str | None = None


class SyncTask(BaseModel):
    """Sync task info."""

    task_id: str
    plugin_name: str
    task_type: str
    status: TaskStatus
    progress: float = 0
    records_processed: int = 0
    total_records: int = 0
    error_message: str | None = None
    trade_dates: list[str] = []
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    # User tracking fields
    user_id: str | None = None
    username: str | None = None


class PluginSchedule(BaseModel):
    """Plugin schedule configuration."""

    frequency: ScheduleFrequency
    time: str = "18:00"
    day_of_week: str | None = None


class PluginStatus(BaseModel):
    """Plugin data status."""

    latest_date: str | None = None
    missing_count: int = 0
    missing_dates: list[str] = []
    total_records: int = 0


class PluginColumn(BaseModel):
    """Plugin schema column definition."""

    name: str
    data_type: str
    nullable: bool = True
    comment: str | None = None
    default: str | None = None


class PluginSchema(BaseModel):
    """Plugin schema definition."""

    table_name: str
    table_type: str = "ods"
    columns: list[PluginColumn] = []
    partition_by: str | None = None
    order_by: list[str] = []
    engine: str = "ReplacingMergeTree"
    engine_params: list[str] = []
    comment: str | None = None


class PluginConfig(BaseModel):
    """Plugin configuration."""

    enabled: bool = True
    rate_limit: int = 120
    timeout: int = 30
    retry_attempts: int = 3
    description: str | None = None
    schedule: PluginSchedule | None = None
    parameters_schema: dict[str, Any] = {}


class PluginInfo(BaseModel):
    """Basic plugin info for list view."""

    name: str
    version: str = "1.0.0"
    description: str = ""
    type: str = "data_source"
    category: str = "stock"
    role: str = "primary"
    is_enabled: bool = True
    schedule_frequency: str | None = None
    schedule_time: str | None = None
    latest_date: str | None = None
    missing_count: int = 0
    last_run_at: str | None = None
    last_run_status: str | None = None
    dependencies: list[str] = []
    optional_dependencies: list[str] = []


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
    columns: list[str]
    data: list[dict[str, Any]]
    total_count: int
    page: int = 1
    page_size: int = 100


class MissingDataInfo(BaseModel):
    """Missing data info for a plugin."""

    plugin_name: str
    table_name: str
    schedule_frequency: str
    latest_date: str | None = None
    missing_dates: list[str] = []
    missing_count: int = 0


class MissingDataSummary(BaseModel):
    """Summary of missing data across all plugins."""

    check_time: datetime
    total_plugins: int
    plugins_with_missing: int
    plugins: list[MissingDataInfo]


class QualityMetrics(BaseModel):
    """Data quality metrics."""

    table_name: str
    completeness_score: float
    consistency_score: float
    timeliness_score: float
    overall_score: float
    record_count: int
    latest_update: str | None = None


class SyncHistory(BaseModel):
    """Sync task history record."""

    task_id: str
    plugin_name: str
    task_type: str
    status: str
    records_processed: int
    error_message: str | None = None
    error_traceback: str | None = None  # 完整错误堆栈
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    # User tracking fields
    user_id: str | None = None
    username: str | None = None


class SyncTaskListResponse(BaseModel):
    """Paginated sync task list response."""

    items: list[SyncTask]
    total: int
    page: int
    page_size: int
    total_pages: int


# AI Diagnosis Models
class DiagnosisRequest(BaseModel):
    """Request model for AI diagnosis."""

    log_lines: int = Field(
        default=100, ge=10, le=500, description="Number of log lines to analyze"
    )
    include_errors_only: bool = Field(
        default=False, description="Only include error logs"
    )
    context: str | None = Field(
        default=None, description="Additional context for diagnosis"
    )


class DiagnosisSuggestion(BaseModel):
    """A single diagnosis suggestion."""

    severity: str  # 'critical', 'warning', 'info'
    category: str  # 'config', 'data', 'connection', 'plugin', 'system'
    title: str
    description: str
    suggestion: str
    related_logs: list[str] = []


class DiagnosisResult(BaseModel):
    """AI diagnosis result."""

    diagnosis_time: datetime
    log_lines_analyzed: int
    error_count: int
    warning_count: int
    summary: str
    suggestions: list[DiagnosisSuggestion]
    raw_errors: list[str] = []


class DataExistsCheckResult(BaseModel):
    """Result of checking if data exists for specific dates."""

    plugin_name: str
    dates_checked: list[str]
    existing_dates: list[str]
    non_existing_dates: list[str]
    record_counts: dict[str, int] = {}  # date -> record count


class GroupDataExistsCheckRequest(BaseModel):
    """Request model for checking if data exists for a group of plugins."""

    dates: list[str] = Field(
        ..., min_length=1, description="List of dates to check (YYYY-MM-DD format)"
    )


class PluginDataExistsInfo(BaseModel):
    """Data existence info for a single plugin."""

    plugin_name: str
    existing_dates: list[str]
    non_existing_dates: list[str]
    has_date_column: bool = True  # False for dimension tables


class GroupDataExistsCheckResult(BaseModel):
    """Result of checking if data exists for a group of plugins."""

    group_id: str
    group_name: str
    dates_checked: list[str]
    plugins: list[PluginDataExistsInfo]
    # Summary
    all_plugins_have_data: bool  # All plugins have data for all dates
    plugins_with_existing_data: list[
        str
    ]  # Plugins that have data (might need overwrite)
    plugins_missing_data: list[str]  # Plugins that don't have data


# ============================================
# Proxy Configuration Models
# ============================================


class ProxyConfig(BaseModel):
    """HTTP Proxy configuration."""

    enabled: bool = Field(default=False, description="Whether proxy is enabled")
    host: str = Field(default="", description="Proxy host address")
    port: int = Field(default=0, description="Proxy port")
    username: str | None = Field(default=None, description="Proxy username (optional)")
    password: str | None = Field(default=None, description="Proxy password (optional)")


class ProxyConfigRequest(BaseModel):
    """Request model for updating proxy configuration."""

    enabled: bool = Field(..., description="Whether to enable proxy")
    host: str = Field(default="", description="Proxy host address")
    port: int = Field(default=0, ge=0, le=65535, description="Proxy port (0-65535)")
    username: str | None = Field(default=None, description="Proxy username")
    password: str | None = Field(default=None, description="Proxy password")


class ProxyTestResult(BaseModel):
    """Result of proxy connection test."""

    success: bool
    message: str
    latency_ms: float | None = None
    external_ip: str | None = None


# ============================================
# Plugin Dependency Models
# ============================================


class PluginDependency(BaseModel):
    """Plugin dependency information."""

    plugin_name: str
    has_data: bool
    table_name: str | None = None
    record_count: int = 0


class DependencyCheckResponse(BaseModel):
    """Response for dependency check endpoint."""

    plugin_name: str
    dependencies: list[str]
    optional_dependencies: list[str] = []
    satisfied: bool
    missing_plugins: list[str] = []
    missing_data: dict[str, str] = {}
    dependency_details: list[PluginDependency] = []


class DependencyGraphResponse(BaseModel):
    """Response for dependency graph endpoint."""

    graph: dict[str, list[str]]
    reverse_graph: dict[str, list[str]]


class BatchSyncRequest(BaseModel):
    """Request model for batch sync."""

    plugin_names: list[str] = Field(
        ..., min_length=1, description="List of plugin names to sync"
    )
    task_type: TaskType = TaskType.INCREMENTAL
    include_optional: bool = True
    trade_dates: list[str] | None = None


class BatchSyncResponse(BaseModel):
    """Response for batch sync endpoint."""

    tasks: list[dict[str, Any]]
    total_plugins: int
    execution_order: list[str]


# ============================================
# Schedule Management Models
# ============================================


class ScheduleFrequencyType(str, Enum):
    """Schedule frequency type."""

    DAILY = "daily"  # 每天执行
    WEEKDAY = "weekday"  # 仅工作日执行


class ScheduleConfig(BaseModel):
    """全局调度配置."""

    enabled: bool = False  # 是否启用定时调度
    cron_expression: str = "0 18 * * 1-5"  # Cron表达式：工作日18:00
    execute_time: str = "18:00"  # 执行时间 HH:MM
    frequency: ScheduleFrequencyType = ScheduleFrequencyType.WEEKDAY  # 频率
    include_optional_deps: bool = True  # 是否包含可选依赖
    skip_non_trading_days: bool = True  # 是否跳过非交易日
    last_run_at: datetime | None = None  # 上次执行时间
    next_run_at: datetime | None = None  # 下次执行时间


class ScheduleConfigRequest(BaseModel):
    """Request model for updating schedule config."""

    enabled: bool | None = None
    execute_time: str | None = Field(
        None, pattern=r"^\d{2}:\d{2}$", description="执行时间 HH:MM"
    )
    frequency: ScheduleFrequencyType | None = None
    include_optional_deps: bool | None = None
    skip_non_trading_days: bool | None = None


class PluginScheduleConfig(BaseModel):
    """单个插件的调度配置."""

    plugin_name: str
    schedule_enabled: bool = True  # 是否加入定时任务
    full_scan_enabled: bool = False  # 是否启用全量扫描
    category: str = "cn_stock"  # 分类
    category_label: str = "A股"  # 分类显示标签
    role: str = "primary"  # 角色
    schedule_frequency: str = "daily"  # 插件调度频率: daily/weekly/monthly
    dependencies: list[str] = []  # 依赖列表
    optional_dependencies: list[str] = []  # 可选依赖


class PluginScheduleConfigRequest(BaseModel):
    """Request model for updating plugin schedule config."""

    schedule_enabled: bool | None = None
    full_scan_enabled: bool | None = None


class ScheduleExecutionRecord(BaseModel):
    """调度执行记录."""

    execution_id: str
    trigger_type: str = "scheduled"  # scheduled, manual
    started_at: datetime
    completed_at: datetime | None = None
    status: str = "running"  # running, completed, failed, skipped, interrupted
    skip_reason: str | None = None  # 跳过原因（非交易日等）
    total_plugins: int = 0
    completed_plugins: int = 0
    failed_plugins: int = 0
    task_ids: list[str] = []  # 关联的同步任务ID
    can_retry: bool = False  # 是否可以重试
    group_name: str | None = None  # 自定义组合名称
    date_range: str | None = None  # 日期范围（如"2026-01-01 ~ 2026-01-25"）


class ScheduleHistoryResponse(BaseModel):
    """Response for schedule history endpoint."""

    items: list[ScheduleExecutionRecord]
    total: int


class BatchTaskDetail(BaseModel):
    """批量任务中单个插件任务的详情."""

    task_id: str
    plugin_name: str
    status: str
    progress: float = 0
    records_processed: int = 0
    error_message: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    trade_dates: list[str] = []  # 处理的日期列表


class BatchExecutionDetail(BaseModel):
    """批量任务执行详情，包含所有子任务."""

    execution_id: str
    trigger_type: str
    started_at: datetime
    completed_at: datetime | None = None
    status: str
    total_plugins: int = 0
    completed_plugins: int = 0
    failed_plugins: int = 0
    tasks: list[BatchTaskDetail] = []  # 所有子任务详情
    error_summary: str = ""  # 所有失败任务的错误信息汇总（用于一键复制）
    group_name: str | None = None  # 自定义组合名称（如果是组合触发的）
    date_range: str | None = None  # 日期范围（如"2026-01-01 ~ 2026-01-25"）


class PartialRetryRequest(BaseModel):
    """Request model for partial retry (only failed tasks)."""

    task_ids: list[str] | None = None  # 指定要重试的task_id列表，为空则重试所有失败的


class GroupCategory(str, Enum):
    """组合分类枚举."""

    SYSTEM = "system"  # 系统维护
    CN_STOCK = "cn_stock"  # A股相关
    HK_STOCK = "hk_stock"  # 港股相关
    INDEX = "index"  # 指数相关
    ETF_FUND = "etf_fund"  # ETF基金相关
    DAILY = "daily"  # 每日更新
    CUSTOM = "custom"  # 用户自定义（无分类）


class PluginGroup(BaseModel):
    """自定义插件组合."""

    group_id: str
    name: str
    description: str = ""
    plugin_names: list[str]
    default_task_type: TaskType = TaskType.INCREMENTAL  # 默认同步类型
    category: GroupCategory = GroupCategory.CUSTOM  # 分类
    is_predefined: bool = False  # 是否为预定义组合
    is_readonly: bool = False  # 是否只读
    created_at: datetime
    updated_at: datetime | None = None
    created_by: str = ""


class PluginGroupCreateRequest(BaseModel):
    """Request model for creating a plugin group."""

    name: str = Field(..., min_length=1, max_length=50, description="组合名称")
    description: str = Field(default="", max_length=200, description="组合描述")
    plugin_names: list[str] = Field(..., min_length=1, description="插件列表")
    default_task_type: TaskType = Field(
        default=TaskType.INCREMENTAL, description="默认同步类型"
    )


class PluginGroupUpdateRequest(BaseModel):
    """Request model for updating a plugin group."""

    name: str | None = Field(None, min_length=1, max_length=50, description="组合名称")
    description: str | None = Field(None, max_length=200, description="组合描述")
    plugin_names: list[str] | None = Field(None, min_length=1, description="插件列表")
    default_task_type: TaskType | None = Field(None, description="默认同步类型")


class PluginGroupListResponse(BaseModel):
    """Response for plugin group list."""

    items: list[PluginGroup]
    total: int
    predefined_count: int = 0  # 预定义组合数量
    custom_count: int = 0  # 用户自定义组合数量


class GroupCategoryInfo(BaseModel):
    """组合分类信息."""

    key: str
    label: str
    order: int = 0


class GroupPluginStatus(BaseModel):
    """组合中插件状态."""

    name: str
    exists: bool
    has_data: bool = False


class PluginGroupDetail(PluginGroup):
    """组合详情（含依赖关系图）."""

    plugin_status: list[GroupPluginStatus] = []  # 各插件状态
    dependency_graph: dict[str, list[str]] = {}  # 依赖关系图
    execution_order: list[str] = []  # 执行顺序


class PredefinedGroupsResponse(BaseModel):
    """预定义组合列表响应."""

    groups: list[PluginGroup]
    categories: list[GroupCategoryInfo]


class PluginGroupTriggerRequest(BaseModel):
    """Request model for triggering a plugin group sync."""

    task_type: TaskType = TaskType.INCREMENTAL
    trade_dates: list[str] | None = None


# ============================================
# Data Explorer Models
# ============================================


class ExplorerColumnInfo(BaseModel):
    """Column info for data explorer."""

    name: str
    data_type: str
    nullable: bool = True
    comment: str | None = None


class ExplorerTableInfo(BaseModel):
    """Table info for data explorer."""

    plugin_name: str
    table_name: str
    category: str  # cn_stock, index, etf_fund, etc.
    columns: list[ExplorerColumnInfo] = []
    row_count: int | None = None
    description: str | None = None


class ExplorerTableSchema(BaseModel):
    """Detailed table schema for data explorer."""

    table_name: str
    columns: list[ExplorerColumnInfo]
    partition_by: str | None = None
    order_by: list[str] | None = None
    engine: str | None = None
    comment: str | None = None


class ExplorerTableListResponse(BaseModel):
    """Table list response for data explorer."""

    tables: list[ExplorerTableInfo]
    categories: list[dict[str, str]]


class ExplorerSimpleQueryRequest(BaseModel):
    """Simple filter query request."""

    filters: dict[str, Any] = Field(default_factory=dict)
    sort_by: str | None = None
    sort_order: str = Field(default="DESC", pattern="^(ASC|DESC)$")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1, le=1000)


class ExportFormat(str, Enum):
    """Export format enum."""

    CSV = "csv"
    XLSX = "xlsx"


class ExplorerSqlExecuteRequest(BaseModel):
    """SQL execute request."""

    sql: str = Field(..., max_length=10000)
    max_rows: int = Field(default=1000, ge=1, le=10000)
    timeout: int = Field(default=30, ge=1, le=300)


class ExplorerSqlExecuteResponse(BaseModel):
    """SQL execute response."""

    columns: list[str]
    data: list[dict[str, Any]]
    row_count: int
    total_count: int | None = None
    execution_time_ms: int
    truncated: bool = False
    table_not_exists: bool = False  # Flag indicating table doesn't exist in database


class ExplorerSqlExportRequest(BaseModel):
    """SQL export request."""

    sql: str = Field(..., max_length=10000)
    format: ExportFormat = ExportFormat.CSV
    filename: str | None = None


class SqlTemplate(BaseModel):
    """SQL template model."""

    id: int | None = None
    name: str = Field(..., max_length=100)
    description: str | None = Field(None, max_length=500)
    sql: str = Field(..., max_length=10000)
    category: str | None = None
    user_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SqlTemplateCreate(BaseModel):
    """Create SQL template request."""

    name: str = Field(..., max_length=100)
    description: str | None = Field(None, max_length=500)
    sql: str = Field(..., max_length=10000)
    category: str | None = None


class SqlTemplateListResponse(BaseModel):
    """SQL template list response."""

    items: list[SqlTemplate]
    total: int


# ============================================
# Data Sync Scheduler Models (定时数据同步调度器)
# ============================================


class SchedulerStatus(BaseModel):
    """数据同步调度器状态."""

    enabled: bool = False  # 是否启用
    is_running: bool = False  # 调度线程是否运行
    data_sync_time: str = "18:00"  # 数据同步时间
    analysis_time: str = "18:30"  # 分析任务时间
    next_data_sync: str | None = None  # 下次数据同步时间
    next_analysis: str | None = None  # 下次分析时间
    last_data_sync: str | None = None  # 上次数据同步时间
    last_analysis: str | None = None  # 上次分析时间
    current_task: str | None = None  # 当前运行的任务类型
    thread_alive: bool = False  # 调度线程是否存活


class SchedulerConfigUpdate(BaseModel):
    """更新调度器配置请求."""

    enabled: bool | None = None
    data_sync_time: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    analysis_time: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")


class SchedulerRunResult(BaseModel):
    """手动运行任务的结果."""

    success: bool
    message: str
    task_type: str


# ============ Realtime Data Management Schemas ============


class RealtimePluginInfo(BaseModel):
    """实时插件信息."""

    plugin_name: str
    display_name: str
    description: str = ""
    api_name: str = ""
    category: str = ""
    tags: list[str] = []
    enabled: bool = False


class RealtimeConfigResponse(BaseModel):
    """实时数据配置响应."""

    enabled: bool = False
    watchlist_monitor_enabled: bool = False
    collect_freq: str = "1MIN"
    plugin_configs: dict[str, Any] = {}


class RealtimeConfigUpdate(BaseModel):
    """更新实时数据配置请求."""

    enabled: bool | None = None
    watchlist_monitor_enabled: bool | None = None
    collect_freq: str | None = None


class RealtimePluginConfigUpdate(BaseModel):
    """更新单个实时插件配置请求."""

    enabled: bool


class RealtimeStatusResponse(BaseModel):
    """实时数据状态响应."""

    global_enabled: bool = False
    watchlist_monitor_enabled: bool = False
    collect_freq: str = "1MIN"
    total_plugins: int = 0
    enabled_plugins: int = 0
    watchlist_count: int = 0
    watchlist_codes: list[str] = []
