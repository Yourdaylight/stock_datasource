/**
 * Query history composable for SQL editor.
 * Stores query history in localStorage with a maximum of 100 records.
 */

import { ref, computed } from 'vue'

const STORAGE_KEY = 'sql_query_history'
const MAX_HISTORY_SIZE = 100

export interface QueryHistoryItem {
  id: string
  sql: string
  tableName?: string
  executedAt: string
  executionTime?: number
  rowCount?: number
}

// Load history from localStorage
const loadHistory = (): QueryHistoryItem[] => {
  try {
    const data = localStorage.getItem(STORAGE_KEY)
    return data ? JSON.parse(data) : []
  } catch {
    return []
  }
}

// Shared state across components
const history = ref<QueryHistoryItem[]>(loadHistory())

// Save to localStorage
const saveHistory = () => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history.value))
  } catch (e) {
    console.warn('Failed to save query history:', e)
  }
}

export function useQueryHistory() {
  // Add to history
  const addToHistory = (item: Omit<QueryHistoryItem, 'id'>) => {
    const newItem: QueryHistoryItem = {
      ...item,
      id: `history_${Date.now()}`
    }
    
    // Check for duplicate (same SQL)
    const existingIndex = history.value.findIndex(h => h.sql.trim() === item.sql.trim())
    if (existingIndex >= 0) {
      // Remove old entry
      history.value.splice(existingIndex, 1)
    }
    
    // Add to top
    history.value.unshift(newItem)
    
    // Limit size
    if (history.value.length > MAX_HISTORY_SIZE) {
      history.value = history.value.slice(0, MAX_HISTORY_SIZE)
    }
    
    saveHistory()
  }
  
  // Remove single record
  const removeFromHistory = (id: string) => {
    history.value = history.value.filter(h => h.id !== id)
    saveHistory()
  }
  
  // Clear all history
  const clearHistory = () => {
    history.value = []
    localStorage.removeItem(STORAGE_KEY)
  }
  
  // Search history
  const searchHistory = (keyword: string): QueryHistoryItem[] => {
    if (!keyword.trim()) return history.value
    const lower = keyword.toLowerCase()
    return history.value.filter(h => 
      h.sql.toLowerCase().includes(lower) ||
      h.tableName?.toLowerCase().includes(lower)
    )
  }
  
  // Get recent history (limited)
  const getRecentHistory = (limit: number = 20): QueryHistoryItem[] => {
    return history.value.slice(0, limit)
  }
  
  return {
    history: computed(() => history.value),
    addToHistory,
    removeFromHistory,
    clearHistory,
    searchHistory,
    getRecentHistory
  }
}
