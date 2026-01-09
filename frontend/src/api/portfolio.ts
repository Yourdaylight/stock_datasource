import { request } from '@/utils/request'

export interface Position {
  id: string
  ts_code: string
  stock_name: string
  quantity: number
  cost_price: number
  buy_date: string
  current_price?: number
  market_value?: number
  profit_loss?: number
  profit_rate?: number
}

export interface AddPositionRequest {
  ts_code: string
  quantity: number
  cost_price: number
  buy_date: string
  notes?: string
}

export interface PortfolioSummary {
  total_value: number
  total_cost: number
  total_profit: number
  profit_rate: number
  daily_change: number
  daily_change_rate: number
  position_count: number
}

export interface DailyAnalysis {
  analysis_date: string
  analysis_summary: string
  stock_analyses: Record<string, string>
  risk_alerts: string[]
  recommendations: string[]
}

export const portfolioApi = {
  getPositions(): Promise<Position[]> {
    return request.get('/portfolio/positions')
  },

  addPosition(data: AddPositionRequest): Promise<Position> {
    return request.post('/portfolio/positions', data)
  },

  updatePosition(id: string, data: Partial<AddPositionRequest>): Promise<Position> {
    return request.put(`/portfolio/positions/${id}`, data)
  },

  deletePosition(id: string): Promise<void> {
    return request.delete(`/portfolio/positions/${id}`)
  },

  getSummary(): Promise<PortfolioSummary> {
    return request.get('/portfolio/summary')
  },

  getProfitHistory(days?: number): Promise<{ date: string; value: number; profit: number }[]> {
    const params = days ? `?days=${days}` : ''
    return request.get(`/portfolio/profit-history${params}`)
  },

  triggerDailyAnalysis(): Promise<{ task_id: string }> {
    return request.post('/portfolio/daily-analysis')
  },

  getAnalysis(date?: string): Promise<DailyAnalysis> {
    const params = date ? `?date=${date}` : ''
    return request.get(`/portfolio/analysis${params}`)
  }
}
