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
}

export interface IndicatorData {
  date: string
  values: Record<string, number>
}

export interface ScreenerCondition {
  field: string
  operator: 'gt' | 'lt' | 'eq' | 'gte' | 'lte' | 'between' | 'in'
  value: number | string | number[]
}
