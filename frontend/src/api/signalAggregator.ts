import { request } from '@/utils/request'

/** 维度评分 */
export interface DimensionScore {
  score: number
  direction: 'bullish' | 'bearish' | 'neutral'
  detail: Record<string, any>
}

/** 单股票信号汇总 */
export interface StockSignalSummary {
  ts_code: string
  stock_name: string
  composite_score: number
  composite_direction: 'bullish' | 'bearish' | 'neutral'
  news_score: number
  capital_score: number
  tech_score: number
  news_detail: Record<string, any>
  capital_detail: Record<string, any>
  tech_detail: Record<string, any>
  signal_date: string
}

/** 信号聚合响应 */
export interface SignalAggregationResponse {
  stocks: StockSignalSummary[]
  trade_date: string
  total_count: number
}

/** 信号快照 */
export interface SignalSnapshot {
  ts_code: string
  signal_date: string
  news_score: number
  capital_score: number
  tech_score: number
  composite_score: number
  news_detail: Record<string, any>
  capital_detail: Record<string, any>
  created_at: string
}

/** 信号时序响应 */
export interface SignalTimelineResponse {
  ts_code: string
  stock_name: string
  snapshots: SignalSnapshot[]
}

/** 信号权重配置 */
export interface SignalWeightsConfig {
  news_weight: number
  capital_weight: number
  tech_weight: number
}

export const signalAggregatorApi = {
  /** 批量获取股票信号聚合评分 */
  aggregate(tsCodes: string[], signalDate?: string): Promise<SignalAggregationResponse> {
    const params = new URLSearchParams()
    params.set('ts_codes', tsCodes.join(','))
    if (signalDate) params.set('signal_date', signalDate)
    return request.get(`/api/signal-aggregator/aggregate?${params.toString()}`)
  },

  /** 获取单只股票信号聚合评分 */
  aggregateSingle(tsCode: string, signalDate?: string): Promise<StockSignalSummary> {
    const params = signalDate ? `?signal_date=${signalDate}` : ''
    return request.get(`/api/signal-aggregator/aggregate/${tsCode}${params}`)
  },

  /** 获取信号时序追踪 */
  getTimeline(tsCode: string, days: number = 30): Promise<SignalTimelineResponse> {
    return request.get(`/api/signal-aggregator/timeline/${tsCode}?days=${days}`)
  },

  /** 更新权重配置 */
  updateWeights(config: SignalWeightsConfig): Promise<{ success: boolean }> {
    return request.put('/api/signal-aggregator/weights', config)
  },
}
