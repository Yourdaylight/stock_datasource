import { request } from '@/utils/request'
import type { StockInfo } from '@/types/common'

export interface ScreenerCondition {
  field: string
  operator: 'gt' | 'lt' | 'eq' | 'gte' | 'lte' | 'between' | 'in' | 'neq'
  value: number | number[] | string | string[]
}

export interface ScreenerRequest {
  conditions: ScreenerCondition[]
  sort_by?: string
  sort_order?: 'asc' | 'desc'
  limit?: number
  trade_date?: string  // 交易日期，格式 YYYY-MM-DD
  market_type?: 'a_share' | 'hk_stock' | 'all'  // 市场类型
  search?: string  // 按名称/代码模糊搜索
}

export interface StockItem {
  ts_code: string
  stock_name?: string  // 股票名称
  trade_date?: string
  open?: number
  high?: number
  low?: number
  close?: number
  pct_chg?: number
  vol?: number
  amount?: number
  pe_ttm?: number
  pb?: number
  ps_ttm?: number
  dv_ratio?: number
  total_mv?: number
  circ_mv?: number
  turnover_rate?: number
  industry?: string
}

export interface StockListResponse {
  items: StockItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface NLScreenerRequest {
  query: string
}

export interface NLScreenerResponse {
  parsed_conditions: ScreenerCondition[]
  items: StockItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
  explanation: string
}

export interface PresetStrategy {
  id: string
  name: string
  description: string
  conditions: ScreenerCondition[]
}

export interface MarketSummary {
  trade_date: string
  total_stocks: number
  up_count: number
  down_count: number
  flat_count: number
  limit_up: number
  limit_down: number
  avg_change: number
  // 交易日历信息
  is_trading_day?: boolean
  prev_trading_day?: string
  next_trading_day?: string
  market_label?: string
}

// =============================================================================
// 十维画像相关类型
// =============================================================================

export interface ProfileDimension {
  name: string
  score: number
  level: string
  weight: number
  indicators: Record<string, any>
}

export interface StockProfile {
  ts_code: string
  stock_name: string
  trade_date: string
  total_score: number
  dimensions: ProfileDimension[]
  recommendation: string
  raw_data?: Record<string, any>
}

// =============================================================================
// 推荐相关类型
// =============================================================================

export interface Recommendation {
  ts_code: string
  stock_name: string
  reason: string
  score: number
  category: string
  profile?: StockProfile
}

export interface RecommendationResponse {
  trade_date: string
  categories: Record<string, Recommendation[]>
}

// =============================================================================
// 行业相关类型
// =============================================================================

export interface SectorInfo {
  name: string
  stock_count: number
}

export interface SectorListResponse {
  sectors: SectorInfo[]
  total: number
}

// =============================================================================
// API 接口
// =============================================================================

export const screenerApi = {
  // 获取分页股票列表（含最新行情）
  getStocks(params: {
    page?: number
    page_size?: number
    sort_by?: string
    sort_order?: 'asc' | 'desc'
    search?: string
    trade_date?: string  // 交易日期，格式 YYYY-MM-DD
    market_type?: 'a_share' | 'hk_stock' | 'all'  // 市场类型
  } = {}): Promise<StockListResponse> {
    const queryParams = new URLSearchParams()
    if (params.page) queryParams.append('page', params.page.toString())
    if (params.page_size) queryParams.append('page_size', params.page_size.toString())
    if (params.sort_by) queryParams.append('sort_by', params.sort_by)
    if (params.sort_order) queryParams.append('sort_order', params.sort_order)
    if (params.search) queryParams.append('search', params.search)
    if (params.trade_date) queryParams.append('trade_date', params.trade_date)
    if (params.market_type) queryParams.append('market_type', params.market_type)
    
    const query = queryParams.toString()
    return request.get(`/api/screener/stocks${query ? '?' + query : ''}`)
  },

  // 获取市场概况
  getSummary(market_type?: string): Promise<MarketSummary> {
    const params = market_type ? `?market_type=${market_type}` : ''
    return request.get(`/api/screener/summary${params}`)
  },

  // 多条件筛选
  filter(params: ScreenerRequest, page = 1, page_size = 20): Promise<StockListResponse> {
    const queryParams = new URLSearchParams()
    queryParams.append('page', page.toString())
    queryParams.append('page_size', page_size.toString())
    return request.post(`/api/screener/filter?${queryParams.toString()}`, params)
  },

  // 自然语言选股
  nlScreener(params: NLScreenerRequest, page = 1, page_size = 20): Promise<NLScreenerResponse> {
    const queryParams = new URLSearchParams()
    queryParams.append('page', page.toString())
    queryParams.append('page_size', page_size.toString())
    return request.post(`/api/screener/nl?${queryParams.toString()}`, params)
  },

  // 获取预设策略列表
  getPresets(): Promise<PresetStrategy[]> {
    return request.get('/api/screener/presets')
  },

  // 应用预设策略
  applyPreset(presetId: string, page = 1, page_size = 20): Promise<StockListResponse> {
    const queryParams = new URLSearchParams()
    queryParams.append('page', page.toString())
    queryParams.append('page_size', page_size.toString())
    return request.post(`/api/screener/presets/${presetId}/apply?${queryParams.toString()}`)
  },

  // 获取可用筛选字段
  getFields(): Promise<{ field: string; label: string; type: string }[]> {
    return request.get('/api/screener/fields')
  },

  // =============================================================================
  // 十维画像 API
  // =============================================================================

  // 获取单只股票画像
  getProfile(tsCode: string): Promise<StockProfile> {
    return request.get(`/api/screener/profile/${tsCode}`)
  },

  // 批量获取股票画像
  batchGetProfiles(tsCodes: string[]): Promise<StockProfile[]> {
    return request.post('/api/screener/batch-profile', { ts_codes: tsCodes })
  },

  // =============================================================================
  // 行业 API
  // =============================================================================

  // 获取行业列表
  getSectors(marketType?: 'a_share' | 'hk_stock' | 'all'): Promise<SectorListResponse> {
    const queryParams = new URLSearchParams()
    if (marketType) queryParams.append('market_type', marketType)
    const query = queryParams.toString()
    return request.get(`/api/screener/sectors${query ? '?' + query : ''}`)
  },

  // 获取行业内股票
  getSectorStocks(sector: string, params: {
    page?: number
    page_size?: number
    sort_by?: string
    sort_order?: 'asc' | 'desc'
  } = {}): Promise<StockListResponse> {
    const queryParams = new URLSearchParams()
    if (params.page) queryParams.append('page', params.page.toString())
    if (params.page_size) queryParams.append('page_size', params.page_size.toString())
    if (params.sort_by) queryParams.append('sort_by', params.sort_by)
    if (params.sort_order) queryParams.append('sort_order', params.sort_order)
    
    const query = queryParams.toString()
    return request.get(`/api/screener/sectors/${encodeURIComponent(sector)}/stocks${query ? '?' + query : ''}`)
  },

  // =============================================================================
  // 推荐 API
  // =============================================================================

  // 获取AI推荐
  getRecommendations(marketType?: 'a_share' | 'hk_stock' | 'all'): Promise<RecommendationResponse> {
    const queryParams = new URLSearchParams()
    if (marketType) queryParams.append('market_type', marketType)
    const query = queryParams.toString()
    return request.get(`/api/screener/recommendations${query ? '?' + query : ''}`)
  },

  // 获取技术信号
  getSignals(): Promise<any> {
    return request.get('/api/screener/signals')
  },
}
