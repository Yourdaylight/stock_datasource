import request from '@/utils/request'

export interface LogEntry {
  timestamp: string
  level: string
  module: string
  message: string
  raw_line: string
}

export interface LogFilter {
  level?: string
  start_time?: string
  end_time?: string
  keyword?: string
  page?: number
  page_size?: number
}

export interface LogListResponse {
  logs: LogEntry[]
  total: number
  page: number
  page_size: number
}

export interface LogFileInfo {
  name: string
  size: number
  modified_time: string
  line_count: number
}

export interface LogAnalysisRequest {
  log_entries?: LogEntry[]
  user_query?: string
  context?: string
  start_time?: string
  end_time?: string
  level?: string
  query?: string
  default_window_hours?: number
  include_code_context?: boolean
  max_entries?: number
}

export interface LogRootCause {
  title: string
  module?: string
  function?: string
  evidence: string[]
  confidence: number
}

export interface LogFixSuggestion {
  title: string
  steps: string[]
  priority: 'low' | 'medium' | 'high'
}

export interface LogAnalysisResponse {
  error_type: string
  possible_causes: string[]
  suggested_fixes: string[]
  confidence: number
  related_logs: string[]
  summary?: string
  analysis_source?: string
  root_causes?: LogRootCause[]
  recent_operations?: Array<Record<string, any>>
  fix_suggestions?: LogFixSuggestion[]
  risk_level?: 'low' | 'medium' | 'high' | 'critical'
  impact_scope?: string
  diagnosis_time?: string
}

export interface LogStatsTrendPoint {
  timestamp: string
  total: number
  error: number
  warning: number
  info: number
  debug: number
}

export interface LogStatsResponse {
  total: number
  error: number
  warning: number
  info: number
  debug: number
  by_level: Record<string, number>
  trend: LogStatsTrendPoint[]
}

export interface ErrorClusterItem {
  signature: string
  count: number
  level: string
  module: string
  latest_time: string
  sample_message: string
}

export interface ErrorClusterResponse {
  clusters: ErrorClusterItem[]
}

export interface OperationTimelineItem {
  timestamp: string
  event_type: string
  level: string
  module: string
  summary: string
  detail?: string
}

export interface OperationTimelineResponse {
  items: OperationTimelineItem[]
}

export interface ArchiveListResponse {
  archives: LogFileInfo[]
}

export const systemLogsApi = {
  // Get system logs
  getLogs(params?: LogFilter) {
    return request.get<LogListResponse>('/api/system_logs', { params })
  },

  // Analyze logs with AI
  analyzeLogs(data: LogAnalysisRequest) {
    return request.post<LogAnalysisResponse>('/api/system_logs/analyze', data)
  },

  // Get log stats and trend
  getStats(params?: LogFilter & { window_hours?: number; limit?: number }) {
    return request.get<LogStatsResponse>('/api/system_logs/stats', { params })
  },

  // Get clustered errors
  getClusters(params?: LogFilter & { window_hours?: number; limit?: number }) {
    return request.get<ErrorClusterResponse>('/api/system_logs/clusters', { params })
  },

  // Get merged operation timeline
  getTimeline(params?: LogFilter & { window_hours?: number; limit?: number }) {
    return request.get<OperationTimelineResponse>('/api/system_logs/timeline', { params })
  },

  // Get log files
  getLogFiles() {
    return request.get<LogFileInfo[]>('/api/system_logs/files')
  },

  // Get archived logs
  getArchives() {
    return request.get<ArchiveListResponse>('/api/system_logs/archives')
  },

  // Archive old logs
  archiveLogs(retentionDays: number = 30) {
    return request.post<{ status: string; archived_count: number; archived_files: string[] }>(
      '/api/system_logs/archive',
      null,
      { params: { retention_days: retentionDays } }
    )
  },

  // Export logs
  exportLogs(params: LogFilter & { format?: string }) {
    return request.get<Blob>('/api/system_logs/export', {
      params,
      responseType: 'blob'
    })
  },

  // Download archive
  downloadArchive(filename: string) {
    return request.get<Blob>(`/api/system_logs/download/${filename}`, {
      responseType: 'blob'
    })
  }
}
