import { request } from '@/utils/request'

export interface HKFinancialRequest {
  code: string
  periods?: number
}

export interface HKStatementRequest {
  code: string
  periods?: number
  period?: string
  indicators?: string
}

export interface HKFinancialIndicator {
  end_date: string
  roe_avg?: number | string
  roa?: number | string
  gross_profit_ratio?: number | string
  net_profit_ratio?: number | string
  basic_eps?: number | string
  pe_ttm?: number | string
  pb_ttm?: number | string
}

export interface HKFinancialResponse {
  status: string
  data?: HKFinancialIndicator[]
  summary?: {
    name?: string
    latest_period?: string
    periods?: number
    profitability?: Record<string, any>
    valuation?: Record<string, any>
  }
  health_analysis?: {
    health_score?: number
    strengths?: string[]
    weaknesses?: string[]
  }
  error?: string
}

export interface HKStatementRow {
  end_date: string
  [key: string]: any
}

export interface HKStatementResponse {
  status: string
  data?: HKStatementRow[]
  error?: string
}

export interface HKAnalysisRequest {
  code: string
  periods?: number
}

export interface HKAnalysisResponse {
  code: string
  analysis_type: string
  content: string
  insights?: {
    investment_thesis?: string[]
    risk_factors?: string[]
    competitive_position?: {
      position: string
      excellent_metrics: number
      total_metrics: number
    }
    financial_strength?: {
      level: string
      score: number
      key_strengths?: string[]
    }
    growth_prospects?: {
      revenue_growth?: number
      profit_growth?: number
    }
  } | null
  status: string
}

export const hkReportApi = {
  // Get comprehensive HK financial analysis
  getFinancial(params: HKFinancialRequest): Promise<HKFinancialResponse> {
    return request.post('/api/hk-report/financial', params)
  },

  // Get HK financial indicators (wide table)
  getIndicators(params: HKFinancialRequest): Promise<{ status: string; data?: HKFinancialIndicator[] }> {
    return request.post('/api/hk-report/indicators', params)
  },

  // Get HK AI analysis
  getAnalysis(params: HKAnalysisRequest): Promise<HKAnalysisResponse> {
    return request.post('/api/hk-report/analysis', params)
  },

  // Get HK income statement
  getIncome(params: HKStatementRequest): Promise<HKStatementResponse> {
    return request.post('/api/hk-report/income', params)
  },

  // Get HK balance sheet
  getBalance(params: HKStatementRequest): Promise<HKStatementResponse> {
    return request.post('/api/hk-report/balance', params)
  },

  // Get HK cash flow statement
  getCashflow(params: HKStatementRequest): Promise<HKStatementResponse> {
    return request.post('/api/hk-report/cashflow', params)
  },

  // Get full HK financial statements
  getStatements(params: HKFinancialRequest): Promise<{
    status: string
    income_statement?: HKStatementResponse
    balance_sheet?: HKStatementResponse
    cash_flow?: HKStatementResponse
  }> {
    return request.post('/api/hk-report/statements', params)
  },

  // Health check
  healthCheck(): Promise<{ status: string }> {
    return request.get('/api/hk-report/health')
  }
}
