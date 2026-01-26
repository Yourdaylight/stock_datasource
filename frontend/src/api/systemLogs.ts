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
  log_entries: LogEntry[]
  user_query?: string
}

export interface LogAnalysisResponse {
  error_type: string
  possible_causes: string[]
  suggested_fixes: string[]
  confidence: number
  related_logs: string[]
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
