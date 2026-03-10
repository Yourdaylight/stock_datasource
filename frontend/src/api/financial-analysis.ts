import { request } from '@/utils/request'

// ========== Types ==========

export interface CompanyItem {
  ts_code: string
  symbol: string
  name: string
  area: string
  industry: string
  market: string
  list_date: string
}

export interface CompanyListResponse {
  status: string
  items: CompanyItem[]
  total: number
  page: number
  page_size: number
}

export interface IndustryListResponse {
  status: string
  industries: string[]
}

export interface ReportPeriod {
  end_date: string
  report_type: string
  report_type_label: string
  revenue: number | null
  net_profit: number | null
  roe: number | null
  gross_margin: number | null
  net_margin: number | null
  eps: number | null
  current_ratio: number | null
  debt_ratio: number | null
  has_analysis: boolean
}

export interface ReportPeriodsResponse {
  status: string
  company: CompanyItem
  periods: ReportPeriod[]
}

export interface ReportDetailResponse {
  status: string
  company: CompanyItem
  end_date: string
  report_type: string
  report_type_label: string
  analysis: Record<string, any>
  statements: {
    income: any[]
    balance: any[]
    cashflow: any[]
  }
}

export interface AnalysisRecord {
  id: string
  ts_code: string
  stock_name: string
  market: string
  end_date: string
  report_type: string
  analysis_type: string
  report_content: string
  health_score: number
  analysis_sections: Array<{ title: string; content: string }>
  analysis_metadata: Record<string, any>
  created_at: string
  data_snapshot?: Record<string, any>
}

export interface AnalyzeRequest {
  code: string
  end_date: string
  market?: string
  analysis_type?: string
}

export interface AnalyzeResponse {
  status: string
  record: AnalysisRecord
}

export interface AnalysisHistoryResponse {
  status: string
  records: AnalysisRecord[]
}

export interface AnalysisRecordResponse {
  status: string
  record: AnalysisRecord
}

// ========== API ==========

const BASE = '/api/financial-analysis'

export const financialAnalysisApi = {
  /** 获取上市公司列表 */
  getCompanies(params: {
    market?: string
    keyword?: string
    industry?: string
    page?: number
    page_size?: number
  }): Promise<CompanyListResponse> {
    const query = new URLSearchParams()
    if (params.market) query.set('market', params.market)
    if (params.keyword) query.set('keyword', params.keyword)
    if (params.industry) query.set('industry', params.industry)
    if (params.page) query.set('page', String(params.page))
    if (params.page_size) query.set('page_size', String(params.page_size))
    return request.get(`${BASE}/companies?${query}`)
  },

  /** 获取行业列表 */
  getIndustries(market?: string): Promise<IndustryListResponse> {
    const query = market ? `?market=${market}` : ''
    return request.get(`${BASE}/industries${query}`)
  },

  /** 获取公司的财报期列表 */
  getReportPeriods(code: string, market?: string): Promise<ReportPeriodsResponse> {
    const query = market ? `?market=${market}` : ''
    return request.get(`${BASE}/companies/${encodeURIComponent(code)}/reports${query}`)
  },

  /** 获取指定期财报详情 */
  getReportDetail(code: string, period: string, market?: string): Promise<ReportDetailResponse> {
    const query = market ? `?market=${market}` : ''
    return request.get(`${BASE}/companies/${encodeURIComponent(code)}/reports/${period}${query}`)
  },

  /** 触发AI财报分析（规则引擎，快速） */
  analyze(params: AnalyzeRequest): Promise<AnalyzeResponse> {
    return request.post(`${BASE}/analyze`, params)
  },

  /** 触发LLM大模型深度分析（需人工触发，耗时较长） */
  analyzeDeep(params: AnalyzeRequest): Promise<AnalyzeResponse> {
    return request.post(`${BASE}/analyze/ai-deep`, params)
  },

  /** 获取历史分析记录 */
  getAnalysisHistory(code: string, params?: {
    end_date?: string
    market?: string
    limit?: number
  }): Promise<AnalysisHistoryResponse> {
    const query = new URLSearchParams()
    if (params?.end_date) query.set('end_date', params.end_date)
    if (params?.market) query.set('market', params.market)
    if (params?.limit) query.set('limit', String(params.limit))
    return request.get(`${BASE}/companies/${encodeURIComponent(code)}/analyses?${query}`)
  },

  /** 获取单条分析记录 */
  getAnalysisRecord(recordId: string): Promise<AnalysisRecordResponse> {
    return request.get(`${BASE}/analyses/${recordId}`)
  },
}
