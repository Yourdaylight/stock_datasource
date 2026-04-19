import { request } from '@/utils/request'

export interface UserPreference {
  risk_level: 'conservative' | 'moderate' | 'aggressive'
  investment_style: 'value' | 'growth' | 'balanced' | 'momentum'
  favorite_sectors: string[]
}

export interface WatchlistItem {
  ts_code: string
  stock_name: string
  group_name: string
  add_reason?: string
  target_price?: number
  stop_loss_price?: number
  created_at: string
}

export interface MemoryItem {
  id: string
  memory_type: string
  memory_key: string
  memory_value: any
  importance: number
  created_at: string
}

export interface InteractionHistory {
  id: string
  intent: string
  user_input: string
  stocks_mentioned: string[]
  timestamp: string
}

export interface UserProfile {
  active_level: string
  expertise_level: string
  focus_industries: string[]
  focus_stocks: string[]
  trading_style: string
}

export interface FactOutput {
  id: string
  content: string
  category: 'risk_preference' | 'sector_focus' | 'stock_opinion' | 'trading_style' | 'conclusion' | 'market_signal' | 'capital_flow'
  confidence: number
  source: string
  created_at: number
  reinforced_at: number[]
  contradicted_at: number[]
}

export interface ConclusionOutput {
  id: string
  data: Record<string, any>
  stored_at: number
}

export const memoryApi = {
  getPreference(): Promise<UserPreference> {
    return request.get('/api/memory/preference')
  },

  updatePreference(data: Partial<UserPreference>): Promise<void> {
    return request.put('/api/memory/preference', data)
  },

  getWatchlist(group?: string): Promise<WatchlistItem[]> {
    const params = group ? `?group=${encodeURIComponent(group)}` : ''
    return request.get(`/api/memory/watchlist${params}`)
  },

  addToWatchlist(data: { ts_code: string; group_name?: string; add_reason?: string }): Promise<void> {
    return request.post('/api/memory/watchlist', data)
  },

  removeFromWatchlist(tsCode: string): Promise<void> {
    return request.delete(`/api/memory/watchlist/${tsCode}`)
  },

  getMemories(type?: string): Promise<MemoryItem[]> {
    const params = type ? `?type=${encodeURIComponent(type)}` : ''
    return request.get(`/api/memory/list${params}`)
  },

  searchMemories(query: string): Promise<MemoryItem[]> {
    return request.get(`/api/memory/search?query=${encodeURIComponent(query)}`)
  },

  getHistory(limit?: number): Promise<InteractionHistory[]> {
    const params = limit ? `?limit=${limit}` : ''
    return request.get(`/api/memory/history${params}`)
  },

  getProfile(): Promise<UserProfile> {
    return request.get('/api/memory/profile')
  },

  // Facts API
  getFacts(category?: string, limit?: number, minConfidence?: number): Promise<FactOutput[]> {
    const params = new URLSearchParams()
    if (category) params.set('category', category)
    if (limit) params.set('limit', String(limit))
    if (minConfidence !== undefined) params.set('min_confidence', String(minConfidence))
    const qs = params.toString()
    return request.get(`/api/memory/facts${qs ? '?' + qs : ''}`)
  },

  createFact(data: { content: string; category: string; confidence?: number; source?: string }): Promise<FactOutput> {
    return request.post('/api/memory/facts', data)
  },

  deleteFact(factId: string): Promise<void> {
    return request.delete(`/api/memory/facts/${factId}`)
  },

  // Conclusions API
  getConclusions(limit?: number): Promise<ConclusionOutput[]> {
    const params = limit ? `?limit=${limit}` : ''
    return request.get(`/api/memory/conclusions${params}`)
  },
}
