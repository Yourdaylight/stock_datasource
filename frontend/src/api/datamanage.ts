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
  source_id: string
  plugin_name: string
  task_type: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  records_processed: number
  error_message?: string
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
  type: string
  is_enabled: boolean
  last_run_at?: string
  last_run_status?: string
}

export interface TableMetadata {
  table_name: string
  description: string
  row_count: number
  size_bytes: number
  last_updated_at?: string
}

export const datamanageApi = {
  getDataSources(): Promise<DataSource[]> {
    return request.get('/datamanage/datasources')
  },

  testConnection(sourceId: string): Promise<{ success: boolean; message: string }> {
    return request.post(`/datamanage/datasources/${sourceId}/test`)
  },

  getSyncTasks(): Promise<SyncTask[]> {
    return request.get('/datamanage/sync/tasks')
  },

  triggerSync(sourceId: string, syncType: 'full' | 'incremental'): Promise<{ task_id: string }> {
    return request.post('/datamanage/sync/trigger', { source_id: sourceId, sync_type: syncType })
  },

  getSyncStatus(taskId: string): Promise<SyncTask> {
    return request.get(`/datamanage/sync/status/${taskId}`)
  },

  getSyncHistory(limit?: number): Promise<SyncTask[]> {
    const params = limit ? `?limit=${limit}` : ''
    return request.get(`/datamanage/sync/history${params}`)
  },

  getQualityMetrics(): Promise<QualityMetrics[]> {
    return request.get('/datamanage/quality/metrics')
  },

  getQualityReport(tableName?: string): Promise<any> {
    const params = tableName ? `?table=${encodeURIComponent(tableName)}` : ''
    return request.get(`/datamanage/quality/report${params}`)
  },

  getPlugins(): Promise<PluginInfo[]> {
    return request.get('/datamanage/plugins')
  },

  enablePlugin(name: string): Promise<void> {
    return request.post(`/datamanage/plugins/${name}/enable`)
  },

  disablePlugin(name: string): Promise<void> {
    return request.post(`/datamanage/plugins/${name}/disable`)
  },

  getTableMetadata(): Promise<TableMetadata[]> {
    return request.get('/datamanage/metadata/tables')
  }
}
