import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  indexApi,
  type IndexInfo,
  type ConstituentResponse,
  type QuickAnalysisResult,
  type MarketOption,
  type CategoryOption,
  type PublisherOption,
} from '@/api/index'

export const useIndexStore = defineStore('index', () => {
  // State
  const indices = ref<IndexInfo[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)
  const tradeDate = ref<string>('')
  
  const currentIndex = ref<IndexInfo | null>(null)
  const constituents = ref<ConstituentResponse | null>(null)
  const quickAnalysis = ref<QuickAnalysisResult | null>(null)
  const aiAnalysisResult = ref<string>('')
  const sessionId = ref<string>('')
  const historyLength = ref<number>(0)
  
  const markets = ref<MarketOption[]>([])
  const categories = ref<CategoryOption[]>([])
  const publishers = ref<PublisherOption[]>([])
  const tradeDates = ref<string[]>([])
  
  const detailLoading = ref(false)
  const analysisLoading = ref(false)
  
  // Filters
  const selectedMarket = ref<string>('')
  const selectedCategory = ref<string>('')
  const searchKeyword = ref<string>('')
  const selectedDate = ref<string>('')
  const selectedPublisher = ref<string>('')
  const selectedPctChgRange = ref<string>('')

  // Computed
  const hasMore = computed(() => indices.value.length < total.value)

  // Helper to parse pct_chg range
  const parsePctChgRange = (range: string): { pct_chg_min?: number; pct_chg_max?: number } => {
    if (!range) return {}
    if (range === 'up') return { pct_chg_min: 0 }
    if (range === 'down') return { pct_chg_max: 0 }
    if (range === 'up1+') return { pct_chg_min: 1 }
    if (range === 'up2+') return { pct_chg_min: 2 }
    if (range === 'down1+') return { pct_chg_max: -1 }
    if (range === 'down2+') return { pct_chg_max: -2 }
    return {}
  }

  // Actions
  const fetchIndices = async (resetPage = false) => {
    if (resetPage) {
      page.value = 1
    }
    
    loading.value = true
    try {
      const pctChgParams = parsePctChgRange(selectedPctChgRange.value)
      
      const result = await indexApi.getIndices({
        market: selectedMarket.value || undefined,
        category: selectedCategory.value || undefined,
        keyword: searchKeyword.value || undefined,
        trade_date: selectedDate.value || undefined,
        publisher: selectedPublisher.value || undefined,
        ...pctChgParams,
        page: page.value,
        page_size: pageSize.value,
      })
      indices.value = result.data
      total.value = result.total
      tradeDate.value = result.trade_date || ''
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

  const fetchPublishers = async () => {
    try {
      publishers.value = await indexApi.getPublishers()
    } catch (e) {
      console.error('Failed to fetch publishers:', e)
    }
  }

  const fetchTradeDates = async () => {
    try {
      tradeDates.value = await indexApi.getTradeDates()
      // Set default date if not set
      if (!selectedDate.value && tradeDates.value.length > 0) {
        selectedDate.value = tradeDates.value[0]
      }
    } catch (e) {
      console.error('Failed to fetch trade dates:', e)
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

  const setDate = (date: string) => {
    selectedDate.value = date
    fetchIndices(true)
  }

  const setPublisher = (publisher: string) => {
    selectedPublisher.value = publisher
    fetchIndices(true)
  }

  const setPctChgRange = (range: string) => {
    selectedPctChgRange.value = range
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
    selectedDate.value = tradeDates.value.length > 0 ? tradeDates.value[0] : ''
    selectedPublisher.value = ''
    selectedPctChgRange.value = ''
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
    tradeDate,
    currentIndex,
    constituents,
    quickAnalysis,
    aiAnalysisResult,
    sessionId,
    historyLength,
    markets,
    categories,
    publishers,
    tradeDates,
    detailLoading,
    analysisLoading,
    selectedMarket,
    selectedCategory,
    searchKeyword,
    selectedDate,
    selectedPublisher,
    selectedPctChgRange,
    
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
    fetchPublishers,
    fetchTradeDates,
    setMarket,
    setCategory,
    setKeyword,
    setDate,
    setPublisher,
    setPctChgRange,
    changePage,
    changePageSize,
    clearFilters,
    clearAnalysis,
  }
})
