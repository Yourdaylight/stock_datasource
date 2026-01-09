import { defineStore } from 'pinia'
import { ref } from 'vue'
import { marketApi, type KLineResponse, type IndicatorResponse } from '@/api/market'
import type { KLineData, IndicatorData } from '@/types/common'

export const useMarketStore = defineStore('market', () => {
  const currentCode = ref('')
  const klineData = ref<KLineData[]>([])
  const indicators = ref<IndicatorData[]>([])
  const loading = ref(false)
  const analysis = ref('')

  const fetchKLine = async (code: string, startDate: string, endDate: string) => {
    loading.value = true
    try {
      const response = await marketApi.getKLine({
        code,
        start_date: startDate,
        end_date: endDate
      })
      currentCode.value = code
      klineData.value = response.data
    } catch (e) {
      // Error handled by interceptor
    } finally {
      loading.value = false
    }
  }

  const fetchIndicators = async (code: string, indicatorList: string[]) => {
    try {
      const response = await marketApi.getIndicators({
        code,
        indicators: indicatorList
      })
      indicators.value = response.indicators
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const analyzeStock = async (code: string) => {
    analysis.value = ''
    loading.value = true
    try {
      // For now, use a simple API call instead of SSE
      analysis.value = '正在分析中...'
      // TODO: Implement SSE streaming
    } finally {
      loading.value = false
    }
  }

  return {
    currentCode,
    klineData,
    indicators,
    loading,
    analysis,
    fetchKLine,
    fetchIndicators,
    analyzeStock
  }
})
