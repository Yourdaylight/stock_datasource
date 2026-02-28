import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  quantApi,
  type CorePoolResult,
  type DataReadinessResult,
  type DeepAnalysisResult,
  type MarketRiskStatus,
  type PipelineRunStatus,
  type PoolChange,
  type QuantConfig,
  type RPSRankItem,
  type ScreeningResult,
  type TradingSignal,
} from '@/api/quant'

export const useQuantStore = defineStore('quant', () => {
  // Pipeline
  const pipelineStatus = ref<PipelineRunStatus | null>(null)
  const pipelineLoading = ref(false)

  // Data Readiness
  const dataReadiness = ref<Record<string, DataReadinessResult>>({})
  const readinessLoading = ref(false)

  // Screening
  const screeningResult = ref<ScreeningResult | null>(null)
  const screeningLoading = ref(false)

  // Pool
  const poolResult = ref<CorePoolResult | null>(null)
  const poolChanges = ref<PoolChange[]>([])
  const poolLoading = ref(false)

  // RPS
  const rpsItems = ref<RPSRankItem[]>([])
  const rpsLoading = ref(false)

  // Analysis
  const analysisResult = ref<DeepAnalysisResult | null>(null)
  const analysisDashboard = ref<any[]>([])
  const analysisLoading = ref(false)

  // Signals
  const signals = ref<TradingSignal[]>([])
  const marketRisk = ref<MarketRiskStatus | null>(null)
  const signalsLoading = ref(false)

  // Config
  const configs = ref<QuantConfig[]>([])

  // =========================================================================
  // Data Readiness
  // =========================================================================

  const fetchDataReadiness = async () => {
    readinessLoading.value = true
    try {
      dataReadiness.value = await quantApi.checkFullReadiness()
    } catch (e) {
      console.error('Failed to fetch data readiness', e)
    } finally {
      readinessLoading.value = false
    }
  }

  // =========================================================================
  // Pipeline
  // =========================================================================

  const runPipeline = async (pipelineType = 'full', tradeDate?: string) => {
    pipelineLoading.value = true
    try {
      pipelineStatus.value = await quantApi.runPipeline({
        pipeline_type: pipelineType,
        trade_date: tradeDate,
      })
      return pipelineStatus.value
    } catch (e) {
      console.error('Pipeline failed', e)
      return null
    } finally {
      pipelineLoading.value = false
    }
  }

  const fetchPipelineStatus = async (runId?: string) => {
    try {
      if (runId) {
        pipelineStatus.value = await quantApi.getPipelineStatus(runId)
      } else {
        pipelineStatus.value = await quantApi.getLatestPipeline()
      }
    } catch (e) {
      console.error('Failed to fetch pipeline status', e)
    }
  }

  // =========================================================================
  // Screening
  // =========================================================================

  const runScreening = async (tradeDate?: string) => {
    screeningLoading.value = true
    try {
      screeningResult.value = await quantApi.runScreening({ trade_date: tradeDate })
      return screeningResult.value
    } catch (e) {
      console.error('Screening failed', e)
      return null
    } finally {
      screeningLoading.value = false
    }
  }

  const fetchScreeningResult = async (runDate?: string) => {
    screeningLoading.value = true
    try {
      screeningResult.value = await quantApi.getScreeningResult(runDate)
    } catch (e) {
      console.error('Failed to fetch screening result', e)
    } finally {
      screeningLoading.value = false
    }
  }

  // =========================================================================
  // Pool
  // =========================================================================

  const fetchPool = async () => {
    poolLoading.value = true
    try {
      poolResult.value = await quantApi.getPool()
    } catch (e) {
      console.error('Failed to fetch pool', e)
    } finally {
      poolLoading.value = false
    }
  }

  const refreshPool = async (tradeDate?: string) => {
    poolLoading.value = true
    try {
      poolResult.value = await quantApi.refreshPool(tradeDate)
      return poolResult.value
    } catch (e) {
      console.error('Pool refresh failed', e)
      return null
    } finally {
      poolLoading.value = false
    }
  }

  const fetchPoolChanges = async (limit = 50) => {
    try {
      poolChanges.value = await quantApi.getPoolChanges(limit)
    } catch (e) {
      console.error('Failed to fetch pool changes', e)
    }
  }

  // =========================================================================
  // RPS
  // =========================================================================

  const fetchRps = async (limit = 100) => {
    rpsLoading.value = true
    try {
      rpsItems.value = await quantApi.getRps(limit)
    } catch (e) {
      console.error('Failed to fetch RPS', e)
    } finally {
      rpsLoading.value = false
    }
  }

  // =========================================================================
  // Analysis
  // =========================================================================

  const analyzeStock = async (tsCode: string) => {
    analysisLoading.value = true
    try {
      analysisResult.value = await quantApi.analyzeStock(tsCode)
      return analysisResult.value
    } catch (e) {
      console.error('Analysis failed', e)
      return null
    } finally {
      analysisLoading.value = false
    }
  }

  const fetchAnalysisDashboard = async () => {
    try {
      analysisDashboard.value = await quantApi.getAnalysisDashboard()
    } catch (e) {
      console.error('Failed to fetch dashboard', e)
    }
  }

  // =========================================================================
  // Signals
  // =========================================================================

  const fetchSignals = async (signalDate?: string, limit = 50) => {
    signalsLoading.value = true
    try {
      signals.value = await quantApi.getSignals(signalDate, limit)
    } catch (e) {
      console.error('Failed to fetch signals', e)
    } finally {
      signalsLoading.value = false
    }
  }

  const fetchMarketRisk = async () => {
    try {
      marketRisk.value = await quantApi.getMarketRisk()
    } catch (e) {
      console.error('Failed to fetch market risk', e)
    }
  }

  // =========================================================================
  // Config
  // =========================================================================

  const fetchConfig = async (configType?: string) => {
    try {
      configs.value = await quantApi.getConfig(configType)
    } catch (e) {
      console.error('Failed to fetch config', e)
    }
  }

  const updateConfig = async (configType: string, configData: Record<string, any>) => {
    try {
      await quantApi.updateConfig({ config_type: configType, config_data: configData })
      await fetchConfig()
    } catch (e) {
      console.error('Failed to update config', e)
    }
  }

  return {
    // State
    pipelineStatus, pipelineLoading,
    dataReadiness, readinessLoading,
    screeningResult, screeningLoading,
    poolResult, poolChanges, poolLoading,
    rpsItems, rpsLoading,
    analysisResult, analysisDashboard, analysisLoading,
    signals, marketRisk, signalsLoading,
    configs,
    // Actions
    fetchDataReadiness,
    runPipeline, fetchPipelineStatus,
    runScreening, fetchScreeningResult,
    fetchPool, refreshPool, fetchPoolChanges,
    fetchRps,
    analyzeStock, fetchAnalysisDashboard,
    fetchSignals, fetchMarketRisk,
    fetchConfig, updateConfig,
  }
})
