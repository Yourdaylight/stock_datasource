import { request } from '@/utils/request'

export interface FinancialData {
  period: string
  revenue?: number
  net_profit?: number
  net_profit_attr_p?: number
  total_assets?: number
  total_liab?: number
  roe?: number
  roa?: number
  gross_margin?: number
  net_margin?: number
  operating_margin?: number
  debt_ratio?: number
  current_ratio?: number
  // Income statement details
  operate_profit?: number
  total_profit?: number
  basic_eps?: number
  diluted_eps?: number
  ebit?: number
  ebitda?: number
  // Cost & expense
  oper_cost?: number
  sell_exp?: number
  admin_exp?: number
  fin_exp?: number
  rd_exp?: number
  total_cogs?: number
  // Expense ratios (% of revenue)
  sell_exp_ratio?: number
  admin_exp_ratio?: number
  fin_exp_ratio?: number
  rd_exp_ratio?: number
  // Tax & other
  income_tax?: number
  biz_tax_surchg?: number
  minority_gain?: number
  invest_income?: number
  non_oper_income?: number
  non_oper_exp?: number
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
