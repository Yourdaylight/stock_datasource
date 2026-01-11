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

export interface QualityMetrics {
  table_name: string
  completeness_score: number
  consistency_score: number
  timeliness_score: number
  overall_score: number
  record_count: number
  latest_update?: string
}

export interface PluginInfo {
  name: string
  version: string
  description: string
  type: string
  is_enabled: boolean
  schedule_frequency?: string
  schedule_time?: string
  latest_date?: string
  missing_count: number
  last_run_at?: string
  last_run_status?: string
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

export const datamanageApi = {
  // Data Sources
  getDataSources(): Promise<DataSource[]> {
    return request.get('/datamanage/datasources')
  },

  testConnection(sourceId: string): Promise<{ success: boolean; message: string }> {
    return request.post(`/datamanage/datasources/${sourceId}/test`)
  },

  // Missing Data Detection
  getMissingData(days: number = 30, forceRefresh: boolean = false): Promise<MissingDataSummary> {
    return request.get(`/datamanage/missing-data?days=${days}&force_refresh=${forceRefresh}`)
  },

  triggerMissingDataDetection(days: number = 30): Promise<MissingDataSummary> {
    return request.post('/datamanage/missing-data/detect', { days })
  },

  // Sync Tasks
  getSyncTasks(): Promise<SyncTask[]> {
    return request.get('/datamanage/sync/tasks')
  },

  triggerSync(req: TriggerSyncRequest): Promise<SyncTask> {
    return request.post('/datamanage/sync/trigger', req)
  },

  getSyncStatus(taskId: string): Promise<SyncTask> {
    return request.get(`/datamanage/sync/status/${taskId}`)
  },

  cancelSyncTask(taskId: string): Promise<{ success: boolean; message: string }> {
    return request.post(`/datamanage/sync/cancel/${taskId}`)
  },

  getSyncHistory(limit?: number, pluginName?: string): Promise<SyncTask[]> {
    let url = '/datamanage/sync/history'
    const params: string[] = []
    if (limit) params.push(`limit=${limit}`)
    if (pluginName) params.push(`plugin_name=${encodeURIComponent(pluginName)}`)
    if (params.length) url += '?' + params.join('&')
    return request.get(url)
  },

  // Plugins
  getPlugins(): Promise<PluginInfo[]> {
    return request.get('/datamanage/plugins')
  },

  getPluginDetail(name: string): Promise<PluginDetail> {
    return request.get(`/datamanage/plugins/${name}/detail`)
  },

  getPluginStatus(name: string): Promise<PluginStatus> {
    return request.get(`/datamanage/plugins/${name}/status`)
  },

  getPluginData(name: string, tradeDate?: string, page: number = 1, pageSize: number = 100): Promise<PluginDataPreview> {
    let url = `/datamanage/plugins/${name}/data?page=${page}&page_size=${pageSize}`
    if (tradeDate) url += `&trade_date=${tradeDate}`
    return request.get(url)
  },

  checkDataExists(name: string, dates: string[]): Promise<DataExistsCheckResult> {
    return request.post(`/datamanage/plugins/${name}/check-exists`, { dates })
  },

  enablePlugin(name: string): Promise<void> {
    return request.post(`/datamanage/plugins/${name}/enable`)
  },

  disablePlugin(name: string): Promise<void> {
    return request.post(`/datamanage/plugins/${name}/disable`)
  },

  // Quality
  getQualityMetrics(): Promise<QualityMetrics[]> {
    return request.get('/datamanage/quality/metrics')
  },

  getQualityReport(tableName?: string): Promise<any> {
    const params = tableName ? `?table=${encodeURIComponent(tableName)}` : ''
    return request.get(`/datamanage/quality/report${params}`)
  },

  // Metadata
  getTableMetadata(): Promise<TableMetadata[]> {
    return request.get('/datamanage/metadata/tables')
  },

  // AI Diagnosis
  getDiagnosis(logLines: number = 100, errorsOnly: boolean = false): Promise<DiagnosisResult> {
    return request.get(`/datamanage/diagnosis?log_lines=${logLines}&errors_only=${errorsOnly}`)
  },

  triggerDiagnosis(req: DiagnosisRequest): Promise<DiagnosisResult> {
    return request.post('/datamanage/diagnosis', req)
  }
}
