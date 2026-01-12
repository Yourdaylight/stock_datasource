import { request } from '@/utils/request'
import type { KLineData, IndicatorData } from '@/types/common'

export interface KLineRequest {
  code: string
  start_date: string
  end_date: string
  adjust?: 'qfq' | 'hfq' | 'none'
}

export interface KLineResponse {
  code: string
  name: string
  data: KLineData[]
}

export interface IndicatorRequest {
  code: string
  indicators: string[]
  period?: number
}

export interface IndicatorResponse {
  code: string
  indicators: IndicatorData[]
}

export interface AnalysisRequest {
  code: string
  period?: number
}

export const marketApi = {
  getKLine(params: KLineRequest): Promise<KLineResponse> {
    return request.post('/api/market/kline', params)
  },

  getIndicators(params: IndicatorRequest): Promise<IndicatorResponse> {
    return request.post('/api/market/indicators', params)
  },

  searchStock(keyword: string): Promise<{ code: string; name: string }[]> {
    return request.get(`/api/market/search?keyword=${encodeURIComponent(keyword)}`)
  },

  analyzeStock(params: AnalysisRequest): EventSource {
    const queryParams = new URLSearchParams({ code: params.code, period: String(params.period || 60) })
    return new EventSource(`/api/market/analysis?${queryParams}`)
  }
}
