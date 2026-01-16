import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  etfApi,
  type EtfInfo,
  type EtfQuoteItem,
  type ExchangeOption,
  type EtfTypeOption,
  type QuickAnalysisResult,
} from '@/api/etf'

export const useEtfStore = defineStore('etf', () => {
  // State
  const etfs = ref<EtfQuoteItem[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)
  
  const currentEtf = ref<EtfInfo | null>(null)
  const quickAnalysis = ref<QuickAnalysisResult | null>(null)
  const aiAnalysisResult = ref<string>('')
  const sessionId = ref<string>('')
  const historyLength = ref<number>(0)
  
  const exchanges = ref<ExchangeOption[]>([])
  const types = ref<EtfTypeOption[]>([])
  const investTypes = ref<EtfTypeOption[]>([])
  
  const detailLoading = ref(false)
  const analysisLoading = ref(false)
  
  // Filters
  const selectedExchange = ref<string>('')
  const selectedType = ref<string>('')
  const selectedInvestType = ref<string>('')
  const selectedStatus = ref<string>('')
  const searchKeyword = ref<string>('')

  // Computed
  const hasMore = computed(() => etfs.value.length < total.value)

  // Actions
  const fetchEtfs = async (resetPage = false) => {
    if (resetPage) {
      page.value = 1
    }
    
    loading.value = true
    try {
      const result = await etfApi.getEtfs({
        market: selectedExchange.value || undefined,
        fund_type: selectedType.value || undefined,
        invest_type: selectedInvestType.value || undefined,
        status: selectedStatus.value || undefined,
        keyword: searchKeyword.value || undefined,
        page: page.value,
        page_size: pageSize.value,
      })
      etfs.value = result.items
      total.value = result.total
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
    currentEtf,
    quickAnalysis,
    aiAnalysisResult,
    sessionId,
    historyLength,
    exchanges,
    types,
    investTypes,
    detailLoading,
    analysisLoading,
    selectedExchange,
    selectedType,
    selectedInvestType,
    selectedStatus,
    searchKeyword,
    
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
    setExchange,
    setType,
    setInvestType,
    setStatus,
    setKeyword,
    changePage,
    changePageSize,
    clearFilters,
    clearAnalysis,
  }
})
