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

export const memoryApi = {
  getPreference(): Promise<UserPreference> {
    return request.get('/memory/preference')
  },

  updatePreference(data: Partial<UserPreference>): Promise<void> {
    return request.put('/memory/preference', data)
  },

  getWatchlist(group?: string): Promise<WatchlistItem[]> {
    const params = group ? `?group=${encodeURIComponent(group)}` : ''
    return request.get(`/memory/watchlist${params}`)
  },

  addToWatchlist(data: { ts_code: string; group_name?: string; add_reason?: string }): Promise<void> {
    return request.post('/memory/watchlist', data)
  },

  removeFromWatchlist(tsCode: string): Promise<void> {
    return request.delete(`/memory/watchlist/${tsCode}`)
  },

  getMemories(type?: string): Promise<MemoryItem[]> {
    const params = type ? `?type=${encodeURIComponent(type)}` : ''
    return request.get(`/memory/list${params}`)
  },

  searchMemories(query: string): Promise<MemoryItem[]> {
    return request.get(`/memory/search?query=${encodeURIComponent(query)}`)
  },

  getHistory(limit?: number): Promise<InteractionHistory[]> {
    const params = limit ? `?limit=${limit}` : ''
    return request.get(`/memory/history${params}`)
  },

  getProfile(): Promise<UserProfile> {
    return request.get('/memory/profile')
  }
}
