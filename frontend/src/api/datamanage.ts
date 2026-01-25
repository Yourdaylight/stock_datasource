import { request } from '@/utils/request'

export interface DataSource {
  id: string
  source_name: string
  source_type: string
  provider: string
  is_enabled: boolean
  last_sync_at?: string
}

export interface SyncTask {
  task_id: string
  plugin_name: string
  task_type: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number
  records_processed: number
  total_records: number
  error_message?: string
  trade_dates: string[]
  created_at?: string
  started_at?: string
  completed_at?: string
}

export interface SyncConfig {
  max_concurrent_tasks: number
  max_date_threads: number
  running_tasks_count: number
  pending_tasks_count: number
  running_plugins: string[]
}

export interface SyncConfigRequest {
  max_concurrent_tasks?: number
  max_date_threads?: number
}

export interface QualityMetrics {
  table_name: string
  completeness_score: number
  consistency_score: number
  timeliness_score: number
  overall_score: number
  record_count: number
  latest_update?: string
}

export type PluginCategory = 'cn_stock' | 'hk_stock' | 'index' | 'etf_fund' | 'market' | 'reference' | 'fundamental' | 'system' | 'stock'
export type PluginRole = 'primary' | 'basic' | 'derived' | 'auxiliary'

export interface PluginInfo {
  name: string
  version: string
  description: string
  type: string
  category: PluginCategory
  role: PluginRole
  is_enabled: boolean
  schedule_frequency?: string
  schedule_time?: string
  latest_date?: string
  missing_count: number
  last_run_at?: string
  last_run_status?: string
  dependencies: string[]
  optional_dependencies: string[]
}

export interface PluginSchedule {
  frequency: 'daily' | 'weekly'
  time: string
  day_of_week?: string
}

export interface PluginColumn {
  name: string
  data_type: string
  nullable: boolean
  comment?: string
  default?: string
}

export interface PluginSchema {
  table_name: string
  table_type: string
  columns: PluginColumn[]
  partition_by?: string
  order_by: string[]
  engine: string
  engine_params: string[]
  comment?: string
}

export interface PluginConfig {
  enabled: boolean
  rate_limit: number
  timeout: number
  retry_attempts: number
  description?: string
  schedule?: PluginSchedule
  parameters_schema: Record<string, any>
}

export interface PluginStatus {
  latest_date?: string
  missing_count: number
  missing_dates: string[]
  total_records: number
}

export interface PluginDetail {
  plugin_name: string
  version: string
  description: string
  config: PluginConfig
  table_schema: PluginSchema
  status: PluginStatus
}

export interface PluginDataPreview {
  plugin_name: string
  table_name: string
  columns: string[]
  data: Record<string, any>[]
  total_count: number
  page: number
  page_size: number
}

export interface MissingDataInfo {
  plugin_name: string
  table_name: string
  schedule_frequency: string
  latest_date?: string
  missing_dates: string[]
  missing_count: number
}

export interface MissingDataSummary {
  check_time: string
  total_plugins: number
  plugins_with_missing: number
  plugins: MissingDataInfo[]
}

export interface TableMetadata {
  table_name: string
  description: string
  row_count: number
  size_bytes: number
  latest_date?: string
}

export interface TriggerSyncRequest {
  plugin_name: string
  task_type: 'full' | 'incremental' | 'backfill'
  trade_dates?: string[]
  force_overwrite?: boolean
}

export interface DataExistsCheckResult {
  plugin_name: string
  dates_checked: string[]
  existing_dates: string[]
  non_existing_dates: string[]
  record_counts: Record<string, number>
}

// AI Diagnosis Types
export interface DiagnosisSuggestion {
  severity: 'critical' | 'warning' | 'info'
  category: 'config' | 'data' | 'connection' | 'plugin' | 'system'
  title: string
  description: string
  suggestion: string
  related_logs: string[]
}

export interface DiagnosisResult {
  diagnosis_time: string
  log_lines_analyzed: number
  error_count: number
  warning_count: number
  summary: string
  suggestions: DiagnosisSuggestion[]
  raw_errors: string[]
}

export interface DiagnosisRequest {
  log_lines?: number
  include_errors_only?: boolean
  context?: string
}

// Proxy Configuration Types
export interface ProxyConfig {
  enabled: boolean
  host: string
  port: number
  username?: string
  password?: string
}

export interface ProxyTestResult {
  success: boolean
  message: string
  latency_ms?: number
  external_ip?: string
}

// Plugin Dependency Types
export interface PluginDependency {
  plugin_name: string
  has_data: boolean
  table_name?: string
  record_count: number
}

export interface DependencyCheckResult {
  plugin_name: string
  dependencies: string[]
  optional_dependencies: string[]
  satisfied: boolean
  missing_plugins: string[]
  missing_data: Record<string, string>
  dependency_details: PluginDependency[]
}

export interface DependencyGraphResult {
  graph: Record<string, string[]>
  reverse_graph: Record<string, string[]>
}

export interface BatchSyncRequest {
  plugin_names: string[]
  task_type: 'full' | 'incremental' | 'backfill'
  include_optional?: boolean
  trade_dates?: string[]
}

export interface BatchSyncTask {
  task_id: string
  plugin_name: string
  task_type: string
  status: string
  order: number
  dependencies_satisfied: boolean
}

export interface BatchSyncResponse {
  tasks: BatchSyncTask[]
  total_plugins: number
  execution_order: string[]
}

export interface PluginFilterParams {
  category?: PluginCategory
  role?: PluginRole
}

// Schedule Management Types
export type ScheduleFrequency = 'daily' | 'weekday'

export interface ScheduleConfig {
  enabled: boolean
  cron_expression: string
  execute_time: string
  frequency: ScheduleFrequency
  include_optional_deps: boolean
  skip_non_trading_days: boolean
  last_run_at?: string
  next_run_at?: string
}

export interface ScheduleConfigRequest {
  enabled?: boolean
  execute_time?: string
  frequency?: ScheduleFrequency
  include_optional_deps?: boolean
  skip_non_trading_days?: boolean
}

export interface PluginScheduleConfig {
  plugin_name: string
  schedule_enabled: boolean
  full_scan_enabled: boolean
  category: string
  category_label: string
  role: string
  dependencies: string[]
  optional_dependencies: string[]
}

export interface PluginScheduleConfigRequest {
  schedule_enabled?: boolean
  full_scan_enabled?: boolean
}

export interface ScheduleExecutionRecord {
  execution_id: string
  trigger_type: 'scheduled' | 'manual' | 'group' | 'retry'
  started_at: string
  completed_at?: string
  status: 'running' | 'completed' | 'failed' | 'skipped' | 'interrupted'
  skip_reason?: string
  total_plugins: number
  completed_plugins: number
  failed_plugins: number
  task_ids: string[]
  can_retry: boolean
  group_name?: string  // Name of plugin group if triggered from group
}

export interface ScheduleHistoryResponse {
  items: ScheduleExecutionRecord[]
  total: number
}

// Batch Execution Detail Types
export interface BatchTaskDetail {
  task_id: string
  plugin_name: string
  status: string
  progress: number
  records_processed: number
  error_message?: string
  created_at?: string
  completed_at?: string
}

export interface BatchExecutionDetail {
  execution_id: string
  trigger_type: 'scheduled' | 'manual' | 'group' | 'retry'
  started_at: string
  completed_at?: string
  status: string
  total_plugins: number
  completed_plugins: number
  failed_plugins: number
  tasks: BatchTaskDetail[]
  error_summary: string  // All error messages concatenated for easy copying
  group_name?: string
}

// Partial Retry Request
export interface PartialRetryRequest {
  task_ids?: string[]  // Specific task IDs to retry, or null for all failed
}

// Plugin Group Types
export type TaskType = 'incremental' | 'full' | 'backfill'
export type GroupCategory = 'cn_stock' | 'index' | 'etf_fund' | 'daily' | 'custom'

export interface PluginGroup {
  group_id: string
  name: string
  description: string
  plugin_names: string[]
  default_task_type: TaskType  // 默认同步类型
  category: GroupCategory      // 分类
  is_predefined: boolean       // 是否为预定义组合
  is_readonly: boolean         // 是否只读
  created_at: string
  updated_at?: string
  created_by: string
}

export interface GroupPluginStatus {
  name: string
  exists: boolean
  has_data: boolean
}

export interface PluginGroupDetail extends PluginGroup {
  plugin_status: GroupPluginStatus[]
  dependency_graph: Record<string, string[]>
  execution_order: string[]
}

export interface GroupCategoryInfo {
  key: GroupCategory
  label: string
  order: number
}

export interface PluginGroupCreateRequest {
  name: string
  description?: string
  plugin_names: string[]
  default_task_type?: TaskType  // 默认同步类型
}

export interface PluginGroupUpdateRequest {
  name?: string
  description?: string
  plugin_names?: string[]
  default_task_type?: TaskType  // 默认同步类型
}

export interface PluginGroupListResponse {
  items: PluginGroup[]
  total: number
  predefined_count: number
  custom_count: number
}

export interface PredefinedGroupsResponse {
  groups: PluginGroup[]
  categories: GroupCategoryInfo[]
}

export interface PluginGroupTriggerRequest {
  task_type?: 'incremental' | 'full' | 'backfill'
  trade_dates?: string[]
  force_overwrite?: boolean
}

// Group data exists check types
export interface GroupDataExistsCheckRequest {
  dates: string[]
}

export interface PluginDataExistsInfo {
  plugin_name: string
  existing_dates: string[]
  non_existing_dates: string[]
  has_date_column: boolean
}

export interface GroupDataExistsCheckResult {
  group_id: string
  group_name: string
  dates_checked: string[]
  plugins: PluginDataExistsInfo[]
  all_plugins_have_data: boolean
  plugins_with_existing_data: string[]
  plugins_missing_data: string[]
}

export interface SyncTaskListResponse {
  items: SyncTask[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface SyncTaskQueryParams {
  page?: number
  page_size?: number
  status?: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  plugin_name?: string
  sort_by?: 'created_at' | 'started_at' | 'completed_at'
  sort_order?: 'asc' | 'desc'
}

// ============ Data Explorer Types ============

export interface ExplorerColumnInfo {
  name: string
  data_type: string
  nullable: boolean
  comment?: string
}

export interface ExplorerTableInfo {
  plugin_name: string
  table_name: string
  category: string
  columns: ExplorerColumnInfo[]
  row_count?: number
  description?: string
}

export interface ExplorerTableSchema {
  table_name: string
  columns: ExplorerColumnInfo[]
  partition_by?: string
  order_by?: string[]
  engine?: string
  comment?: string
}

export interface ExplorerTableListResponse {
  tables: ExplorerTableInfo[]
  categories: { key: string; label: string }[]
}

export interface ExplorerSimpleQueryRequest {
  filters?: Record<string, any>
  sort_by?: string
  sort_order?: 'ASC' | 'DESC'
  page?: number
  page_size?: number
}

export interface ExplorerSqlExecuteRequest {
  sql: string
  max_rows?: number
  timeout?: number
}

export interface ExplorerSqlExecuteResponse {
  columns: string[]
  data: Record<string, any>[]
  row_count: number
  total_count?: number
  execution_time_ms: number
  truncated: boolean
  table_not_exists?: boolean  // Flag indicating table doesn't exist in database
}

export interface SqlTemplate {
  id?: number
  name: string
  description?: string
  sql: string
  category?: string
  user_id?: string
  created_at?: string
  updated_at?: string
}

export interface SqlTemplateCreate {
  name: string
  description?: string
  sql: string
  category?: string
}

export const datamanageApi = {
  // Data Sources
  getDataSources(): Promise<DataSource[]> {
    return request.get('/api/datamanage/datasources')
  },

  testConnection(sourceId: string): Promise<{ success: boolean; message: string }> {
    return request.post(`/api/datamanage/datasources/${sourceId}/test`)
  },

  // Missing Data Detection
  getMissingData(days: number = 30, forceRefresh: boolean = false): Promise<MissingDataSummary> {
    return request.get(`/api/datamanage/missing-data?days=${days}&force_refresh=${forceRefresh}`)
  },

  triggerMissingDataDetection(days: number = 30): Promise<MissingDataSummary> {
    return request.post('/api/datamanage/missing-data/detect', { days })
  },

  // Sync Tasks
  getSyncTasks(params?: SyncTaskQueryParams): Promise<SyncTaskListResponse> {
    const searchParams = new URLSearchParams()
    if (params?.page) searchParams.append('page', params.page.toString())
    if (params?.page_size) searchParams.append('page_size', params.page_size.toString())
    if (params?.status) searchParams.append('status', params.status)
    if (params?.plugin_name) searchParams.append('plugin_name', params.plugin_name)
    if (params?.sort_by) searchParams.append('sort_by', params.sort_by)
    if (params?.sort_order) searchParams.append('sort_order', params.sort_order)
    const queryString = searchParams.toString()
    return request.get(`/api/datamanage/sync/tasks${queryString ? '?' + queryString : ''}`)
  },

  triggerSync(req: TriggerSyncRequest): Promise<SyncTask> {
    return request.post('/api/datamanage/sync/trigger', req)
  },

  getSyncStatus(taskId: string): Promise<SyncTask> {
    return request.get(`/api/datamanage/sync/status/${taskId}`)
  },

  cancelSyncTask(taskId: string): Promise<{ success: boolean; message: string }> {
    return request.post(`/api/datamanage/sync/cancel/${taskId}`)
  },

  updateSyncConfig(req: SyncConfigRequest): Promise<SyncConfig> {
    return request.put('/api/datamanage/sync/config', req)
  },

  getSyncConfig(): Promise<SyncConfig> {
    return request.get('/api/datamanage/sync/config')
  },

  deleteSyncTask(taskId: string): Promise<{ success: boolean; message: string }> {
    return request.delete(`/api/datamanage/sync/tasks/${taskId}`)
  },

  retrySyncTask(taskId: string): Promise<SyncTask> {
    return request.post(`/api/datamanage/sync/retry/${taskId}`)
  },

  getSyncHistory(limit?: number, pluginName?: string): Promise<SyncTask[]> {
    let url = '/api/datamanage/sync/history'
    const params: string[] = []
    if (limit) params.push(`limit=${limit}`)
    if (pluginName) params.push(`plugin_name=${encodeURIComponent(pluginName)}`)
    if (params.length) url += '?' + params.join('&')
    return request.get(url)
  },

  // Plugins
  getPlugins(params?: PluginFilterParams): Promise<PluginInfo[]> {
    let url = '/api/datamanage/plugins'
    const queryParams: string[] = []
    if (params?.category) queryParams.push(`category=${params.category}`)
    if (params?.role) queryParams.push(`role=${params.role}`)
    if (queryParams.length) url += '?' + queryParams.join('&')
    return request.get(url)
  },

  getPluginDetail(name: string): Promise<PluginDetail> {
    return request.get(`/api/datamanage/plugins/${name}/detail`)
  },

  getPluginStatus(name: string): Promise<PluginStatus> {
    return request.get(`/api/datamanage/plugins/${name}/status`)
  },

  getPluginData(name: string, tradeDate?: string, page: number = 1, pageSize: number = 100): Promise<PluginDataPreview> {
    let url = `/api/datamanage/plugins/${name}/data?page=${page}&page_size=${pageSize}`
    if (tradeDate) url += `&trade_date=${tradeDate}`
    return request.get(url)
  },

  checkDataExists(name: string, dates: string[]): Promise<DataExistsCheckResult> {
    return request.post(`/api/datamanage/plugins/${name}/check-exists`, { dates })
  },

  enablePlugin(name: string): Promise<void> {
    return request.post(`/api/datamanage/plugins/${name}/enable`)
  },

  disablePlugin(name: string): Promise<void> {
    return request.post(`/api/datamanage/plugins/${name}/disable`)
  },

  // Plugin Dependencies
  getPluginDependencies(name: string): Promise<DependencyCheckResult> {
    return request.get(`/api/datamanage/plugins/${name}/dependencies`)
  },

  checkPluginDependencies(name: string): Promise<DependencyCheckResult> {
    return request.get(`/api/datamanage/plugins/${name}/check-dependencies`)
  },

  getDependencyGraph(): Promise<DependencyGraphResult> {
    return request.get('/api/datamanage/plugins/dependency-graph')
  },

  // Batch Sync
  batchTriggerSync(req: BatchSyncRequest): Promise<BatchSyncResponse> {
    return request.post('/api/datamanage/sync/batch', req)
  },

  // Quality
  getQualityMetrics(): Promise<QualityMetrics[]> {
    return request.get('/api/datamanage/quality/metrics')
  },

  getQualityReport(tableName?: string): Promise<any> {
    const params = tableName ? `?table=${encodeURIComponent(tableName)}` : ''
    return request.get(`/api/datamanage/quality/report${params}`)
  },

  // Metadata
  getTableMetadata(): Promise<TableMetadata[]> {
    return request.get('/api/datamanage/metadata/tables')
  },

  // AI Diagnosis
  getDiagnosis(logLines: number = 100, errorsOnly: boolean = false): Promise<DiagnosisResult> {
    return request.get(`/api/datamanage/diagnosis?log_lines=${logLines}&errors_only=${errorsOnly}`)
  },

  triggerDiagnosis(req: DiagnosisRequest): Promise<DiagnosisResult> {
    return request.post('/api/datamanage/diagnosis', req)
  },

  // Proxy Configuration
  getProxyConfig(): Promise<ProxyConfig> {
    return request.get('/api/datamanage/proxy/config')
  },

  updateProxyConfig(config: ProxyConfig): Promise<ProxyConfig> {
    return request.put('/api/datamanage/proxy/config', config)
  },

  testProxyConnection(config: ProxyConfig): Promise<ProxyTestResult> {
    return request.post('/api/datamanage/proxy/test', config)
  },

  // Schedule Management
  getScheduleConfig(): Promise<ScheduleConfig> {
    return request.get('/api/datamanage/schedule/config')
  },

  updateScheduleConfig(config: ScheduleConfigRequest): Promise<ScheduleConfig> {
    return request.put('/api/datamanage/schedule/config', config)
  },

  getPluginScheduleConfigs(category?: PluginCategory): Promise<PluginScheduleConfig[]> {
    const params = category ? `?category=${category}` : ''
    return request.get(`/api/datamanage/schedule/plugins${params}`)
  },

  updatePluginScheduleConfig(name: string, config: PluginScheduleConfigRequest): Promise<PluginScheduleConfig> {
    return request.put(`/api/datamanage/schedule/plugins/${name}`, config)
  },

  triggerScheduleNow(): Promise<ScheduleExecutionRecord> {
    return request.post('/api/datamanage/schedule/trigger')
  },

  retryScheduleExecution(executionId: string): Promise<ScheduleExecutionRecord> {
    return request.post(`/api/datamanage/schedule/retry/${executionId}`)
  },

  getScheduleHistory(days: number = 7, limit: number = 50, status?: string, triggerType?: string): Promise<ScheduleHistoryResponse> {
    let url = `/api/datamanage/schedule/history?days=${days}&limit=${limit}`
    if (status) url += `&status=${encodeURIComponent(status)}`
    if (triggerType) url += `&trigger_type=${encodeURIComponent(triggerType)}`
    return request.get(url)
  },

  getExecutionDetail(executionId: string): Promise<BatchExecutionDetail> {
    return request.get(`/api/datamanage/schedule/execution/${executionId}`)
  },

  stopExecution(executionId: string): Promise<ScheduleExecutionRecord> {
    return request.post(`/api/datamanage/schedule/stop/${executionId}`)
  },

  deleteScheduleExecution(executionId: string): Promise<{ success: boolean; message: string }> {
    return request.delete(`/api/datamanage/schedule/execution/${executionId}`)
  },

  partialRetryExecution(executionId: string, taskIds?: string[]): Promise<ScheduleExecutionRecord> {
    return request.post(`/api/datamanage/schedule/partial-retry/${executionId}`, { task_ids: taskIds })
  },

  // Plugin Groups
  getPluginGroups(category?: GroupCategory): Promise<PluginGroupListResponse> {
    const params = category ? `?category=${category}` : ''
    return request.get(`/api/datamanage/groups${params}`)
  },

  getPredefinedGroups(): Promise<PredefinedGroupsResponse> {
    return request.get('/api/datamanage/groups/predefined')
  },

  createPluginGroup(data: PluginGroupCreateRequest): Promise<PluginGroup> {
    return request.post('/api/datamanage/groups', data)
  },

  getPluginGroup(groupId: string): Promise<PluginGroupDetail> {
    return request.get(`/api/datamanage/groups/${groupId}`)
  },

  updatePluginGroup(groupId: string, data: PluginGroupUpdateRequest): Promise<PluginGroup> {
    return request.put(`/api/datamanage/groups/${groupId}`, data)
  },

  deletePluginGroup(groupId: string): Promise<void> {
    return request.delete(`/api/datamanage/groups/${groupId}`)
  },

  checkGroupDataExists(groupId: string, dates: string[]): Promise<GroupDataExistsCheckResult> {
    return request.post(`/api/datamanage/groups/${groupId}/check-exists`, { dates })
  },

  triggerPluginGroup(groupId: string, data?: PluginGroupTriggerRequest): Promise<ScheduleExecutionRecord> {
    return request.post(`/api/datamanage/groups/${groupId}/trigger`, data || {})
  },

  // ============ Data Explorer API ============
  
  // Get available tables for exploration
  getExplorerTables(category?: string): Promise<ExplorerTableListResponse> {
    const params = category ? `?category=${category}` : ''
    return request.get(`/api/datamanage/explorer/tables${params}`)
  },

  // Get table schema details
  getExplorerTableSchema(tableName: string): Promise<ExplorerTableSchema> {
    return request.get(`/api/datamanage/explorer/tables/${tableName}/schema`)
  },

  // Simple filter query
  queryExplorerTable(tableName: string, params: ExplorerSimpleQueryRequest): Promise<ExplorerSqlExecuteResponse> {
    return request.post(`/api/datamanage/explorer/tables/${tableName}/query`, params)
  },

  // Execute SQL query
  executeExplorerSql(params: ExplorerSqlExecuteRequest): Promise<ExplorerSqlExecuteResponse> {
    return request.post('/api/datamanage/explorer/sql/execute', params)
  },

  // Export query results
  exportExplorerSql(sql: string, format: 'csv' | 'xlsx', filename?: string): Promise<Blob> {
    return request.post('/api/datamanage/explorer/sql/export', { sql, format, filename }, {
      responseType: 'blob'
    })
  },

  // Get SQL templates
  getExplorerTemplates(category?: string): Promise<SqlTemplate[]> {
    const params = category ? `?category=${category}` : ''
    return request.get(`/api/datamanage/explorer/sql/templates${params}`)
  },

  // Create SQL template
  createExplorerTemplate(template: SqlTemplateCreate): Promise<SqlTemplate> {
    return request.post('/api/datamanage/explorer/sql/templates', template)
  },

  // Delete SQL template
  deleteExplorerTemplate(templateId: number): Promise<void> {
    return request.delete(`/api/datamanage/explorer/sql/templates/${templateId}`)
  }
}
