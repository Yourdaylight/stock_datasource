import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  etfApi,
  type EtfInfo,
  type EtfQuoteItem,
  type ExchangeOption,
  type EtfTypeOption,
  type ManagerOption,
  type TrackingIndexOption,
  type QuickAnalysisResult,
} from '@/api/etf'

export const useEtfStore = defineStore('etf', () => {
  // State
  const etfs = ref<EtfQuoteItem[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)
  const tradeDate = ref<string>('')
  
  const currentEtf = ref<EtfInfo | null>(null)
  const quickAnalysis = ref<QuickAnalysisResult | null>(null)
  const aiAnalysisResult = ref<string>('')
  const sessionId = ref<string>('')
  const historyLength = ref<number>(0)
  
  const exchanges = ref<ExchangeOption[]>([])
  const types = ref<EtfTypeOption[]>([])
  const investTypes = ref<EtfTypeOption[]>([])
  const managers = ref<ManagerOption[]>([])
  const trackingIndices = ref<TrackingIndexOption[]>([])
  const tradeDates = ref<string[]>([])
  
  const detailLoading = ref(false)
  const analysisLoading = ref(false)
  
  // Filters
  const selectedExchange = ref<string>('')
  const selectedType = ref<string>('')
  const selectedInvestType = ref<string>('')
  const selectedStatus = ref<string>('')
  const searchKeyword = ref<string>('')
  const selectedDate = ref<string>('')
  const selectedManager = ref<string>('')
  const selectedTrackingIndex = ref<string>('')
  const selectedFeeRange = ref<string>('')
  const selectedAmountRange = ref<string>('')
  const selectedPctChgRange = ref<string>('')

  // Computed
  const hasMore = computed(() => etfs.value.length < total.value)

  // Helper to parse fee range
  const parseFeeRange = (range: string): { fee_min?: number; fee_max?: number } => {
    if (!range) return {}
    if (range === '0-0.2') return { fee_min: 0, fee_max: 0.2 }
    if (range === '0.2-0.5') return { fee_min: 0.2, fee_max: 0.5 }
    if (range === '0.5+') return { fee_min: 0.5 }
    return {}
  }

  // Helper to parse amount range (in 万元)
  const parseAmountRange = (range: string): { amount_min?: number } => {
    if (!range) return {}
    if (range === '1000+') return { amount_min: 1000 }
    if (range === '5000+') return { amount_min: 5000 }
    if (range === '1e+') return { amount_min: 10000 }
    return {}
  }

  // Helper to parse pct_chg range
  const parsePctChgRange = (range: string): { pct_chg_min?: number; pct_chg_max?: number } => {
    if (!range) return {}
    if (range === 'up') return { pct_chg_min: 0 }
    if (range === 'down') return { pct_chg_max: 0 }
    if (range === 'up2+') return { pct_chg_min: 2 }
    if (range === 'up5+') return { pct_chg_min: 5 }
    if (range === 'down2+') return { pct_chg_max: -2 }
    if (range === 'down5+') return { pct_chg_max: -5 }
    return {}
  }

  // Actions
  const fetchEtfs = async (resetPage = false) => {
    if (resetPage) {
      page.value = 1
    }
    
    loading.value = true
    try {
      const feeParams = parseFeeRange(selectedFeeRange.value)
      const amountParams = parseAmountRange(selectedAmountRange.value)
      const pctChgParams = parsePctChgRange(selectedPctChgRange.value)
      
      const result = await etfApi.getEtfs({
        market: selectedExchange.value || undefined,
        fund_type: selectedType.value || undefined,
        invest_type: selectedInvestType.value || undefined,
        status: selectedStatus.value || undefined,
        keyword: searchKeyword.value || undefined,
        trade_date: selectedDate.value || undefined,
        manager: selectedManager.value || undefined,
        tracking_index: selectedTrackingIndex.value || undefined,
        ...feeParams,
        ...amountParams,
        ...pctChgParams,
        page: page.value,
        page_size: pageSize.value,
      })
      etfs.value = result.items
      total.value = result.total
      tradeDate.value = result.trade_date || ''
    } catch (e) {
      console.error('Failed to fetch ETFs:', e)
    } finally {
      loading.value = false
    }
  }

  const fetchEtfDetail = async (tsCode: string) => {
    detailLoading.value = true
    try {
      currentEtf.value = await etfApi.getEtfDetail(tsCode)
    } catch (e) {
      console.error('Failed to fetch ETF detail:', e)
      currentEtf.value = null
    } finally {
      detailLoading.value = false
    }
  }

  const fetchQuickAnalysis = async (tsCode: string) => {
    analysisLoading.value = true
    quickAnalysis.value = null
    try {
      quickAnalysis.value = await etfApi.getQuickAnalysis(tsCode)
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
      const result = await etfApi.analyze({ 
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
      const result = await etfApi.clearHistory(tsCode)
      aiAnalysisResult.value = result.response
      sessionId.value = result.session_id
      historyLength.value = result.history_length
    } catch (e) {
      console.error('Failed to clear history:', e)
    } finally {
      analysisLoading.value = false
    }
  }

  const fetchExchanges = async () => {
    try {
      exchanges.value = await etfApi.getExchanges()
    } catch (e) {
      console.error('Failed to fetch exchanges:', e)
    }
  }

  const fetchTypes = async () => {
    try {
      types.value = await etfApi.getTypes()
    } catch (e) {
      console.error('Failed to fetch types:', e)
    }
  }

  const fetchInvestTypes = async () => {
    try {
      investTypes.value = await etfApi.getInvestTypes()
    } catch (e) {
      console.error('Failed to fetch invest types:', e)
    }
  }

  const fetchManagers = async () => {
    try {
      managers.value = await etfApi.getManagers()
    } catch (e) {
      console.error('Failed to fetch managers:', e)
    }
  }

  const fetchTrackingIndices = async () => {
    try {
      trackingIndices.value = await etfApi.getTrackingIndices()
    } catch (e) {
      console.error('Failed to fetch tracking indices:', e)
    }
  }

  const fetchTradeDates = async () => {
    try {
      tradeDates.value = await etfApi.getTradeDates()
      // Set default date if not set
      if (!selectedDate.value && tradeDates.value.length > 0) {
        selectedDate.value = tradeDates.value[0]
      }
    } catch (e) {
      console.error('Failed to fetch trade dates:', e)
    }
  }

  const setExchange = (exchange: string) => {
    selectedExchange.value = exchange
    fetchEtfs(true)
  }

  const setType = (type: string) => {
    selectedType.value = type
    fetchEtfs(true)
  }

  const setInvestType = (investType: string) => {
    selectedInvestType.value = investType
    fetchEtfs(true)
  }

  const setStatus = (status: string) => {
    selectedStatus.value = status
    fetchEtfs(true)
  }

  const setKeyword = (keyword: string) => {
    searchKeyword.value = keyword
    fetchEtfs(true)
  }

  const setDate = (date: string) => {
    selectedDate.value = date
    fetchEtfs(true)
  }

  const setManager = (manager: string) => {
    selectedManager.value = manager
    fetchEtfs(true)
  }

  const setTrackingIndex = (index: string) => {
    selectedTrackingIndex.value = index
    fetchEtfs(true)
  }

  const setFeeRange = (range: string) => {
    selectedFeeRange.value = range
    fetchEtfs(true)
  }

  const setAmountRange = (range: string) => {
    selectedAmountRange.value = range
    fetchEtfs(true)
  }

  const setPctChgRange = (range: string) => {
    selectedPctChgRange.value = range
    fetchEtfs(true)
  }

  const changePage = (newPage: number) => {
    page.value = newPage
    fetchEtfs()
  }

  const changePageSize = (newSize: number) => {
    pageSize.value = newSize
    page.value = 1
    fetchEtfs()
  }

  const clearFilters = () => {
    selectedExchange.value = ''
    selectedType.value = ''
    selectedInvestType.value = ''
    selectedStatus.value = ''
    searchKeyword.value = ''
    selectedDate.value = tradeDates.value.length > 0 ? tradeDates.value[0] : ''
    selectedManager.value = ''
    selectedTrackingIndex.value = ''
    selectedFeeRange.value = ''
    selectedAmountRange.value = ''
    selectedPctChgRange.value = ''
    fetchEtfs(true)
  }

  const clearAnalysis = () => {
    quickAnalysis.value = null
    aiAnalysisResult.value = ''
    sessionId.value = ''
    historyLength.value = 0
  }

  return {
    // State
    etfs,
    total,
    page,
    pageSize,
    loading,
    tradeDate,
    currentEtf,
    quickAnalysis,
    aiAnalysisResult,
    sessionId,
    historyLength,
    exchanges,
    types,
    investTypes,
    managers,
    trackingIndices,
    tradeDates,
    detailLoading,
    analysisLoading,
    selectedExchange,
    selectedType,
    selectedInvestType,
    selectedStatus,
    searchKeyword,
    selectedDate,
    selectedManager,
    selectedTrackingIndex,
    selectedFeeRange,
    selectedAmountRange,
    selectedPctChgRange,
    
    // Computed
    hasMore,
    
    // Actions
    fetchEtfs,
    fetchEtfDetail,
    fetchQuickAnalysis,
    runAIAnalysis,
    clearConversation,
    fetchExchanges,
    fetchTypes,
    fetchInvestTypes,
    fetchManagers,
    fetchTrackingIndices,
    fetchTradeDates,
    setExchange,
    setType,
    setInvestType,
    setStatus,
    setKeyword,
    setDate,
    setManager,
    setTrackingIndex,
    setFeeRange,
    setAmountRange,
    setPctChgRange,
    changePage,
    changePageSize,
    clearFilters,
    clearAnalysis,
  }
})
