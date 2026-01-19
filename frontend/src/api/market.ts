import { request } from '@/utils/request'
import type { 
  KLineData, 
  IndicatorData, 
  IndicatorDataV2,
  MarketOverview, 
  HotSector,
  TrendAnalysis,
  TechnicalSignal,
  ChipData,
  ChipStats
} from '@/types/common'

// Request Types
export interface KLineRequest {
  code: string
  start_date: string
  end_date: string
  adjust?: 'qfq' | 'hfq' | 'none'
}

export interface IndicatorRequest {
  code: string
  indicators: string[]
  period?: number
  params?: Record<string, any>
}

export interface AnalysisRequest {
  code: string
  period?: number
}

// Response Types
export interface KLineResponse {
  code: string
  name: string
  data: KLineData[]
}

export interface IndicatorResponse {
  code: string
  indicators: IndicatorData[]
}

export interface IndicatorResponseV2 {
  code: string
  name: string
  dates: string[]
  indicators: Record<string, number[]>
  signals?: TechnicalSignal[]
}

export interface MarketOverviewResponse {
  date: string
  indices: {
    code: string
    name: string
    close: number
    pct_chg: number
    volume?: number
    amount?: number
  }[]
  stats: {
    up_count: number
    down_count: number
    flat_count: number
    limit_up_count: number
    limit_down_count: number
    total_amount: number
  }
}

export interface HotSectorsResponse {
  date: string
  sectors: HotSector[]
}

export interface TrendAnalysisResponse {
  code: string
  name: string
  trend: string
  support: number
  resistance: number
  signals: TechnicalSignal[]
  summary: string
  disclaimer: string
}

export const marketApi = {
  // K-Line Data
  getKLine(params: KLineRequest): Promise<KLineResponse> {
    return request.post('/api/market/kline', params)
  },

  // Technical Indicators (legacy format)
  getIndicators(params: IndicatorRequest): Promise<IndicatorResponse> {
    return request.post('/api/market/indicators', params)
  },

  // Technical Indicators V2 (better format with signals)
  getIndicatorsV2(params: IndicatorRequest): Promise<IndicatorResponseV2> {
    return request.post('/api/market/indicators/v2', params)
  },

  // Stock Search
  searchStock(keyword: string): Promise<{ code: string; name: string }[]> {
    return request.get(`/api/market/search?keyword=${encodeURIComponent(keyword)}`)
  },

  // Market Overview
  getMarketOverview(): Promise<MarketOverviewResponse> {
    return request.get('/api/market/overview')
  },

  // Hot Sectors
  getHotSectors(): Promise<HotSectorsResponse> {
    return request.get('/api/market/hot-sectors')
  },

  // Trend Analysis
  analyzeTrend(params: AnalysisRequest): Promise<TrendAnalysisResponse> {
    return request.post('/api/market/analysis', params)
  },

  // AI Analysis
  aiAnalyze(params: AnalysisRequest): Promise<{
    code: string
    analysis: string
    trend?: string
    signals?: TechnicalSignal[]
    metadata?: Record<string, any>
  }> {
    return request.post('/api/market/analysis/ai', params)
  },

  // SSE Stream Analysis
  analyzeStream(code: string, period: number = 60): EventSource {
    const queryParams = new URLSearchParams({ code, period: String(period) })
    return new EventSource(`/api/market/analysis/stream?${queryParams}`)
  },

  // Chip Distribution (筹码分布)
  async getChipDistribution(params: { ts_code: string; trade_date?: string }): Promise<ChipData[]> {
    const endpoint = params.trade_date 
      ? '/api/tushare_cyq_chips/get_by_date'
      : '/api/tushare_cyq_chips/get_latest'
    const response = await request.post<{ status: string; data: ChipData[] }>(endpoint, params)
    return response.data || []
  },

  async getChipStats(params: { ts_code: string; trade_date: string }): Promise<ChipStats> {
    const response = await request.post<{ status: string; data: ChipStats }>('/api/tushare_cyq_chips/get_distribution_stats', params)
    return response.data
  },

  async getChipProfitRatio(params: { ts_code: string; trade_date: string; current_price: number }): Promise<{
    ts_code: string
    trade_date: string
    current_price: number
    profit_ratio: number
    loss_ratio: number
    price_levels: number
    min_price: number
    max_price: number
  }> {
    const response = await request.post<{ status: string; data: any }>('/api/tushare_cyq_chips/get_profit_ratio', params)
    return response.data
  }
}
