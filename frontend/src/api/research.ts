import { request } from '@/utils/request'

// ==================== 机构调研 (stk_surv) 类型定义 ====================

export interface SurveyItem {
  ts_code: string
  name?: string
  surv_date: string
  fund_visitors?: string
  securities_visitors?: string
  insur_visitors?: string
  qfii_visitors?: string
  other_visitors?: string
  total_visitors?: string
  rece_place?: string
  rece_mode?: string
  rece_org?: string
  org_type?: string
  comp_rece?: string
  content?: string
}

export interface SurveyResponse {
  total: number
  page: number
  page_size: number
  data: SurveyItem[]
}

export interface HotSurveyedStock {
  ts_code: string
  name?: string
  survey_count: number
  unique_org_count?: number
  latest_survey_date?: string
  org_types?: string[]
}

export interface OrgTypeStats {
  org_type: string
  count: number
  percentage: number
}

// ==================== 研报盈利预测 (report_rc) 类型定义 ====================

export interface ReportRcItem {
  ts_code: string
  name?: string
  report_date: string
  report_title?: string
  report_type?: string
  classify?: string
  org_name?: string
  author?: string
  eps_last?: number
  eps_curr?: number
  eps_next?: number
  bps?: number
  pe_last?: number
  pe_curr?: number
  pe_next?: number
  rating?: string
  target_price?: number
  status?: string
}

export interface ReportRcResponse {
  total: number
  page: number
  page_size: number
  data: ReportRcItem[]
}

export interface HotCoveredStock {
  ts_code: string
  name?: string
  report_count: number
  unique_org_count?: number
  latest_report_date?: string
  avg_target_price?: number
  ratings?: Record<string, number>
}

export interface ConsensusForecast {
  ts_code: string
  name?: string
  eps_avg?: number
  eps_median?: number
  eps_high?: number
  eps_low?: number
  target_price_avg?: number
  target_price_median?: number
  target_price_high?: number
  target_price_low?: number
  rating_distribution?: Record<string, number>
  report_count: number
}

export interface RatingDistribution {
  rating: string
  count: number
  percentage: number
}

// ==================== API 方法 ====================

export const researchApi = {
  // ==================== 机构调研 API ====================
  
  // 按日期获取调研数据
  getSurveysByDate(
    surv_date: string,
    page: number = 1,
    pageSize: number = 50
  ): Promise<SurveyResponse> {
    return request.post('/api/tushare_stk_surv/get_surveys_by_date', {
      surv_date,
      limit: pageSize
    })
  },

  // 按股票获取调研数据
  getSurveysByStock(
    ts_code: string,
    days: number = 90,
    page: number = 1,
    pageSize: number = 50
  ): Promise<SurveyResponse> {
    return request.post('/api/tushare_stk_surv/get_surveys_by_stock', {
      ts_code,
      limit: pageSize
    })
  },

  // 获取热门调研股票
  getHotSurveyedStocks(
    days: number = 30,
    limit: number = 20
  ): Promise<{ data: HotSurveyedStock[] }> {
    return request.post('/api/tushare_stk_surv/get_hot_surveyed_stocks', {
      days,
      limit
    })
  },

  // 获取机构类型统计
  getOrgTypeStats(
    ts_code?: string,
    days: number = 30
  ): Promise<{ data: OrgTypeStats[] }> {
    return request.post('/api/tushare_stk_surv/get_org_type_stats', {
      ts_code,
      days
    })
  },

  // 搜索调研内容
  searchSurveyContent(
    keyword: string,
    days: number = 90,
    page: number = 1,
    pageSize: number = 50
  ): Promise<SurveyResponse> {
    return request.post('/api/tushare_stk_surv/search_survey_content', {
      keyword,
      days,
      limit: pageSize
    })
  },

  // ==================== 研报盈利预测 API ====================

  // 按日期获取研报数据
  getReportsByDate(
    report_date: string,
    page: number = 1,
    pageSize: number = 50
  ): Promise<ReportRcResponse> {
    return request.post('/api/tushare_report_rc/get_reports_by_date', {
      report_date,
      limit: pageSize
    })
  },

  // 按股票获取研报数据
  getReportsByStock(
    ts_code: string,
    days: number = 180,
    page: number = 1,
    pageSize: number = 50
  ): Promise<ReportRcResponse> {
    return request.post('/api/tushare_report_rc/get_reports_by_stock', {
      ts_code,
      limit: pageSize
    })
  },

  // 获取热门覆盖股票
  getHotCoveredStocks(
    days: number = 30,
    limit: number = 20
  ): Promise<{ data: HotCoveredStock[] }> {
    return request.post('/api/tushare_report_rc/get_hot_covered_stocks', {
      days,
      limit
    })
  },

  // 获取一致性预期
  getConsensusForecast(
    ts_code: string,
    days: number = 90
  ): Promise<{ data: ConsensusForecast }> {
    return request.post('/api/tushare_report_rc/get_consensus_forecast', {
      ts_code,
      days
    })
  },

  // 获取评级分布
  getRatingDistribution(
    ts_code?: string,
    days: number = 30
  ): Promise<{ data: RatingDistribution[] }> {
    return request.post('/api/tushare_report_rc/get_rating_distribution', {
      ts_code,
      days
    })
  }
}
