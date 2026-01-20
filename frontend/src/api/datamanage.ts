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

export type PluginCategory = 'stock' | 'index' | 'etf_fund' | 'system'
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
  }
}
