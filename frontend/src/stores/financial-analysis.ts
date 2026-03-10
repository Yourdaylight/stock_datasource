import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  financialAnalysisApi,
  type CompanyItem,
  type ReportPeriod,
  type ReportDetailResponse,
  type AnalysisRecord,
} from '@/api/financial-analysis'

export const useFinancialAnalysisStore = defineStore('financialAnalysis', () => {
  // ========== State ==========

  // Company list
  const companies = ref<CompanyItem[]>([])
  const companyTotal = ref(0)
  const companyPage = ref(1)
  const companyLoading = ref(false)

  // Industries
  const industries = ref<string[]>([])

  // Report periods
  const currentCompany = ref<CompanyItem | null>(null)
  const reportPeriods = ref<ReportPeriod[]>([])
  const periodsLoading = ref(false)

  // Report detail
  const reportDetail = ref<ReportDetailResponse | null>(null)
  const detailLoading = ref(false)

  // Analysis
  const analysisRecords = ref<AnalysisRecord[]>([])
  const currentAnalysis = ref<AnalysisRecord | null>(null)
  const analysisLoading = ref(false)
  const analyzeRunning = ref(false)
  const aiDeepRunning = ref(false)

  // ========== Actions ==========

  const fetchCompanies = async (params: {
    market?: string
    keyword?: string
    industry?: string
    page?: number
    page_size?: number
  }) => {
    companyLoading.value = true
    try {
      const res = await financialAnalysisApi.getCompanies(params)
      companies.value = res.items
      companyTotal.value = res.total
      companyPage.value = res.page
      return res
    } catch (error) {
      console.error('Failed to fetch companies:', error)
      companies.value = []
      companyTotal.value = 0
      throw error
    } finally {
      companyLoading.value = false
    }
  }

  const fetchIndustries = async (market?: string) => {
    try {
      const res = await financialAnalysisApi.getIndustries(market)
      industries.value = res.industries
      return res
    } catch (error) {
      console.error('Failed to fetch industries:', error)
      industries.value = []
      throw error
    }
  }

  const fetchReportPeriods = async (code: string, market?: string) => {
    periodsLoading.value = true
    try {
      const res = await financialAnalysisApi.getReportPeriods(code, market)
      currentCompany.value = res.company
      reportPeriods.value = res.periods
      return res
    } catch (error) {
      console.error('Failed to fetch report periods:', error)
      reportPeriods.value = []
      throw error
    } finally {
      periodsLoading.value = false
    }
  }

  const fetchReportDetail = async (code: string, period: string, market?: string) => {
    detailLoading.value = true
    try {
      const res = await financialAnalysisApi.getReportDetail(code, period, market)
      reportDetail.value = res
      return res
    } catch (error) {
      console.error('Failed to fetch report detail:', error)
      reportDetail.value = null
      throw error
    } finally {
      detailLoading.value = false
    }
  }

  const runAnalysis = async (params: {
    code: string
    end_date: string
    market?: string
    analysis_type?: string
  }) => {
    analyzeRunning.value = true
    try {
      const res = await financialAnalysisApi.analyze(params)
      if (res.record) {
        currentAnalysis.value = res.record
        // Prepend to history
        analysisRecords.value.unshift(res.record)
      }
      return res
    } catch (error) {
      console.error('Failed to run analysis:', error)
      throw error
    } finally {
      analyzeRunning.value = false
    }
  }

  const runLLMAnalysis = async (params: {
    code: string
    end_date: string
    market?: string
  }) => {
    aiDeepRunning.value = true
    try {
      const res = await financialAnalysisApi.analyzeDeep({
        ...params,
        analysis_type: 'ai_deep',
      })
      if (res.record) {
        currentAnalysis.value = res.record
        // Prepend to history
        analysisRecords.value.unshift(res.record)
      }
      return res
    } catch (error) {
      console.error('Failed to run LLM analysis:', error)
      throw error
    } finally {
      aiDeepRunning.value = false
    }
  }

  const fetchAnalysisHistory = async (code: string, params?: {
    end_date?: string
    market?: string
    limit?: number
  }) => {
    analysisLoading.value = true
    try {
      const res = await financialAnalysisApi.getAnalysisHistory(code, params)
      analysisRecords.value = res.records
      return res
    } catch (error) {
      console.error('Failed to fetch analysis history:', error)
      analysisRecords.value = []
      throw error
    } finally {
      analysisLoading.value = false
    }
  }

  const fetchAnalysisRecord = async (recordId: string) => {
    try {
      const res = await financialAnalysisApi.getAnalysisRecord(recordId)
      currentAnalysis.value = res.record
      return res
    } catch (error) {
      console.error('Failed to fetch analysis record:', error)
      throw error
    }
  }

  const clearAll = () => {
    companies.value = []
    companyTotal.value = 0
    currentCompany.value = null
    reportPeriods.value = []
    reportDetail.value = null
    analysisRecords.value = []
    currentAnalysis.value = null
  }

  return {
    // State
    companies,
    companyTotal,
    companyPage,
    companyLoading,
    industries,
    currentCompany,
    reportPeriods,
    periodsLoading,
    reportDetail,
    detailLoading,
    analysisRecords,
    currentAnalysis,
    analysisLoading,
    analyzeRunning,
    aiDeepRunning,

    // Actions
    fetchCompanies,
    fetchIndustries,
    fetchReportPeriods,
    fetchReportDetail,
    runAnalysis,
    runLLMAnalysis,
    fetchAnalysisHistory,
    fetchAnalysisRecord,
    clearAll,
  }
})
