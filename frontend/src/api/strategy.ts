import { request } from '@/utils/request'

export interface ParameterSchema {
  name: string
  type: string
  default: any
  min_value?: number
  max_value?: number
  description: string
  required: boolean
}

export interface StrategyMetadata {
  id: string
  name: string
  description: string
  category: string
  author: string
  version: string
  tags: string[]
  risk_level: string
  created_at: string
  updated_at: string
  usage_count: number
  is_ai_generated: boolean
  parameter_schema: ParameterSchema[]
  generation_prompt?: string
}

export interface BacktestConfig {
  strategy_id: string
  symbol: string
  start_date: string
  end_date: string
  initial_capital: number
  parameters: Record<string, any>
}

export interface BacktestResult {
  id: string
  strategy_id: string
  config: BacktestConfig
  performance_metrics: {
    total_return: number
    annual_return: number
    sharpe_ratio: number
    max_drawdown: number
    win_rate: number
    profit_factor: number
  }
  trades: any[]
  equity_curve: any[]
  created_at: string
}

export interface OptimizationConfig {
  strategy_id: string
  symbol: string
  start_date: string
  end_date: string
  initial_capital: number
  parameter_ranges: Record<string, { min: number; max: number; step: number }>
  optimization_target: string
}

export interface AIGenerationRequest {
  description: string
  market_type: string
  risk_level: string
  time_frame: string
  additional_requirements?: string
}

export const strategyApi = {
  // 获取策略列表
  async getStrategies(): Promise<{ data: StrategyMetadata[] }> {
    return request.get('/api/strategies/')
  },

  // 获取单个策略详情
  async getStrategy(id: string): Promise<{ data: StrategyMetadata }> {
    return request.get(`/api/strategies/${id}`)
  },

  // 创建新策略
  async createStrategy(strategy: Partial<StrategyMetadata>): Promise<{ data: StrategyMetadata }> {
    return request.post('/api/strategies/', strategy)
  },

  // 更新策略
  async updateStrategy(id: string, strategy: Partial<StrategyMetadata>): Promise<{ data: StrategyMetadata }> {
    return request.put(`/api/strategies/${id}`, strategy)
  },

  // 删除策略
  async deleteStrategy(id: string): Promise<void> {
    return request.delete(`/api/strategies/${id}`)
  },

  // 运行回测
  async runBacktest(config: BacktestConfig): Promise<{ data: BacktestResult }> {
    return request.post('/api/strategies/backtest', config)
  },

  // 获取回测结果
  async getBacktestResult(id: string): Promise<{ data: BacktestResult }> {
    return request.get(`/api/strategies/backtest/${id}`)
  },

  // 获取策略的回测历史
  async getBacktestHistory(strategyId: string): Promise<{ data: BacktestResult[] }> {
    return request.get(`/api/strategies/${strategyId}/backtest-history`)
  },

  // 参数优化
  async optimizeStrategy(config: OptimizationConfig): Promise<{ data: any }> {
    return request.post('/api/strategies/optimize', config)
  },

  // AI生成策略
  async generateAIStrategy(req: AIGenerationRequest): Promise<{ data: StrategyMetadata }> {
    return request.post('/api/strategies/ai-generate', req)
  },

  // 获取AI策略解释
  async explainStrategy(strategyId: string): Promise<{ data: { explanation: string } }> {
    return request.get(`/api/strategies/${strategyId}/explain`)
  },

  // 获取策略分类统计
  async getCategoryStats(): Promise<{ data: Record<string, number> }> {
    return request.get('/api/strategies/category-stats')
  },

  // 搜索策略
  async searchStrategies(query: string, filters?: Record<string, any>): Promise<{ data: StrategyMetadata[] }> {
    const params = new URLSearchParams({ q: query })
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          params.append(key, String(value))
        }
      })
    }
    return request.get(`/api/strategies/search?${params.toString()}`)
  }
}