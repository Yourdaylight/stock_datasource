import request from '@/utils/request'
import type { 
  Position, 
  PortfolioSummary, 
  CreatePositionRequest,
  UpdatePositionRequest,
  AnalysisReport,
  AlertCreateRequest
} from '@/types/portfolio'

export const portfolioApi = {
  // Position management
  getPositions(params?: { include_inactive?: boolean }) {
    return request.get<Position[]>('/portfolio/positions', { params })
  },

  createPosition(data: CreatePositionRequest) {
    return request.post<Position>('/portfolio/positions', data)
  },

  updatePosition(id: string, data: UpdatePositionRequest) {
    return request.put<Position>(`/portfolio/positions/${id}`, data)
  },

  deletePosition(id: string) {
    return request.delete(`/portfolio/positions/${id}`)
  },

  // Portfolio summary
  getSummary() {
    return request.get<PortfolioSummary>('/portfolio/summary')
  },

  getProfitHistory(days: number = 30) {
    return request.get('/portfolio/profit-history', { 
      params: { days } 
    })
  },

  // Analysis
  triggerDailyAnalysis(analysisDate?: string) {
    return request.post('/portfolio/daily-analysis', {
      analysis_date: analysisDate
    })
  },

  getAnalysisReport(reportDate: string) {
    return request.get<AnalysisReport>(`/portfolio/analysis/${reportDate}`)
  },

  getAnalysisHistory(days: number = 30) {
    return request.get<AnalysisReport[]>('/portfolio/analysis', {
      params: { days }
    })
  },

  // Alerts
  createAlert(data: AlertCreateRequest) {
    return request.post('/portfolio/alerts', data)
  },

  checkAlerts() {
    return request.get('/portfolio/alerts/check')
  },

  // Batch operations
  batchUpdatePrices() {
    return request.post('/portfolio/batch/update-prices')
  }
}