import { defineStore } from 'pinia'
import { ref } from 'vue'
import { portfolioApi, type Position, type PortfolioSummary, type DailyAnalysis, type AddPositionRequest } from '@/api/portfolio'

export const usePortfolioStore = defineStore('portfolio', () => {
  const positions = ref<Position[]>([])
  const summary = ref<PortfolioSummary | null>(null)
  const analysis = ref<DailyAnalysis | null>(null)
  const loading = ref(false)

  const fetchPositions = async () => {
    loading.value = true
    try {
      positions.value = await portfolioApi.getPositions()
    } catch (e) {
      // Error handled by interceptor
    } finally {
      loading.value = false
    }
  }

  const addPosition = async (data: AddPositionRequest) => {
    loading.value = true
    try {
      await portfolioApi.addPosition(data)
      await fetchPositions()
      await fetchSummary()
    } finally {
      loading.value = false
    }
  }

  const deletePosition = async (id: string) => {
    try {
      await portfolioApi.deletePosition(id)
      positions.value = positions.value.filter(p => p.id !== id)
      await fetchSummary()
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const fetchSummary = async () => {
    try {
      summary.value = await portfolioApi.getSummary()
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const fetchAnalysis = async (date?: string) => {
    try {
      analysis.value = await portfolioApi.getAnalysis(date)
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const triggerDailyAnalysis = async () => {
    loading.value = true
    try {
      await portfolioApi.triggerDailyAnalysis()
      await fetchAnalysis()
    } catch (e) {
      // Error handled by interceptor
    } finally {
      loading.value = false
    }
  }

  return {
    positions,
    summary,
    analysis,
    loading,
    fetchPositions,
    addPosition,
    deletePosition,
    fetchSummary,
    fetchAnalysis,
    triggerDailyAnalysis
  }
})
