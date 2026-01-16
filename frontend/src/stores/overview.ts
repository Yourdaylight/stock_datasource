import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  overviewApi,
  type DailyOverviewResponse,
  type QuickAnalysisResponse,
  type IndexStatus,
  type HotEtf,
} from '@/api/overview'

export const useOverviewStore = defineStore('overview', () => {
  // State
  const dailyOverview = ref<DailyOverviewResponse | null>(null)
  const quickAnalysis = ref<QuickAnalysisResponse | null>(null)
  const majorIndices = ref<IndexStatus[]>([])
  const hotEtfsByAmount = ref<HotEtf[]>([])
  const hotEtfsByChange = ref<HotEtf[]>([])
  
  const aiAnalysisResult = ref<string>('')
  const sessionId = ref<string>('')
  const historyLength = ref<number>(0)
  
  const loading = ref(false)
  const analysisLoading = ref(false)
  const currentDate = ref<string>('')

  // Actions
  const fetchDailyOverview = async (date?: string) => {
    loading.value = true
    try {
      const result = await overviewApi.getDailyOverview(date)
      dailyOverview.value = result
      majorIndices.value = result.major_indices
      hotEtfsByAmount.value = result.hot_etfs_by_amount
      hotEtfsByChange.value = result.hot_etfs_by_change
      currentDate.value = result.trade_date
    } catch (e) {
      console.error('Failed to fetch daily overview:', e)
    } finally {
      loading.value = false
    }
  }

  const fetchQuickAnalysis = async (date?: string) => {
    analysisLoading.value = true
    quickAnalysis.value = null
    try {
      quickAnalysis.value = await overviewApi.getQuickAnalysis(date)
      currentDate.value = quickAnalysis.value.trade_date
    } catch (e) {
      console.error('Failed to fetch quick analysis:', e)
    } finally {
      analysisLoading.value = false
    }
  }

  const fetchHotEtfs = async (sortBy: 'amount' | 'pct_chg' = 'amount', limit: number = 10) => {
    try {
      const result = await overviewApi.getHotEtfs({ sort_by: sortBy, limit })
      if (sortBy === 'amount') {
        hotEtfsByAmount.value = result.data
      } else {
        hotEtfsByChange.value = result.data
      }
    } catch (e) {
      console.error('Failed to fetch hot ETFs:', e)
    }
  }

  const runAIAnalysis = async (question: string, clearHistory: boolean = false) => {
    analysisLoading.value = true
    aiAnalysisResult.value = ''
    try {
      const result = await overviewApi.analyze({ 
        question,
        date: currentDate.value || undefined,
        clear_history: clearHistory
      })
      aiAnalysisResult.value = result.response
      sessionId.value = result.session_id
      historyLength.value = result.history_length
    } catch (e) {
      console.error('Failed to run AI analysis:', e)
      aiAnalysisResult.value = '分析失败，请稍后重试'
    } finally {
      analysisLoading.value = false
    }
  }

  const clearConversation = async () => {
    analysisLoading.value = true
    try {
      const result = await overviewApi.clearHistory('default', currentDate.value)
      aiAnalysisResult.value = result.response
      sessionId.value = result.session_id
      historyLength.value = result.history_length
    } catch (e) {
      console.error('Failed to clear history:', e)
    } finally {
      analysisLoading.value = false
    }
  }

  const clearAnalysis = () => {
    quickAnalysis.value = null
    aiAnalysisResult.value = ''
    sessionId.value = ''
    historyLength.value = 0
  }

  return {
    // State
    dailyOverview,
    quickAnalysis,
    majorIndices,
    hotEtfsByAmount,
    hotEtfsByChange,
    aiAnalysisResult,
    sessionId,
    historyLength,
    loading,
    analysisLoading,
    currentDate,
    
    // Actions
    fetchDailyOverview,
    fetchQuickAnalysis,
    fetchHotEtfs,
    runAIAnalysis,
    clearConversation,
    clearAnalysis,
  }
})
