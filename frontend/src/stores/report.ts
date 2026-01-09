import { defineStore } from 'pinia'
import { ref } from 'vue'
import { reportApi, type FinancialData } from '@/api/report'

export const useReportStore = defineStore('report', () => {
  const financialData = ref<FinancialData[]>([])
  const loading = ref(false)
  const analysis = ref('')

  const fetchFinancial = async (code: string, reportType: 'income' | 'balance' | 'cashflow') => {
    loading.value = true
    try {
      const response = await reportApi.getFinancial({
        code,
        report_type: reportType
      })
      financialData.value = response.data
    } catch (e) {
      // Error handled by interceptor
    } finally {
      loading.value = false
    }
  }

  const analyzeReport = async (code: string) => {
    analysis.value = ''
    loading.value = true
    try {
      // TODO: Implement SSE streaming
      analysis.value = '正在分析财报...'
    } finally {
      loading.value = false
    }
  }

  return {
    financialData,
    loading,
    analysis,
    fetchFinancial,
    analyzeReport
  }
})
