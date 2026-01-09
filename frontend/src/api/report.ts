import { request } from '@/utils/request'

export interface FinancialData {
  period: string
  revenue?: number
  net_profit?: number
  total_assets?: number
  total_liab?: number
  roe?: number
  gross_margin?: number
}

export interface FinancialRequest {
  code: string
  report_type?: 'income' | 'balance' | 'cashflow'
  periods?: number
}

export interface FinancialResponse {
  code: string
  name: string
  data: FinancialData[]
}

export interface AnalysisRequest {
  code: string
  focus?: string[]
}

export interface CompareRequest {
  codes: string[]
  metrics: string[]
}

export const reportApi = {
  getFinancial(params: FinancialRequest): Promise<FinancialResponse> {
    return request.post('/report/financial', params)
  },

  analyze(params: AnalysisRequest): EventSource {
    const queryParams = new URLSearchParams({ code: params.code })
    if (params.focus) {
      queryParams.set('focus', params.focus.join(','))
    }
    return new EventSource(`/api/report/analysis?${queryParams}`)
  },

  compare(params: CompareRequest): Promise<Record<string, FinancialData[]>> {
    return request.post('/report/compare', params)
  }
}
