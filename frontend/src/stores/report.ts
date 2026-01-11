import { defineStore } from 'pinia'
import { ref } from 'vue'
import { reportApi, type FinancialResponse, type CompareResponse, type AnalysisResponse } from '@/api/report'

export const useReportStore = defineStore('report', () => {
  // State
  const financialData = ref<FinancialResponse | null>(null)
  const comparisonData = ref<CompareResponse | null>(null)
  const analysisData = ref<AnalysisResponse | null>(null)
  const loading = ref(false)
  const analysisLoading = ref(false)
  const comparisonLoading = ref(false)

  // Actions
  const fetchFinancial = async (code: string, periods: number = 4) => {
    loading.value = true
    try {
      const response = await reportApi.getFinancial({ code, periods })
      financialData.value = response
      return response
    } catch (error) {
      console.error('Failed to fetch financial data:', error)
      financialData.value = null
      throw error
    } finally {
      loading.value = false
    }
  }

  const fetchComparison = async (code: string, endDate?: string, industryLimit?: number) => {
    comparisonLoading.value = true
    try {
      const response = await reportApi.getComparison({ 
        code, 
        end_date: endDate,
        industry_limit: industryLimit 
      })
      comparisonData.value = response
      return response
    } catch (error) {
      console.error('Failed to fetch comparison data:', error)
      comparisonData.value = null
      throw error
    } finally {
      comparisonLoading.value = false
    }
  }

  const fetchAnalysis = async (
    code: string, 
    analysisType: 'comprehensive' | 'peer_comparison' | 'investment_insights' = 'comprehensive',
    periods: number = 4
  ) => {
    analysisLoading.value = true
    try {
      const response = await reportApi.getAnalysis({ 
        code, 
        analysis_type: analysisType,
        periods 
      })
      analysisData.value = response
      return response
    } catch (error) {
      console.error('Failed to fetch analysis:', error)
      analysisData.value = null
      throw error
    } finally {
      analysisLoading.value = false
    }
  }

  // Comprehensive analysis - fetch all data
  const fetchComprehensiveReport = async (code: string, periods: number = 4) => {
    try {
      // Fetch financial data first
      await fetchFinancial(code, periods)
      
      // Fetch comparison data
      await fetchComparison(code)
      
      // Fetch comprehensive analysis
      await fetchAnalysis(code, 'comprehensive', periods)
      
      return {
        financial: financialData.value,
        comparison: comparisonData.value,
        analysis: analysisData.value
      }
    } catch (error) {
      console.error('Failed to fetch comprehensive report:', error)
      throw error
    }
  }

  // Clear all data
  const clearData = () => {
    financialData.value = null
    comparisonData.value = null
    analysisData.value = null
  }

  // Legacy method for backward compatibility
  const analyzeReport = async (code: string) => {
    return fetchAnalysis(code, 'comprehensive')
  }

  return {
    // State
    financialData,
    comparisonData,
    analysisData,
    loading,
    analysisLoading,
    comparisonLoading,
    
    // Actions
    fetchFinancial,
    fetchComparison,
    fetchAnalysis,
    fetchComprehensiveReport,
    clearData,
    
    // Legacy
    analyzeReport
  }
})
