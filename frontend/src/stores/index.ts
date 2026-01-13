import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  indexApi,
  type IndexInfo,
  type ConstituentResponse,
  type QuickAnalysisResult,
  type MarketOption,
  type CategoryOption,
} from '@/api/index'

export const useIndexStore = defineStore('index', () => {
  // State
  const indices = ref<IndexInfo[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)
  
  const currentIndex = ref<IndexInfo | null>(null)
  const constituents = ref<ConstituentResponse | null>(null)
  const quickAnalysis = ref<QuickAnalysisResult | null>(null)
  const aiAnalysisResult = ref<string>('')
  const sessionId = ref<string>('')
  const historyLength = ref<number>(0)
  
  const markets = ref<MarketOption[]>([])
  const categories = ref<CategoryOption[]>([])
  
  const detailLoading = ref(false)
  const analysisLoading = ref(false)
  
  // Filters
  const selectedMarket = ref<string>('')
  const selectedCategory = ref<string>('')
  const searchKeyword = ref<string>('')

  // Computed
  const hasMore = computed(() => indices.value.length < total.value)

  // Actions
  const fetchIndices = async (resetPage = false) => {
    if (resetPage) {
      page.value = 1
    }
    
    loading.value = true
    try {
      const result = await indexApi.getIndices({
        market: selectedMarket.value || undefined,
        category: selectedCategory.value || undefined,
        keyword: searchKeyword.value || undefined,
        page: page.value,
        page_size: pageSize.value,
      })
      indices.value = result.data
      total.value = result.total
    } catch (e) {
      console.error('Failed to fetch indices:', e)
    } finally {
      loading.value = false
    }
  }

  const fetchIndexDetail = async (tsCode: string) => {
    detailLoading.value = true
    try {
      currentIndex.value = await indexApi.getIndexDetail(tsCode)
    } catch (e) {
      console.error('Failed to fetch index detail:', e)
      currentIndex.value = null
    } finally {
      detailLoading.value = false
    }
  }

  const fetchConstituents = async (tsCode: string, tradeDate?: string) => {
    detailLoading.value = true
    try {
      constituents.value = await indexApi.getConstituents(tsCode, tradeDate)
    } catch (e) {
      console.error('Failed to fetch constituents:', e)
      constituents.value = null
    } finally {
      detailLoading.value = false
    }
  }

  const fetchQuickAnalysis = async (tsCode: string) => {
    analysisLoading.value = true
    quickAnalysis.value = null
    try {
      quickAnalysis.value = await indexApi.getQuickAnalysis(tsCode)
    } catch (e) {
      console.error('Failed to fetch quick analysis:', e)
    } finally {
      analysisLoading.value = false
    }
  }

  const runAIAnalysis = async (tsCode: string, question?: string, clearHistory: boolean = false) => {
    analysisLoading.value = true
    aiAnalysisResult.value = ''
    try {
      const result = await indexApi.analyze({ 
        ts_code: tsCode, 
        question,
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

  const clearConversation = async (tsCode: string) => {
    analysisLoading.value = true
    try {
      const result = await indexApi.clearHistory(tsCode)
      aiAnalysisResult.value = result.response
      sessionId.value = result.session_id
      historyLength.value = result.history_length
    } catch (e) {
      console.error('Failed to clear history:', e)
    } finally {
      analysisLoading.value = false
    }
  }

  const fetchMarkets = async () => {
    try {
      markets.value = await indexApi.getMarkets()
    } catch (e) {
      console.error('Failed to fetch markets:', e)
    }
  }

  const fetchCategories = async () => {
    try {
      categories.value = await indexApi.getCategories()
    } catch (e) {
      console.error('Failed to fetch categories:', e)
    }
  }

  const setMarket = (market: string) => {
    selectedMarket.value = market
    fetchIndices(true)
  }

  const setCategory = (category: string) => {
    selectedCategory.value = category
    fetchIndices(true)
  }

  const setKeyword = (keyword: string) => {
    searchKeyword.value = keyword
    fetchIndices(true)
  }

  const changePage = (newPage: number) => {
    page.value = newPage
    fetchIndices()
  }

  const changePageSize = (newSize: number) => {
    pageSize.value = newSize
    page.value = 1
    fetchIndices()
  }

  const clearFilters = () => {
    selectedMarket.value = ''
    selectedCategory.value = ''
    searchKeyword.value = ''
    fetchIndices(true)
  }

  const clearAnalysis = () => {
    quickAnalysis.value = null
    aiAnalysisResult.value = ''
    sessionId.value = ''
    historyLength.value = 0
  }

  return {
    // State
    indices,
    total,
    page,
    pageSize,
    loading,
    currentIndex,
    constituents,
    quickAnalysis,
    aiAnalysisResult,
    sessionId,
    historyLength,
    markets,
    categories,
    detailLoading,
    analysisLoading,
    selectedMarket,
    selectedCategory,
    searchKeyword,
    
    // Computed
    hasMore,
    
    // Actions
    fetchIndices,
    fetchIndexDetail,
    fetchConstituents,
    fetchQuickAnalysis,
    runAIAnalysis,
    clearConversation,
    fetchMarkets,
    fetchCategories,
    setMarket,
    setCategory,
    setKeyword,
    changePage,
    changePageSize,
    clearFilters,
    clearAnalysis,
  }
})
