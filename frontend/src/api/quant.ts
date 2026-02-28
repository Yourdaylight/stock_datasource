import { request } from '@/utils/request'

// =============================================================================
// Types
// =============================================================================

export interface DataRequirement {
  plugin_name: string
  table_name: string
  required_columns: string[]
  date_column: string
  description: string
}

export interface PluginTriggerInfo {
  plugin_name: string
  display_name: string
  table_name: string
  missing_dates: string[]
  task_type: string
  description: string
}

export interface MissingDataSummary {
  total_requirements: number
  ready_count: number
  missing_count: number
  affected_engines: string[]
  plugins_to_trigger: PluginTriggerInfo[]
  estimated_sync_time: string
}

export interface DataRequirementStatus {
  requirement: DataRequirement
  status: string
  existing_date_range: string[] | null
  missing_dates: string[]
  record_count: number
  suggested_plugins: string[]
}

export interface DataReadinessResult {
  is_ready: boolean
  checked_at: string
  stage: string
  requirements: DataRequirementStatus[]
  missing_summary: MissingDataSummary | null
}

export interface RuleExecutionDetail {
  rule_name: string
  category: string
  enabled: boolean
  total_checked: number
  passed_count: number
  rejected_count: number
  skipped_count: number
  execution_time_ms: number
  threshold: string
  sample_rejects: Array<{ ts_code: string; reason: string }>
}

export interface ScreeningResultItem {
  ts_code: string
  stock_name: string
  overall_pass: boolean
  reject_reasons: string[]
  rule_details: Array<Record<string, any>>
}

export interface ScreeningResult {
  run_date: string
  run_id: string
  total_stocks: number
  passed_count: number
  rejected_count: number
  passed_stocks: ScreeningResultItem[]
  rejected_stocks: ScreeningResultItem[]
  rule_details: RuleExecutionDetail[]
  data_readiness: DataReadinessResult | null
  execution_time_ms: number
  status: string
}

export interface FactorScoreDetail {
  ts_code: string
  stock_name: string
  quality_score: number
  quality_breakdown: Record<string, number>
  growth_score: number
  growth_breakdown: Record<string, number>
  value_score: number
  value_breakdown: Record<string, number>
  momentum_score: number
  momentum_breakdown: Record<string, number>
  total_score: number
  rank: number
  pool_type: string
  rps_250: number
}

export interface PoolChange {
  ts_code: string
  stock_name: string
  change_type: string
  change_date: string
  old_rank: number | null
  new_rank: number | null
  total_score: number
  reason: string
}

export interface CorePoolResult {
  update_date: string
  core_stocks: FactorScoreDetail[]
  supplement_stocks: FactorScoreDetail[]
  pool_changes: PoolChange[]
  factor_distribution: Record<string, any>
  data_readiness: DataReadinessResult | null
  execution_time_ms: number
}

export interface TechSnapshot {
  ts_code: string
  stock_name: string
  ma25: number | null
  ma120: number | null
  ma250: number | null
  macd: number | null
  macd_signal: number | null
  macd_hist: number | null
  rsi_14: number | null
  volume_ratio: number | null
  close: number | null
  pct_chg: number | null
  ma_position: string
}

export interface AiAnalysisCard {
  ts_code: string
  stock_name: string
  credibility_score: number
  optimism_score: number
  key_findings: string[]
  risk_factors: string[]
  verification_points: string[]
  ai_summary: string
}

export interface DeepAnalysisResult {
  ts_code: string
  stock_name: string
  analysis_date: string
  tech_snapshot: TechSnapshot | null
  ai_analysis: AiAnalysisCard | null
  tech_score: number
  overall_score: number
}

export interface TradingSignal {
  signal_date: string
  ts_code: string
  stock_name: string
  signal_type: string
  signal_source: string
  price: number
  target_position: number
  confidence: number
  reason: string
  pool_type: string
  ma25: number
  ma120: number
  signal_context: Record<string, any>
}

export interface MarketRiskStatus {
  index_code: string
  index_name: string
  index_close: number
  index_ma250: number
  is_above_ma250: boolean
  risk_level: string
  suggested_position: number
  description: string
}

export interface SignalResult {
  signal_date: string
  signals: TradingSignal[]
  market_risk: MarketRiskStatus | null
  data_readiness: DataReadinessResult | null
  execution_time_ms: number
}

export interface PipelineStageStatus {
  name: string
  stage: string
  status: string
  start_time: string | null
  end_time: string | null
  result_summary: Record<string, any>
  data_readiness: DataReadinessResult | null
  error_message: string
}

export interface PipelineRunStatus {
  run_id: string
  run_date: string
  pipeline_type: string
  overall_status: string
  triggered_by: string
  stages: PipelineStageStatus[]
  created_at: string
  updated_at: string
}

export interface QuantConfig {
  config_id: string
  config_name: string
  config_type: string
  config_data: Record<string, any>
  is_active: boolean
  updated_at: string
}

export interface RPSRankItem {
  ts_code: string
  stock_name: string
  rps_250: number
  rps_120: number
  rps_60: number
  price_chg_250: number
  price_chg_120: number
  price_chg_60: number
  calc_date: string
}

// =============================================================================
// API Client
// =============================================================================

export const quantApi = {
  // Data Readiness
  checkFullReadiness(): Promise<Record<string, DataReadinessResult>> {
    return request.get('/api/quant/data-readiness')
  },
  checkStageReadiness(stage: string): Promise<DataReadinessResult> {
    return request.get(`/api/quant/data-readiness/${stage}`)
  },

  // Pipeline
  runPipeline(data: { pipeline_type?: string; trade_date?: string }): Promise<PipelineRunStatus> {
    return request.post('/api/quant/pipeline/run', data)
  },
  getPipelineStatus(runId: string): Promise<PipelineRunStatus> {
    return request.get(`/api/quant/pipeline/status/${runId}`)
  },
  getLatestPipeline(): Promise<PipelineRunStatus | null> {
    return request.get('/api/quant/pipeline/latest')
  },

  // Screening
  runScreening(data?: { trade_date?: string }): Promise<ScreeningResult> {
    return request.post('/api/quant/screening/run', data || {})
  },
  getScreeningResult(runDate?: string): Promise<ScreeningResult | null> {
    return request.get('/api/quant/screening/result', { params: { run_date: runDate } })
  },
  getScreeningRules(): Promise<QuantConfig> {
    return request.get('/api/quant/screening/rules')
  },
  updateScreeningRules(data: Record<string, any>): Promise<QuantConfig> {
    return request.put('/api/quant/screening/rules', { config_type: 'screening_rules', config_data: data })
  },

  // Pool
  getPool(): Promise<CorePoolResult> {
    return request.get('/api/quant/pool')
  },
  refreshPool(tradeDate?: string): Promise<CorePoolResult> {
    return request.post('/api/quant/pool/refresh', null, { params: { trade_date: tradeDate } })
  },
  getPoolChanges(limit?: number): Promise<PoolChange[]> {
    return request.get('/api/quant/pool/changes', { params: { limit } })
  },

  // RPS
  getRps(limit?: number): Promise<RPSRankItem[]> {
    return request.get('/api/quant/rps', { params: { limit } })
  },
  getRpsDetail(tsCode: string): Promise<RPSRankItem[]> {
    return request.get(`/api/quant/rps/${tsCode}`)
  },

  // Deep Analysis
  analyzeStock(tsCode: string): Promise<DeepAnalysisResult> {
    return request.post(`/api/quant/analysis/${tsCode}`)
  },
  getAnalysisDashboard(): Promise<any[]> {
    return request.get('/api/quant/analysis/dashboard')
  },

  // Signals
  getSignals(signalDate?: string, limit?: number): Promise<TradingSignal[]> {
    return request.get('/api/quant/signals', { params: { signal_date: signalDate, limit } })
  },
  getSignalHistory(limit?: number): Promise<any[]> {
    return request.get('/api/quant/signals/history', { params: { limit } })
  },
  getMarketRisk(): Promise<MarketRiskStatus> {
    return request.get('/api/quant/risk')
  },

  // Config
  getConfig(configType?: string): Promise<QuantConfig[]> {
    return request.get('/api/quant/config', { params: { config_type: configType } })
  },
  updateConfig(data: { config_type: string; config_data: Record<string, any> }): Promise<QuantConfig> {
    return request.put('/api/quant/config', data)
  },

  // Report
  getReport(): Promise<any> {
    return request.get('/api/quant/report')
  },
}
