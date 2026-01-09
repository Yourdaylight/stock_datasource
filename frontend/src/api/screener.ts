import { request } from '@/utils/request'
import type { StockInfo } from '@/types/common'

export interface ScreenerCondition {
  field: string
  operator: 'gt' | 'lt' | 'eq' | 'gte' | 'lte' | 'between' | 'in'
  value: number | number[] | string[]
}

export interface ScreenerRequest {
  conditions: ScreenerCondition[]
  sort_by?: string
  sort_order?: 'asc' | 'desc'
  limit?: number
}

export interface StockItem {
  ts_code: string
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
  total_mv?: number
  turnover_rate?: number
}

export interface StockListResponse {
  items: StockItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface ScreenerResult extends StockInfo {
  pe?: number
  pb?: number
  turnover_rate?: number
  pct_chg?: number
  close?: number
}

export interface NLScreenerRequest {
  query: string
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
}

export const screenerApi = {
  // Get paginated stock list with latest quotes
  getStocks(params: {
    page?: number
    page_size?: number
    sort_by?: string
    sort_order?: 'asc' | 'desc'
    search?: string
  } = {}): Promise<StockListResponse> {
    const queryParams = new URLSearchParams()
    if (params.page) queryParams.append('page', params.page.toString())
    if (params.page_size) queryParams.append('page_size', params.page_size.toString())
    if (params.sort_by) queryParams.append('sort_by', params.sort_by)
    if (params.sort_order) queryParams.append('sort_order', params.sort_order)
    if (params.search) queryParams.append('search', params.search)
    
    const query = queryParams.toString()
    return request.get(`/screener/stocks${query ? '?' + query : ''}`)
  },

  // Get market summary
  getSummary(): Promise<MarketSummary> {
    return request.get('/screener/summary')
  },

  filter(params: ScreenerRequest, page = 1, page_size = 20): Promise<StockListResponse> {
    const queryParams = new URLSearchParams()
    queryParams.append('page', page.toString())
    queryParams.append('page_size', page_size.toString())
    return request.post(`/screener/filter?${queryParams.toString()}`, params)
  },

  nlScreener(params: NLScreenerRequest, page = 1, page_size = 20): Promise<StockListResponse> {
    const queryParams = new URLSearchParams()
    queryParams.append('page', page.toString())
    queryParams.append('page_size', page_size.toString())
    return request.post(`/screener/nl?${queryParams.toString()}`, params)
  },

  getPresets(): Promise<PresetStrategy[]> {
    return request.get('/screener/presets')
  },

  getFields(): Promise<{ field: string; label: string; type: string }[]> {
    return request.get('/screener/fields')
  }
}
