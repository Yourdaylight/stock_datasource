import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { 
  marketApi, 
  type KLineResponse, 
  type IndicatorResponseV2,
  type MarketOverviewResponse,
  type HotSectorsResponse,
  type TrendAnalysisResponse
} from '@/api/market'
import type { KLineData, TechnicalSignal, IndexData, MarketStats, HotSector } from '@/types/common'

export const useMarketStore = defineStore('market', () => {
  // State
  const currentCode = ref('')
  const currentName = ref('')
  const klineData = ref<KLineData[]>([])
  const indicators = ref<Record<string, number[]>>({})
  const indicatorDates = ref<string[]>([])
  const signals = ref<TechnicalSignal[]>([])
  const loading = ref(false)
  const analysis = ref('')
  const trendAnalysis = ref<TrendAnalysisResponse | null>(null)
  
  // Market Overview State
  const marketOverview = ref<MarketOverviewResponse | null>(null)
  const hotSectors = ref<HotSector[]>([])
  const overviewLoading = ref(false)

  // Computed
  const latestPrice = computed(() => {
    if (klineData.value.length === 0) return null
    return klineData.value[klineData.value.length - 1]
  })

  const priceChange = computed(() => {
    if (klineData.value.length < 2) return null
    const latest = klineData.value[klineData.value.length - 1]
    const prev = klineData.value[klineData.value.length - 2]
    const change = latest.close - prev.close
    const changePct = (change / prev.close) * 100
    return { change: change.toFixed(2), changePct: changePct.toFixed(2) }
  })

  // Actions
  const fetchKLine = async (code: string, startDate: string, endDate: string, adjust: 'qfq' | 'hfq' | 'none' = 'qfq') => {
    loading.value = true
    try {
      const response = await marketApi.getKLine({
        code,
        start_date: startDate,
        end_date: endDate,
        adjust
      })
      currentCode.value = code
      currentName.value = response.name
      klineData.value = response.data
    } catch (e) {
      console.error('Failed to fetch K-line:', e)
    } finally {
      loading.value = false
    }
  }

  const fetchIndicators = async (code: string, indicatorList: string[], period: number = 60) => {
    try {
      const response = await marketApi.getIndicatorsV2({
        code,
        indicators: indicatorList,
        period
      })
      indicators.value = response.indicators
      indicatorDates.value = response.dates
      signals.value = response.signals || []
    } catch (e) {
      console.error('Failed to fetch indicators:', e)
    }
  }

  const fetchMarketOverview = async () => {
    overviewLoading.value = true
    try {
      const [overviewRes, sectorsRes] = await Promise.all([
        marketApi.getMarketOverview(),
        marketApi.getHotSectors()
      ])
      marketOverview.value = overviewRes
      hotSectors.value = sectorsRes.sectors
    } catch (e) {
      console.error('Failed to fetch market overview:', e)
    } finally {
      overviewLoading.value = false
    }
  }

  const analyzeStock = async (code: string, period: number = 60) => {
    analysis.value = ''
    loading.value = true
    try {
      const response = await marketApi.analyzeTrend({ code, period })
      trendAnalysis.value = response
      analysis.value = response.summary
    } catch (e) {
      console.error('Failed to analyze stock:', e)
      analysis.value = '分析失败，请稍后重试'
    } finally {
      loading.value = false
    }
  }

  const aiAnalyzeStock = async (code: string, period: number = 60) => {
    analysis.value = ''
    loading.value = true
    try {
      const response = await marketApi.aiAnalyze({ code, period })
      analysis.value = response.analysis
      if (response.signals) {
        signals.value = response.signals
      }
    } catch (e) {
      console.error('Failed to AI analyze stock:', e)
      analysis.value = 'AI分析失败，请稍后重试'
    } finally {
      loading.value = false
    }
  }

  const streamAnalyzeStock = (code: string, period: number = 60) => {
    analysis.value = ''
    loading.value = true
    
    const eventSource = marketApi.analyzeStream(code, period)
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'status') {
          analysis.value = data.message
        } else if (data.type === 'result') {
          trendAnalysis.value = data.data
          analysis.value = data.data.summary
          loading.value = false
        } else if (data.type === 'done') {
          eventSource.close()
          loading.value = false
        } else if (data.type === 'error') {
          analysis.value = `分析失败: ${data.message}`
          eventSource.close()
          loading.value = false
        }
      } catch (e) {
        console.error('Failed to parse SSE data:', e)
      }
    }
    
    eventSource.onerror = () => {
      analysis.value = '连接断开，请重试'
      eventSource.close()
      loading.value = false
    }
    
    return eventSource
  }

  const clearAnalysis = () => {
    analysis.value = ''
    trendAnalysis.value = null
  }

  return {
    // State
    currentCode,
    currentName,
    klineData,
    indicators,
    indicatorDates,
    signals,
    loading,
    analysis,
    trendAnalysis,
    marketOverview,
    hotSectors,
    overviewLoading,
    // Computed
    latestPrice,
    priceChange,
    // Actions
    fetchKLine,
    fetchIndicators,
    fetchMarketOverview,
    analyzeStock,
    aiAnalyzeStock,
    streamAnalyzeStock,
    clearAnalysis
  }
})
