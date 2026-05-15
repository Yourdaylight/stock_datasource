import { request } from '@/utils/request'

/** 哨兵告警 */
export interface SentinelAlert {
  alert_id: string
  sentinel_type: string
  category: string
  severity: 'info' | 'warning' | 'critical'
  timestamp: string
  ts_code?: string
  sector_code?: string
  index_code?: string
  signal_type: string
  description: string
  metric_name: string
  metric_value: number
  threshold: number
  deviation_pct: number
  context: Record<string, any>
}

/** 投资决策 */
export interface InvestmentDecision {
  decision_id: string
  trade_date: string
  market_regime: string
  market_risk_level: string
  suggested_total_position: number
  buy_count: number
  sell_count: number
  confidence: number
  decision_json: string
  created_at: string
}

/** 系统状态 */
export interface SentinelStatus {
  initialized: boolean
  sentinels: Array<{
    type: string
    category: string
    last_scan: number
    alert_count: number
    consecutive_silent: number
    description: string
  }>
  analysts: Array<{
    type: string
    buffer_size: number
    report_count: number
    last_analysis: number
    subscribed_patterns: string[]
  }>
  director: {
    buffer_size: number
    decision_count: number
    last_decision_id: string | null
  } | null
  message_bus: Record<string, any>
}

/** 手动触发全量扫描 */
export function triggerScan() {
  return request.post<{ status: string; message: string; result: any }>('/api/sentinel/scan')
}

/** 获取系统状态 */
export function getStatus() {
  return request.get<{ status: string; data: SentinelStatus }>('/api/sentinel/status')
}

/** 获取最近决策 */
export function getDecisions(limit = 10) {
  return request.get<{ status: string; count: number; data: InvestmentDecision[] }>(
    '/api/sentinel/decisions',
    { params: { limit } }
  )
}

/** 获取最近告警 */
export function getAlerts(params?: { limit?: number; sentinel_type?: string }) {
  return request.get<{ status: string; count: number; data: SentinelAlert[] }>(
    '/api/sentinel/alerts',
    { params }
  )
}
