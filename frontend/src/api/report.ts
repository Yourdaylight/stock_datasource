import { request } from '@/utils/request'

export interface FinancialData {
  period: string
  revenue?: number
  net_profit?: number
  total_assets?: number
  total_liab?: number
  roe?: number
  roa?: number
  gross_margin?: number
  net_margin?: number
  debt_ratio?: number
  current_ratio?: number
}

export interface FinancialSummary {
  profitability: {
    roe?: number
    roa?: number
    gross_profit_margin?: number
    net_profit_margin?: number
    eps?: number
  }
  solvency: {
    debt_to_assets?: number
    debt_to_equity?: number
    current_ratio?: number
    quick_ratio?: number
  }
  efficiency: {
    asset_turnover?: number
    inventory_turnover?: number
    receivable_turnover?: number
  }
  growth: {
    revenue_growth?: number
    profit_growth?: number
  }
}

export interface FinancialRequest {
  code: string
  periods?: number
}

export interface FinancialResponse {
  code: string
  name?: string
  periods: number
  latest_period?: string
  data: FinancialData[]
  summary?: FinancialSummary & { health_score: number }
  status: string
}

export interface CompareRequest {
  code: string
  end_date?: string
  industry_limit?: number
}

export interface CompareResponse {
  code: string
  end_date: string
  peer_count: number
  comparison: Record<string, {
    target_value: number
    industry_median: number
    industry_mean: number
    industry_p25: number
    industry_p75: number
    percentile_rank: number
  }>
  interpretation: Record<string, {
    level: string
    percentile: number
    vs_industry: string
  }>
  status: string
}

export interface AnalysisRequest {
  code: string
  analysis_type?: 'comprehensive' | 'peer_comparison' | 'investment_insights'
  periods?: number
}

export interface AnalysisResponse {
  code: string
  analysis_type: string
  content: string
  insights?: {
    investment_thesis: string[]
    risk_factors: string[]
    competitive_position: {
      position: string
      excellent_metrics: number
      total_metrics: number
    }
    financial_strength: {
      level: string
      score: number
      key_strengths: string[]
    }
    growth_prospects: {
      prospects: string
      revenue_growth: number
      profit_growth: number
    }
  }
  status: string
}

export const reportApi = {
  // Get comprehensive financial data
  getFinancial(params: FinancialRequest): Promise<FinancialResponse> {
    return request.post('/api/report/financial', params)
  },

  // Get peer comparison analysis
  getComparison(params: CompareRequest): Promise<CompareResponse> {
    return request.post('/api/report/compare', params)
  },

  // Get AI analysis
  getAnalysis(params: AnalysisRequest): Promise<AnalysisResponse> {
    return request.post('/api/report/analysis', params)
  },

  // Legacy streaming analysis (for backward compatibility)
  analyzeStream(params: { code: string; focus?: string[] }): EventSource {
    const queryParams = new URLSearchParams({ code: params.code })
    if (params.focus) {
      queryParams.set('focus', params.focus.join(','))
    }
    return new EventSource(`/api/report/analysis?${queryParams}`)
  }
}
