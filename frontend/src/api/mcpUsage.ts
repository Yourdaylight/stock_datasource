import { request } from '@/utils/request'

export interface McpUsageRecord {
  id: string
  user_id: string
  api_key_id: string
  tool_name: string
  service_prefix: string
  table_name: string
  arguments: string
  record_count: number
  duration_ms: number
  is_error: boolean
  error_message: string
  created_at: string
}

export interface McpUsageHistoryResponse {
  records: McpUsageRecord[]
  total: number
  page: number
  page_size: number
}

export interface McpDailyStat {
  date: string
  call_count: number
  total_records: number
}

export interface McpTopTool {
  tool_name: string
  table_name: string
  call_count: number
  total_records: number
}

export interface McpUsageStatsResponse {
  daily_stats: McpDailyStat[]
  total_calls: number
  total_records: number
  avg_daily_calls: number
  top_tools: McpTopTool[]
}

export const mcpUsageApi = {
  getHistory(params?: {
    page?: number
    page_size?: number
    start_date?: string
    end_date?: string
    tool_name?: string
  }): Promise<McpUsageHistoryResponse> {
    return request.get('/api/mcp-usage/history', { params })
  },

  getStats(days?: number): Promise<McpUsageStatsResponse> {
    return request.get('/api/mcp-usage/stats', { params: { days: days || 30 } })
  }
}
