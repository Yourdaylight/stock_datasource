import { request } from '@/utils/request'

export interface TokenBalance {
  user_id: string
  total_quota: number
  used_tokens: number
  remaining_tokens: number
}

export interface UsageRecord {
  id: string
  session_id: string
  session_title: string
  agent_name: string
  model_name: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  created_at: string
}

export interface UsageHistoryResponse {
  records: UsageRecord[]
  total: number
  page: number
  page_size: number
}

export interface DailyUsageStat {
  date: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  call_count: number
}

export interface UsageStatsResponse {
  daily_stats: DailyUsageStat[]
  total_prompt_tokens: number
  total_completion_tokens: number
  total_tokens: number
  total_calls: number
  avg_daily_tokens: number
}

export const tokenApi = {
  getBalance(): Promise<TokenBalance> {
    return request.get('/api/token/balance')
  },

  getHistory(params?: {
    page?: number
    page_size?: number
    start_date?: string
    end_date?: string
  }): Promise<UsageHistoryResponse> {
    return request.get('/api/token/history', { params })
  },

  getStats(days?: number): Promise<UsageStatsResponse> {
    return request.get('/api/token/stats', { params: { days: days || 30 } })
  }
}
