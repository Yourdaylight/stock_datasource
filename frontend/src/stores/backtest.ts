import { defineStore } from 'pinia'
import { ref } from 'vue'
import { backtestApi, type Strategy, type BacktestResult, type BacktestRequest } from '@/api/backtest'

export const useBacktestStore = defineStore('backtest', () => {
  const strategies = ref<Strategy[]>([])
  const results = ref<BacktestResult[]>([])
  const currentResult = ref<BacktestResult | null>(null)
  const loading = ref(false)

  const fetchStrategies = async () => {
    try {
      strategies.value = await backtestApi.getStrategies()
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const fetchResults = async (limit?: number) => {
    try {
      results.value = await backtestApi.getResults(limit)
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const runBacktest = async (data: BacktestRequest) => {
    loading.value = true
    try {
      currentResult.value = await backtestApi.runBacktest(data)
      await fetchResults()
    } catch (e) {
      // Error handled by interceptor
    } finally {
      loading.value = false
    }
  }

  return {
    strategies,
    results,
    currentResult,
    loading,
    fetchStrategies,
    fetchResults,
    runBacktest
  }
})
