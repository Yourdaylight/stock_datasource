export interface Position {
  id: string
  user_id: string
  ts_code: string
  stock_name: string
  quantity: number
  cost_price: number
  buy_date: string
  current_price?: number
  market_value?: number
  profit_loss?: number
  profit_rate?: number
  notes?: string
  sector?: string
  industry?: string
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface PortfolioSummary {
  total_value: number
  total_cost: number
  total_profit: number
  profit_rate: number
  daily_change: number
  daily_change_rate: number
  position_count: number
  risk_score?: number
  top_performer?: string
  worst_performer?: string
  sector_distribution?: Record<string, number>
}

export interface CreatePositionRequest {
  ts_code: string
  quantity: number
  cost_price: number
  buy_date: string
  notes?: string
}

export interface UpdatePositionRequest {
  quantity?: number
  cost_price?: number
  notes?: string
}

export interface AnalysisReport {
  id: string
  user_id: string
  report_date: string
  report_type: string
  market_analysis: string
  portfolio_summary: string
  individual_analysis: string
  risk_assessment: string
  recommendations: string
  ai_insights: string
  status: string
  created_at?: string
  updated_at?: string
}

export interface AlertCreateRequest {
  position_id: string
  ts_code: string
  alert_type: 'price_high' | 'price_low' | 'profit_target' | 'stop_loss'
  condition_value: number
  message?: string
}

export interface Alert {
  id: string
  user_id: string
  position_id: string
  ts_code: string
  alert_type: string
  condition_value: number
  current_value: number
  is_triggered: boolean
  is_active: boolean
  trigger_count: number
  last_triggered?: string
  message: string
  created_at?: string
  updated_at?: string
}

export interface ProfitHistoryItem {
  record_date: string
  total_value: number
  total_cost: number
  total_profit: number
}