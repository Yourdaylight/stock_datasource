import { request } from '@/utils/request'

export interface IndexInfo {
  ts_code: string
  name?: string
  fullname?: string
  market?: string
  publisher?: string
  index_type?: string
  category?: string
  base_date?: string
  base_point?: number
  list_date?: string
  weight_rule?: string
  desc?: string
}

export interface IndexListResponse {
  total: number
  page: number
  page_size: number
  data: IndexInfo[]
}

export interface Constituent {
  index_code: string
  con_code: string
  trade_date?: string
  weight?: number
}

export interface ConstituentResponse {
  index_code: string
  trade_date?: string
  constituent_count: number
  total_weight: number
  constituents: Constituent[]
}

export interface FactorResponse {
  ts_code: string
  days: number
  data: Record<string, any>[]
}

export interface AnalyzeRequest {
  ts_code: string
  question?: string
  user_id?: string
  clear_history?: boolean
}

export interface AnalysisResult {
  ts_code: string
  question?: string
  response: string
  success: boolean
  metadata?: Record<string, any>
  session_id: string
  history_length: number
}

export interface QuickAnalysisResult {
  ts_code: string
  index_name?: string
  trade_date?: string
  overall_score: number
  suggestion: string
  suggestion_detail: string
  risks: string[]
  dimension_scores: {
    trend: { score: number; weight: string; direction: string }
    momentum: { score: number; weight: string; status: string }
    volatility: { score: number; weight: string; status: string }
    volume: { score: number; weight: string; status: string }
    sentiment: { score: number; weight: string; status: string }
  }
  concentration?: {
    cr10: number
    hhi: number
    risk_level: string
  }
  disclaimer: string
}

export interface MarketOption {
  market: string
  count: number
}

export interface CategoryOption {
  category: string
  count: number
}

export const etfApi = {
  // Get index list with pagination and filters
  getIndices(params: {
    market?: string
    category?: string
    keyword?: string
    page?: number
    page_size?: number
  } = {}): Promise<IndexListResponse> {
    const queryParams = new URLSearchParams()
    if (params.market) queryParams.append('market', params.market)
    if (params.category) queryParams.append('category', params.category)
    if (params.keyword) queryParams.append('keyword', params.keyword)
    if (params.page) queryParams.append('page', params.page.toString())
    if (params.page_size) queryParams.append('page_size', params.page_size.toString())
    
    const queryString = queryParams.toString()
    return request.get(`/etf/indices${queryString ? '?' + queryString : ''}`)
  },

  // Get index detail
  getIndexDetail(tsCode: string): Promise<IndexInfo> {
    return request.get(`/etf/indices/${tsCode}`)
  },

  // Get index constituents
  getConstituents(tsCode: string, tradeDate?: string, limit: number = 100): Promise<ConstituentResponse> {
    const params = new URLSearchParams()
    if (tradeDate) params.append('trade_date', tradeDate)
    params.append('limit', limit.toString())
    return request.get(`/etf/indices/${tsCode}/constituents?${params.toString()}`)
  },

  // Get technical factors
  getFactors(tsCode: string, days: number = 30, indicators?: string[]): Promise<FactorResponse> {
    const params = new URLSearchParams()
    params.append('days', days.toString())
    if (indicators && indicators.length > 0) {
      params.append('indicators', indicators.join(','))
    }
    return request.get(`/etf/indices/${tsCode}/factors?${params.toString()}`)
  },

  // Get available markets
  getMarkets(): Promise<MarketOption[]> {
    return request.get('/etf/markets')
  },

  // Get available categories
  getCategories(): Promise<CategoryOption[]> {
    return request.get('/etf/categories')
  },

  // AI analysis with conversation memory
  analyze(req: AnalyzeRequest): Promise<AnalysisResult> {
    return request.post('/etf/analyze', req)
  },

  // Clear conversation history for a specific index
  clearHistory(tsCode: string, userId: string = 'default'): Promise<AnalysisResult> {
    return request.post('/etf/analyze', {
      ts_code: tsCode,
      user_id: userId,
      clear_history: true,
      question: '请重新开始分析'
    })
  },

  // Quick analysis (without AI)
  getQuickAnalysis(tsCode: string): Promise<QuickAnalysisResult> {
    return request.get(`/etf/indices/${tsCode}/quick-analysis`)
  }
}
