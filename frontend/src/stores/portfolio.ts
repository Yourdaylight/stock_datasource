import { defineStore } from 'pinia'
import { ref } from 'vue'
import { portfolioApi } from '@/api/portfolio'
import type { Position, PortfolioSummary, AnalysisReport, CreatePositionRequest } from '@/types/portfolio'

export const usePortfolioStore = defineStore('portfolio', () => {
  const positions = ref<Position[]>([])
  const summary = ref<PortfolioSummary | null>(null)
  const analysis = ref<AnalysisReport | null>(null)
  const loading = ref(false)

  const fetchPositions = async () => {
    loading.value = true
    try {
      const response = await portfolioApi.getPositions()
      positions.value = Array.isArray(response) ? response : []
    } catch (e) {
      positions.value = []
      // Error handled by interceptor
    } finally {
      loading.value = false
    }
  }

  const addPosition = async (data: CreatePositionRequest) => {
    loading.value = true
    try {
      await portfolioApi.createPosition(data)
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
      const response = await portfolioApi.getSummary()
      summary.value = response || null
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const fetchAnalysis = async (date?: string) => {
    try {
      const today = date || new Date().toISOString().split('T')[0]
      const response = await portfolioApi.getAnalysisReport(today)
      analysis.value = response || null
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
