import { request } from '@/utils/request'

export interface IndexStatus {
  ts_code: string
  name?: string
  close?: number
  pct_chg?: number
  vol?: number
  amount?: number
}

export interface MarketStats {
  trade_date: string
  up_count: number
  down_count: number
  flat_count: number
  limit_up_count: number
  limit_down_count: number
  total_amount?: number
  total_vol?: number
}

export interface HotEtf {
  ts_code: string
  name?: string
  close?: number
  pct_chg?: number
  amount?: number
  vol?: number
}

export interface DailyOverviewResponse {
  trade_date: string
  major_indices: IndexStatus[]
  market_stats?: MarketStats
  hot_etfs_by_amount: HotEtf[]
  hot_etfs_by_change: HotEtf[]
}

export interface HotEtfResponse {
  trade_date: string
  sort_by: string
  data: HotEtf[]
}

export interface AnalyzeRequest {
  question: string
  user_id?: string
  date?: string
  clear_history?: boolean
}

export interface AnalyzeResponse {
  date: string
  question: string
  response: string
  success: boolean
  metadata?: Record<string, any>
  session_id: string
  history_length: number
}

export interface QuickAnalysisResponse {
  trade_date: string
  market_summary: string
  indices_summary: {
    data: IndexStatus[]
    up_count?: number
    down_count?: number
  }
  market_breadth: {
    up_count?: number
    down_count?: number
    limit_up_count?: number
    limit_down_count?: number
    total_amount_yi?: number
    up_down_ratio?: number
  }
  sentiment: {
    score?: number
    label?: string
    description?: string
  }
  hot_etfs: HotEtf[]
  signals: string[]
}

export const overviewApi = {
  // Get daily overview
  getDailyOverview(date?: string): Promise<DailyOverviewResponse> {
    const queryParams = date ? `?date=${date}` : ''
    return request.get(`/api/overview/daily${queryParams}`)
  },

  // Get hot ETFs
  getHotEtfs(params: {
    date?: string
    sort_by?: 'amount' | 'pct_chg'
    limit?: number
  } = {}): Promise<HotEtfResponse> {
    const queryParams = new URLSearchParams()
    if (params.date) queryParams.append('date', params.date)
    if (params.sort_by) queryParams.append('sort_by', params.sort_by)
    if (params.limit) queryParams.append('limit', params.limit.toString())
    const queryString = queryParams.toString()
    return request.get(`/api/overview/hot-etfs${queryString ? '?' + queryString : ''}`)
  },

  // Get major indices
  getIndices(date?: string): Promise<{ trade_date: string; data: IndexStatus[] }> {
    const queryParams = date ? `?date=${date}` : ''
    return request.get(`/api/overview/indices${queryParams}`)
  },

  // AI market analysis
  analyze(req: AnalyzeRequest): Promise<AnalyzeResponse> {
    return request.post('/api/overview/analyze', req)
  },

  // Clear conversation history
  clearHistory(userId: string = 'default', date?: string): Promise<AnalyzeResponse> {
    return request.post('/api/overview/analyze', {
      question: '请重新开始分析',
      user_id: userId,
      date,
      clear_history: true
    })
  },

  // Quick analysis (without AI)
  getQuickAnalysis(date?: string): Promise<QuickAnalysisResponse> {
    const queryParams = date ? `?date=${date}` : ''
    return request.get(`/api/overview/quick-analysis${queryParams}`)
  }
}
