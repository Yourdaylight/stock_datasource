import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { memoryApi, type UserPreference, type WatchlistItem, type InteractionHistory, type UserProfile } from '@/api/memory'

export const useMemoryStore = defineStore('memory', () => {
  const preference = reactive<UserPreference>({
    risk_level: 'moderate',
    investment_style: 'balanced',
    favorite_sectors: []
  })
  const watchlist = ref<WatchlistItem[]>([])
  const history = ref<InteractionHistory[]>([])
  const profile = ref<UserProfile | null>(null)
  const loading = ref(false)

  const fetchPreference = async () => {
    try {
      const data = await memoryApi.getPreference()
      Object.assign(preference, data)
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const updatePreference = async (data: Partial<UserPreference>) => {
    loading.value = true
    try {
      await memoryApi.updatePreference(data)
      Object.assign(preference, data)
    } catch (e) {
      // Error handled by interceptor
    } finally {
      loading.value = false
    }
  }

  const fetchWatchlist = async (group?: string) => {
    loading.value = true
    try {
      watchlist.value = await memoryApi.getWatchlist(group)
    } catch (e) {
      // Error handled by interceptor
    } finally {
      loading.value = false
    }
  }

  const addToWatchlist = async (tsCode: string, groupName?: string) => {
    try {
      await memoryApi.addToWatchlist({ ts_code: tsCode, group_name: groupName })
      await fetchWatchlist()
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const removeFromWatchlist = async (tsCode: string) => {
    try {
      await memoryApi.removeFromWatchlist(tsCode)
      watchlist.value = watchlist.value.filter(w => w.ts_code !== tsCode)
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const fetchHistory = async (limit?: number) => {
    try {
      history.value = await memoryApi.getHistory(limit)
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const fetchProfile = async () => {
    try {
      profile.value = await memoryApi.getProfile()
    } catch (e) {
      // Error handled by interceptor
    }
  }

  return {
    preference,
    watchlist,
    history,
    profile,
    loading,
    fetchPreference,
    updatePreference,
    fetchWatchlist,
    addToWatchlist,
    removeFromWatchlist,
    fetchHistory,
    fetchProfile
  }
})
