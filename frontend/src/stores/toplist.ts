import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { toplistApi, type TopListItem, type TopInstItem, type TopListAnalysis, type AnomalyAlert, type PortfolioTopListAnalysis } from '@/api/toplist'

export const useTopListStore = defineStore('toplist', () => {
  // State
  const topListData = ref<TopListItem[]>([])
  const topInstData = ref<TopInstItem[]>([])
  const currentAnalysis = ref<TopListAnalysis | null>(null)
  const anomalyAlerts = ref<AnomalyAlert[]>([])
  const portfolioAnalysis = ref<PortfolioTopListAnalysis | null>(null)
  const marketStats = ref<any>(null)
  
  const loading = ref(false)
  const error = ref<string | null>(null)
  
  // Pagination
  const currentPage = ref(1)
  const pageSize = ref(50)
  const total = ref(0)
  
  // Filters
  const selectedDate = ref<string>(new Date().toISOString().split('T')[0])
  const selectedStock = ref<string>('')
  const selectedSeverity = ref<string>('')
  const analysisTimeRange = ref<number>(10)

  // Computed
  const hasData = computed(() => topListData.value.length > 0)
  const totalPages = computed(() => Math.ceil(total.value / pageSize.value))
  const hasAlerts = computed(() => anomalyAlerts.value.length > 0)
  const highRiskAlerts = computed(() => 
    anomalyAlerts.value.filter(alert => alert.severity === 'high')
  )

  // Actions
  const setLoading = (state: boolean) => {
    loading.value = state
  }

  const setError = (message: string | null) => {
    error.value = message
  }

  const clearError = () => {
    error.value = null
  }

  // Fetch top list data by date
  const fetchTopListByDate = async (date?: string, page?: number) => {
    try {
      setLoading(true)
      clearError()
      
      const targetDate = date || selectedDate.value
      const targetPage = page || currentPage.value
      
      const response = await toplistApi.getTopListByDate(targetDate, targetPage, pageSize.value)
      
      topListData.value = response.data
      total.value = response.total
      currentPage.value = response.page
      
      if (date) selectedDate.value = date
      if (page) currentPage.value = page
      
    } catch (err: any) {
      setError(err.message || '获取龙虎榜数据失败')
      console.error('Failed to fetch top list:', err)
    } finally {
      setLoading(false)
    }
  }

  // Fetch stock's top list history
  const fetchStockHistory = async (tsCode: string, days?: number) => {
    try {
      setLoading(true)
      clearError()
      
      const targetDays = days || analysisTimeRange.value
      const response = await toplistApi.getStockTopListHistory(tsCode, targetDays, 1, 100)
      
      topListData.value = response.data
      selectedStock.value = tsCode
      
    } catch (err: any) {
      setError(err.message || '获取股票龙虎榜历史失败')
      console.error('Failed to fetch stock history:', err)
    } finally {
      setLoading(false)
    }
  }

  // Fetch institutional data
  const fetchTopInst = async (date?: string, tsCode?: string) => {
    try {
      setLoading(true)
      clearError()
      
      const response = await toplistApi.getTopInst(
        date || selectedDate.value,
        tsCode || selectedStock.value,
        currentPage.value,
        pageSize.value
      )
      
      topInstData.value = response.data
      total.value = response.total
      
    } catch (err: any) {
      setError(err.message || '获取机构席位数据失败')
      console.error('Failed to fetch institutional data:', err)
    } finally {
      setLoading(false)
    }
  }

  // Fetch stock analysis
  const fetchStockAnalysis = async (tsCode: string, days?: number) => {
    try {
      setLoading(true)
      clearError()
      
      const targetDays = days || analysisTimeRange.value
      const analysis = await toplistApi.getStockAnalysis(tsCode, targetDays)
      
      currentAnalysis.value = analysis
      
    } catch (err: any) {
      setError(err.message || '获取股票分析失败')
      console.error('Failed to fetch stock analysis:', err)
    } finally {
      setLoading(false)
    }
  }

  // Fetch anomaly alerts
  const fetchAnomalyAlerts = async (date?: string, severity?: string) => {
    try {
      setLoading(true)
      clearError()
      
      const response = await toplistApi.getAnomalyAlerts(
        date || selectedDate.value,
        severity || selectedSeverity.value,
        1,
        50
      )
      
      anomalyAlerts.value = response.data
      
    } catch (err: any) {
      setError(err.message || '获取异动预警失败')
      console.error('Failed to fetch anomaly alerts:', err)
    } finally {
      setLoading(false)
    }
  }

  // Portfolio analysis
  const analyzePortfolio = async (userId?: string) => {
    try {
      setLoading(true)
      clearError()
      
      const response = await toplistApi.analyzePortfolioTopList(userId)
      
      if (response.success) {
        portfolioAnalysis.value = response.data
      } else {
        throw new Error(response.message || '分析失败')
      }
      
    } catch (err: any) {
      setError(err.message || '投资组合龙虎榜分析失败')
      console.error('Failed to analyze portfolio:', err)
    } finally {
      setLoading(false)
    }
  }

  // Check position status
  const checkPositionStatus = async (userId?: string) => {
    try {
      setLoading(true)
      clearError()
      
      const response = await toplistApi.checkPositionTopListStatus(userId)
      
      if (response.success) {
        return response.data
      } else {
        throw new Error(response.message || '检查失败')
      }
      
    } catch (err: any) {
      setError(err.message || '检查持仓龙虎榜状态失败')
      console.error('Failed to check position status:', err)
      return null
    } finally {
      setLoading(false)
    }
  }

  // Analyze capital flow
  const analyzeCapitalFlow = async (userId?: string, days?: number) => {
    try {
      setLoading(true)
      clearError()
      
      const response = await toplistApi.analyzePositionCapitalFlow(
        userId,
        days || analysisTimeRange.value
      )
      
      if (response.success) {
        return response.data
      } else {
        throw new Error(response.message || '分析失败')
      }
      
    } catch (err: any) {
      setError(err.message || '资金流向分析失败')
      console.error('Failed to analyze capital flow:', err)
      return null
    } finally {
      setLoading(false)
    }
  }

  // Fetch market statistics
  const fetchMarketStats = async (date?: string) => {
    try {
      setLoading(true)
      clearError()
      
      const stats = await toplistApi.getMarketStats(date || selectedDate.value)
      marketStats.value = stats
      
    } catch (err: any) {
      setError(err.message || '获取市场统计失败')
      console.error('Failed to fetch market stats:', err)
    } finally {
      setLoading(false)
    }
  }

  // Search top list
  const searchTopList = async (params: {
    keyword?: string
    start_date?: string
    end_date?: string
    min_pct_chg?: number
    max_pct_chg?: number
    reason?: string
  }) => {
    try {
      setLoading(true)
      clearError()
      
      const response = await toplistApi.searchTopList({
        ...params,
        page: currentPage.value,
        page_size: pageSize.value
      })
      
      topListData.value = response.data
      total.value = response.total
      
    } catch (err: any) {
      setError(err.message || '搜索龙虎榜失败')
      console.error('Failed to search top list:', err)
    } finally {
      setLoading(false)
    }
  }

  // Pagination
  const setPage = (page: number) => {
    currentPage.value = page
  }

  const setPageSize = (size: number) => {
    pageSize.value = size
    currentPage.value = 1 // Reset to first page
  }

  // Filters
  const setSelectedDate = (date: string) => {
    selectedDate.value = date
  }

  const setSelectedStock = (tsCode: string) => {
    selectedStock.value = tsCode
  }

  const setSelectedSeverity = (severity: string) => {
    selectedSeverity.value = severity
  }

  const setAnalysisTimeRange = (days: number) => {
    analysisTimeRange.value = days
  }

  // Reset state
  const reset = () => {
    topListData.value = []
    topInstData.value = []
    currentAnalysis.value = null
    anomalyAlerts.value = []
    portfolioAnalysis.value = null
    marketStats.value = null
    error.value = null
    currentPage.value = 1
    total.value = 0
  }

  return {
    // State
    topListData,
    topInstData,
    currentAnalysis,
    anomalyAlerts,
    portfolioAnalysis,
    marketStats,
    loading,
    error,
    currentPage,
    pageSize,
    total,
    selectedDate,
    selectedStock,
    selectedSeverity,
    analysisTimeRange,
    
    // Computed
    hasData,
    totalPages,
    hasAlerts,
    highRiskAlerts,
    
    // Actions
    setLoading,
    setError,
    clearError,
    fetchTopListByDate,
    fetchStockHistory,
    fetchTopInst,
    fetchStockAnalysis,
    fetchAnomalyAlerts,
    analyzePortfolio,
    checkPositionStatus,
    analyzeCapitalFlow,
    fetchMarketStats,
    searchTopList,
    setPage,
    setPageSize,
    setSelectedDate,
    setSelectedStock,
    setSelectedSeverity,
    setAnalysisTimeRange,
    reset
  }
})