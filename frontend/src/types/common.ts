// Common types

export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

export interface PaginationParams {
  page: number
  pageSize: number
}

export interface PaginationResult<T> {
  list: T[]
  total: number
  page: number
  pageSize: number
}

export interface StockInfo {
  ts_code: string
  name: string
  industry?: string
  market?: string
}

export interface KLineData {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
  pct_chg?: number
}

export interface IndicatorData {
  date: string
  values: Record<string, number>
}

export interface IndicatorDataV2 {
  dates: string[]
  indicators: Record<string, number[]>
  signals?: TechnicalSignal[]
}

export interface TechnicalSignal {
  type: 'bullish' | 'bearish' | 'neutral'
  indicator: string
  signal: string
  description: string
}

export interface ScreenerCondition {
  field: string
  operator: 'gt' | 'lt' | 'eq' | 'gte' | 'lte' | 'between' | 'in'
  value: number | string | number[]
}

// Market Overview Types
export interface IndexData {
  code: string
  name: string
  close: number
  pct_chg: number
  volume?: number
  amount?: number
}

export interface MarketStats {
  up_count: number
  down_count: number
  flat_count: number
  limit_up_count: number
  limit_down_count: number
  total_amount: number
}

export interface MarketOverview {
  date: string
  indices: IndexData[]
  stats: MarketStats
}

export interface HotSector {
  name: string
  pct_chg: number
  leading_stock?: string
  leading_stock_code?: string
}

// Trend Analysis Types
export interface TrendAnalysis {
  code: string
  name: string
  trend: string
  support: number
  resistance: number
  signals: TechnicalSignal[]
  summary: string
  disclaimer: string
}

// Chip Distribution Types (筹码分布)
export interface ChipData {
  ts_code: string
  trade_date: string
  price: number
  percent: number
}

export interface ChipStats {
  ts_code: string
  trade_date: string
  price_levels: number
  min_price: number
  max_price: number
  weighted_avg_price: number
  max_percent: number
  profit_ratio?: number
  loss_ratio?: number
  current_price?: number
}
