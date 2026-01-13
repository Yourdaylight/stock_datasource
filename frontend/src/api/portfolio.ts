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
    return request.get<Position[]>('/api/portfolio/positions', { params })
  },

  createPosition(data: CreatePositionRequest) {
    return request.post<Position>('/api/portfolio/positions', data)
  },

  updatePosition(id: string, data: UpdatePositionRequest) {
    return request.put<Position>(`/api/portfolio/positions/${id}`, data)
  },

  deletePosition(id: string) {
    return request.delete(`/api/portfolio/positions/${id}`)
  },

  // Portfolio summary
  getSummary() {
    return request.get<PortfolioSummary>('/api/portfolio/summary')
  },

  getProfitHistory(days: number = 30) {
    return request.get('/api/portfolio/profit-history', { 
      params: { days } 
    })
  },

  // Analysis
  triggerDailyAnalysis(analysisDate?: string) {
    return request.post('/api/portfolio/daily-analysis', {
      analysis_date: analysisDate
    })
  },

  getAnalysisReport(reportDate?: string) {
    return request.get<AnalysisReport>('/api/portfolio/analysis', {
      params: reportDate ? { date: reportDate } : {}
    })
  },

  getAnalysisHistory(days: number = 30) {
    return request.get<AnalysisReport[]>('/api/portfolio/analysis', {
      params: { days }
    })
  },

  // Alerts
  createAlert(data: AlertCreateRequest) {
    return request.post('/api/portfolio/alerts', data)
  },

  checkAlerts() {
    return request.get('/api/portfolio/alerts/check')
  },

  // Batch operations
  batchUpdatePrices() {
    return request.post('/api/portfolio/batch/update-prices')
  }
}