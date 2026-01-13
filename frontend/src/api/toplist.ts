import { request } from '@/utils/request'

export interface TopListItem {
  ts_code: string
  trade_date: string
  name?: string
  close?: number
  pct_chg?: number
  turnover_rate?: number
  amount?: number
  l_sell?: number
  l_buy?: number
  l_amount?: number
  net_amount?: number
  net_rate?: number
  amount_rate?: number
  float_values?: number
  reason?: string
}

export interface TopListResponse {
  total: number
  page: number
  page_size: number
  data: TopListItem[]
}

export interface TopInstItem {
  ts_code: string
  trade_date: string
  exalter?: string
  buy?: number
  buy_rate?: number
  sell?: number
  sell_rate?: number
  net_buy?: number
}

export interface TopInstResponse {
  total: number
  page: number
  page_size: number
  data: TopInstItem[]
}

export interface SeatConcentration {
  ts_code: string
  concentration_index: number
  institution_dominance: number
  top_seat_ratio: number
  risk_level: string
  analysis_period: number
}

export interface AnomalyAlert {
  ts_code: string
  stock_name?: string
  alert_type: string
  severity: 'low' | 'medium' | 'high'
  message: string
  detected_at: string
  indicators: Record<string, any>
}

export interface TopListAnalysis {
  ts_code: string
  stock_name?: string
  analysis_date: string
  seat_concentration: SeatConcentration
  capital_flow_trend: {
    net_flow_5d: number
    net_flow_10d: number
    flow_direction: string
    stability_score: number
  }
  trading_pattern: {
    avg_turnover_rate: number
    volatility_index: number
    volume_surge_count: number
  }
  risk_assessment: {
    overall_risk: string
    risk_factors: string[]
    suggestions: string[]
  }
}

export interface PortfolioTopListAnalysis {
  on_list_positions: Array<{
    ts_code: string
    stock_name: string
    position_weight: number
    toplist_appearances: number
    latest_appearance?: string
    concentration_index: number
    institution_dominance: number
    recent_net_flow: number
    risk_level: string
  }>
  capital_flow_analysis: {
    total_net_flow: number
    average_concentration: number
    positions_on_toplist: number
    high_risk_positions: number
  }
  risk_alerts: Array<{
    ts_code: string
    type: string
    message: string
  }>
  investment_suggestions: string[]
}

export const toplistApi = {
  // Get top list data by date
  getTopListByDate(
    date: string,
    page: number = 1,
    pageSize: number = 50
  ): Promise<TopListResponse> {
    const params = new URLSearchParams()
    params.append('page', page.toString())
    params.append('page_size', pageSize.toString())
    return request.get(`/api/toplist/data/${date}?${params.toString()}`)
  },

  // Get stock's top list history
  getStockTopListHistory(
    tsCode: string,
    days: number = 30,
    page: number = 1,
    pageSize: number = 50
  ): Promise<TopListResponse> {
    const params = new URLSearchParams()
    params.append('days', days.toString())
    params.append('page', page.toString())
    params.append('page_size', pageSize.toString())
    return request.get(`/api/toplist/stock/${tsCode}/history?${params.toString()}`)
  },

  // Get institutional seat data
  getTopInst(
    date?: string,
    tsCode?: string,
    page: number = 1,
    pageSize: number = 50
  ): Promise<TopInstResponse> {
    const params = new URLSearchParams()
    if (tsCode) params.append('ts_code', tsCode)
    params.append('page', page.toString())
    params.append('page_size', pageSize.toString())
    if (date) {
      return request.get(`/api/toplist/institutional-seats/${date}?${params.toString()}`)
    } else {
      return request.get(`/api/toplist/institutional-seats?${params.toString()}`)
    }
  },

  // Calculate seat concentration
  getSeatConcentration(
    tsCode: string,
    days: number = 5
  ): Promise<SeatConcentration> {
    const params = new URLSearchParams()
    params.append('days', days.toString())
    return request.get(`/api/toplist/analysis/concentration/${tsCode}?${params.toString()}`)
  },

  // Get comprehensive analysis
  getStockAnalysis(
    tsCode: string,
    days: number = 10
  ): Promise<TopListAnalysis> {
    const params = new URLSearchParams()
    params.append('days', days.toString())
    return request.get(`/api/toplist/analysis/stock/${tsCode}?${params.toString()}`)
  },

  // Get anomaly alerts
  getAnomalyAlerts(
    date?: string,
    severity?: string,
    page: number = 1,
    pageSize: number = 20
  ): Promise<{ total: number; data: AnomalyAlert[] }> {
    const params = new URLSearchParams()
    if (date) params.append('date', date)
    if (severity) params.append('severity', severity)
    params.append('page', page.toString())
    params.append('page_size', pageSize.toString())
    return request.get(`/api/toplist/anomalies/detection?${params.toString()}`)
  },

  // Portfolio analysis endpoints
  analyzePortfolioTopList(userId: string = 'default_user'): Promise<{
    success: boolean
    data: PortfolioTopListAnalysis
    message: string
  }> {
    return request.post('/api/toplist/portfolio/analyze', { user_id: userId })
  },

  checkPositionTopListStatus(userId: string = 'default_user'): Promise<{
    success: boolean
    data: {
      positions_status: Array<{
        ts_code: string
        stock_name: string
        on_toplist: boolean
        pct_chg?: number
        net_amount?: number
        reason?: string
        position_weight: number
      }>
      total_positions: number
      on_toplist_count: number
      toplist_ratio: number
    }
    message: string
  }> {
    return request.post('/api/toplist/portfolio/status', { user_id: userId })
  },

  analyzePositionCapitalFlow(
    userId: string = 'default_user',
    days: number = 5
  ): Promise<{
    success: boolean
    data: {
      position_flows: Array<{
        ts_code: string
        stock_name: string
        position_weight: number
        net_flow: number
        avg_pct_chg: number
        concentration_index: number
        institution_dominance: number
        appearance_count: number
        flow_direction: string
        risk_assessment: string
      }>
      summary: {
        total_positions: number
        analyzed_positions: number
        net_inflow_positions: number
        net_outflow_positions: number
        total_net_flow: number
      }
    }
    message: string
  }> {
    const params = new URLSearchParams()
    params.append('days', days.toString())
    return request.post(`/api/toplist/portfolio/capital-flow?${params.toString()}`, { user_id: userId })
  },

  // Search and filter
  searchTopList(params: {
    keyword?: string
    start_date?: string
    end_date?: string
    min_pct_chg?: number
    max_pct_chg?: number
    reason?: string
    page?: number
    page_size?: number
  }): Promise<TopListResponse> {
    const queryParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        queryParams.append(key, value.toString())
      }
    })
    return request.get(`/api/toplist/search?${queryParams.toString()}`)
  },

  // Get market statistics
  getMarketStats(date?: string): Promise<{
    total_stocks: number
    total_amount: number
    avg_pct_chg: number
    top_reasons: Array<{ reason: string; count: number }>
    sector_distribution: Array<{ sector: string; count: number; avg_pct_chg: number }>
  }> {
    if (date) {
      return request.get(`/api/toplist/statistics/reasons/${date}`)
    } else {
      // 如果没有指定日期，使用当前日期
      const today = new Date().toISOString().slice(0, 10).replace(/-/g, '')
      return request.get(`/api/toplist/statistics/reasons/${today}`)
    }
  }
}