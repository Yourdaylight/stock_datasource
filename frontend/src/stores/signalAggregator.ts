import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  signalAggregatorApi,
  type StockSignalSummary,
  type SignalTimelineResponse,
  type SignalWeightsConfig,
} from '@/api/signalAggregator'

export const useSignalAggregatorStore = defineStore('signalAggregator', () => {
  const stocks = ref<StockSignalSummary[]>([])
  const currentStock = ref<StockSignalSummary | null>(null)
  const timeline = ref<SignalTimelineResponse | null>(null)
  const loading = ref(false)
  const tradeDate = ref('')

  const fetchAggregate = async (tsCodes: string[], signalDate?: string) => {
    loading.value = true
    try {
      const res = await signalAggregatorApi.aggregate(tsCodes, signalDate)
      stocks.value = res.stocks
      tradeDate.value = res.trade_date
    } catch (e) {
      // Error handled by interceptor
    } finally {
      loading.value = false
    }
  }

  const fetchSingleStock = async (tsCode: string, signalDate?: string) => {
    loading.value = true
    try {
      currentStock.value = await signalAggregatorApi.aggregateSingle(tsCode, signalDate)
    } catch (e) {
      // Error handled by interceptor
    } finally {
      loading.value = false
    }
  }

  const fetchTimeline = async (tsCode: string, days: number = 30) => {
    loading.value = true
    try {
      timeline.value = await signalAggregatorApi.getTimeline(tsCode, days)
    } catch (e) {
      // Error handled by interceptor
    } finally {
      loading.value = false
    }
  }

  const updateWeights = async (config: SignalWeightsConfig) => {
    try {
      await signalAggregatorApi.updateWeights(config)
    } catch (e) {
      // Error handled by interceptor
    }
  }

  return {
    stocks,
    currentStock,
    timeline,
    loading,
    tradeDate,
    fetchAggregate,
    fetchSingleStock,
    fetchTimeline,
    updateWeights,
  }
})
