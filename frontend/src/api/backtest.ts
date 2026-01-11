import { request } from '@/utils/request'

export interface StrategyParam {
  name: string
  type: 'int' | 'float' | 'bool'
  default: any
  min_value?: number
  max_value?: number
  description: string
}

export interface Strategy {
  id: string
  name: string
  description: string
  category: string
  params: StrategyParam[]
}

export interface BacktestRequest {
  strategy_id: string
  ts_codes: string[]
  start_date: string
  end_date: string
  initial_capital?: number
  params?: Record<string, any>
}

export interface Trade {
  date: string
  direction: 'buy' | 'sell'
  price: number
  quantity: number
  amount: number
  signal_reason: string
}

export interface BacktestResult {
  task_id: string
  strategy_name: string
  ts_codes: string[]
  start_date: string
  end_date: string
  initial_capital: number
  final_capital: number
  total_return: number
  annual_return: number
  max_drawdown: number
  sharpe_ratio: number
  win_rate: number
  trade_count: number
  trades: Trade[]
  equity_curve: { date: string; value: number }[]
}

export const backtestApi = {
  getStrategies(): Promise<Strategy[]> {
    return request.get('/api/backtest/strategies')
  },

  getStrategy(id: string): Promise<Strategy> {
    return request.get(`/api/backtest/strategies/${id}`)
  },

  runBacktest(data: BacktestRequest): Promise<BacktestResult> {
    return request.post('/api/backtest/run', data)
  },

  getResults(limit?: number): Promise<BacktestResult[]> {
    const params = limit ? `?limit=${limit}` : ''
    return request.get(`/api/backtest/results${params}`)
  },

  getResult(taskId: string): Promise<BacktestResult> {
    return request.get(`/api/backtest/results/${taskId}`)
  }
}
