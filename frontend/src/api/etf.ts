import { request } from '@/utils/request'

export interface EtfInfo {
  ts_code: string
  csname?: string
  cname?: string
  mgr_name?: string
  custod_name?: string
  etf_type?: string
  setup_date?: string
  list_date?: string
  mgt_fee?: number
  index_code?: string
  index_name?: string
  list_status?: string
  exchange?: string
}

export interface EtfQuoteItem {
  ts_code: string
  trade_date?: string
  open?: number
  high?: number
  low?: number
  close?: number
  pct_chg?: number
  vol?: number
  amount?: number
  csname?: string
  cname?: string
  index_code?: string
  index_name?: string
  exchange?: string
  mgr_name?: string
  custod_name?: string
  list_date?: string
  list_status?: string
  etf_type?: string
  mgt_fee?: number
}

export interface EtfListResponse {
  items: EtfQuoteItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface EtfDailyData {
  ts_code: string
  trade_date: string
  open?: number
  high?: number
  low?: number
  close?: number
  pre_close?: number
  change?: number
  pct_chg?: number
  vol?: number
  amount?: number
}

export interface EtfDailyResponse {
  ts_code: string
  days: number
  data: EtfDailyData[]
}

export interface EtfKLineData {
  ts_code: string
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  vol?: number
  amount?: number
  pct_chg?: number
}

export interface EtfKLineResponse {
  ts_code: string
  name?: string
  adjust: string
  data: EtfKLineData[]
}

export interface ExchangeOption {
  value: string
  label: string
  count: number
}

export interface EtfTypeOption {
  value: string
  label: string
  count: number
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
  name?: string
  trade_date?: string
  basic_info: {
    management?: string
    custodian?: string
    fund_type?: string
    list_date?: string
    m_fee?: number
    c_fee?: number
    benchmark?: string
    status?: string
  }
  price_metrics: {
    latest_close?: number
    latest_pct_chg?: number
    return_5d?: number
    return_20d?: number
    period_return?: number
  }
  volume_metrics: {
    avg_volume?: number
    avg_amount_wan?: number
  }
  risk_metrics: {
    annual_volatility?: number
    max_drawdown?: number
  }
  tracking_info: {
    benchmark?: string
    tracking_index?: Record<string, any>
    tracking_diff?: number
    analysis?: string
  }
  signals: string[]
}

export const etfApi = {
  // Get ETF list with pagination and filters
  getEtfs(params: {
    market?: string
    fund_type?: string
    invest_type?: string
    status?: string
    keyword?: string
    page?: number
    page_size?: number
  } = {}): Promise<EtfListResponse> {
    const queryParams = new URLSearchParams()
    if (params.market) queryParams.append('market', params.market)
    if (params.fund_type) queryParams.append('fund_type', params.fund_type)
    if (params.invest_type) queryParams.append('invest_type', params.invest_type)
    if (params.status) queryParams.append('status', params.status)
    if (params.keyword) queryParams.append('keyword', params.keyword)
    if (params.page) queryParams.append('page', params.page.toString())
    if (params.page_size) queryParams.append('page_size', params.page_size.toString())
    
    const queryString = queryParams.toString()
    return request.get(`/api/etf/etfs${queryString ? '?' + queryString : ''}`)
  },

  // Get ETF detail
  getEtfDetail(tsCode: string): Promise<EtfInfo> {
    return request.get(`/api/etf/etfs/${tsCode}`)
  },

  // Get ETF daily data
  getDaily(tsCode: string, days: number = 30): Promise<EtfDailyResponse> {
    return request.get(`/api/etf/etfs/${tsCode}/daily?days=${days}`)
  },

  // Get ETF K-line data
  getKLine(tsCode: string, params: {
    start_date?: string
    end_date?: string
    adjust?: 'qfq' | 'hfq' | 'none'
  } = {}): Promise<EtfKLineResponse> {
    const queryParams = new URLSearchParams()
    if (params.start_date) queryParams.append('start_date', params.start_date)
    if (params.end_date) queryParams.append('end_date', params.end_date)
    if (params.adjust) queryParams.append('adjust', params.adjust)
    const queryString = queryParams.toString()
    return request.get(`/api/etf/etfs/${tsCode}/kline${queryString ? '?' + queryString : ''}`)
  },

  // Get available exchanges
  getExchanges(): Promise<ExchangeOption[]> {
    return request.get('/api/etf/exchanges')
  },

  // Get available ETF types
  getTypes(): Promise<EtfTypeOption[]> {
    return request.get('/api/etf/types')
  },

  // Get available invest types
  getInvestTypes(): Promise<EtfTypeOption[]> {
    return request.get('/api/etf/invest-types')
  },

  // AI analysis with conversation memory
  analyze(req: AnalyzeRequest): Promise<AnalysisResult> {
    return request.post('/api/etf/analyze', req)
  },

  // Clear conversation history
  clearHistory(tsCode: string, userId: string = 'default'): Promise<AnalysisResult> {
    return request.post('/api/etf/analyze', {
      ts_code: tsCode,
      user_id: userId,
      clear_history: true,
      question: '请重新开始分析'
    })
  },

  // Quick analysis (without AI)
  getQuickAnalysis(tsCode: string): Promise<QuickAnalysisResult> {
    return request.get(`/api/etf/etfs/${tsCode}/quick-analysis`)
  }
}
