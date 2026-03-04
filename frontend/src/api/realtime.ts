import { request } from '@/utils/request'

// ============ Types ============

export interface MinuteBar {
  ts_code: string
  trade_time: string
  open: number
  high: number
  low: number
  close: number
  vol: number
  amount: number
  pct_chg?: number
  name?: string
  market?: string
}

export interface MinuteDataResponse {
  ts_code: string
  freq: string
  count: number
  data: MinuteBar[]
}

export interface BatchMinuteItem {
  ts_code: string
  name?: string
  latest: MinuteBar | null
}

export interface BatchMinuteDataResponse {
  freq: string
  count: number
  data: BatchMinuteItem[]
}

export interface MarketOverviewResponse {
  freq: string
  index_data: MinuteBar[]
  market_stats: {
    up_count: number
    down_count: number
    flat_count: number
    total_vol: number
    total_amount: number
  }
  updated_at: string
}

export interface CollectStatusResponse {
  markets: Record<string, {
    last_collect_time: string
    bar_count: number
    status: string
  }>
  global_status: string
}

export interface TriggerResponse {
  success: boolean
  message: string
  markets_collected: Record<string, number>
}

// ============ API Functions ============

export const realtimeApi = {
  /** 获取单只证券最新分钟数据 */
  getLatestMinute(tsCode: string, freq = '1min'): Promise<{ ts_code: string; freq: string; data: MinuteBar | null }> {
    return request.get('/api/realtime/minute/latest', { params: { ts_code: tsCode, freq } })
  },

  /** 获取单只证券分钟K线 */
  getMinuteData(tsCode: string, freq = '1min', date?: string): Promise<MinuteDataResponse> {
    return request.get('/api/realtime/minute', { params: { ts_code: tsCode, freq, date } })
  },

  /** 批量获取多只证券最新分钟数据 */
  getBatchMinuteData(tsCodes: string[], freq = '1min', date?: string): Promise<BatchMinuteDataResponse> {
    const codes = tsCodes.join(',')
    return request.get('/api/realtime/minute/batch', { params: { ts_codes: codes, freq, date } })
  },

  /** 获取市场概览（指数 + 市场统计） */
  getMarketOverview(freq = '1min'): Promise<MarketOverviewResponse> {
    return request.get('/api/realtime/market/overview', { params: { freq } })
  },

  /** 获取采集状态 */
  getCollectStatus(): Promise<CollectStatusResponse> {
    return request.get('/api/realtime/status')
  },

  /** 手动触发采集 */
  triggerCollection(freq = '1min', markets?: string): Promise<TriggerResponse> {
    return request.post('/api/realtime/trigger', null, { params: { freq, markets } })
  },

  /** 涨幅榜 */
  getTopGainers(freq = '1min', market?: string, limit = 20) {
    return request.get('/api/realtime/rank/gainers', { params: { freq, market, limit } })
  },

  /** 跌幅榜 */
  getTopLosers(freq = '1min', market?: string, limit = 20) {
    return request.get('/api/realtime/rank/losers', { params: { freq, market, limit } })
  },
}
