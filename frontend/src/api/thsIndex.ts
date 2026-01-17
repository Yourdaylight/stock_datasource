import { request } from '@/utils/request'

// Types
export interface THSIndexItem {
  ts_code: string
  name: string
  count?: number
  exchange?: string
  type?: string
  list_date?: string
}

export interface THSDailyItem {
  ts_code: string
  trade_date: string
  open?: number
  high?: number
  low?: number
  close?: number
  pre_close?: number
  pct_change?: number
  vol?: number
  turnover_rate?: number
  total_mv?: number
  float_mv?: number
}

export interface THSRankingItem {
  ts_code: string
  name: string
  type?: string
  count?: number
  close?: number
  pct_change?: number
  vol?: number
  turnover_rate?: number
}

export interface THSIndexListResponse {
  data: THSIndexItem[]
  total: number
  exchange?: string
  index_type?: string
}

export interface THSDailyResponse {
  ts_code: string
  name?: string
  data: THSDailyItem[]
}

export interface THSRankingResponse {
  trade_date: string
  sort_by: string
  order: string
  index_type?: string
  data: THSRankingItem[]
}

export interface THSSearchResponse {
  keyword: string
  data: THSIndexItem[]
}

export interface THSStatsItem {
  type?: string
  exchange?: string
  index_count: number
  total_constituents?: number
  avg_constituents?: number
}

export interface THSStatsResponse {
  data: THSStatsItem[]
}

// Index type labels
export const INDEX_TYPE_LABELS: Record<string, string> = {
  'N': '概念板块',
  'I': '行业板块',
  'R': '地域板块',
  'S': '特色板块',
  'ST': '风格板块',
  'TH': '主题板块',
  'BB': '宽基指数',
}

// API
export const thsIndexApi = {
  // Get index list
  getIndexList(params: {
    exchange?: string
    type?: string
    limit?: number
    offset?: number
  } = {}): Promise<THSIndexListResponse> {
    const queryParams = new URLSearchParams()
    if (params.exchange) queryParams.append('exchange', params.exchange)
    if (params.type) queryParams.append('type', params.type)
    if (params.limit) queryParams.append('limit', params.limit.toString())
    if (params.offset) queryParams.append('offset', params.offset.toString())
    const queryString = queryParams.toString()
    return request.get(`/api/ths-index/list${queryString ? '?' + queryString : ''}`)
  },

  // Get index detail
  getIndexDetail(tsCode: string): Promise<THSIndexItem> {
    return request.get(`/api/ths-index/${tsCode}`)
  },

  // Get daily data
  getDailyData(tsCode: string, params: {
    start_date?: string
    end_date?: string
    limit?: number
  } = {}): Promise<THSDailyResponse> {
    const queryParams = new URLSearchParams()
    if (params.start_date) queryParams.append('start_date', params.start_date)
    if (params.end_date) queryParams.append('end_date', params.end_date)
    if (params.limit) queryParams.append('limit', params.limit.toString())
    const queryString = queryParams.toString()
    return request.get(`/api/ths-index/${tsCode}/daily${queryString ? '?' + queryString : ''}`)
  },

  // Get ranking
  getRanking(params: {
    date?: string
    type?: string
    sort_by?: 'pct_change' | 'vol' | 'turnover_rate' | 'close'
    order?: 'desc' | 'asc'
    limit?: number
  } = {}): Promise<THSRankingResponse> {
    const queryParams = new URLSearchParams()
    if (params.date) queryParams.append('date', params.date)
    if (params.type) queryParams.append('type', params.type)
    if (params.sort_by) queryParams.append('sort_by', params.sort_by)
    if (params.order) queryParams.append('order', params.order)
    if (params.limit) queryParams.append('limit', params.limit.toString())
    const queryString = queryParams.toString()
    return request.get(`/api/ths-index/ranking${queryString ? '?' + queryString : ''}`)
  },

  // Search index
  searchIndex(keyword: string, limit: number = 50): Promise<THSSearchResponse> {
    const queryParams = new URLSearchParams()
    queryParams.append('keyword', keyword)
    queryParams.append('limit', limit.toString())
    return request.get(`/api/ths-index/search?${queryParams.toString()}`)
  },

  // Get statistics
  getStats(): Promise<THSStatsResponse> {
    return request.get('/api/ths-index/stats')
  },
}
