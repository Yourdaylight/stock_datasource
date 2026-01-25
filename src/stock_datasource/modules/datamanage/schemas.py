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


class PluginCategoryEnum(str, Enum):
    """Plugin category enum."""
    CN_STOCK = "cn_stock"  # A股相关
    HK_STOCK = "hk_stock"  # 港股相关
    INDEX = "index"        # 指数相关
    ETF_FUND = "etf_fund"  # ETF/基金相关
    SYSTEM = "system"      # 系统数据
    STOCK = "stock"        # 兼容旧值


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
    trade_dates: Optional[List[str]] = None  # For backfill
    force_overwrite: bool = False  # Whether to overwrite existing data
    include_optional: bool = True  # Whether to include optional dependencies
    # Parallelism settings (optional, use global settings if not provided)
    max_concurrent_tasks: Optional[int] = Field(None, ge=1, le=10, description="Max parallel tasks (1-10)")
    max_date_threads: Optional[int] = Field(None, ge=1, le=20, description="Max threads per task for multi-date (1-20)")


class ManualDetectRequest(BaseModel):
    """Request model for manual missing data detection."""
    days: int = Field(default=1825, ge=1, le=3650)  # Default 5 years, max 10 years


class CheckDataExistsRequest(BaseModel):
    """Request model for checking if data exists for specific dates."""
    dates: List[str] = Field(..., min_length=1, description="List of dates to check (YYYY-MM-DD format)")


class SyncConfigRequest(BaseModel):
    """Request model for updating sync configuration."""
    max_concurrent_tasks: Optional[int] = Field(None, ge=1, le=10, description="Max parallel tasks (1-10)")
    max_date_threads: Optional[int] = Field(None, ge=1, le=20, description="Max threads per task for multi-date (1-20)")


class SyncConfig(BaseModel):
    """Sync configuration response."""
    max_concurrent_tasks: int = Field(description="Current max parallel tasks")
    max_date_threads: int = Field(description="Current max threads per task")
    running_tasks_count: int = Field(description="Currently running tasks")
    pending_tasks_count: int = Field(description="Pending tasks in queue")
    running_plugins: List[str] = Field(description="Plugins currently running")


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
    # User tracking fields
    user_id: Optional[str] = None
    username: Optional[str] = None


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
    category: str = "stock"
    role: str = "primary"
    is_enabled: bool = True
    schedule_frequency: Optional[str] = None
    schedule_time: Optional[str] = None
    latest_date: Optional[str] = None
    missing_count: int = 0
    last_run_at: Optional[str] = None
    last_run_status: Optional[str] = None
    dependencies: List[str] = []
    optional_dependencies: List[str] = []


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
    error_traceback: Optional[str] = None  # 完整错误堆栈
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    # User tracking fields
    user_id: Optional[str] = None
    username: Optional[str] = None


class SyncTaskListResponse(BaseModel):
    """Paginated sync task list response."""
    items: List[SyncTask]
    total: int
    page: int
    page_size: int
    total_pages: int


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


class GroupDataExistsCheckRequest(BaseModel):
    """Request model for checking if data exists for a group of plugins."""
    dates: List[str] = Field(..., min_length=1, description="List of dates to check (YYYY-MM-DD format)")


class PluginDataExistsInfo(BaseModel):
    """Data existence info for a single plugin."""
    plugin_name: str
    existing_dates: List[str]
    non_existing_dates: List[str]
    has_date_column: bool = True  # False for dimension tables


class GroupDataExistsCheckResult(BaseModel):
    """Result of checking if data exists for a group of plugins."""
    group_id: str
    group_name: str
    dates_checked: List[str]
    plugins: List[PluginDataExistsInfo]
    # Summary
    all_plugins_have_data: bool  # All plugins have data for all dates
    plugins_with_existing_data: List[str]  # Plugins that have data (might need overwrite)
    plugins_missing_data: List[str]  # Plugins that don't have data


# ============================================
# Proxy Configuration Models
# ============================================

class ProxyConfig(BaseModel):
    """HTTP Proxy configuration."""
    enabled: bool = Field(default=False, description="Whether proxy is enabled")
    host: str = Field(default="", description="Proxy host address")
    port: int = Field(default=0, description="Proxy port")
    username: Optional[str] = Field(default=None, description="Proxy username (optional)")
    password: Optional[str] = Field(default=None, description="Proxy password (optional)")


class ProxyConfigRequest(BaseModel):
    """Request model for updating proxy configuration."""
    enabled: bool = Field(..., description="Whether to enable proxy")
    host: str = Field(default="", description="Proxy host address")
    port: int = Field(default=0, ge=0, le=65535, description="Proxy port (0-65535)")
    username: Optional[str] = Field(default=None, description="Proxy username")
    password: Optional[str] = Field(default=None, description="Proxy password")


class ProxyTestResult(BaseModel):
    """Result of proxy connection test."""
    success: bool
    message: str
    latency_ms: Optional[float] = None
    external_ip: Optional[str] = None


# ============================================
# Plugin Dependency Models
# ============================================

class PluginDependency(BaseModel):
    """Plugin dependency information."""
    plugin_name: str
    has_data: bool
    table_name: Optional[str] = None
    record_count: int = 0


class DependencyCheckResponse(BaseModel):
    """Response for dependency check endpoint."""
    plugin_name: str
    dependencies: List[str]
    optional_dependencies: List[str] = []
    satisfied: bool
    missing_plugins: List[str] = []
    missing_data: Dict[str, str] = {}
    dependency_details: List[PluginDependency] = []


class DependencyGraphResponse(BaseModel):
    """Response for dependency graph endpoint."""
    graph: Dict[str, List[str]]
    reverse_graph: Dict[str, List[str]]


class BatchSyncRequest(BaseModel):
    """Request model for batch sync."""
    plugin_names: List[str] = Field(..., min_length=1, description="List of plugin names to sync")
    task_type: TaskType = TaskType.INCREMENTAL
    include_optional: bool = True
    trade_dates: Optional[List[str]] = None


class BatchSyncResponse(BaseModel):
    """Response for batch sync endpoint."""
    tasks: List[Dict[str, Any]]
    total_plugins: int
    execution_order: List[str]


# ============================================
# Schedule Management Models
# ============================================

class ScheduleFrequencyType(str, Enum):
    """Schedule frequency type."""
    DAILY = "daily"      # 每天执行
    WEEKDAY = "weekday"  # 仅工作日执行


class ScheduleConfig(BaseModel):
    """全局调度配置."""
    enabled: bool = False                        # 是否启用定时调度
    cron_expression: str = "0 18 * * 1-5"        # Cron表达式：工作日18:00
    execute_time: str = "18:00"                  # 执行时间 HH:MM
    frequency: ScheduleFrequencyType = ScheduleFrequencyType.WEEKDAY  # 频率
    include_optional_deps: bool = True           # 是否包含可选依赖
    skip_non_trading_days: bool = True           # 是否跳过非交易日
    last_run_at: Optional[datetime] = None       # 上次执行时间
    next_run_at: Optional[datetime] = None       # 下次执行时间


class ScheduleConfigRequest(BaseModel):
    """Request model for updating schedule config."""
    enabled: Optional[bool] = None
    execute_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$", description="执行时间 HH:MM")
    frequency: Optional[ScheduleFrequencyType] = None
    include_optional_deps: Optional[bool] = None
    skip_non_trading_days: Optional[bool] = None


class PluginScheduleConfig(BaseModel):
    """单个插件的调度配置."""
    plugin_name: str
    schedule_enabled: bool = True                # 是否加入定时任务
    full_scan_enabled: bool = False              # 是否启用全量扫描
    category: str = "cn_stock"                   # 分类
    category_label: str = "A股"                  # 分类显示标签
    role: str = "primary"                        # 角色
    dependencies: List[str] = []                 # 依赖列表
    optional_dependencies: List[str] = []        # 可选依赖


class PluginScheduleConfigRequest(BaseModel):
    """Request model for updating plugin schedule config."""
    schedule_enabled: Optional[bool] = None
    full_scan_enabled: Optional[bool] = None


class ScheduleExecutionRecord(BaseModel):
    """调度执行记录."""
    execution_id: str
    trigger_type: str = "scheduled"              # scheduled, manual
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "running"                      # running, completed, failed, skipped, interrupted
    skip_reason: Optional[str] = None            # 跳过原因（非交易日等）
    total_plugins: int = 0
    completed_plugins: int = 0
    failed_plugins: int = 0
    task_ids: List[str] = []                     # 关联的同步任务ID
    can_retry: bool = False                      # 是否可以重试


class ScheduleHistoryResponse(BaseModel):
    """Response for schedule history endpoint."""
    items: List[ScheduleExecutionRecord]
    total: int


class BatchTaskDetail(BaseModel):
    """批量任务中单个插件任务的详情."""
    task_id: str
    plugin_name: str
    status: str
    progress: float = 0
    records_processed: int = 0
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class BatchExecutionDetail(BaseModel):
    """批量任务执行详情，包含所有子任务."""
    execution_id: str
    trigger_type: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    total_plugins: int = 0
    completed_plugins: int = 0
    failed_plugins: int = 0
    tasks: List[BatchTaskDetail] = []            # 所有子任务详情
    error_summary: str = ""                      # 所有失败任务的错误信息汇总（用于一键复制）
    group_name: Optional[str] = None             # 自定义组合名称（如果是组合触发的）


class PartialRetryRequest(BaseModel):
    """Request model for partial retry (only failed tasks)."""
    task_ids: Optional[List[str]] = None         # 指定要重试的task_id列表，为空则重试所有失败的


class GroupCategory(str, Enum):
    """组合分类枚举."""
    SYSTEM = "system"        # 系统维护
    CN_STOCK = "cn_stock"    # A股相关
    INDEX = "index"          # 指数相关
    ETF_FUND = "etf_fund"    # ETF基金相关
    DAILY = "daily"          # 每日更新
    CUSTOM = "custom"        # 用户自定义（无分类）


class PluginGroup(BaseModel):
    """自定义插件组合."""
    group_id: str
    name: str
    description: str = ""
    plugin_names: List[str]
    default_task_type: TaskType = TaskType.INCREMENTAL  # 默认同步类型
    category: GroupCategory = GroupCategory.CUSTOM      # 分类
    is_predefined: bool = False                         # 是否为预定义组合
    is_readonly: bool = False                           # 是否只读
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: str = ""


class PluginGroupCreateRequest(BaseModel):
    """Request model for creating a plugin group."""
    name: str = Field(..., min_length=1, max_length=50, description="组合名称")
    description: str = Field(default="", max_length=200, description="组合描述")
    plugin_names: List[str] = Field(..., min_length=1, description="插件列表")
    default_task_type: TaskType = Field(default=TaskType.INCREMENTAL, description="默认同步类型")


class PluginGroupUpdateRequest(BaseModel):
    """Request model for updating a plugin group."""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="组合名称")
    description: Optional[str] = Field(None, max_length=200, description="组合描述")
    plugin_names: Optional[List[str]] = Field(None, min_length=1, description="插件列表")
    default_task_type: Optional[TaskType] = Field(None, description="默认同步类型")


class PluginGroupListResponse(BaseModel):
    """Response for plugin group list."""
    items: List[PluginGroup]
    total: int
    predefined_count: int = 0                           # 预定义组合数量
    custom_count: int = 0                               # 用户自定义组合数量


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
    plugin_status: List[GroupPluginStatus] = []         # 各插件状态
    dependency_graph: Dict[str, List[str]] = {}         # 依赖关系图
    execution_order: List[str] = []                     # 执行顺序


class PredefinedGroupsResponse(BaseModel):
    """预定义组合列表响应."""
    groups: List[PluginGroup]
    categories: List[GroupCategoryInfo]


class PluginGroupTriggerRequest(BaseModel):
    """Request model for triggering a plugin group sync."""
    task_type: TaskType = TaskType.INCREMENTAL
    trade_dates: Optional[List[str]] = None


# ============================================
# Data Explorer Models
# ============================================

class ExplorerColumnInfo(BaseModel):
    """Column info for data explorer."""
    name: str
    data_type: str
    nullable: bool = True
    comment: Optional[str] = None


class ExplorerTableInfo(BaseModel):
    """Table info for data explorer."""
    plugin_name: str
    table_name: str
    category: str  # cn_stock, index, etf_fund, etc.
    columns: List[ExplorerColumnInfo] = []
    row_count: Optional[int] = None
    description: Optional[str] = None


class ExplorerTableSchema(BaseModel):
    """Detailed table schema for data explorer."""
    table_name: str
    columns: List[ExplorerColumnInfo]
    partition_by: Optional[str] = None
    order_by: Optional[List[str]] = None
    engine: Optional[str] = None
    comment: Optional[str] = None


class ExplorerTableListResponse(BaseModel):
    """Table list response for data explorer."""
    tables: List[ExplorerTableInfo]
    categories: List[Dict[str, str]]


class ExplorerSimpleQueryRequest(BaseModel):
    """Simple filter query request."""
    filters: Dict[str, Any] = Field(default_factory=dict)
    sort_by: Optional[str] = None
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
    columns: List[str]
    data: List[Dict[str, Any]]
    row_count: int
    total_count: Optional[int] = None
    execution_time_ms: int
    truncated: bool = False
    table_not_exists: bool = False  # Flag indicating table doesn't exist in database


class ExplorerSqlExportRequest(BaseModel):
    """SQL export request."""
    sql: str = Field(..., max_length=10000)
    format: ExportFormat = ExportFormat.CSV
    filename: Optional[str] = None


class SqlTemplate(BaseModel):
    """SQL template model."""
    id: Optional[int] = None
    name: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    sql: str = Field(..., max_length=10000)
    category: Optional[str] = None
    user_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SqlTemplateCreate(BaseModel):
    """Create SQL template request."""
    name: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    sql: str = Field(..., max_length=10000)
    category: Optional[str] = None


class SqlTemplateListResponse(BaseModel):
    """SQL template list response."""
    items: List[SqlTemplate]
    total: int
