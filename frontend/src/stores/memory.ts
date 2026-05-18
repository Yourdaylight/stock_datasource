import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'
import { memoryApi, type UserPreference, type WatchlistItem, type InteractionHistory, type UserProfile, type FactOutput, type ConclusionOutput } from '@/api/memory'

export const useMemoryStore = defineStore('memory', () => {
  // --- Existing state ---
  const preference = reactive<UserPreference>({
    risk_level: 'moderate',
    investment_style: 'balanced',
    favorite_sectors: []
  })
  const watchlist = ref<WatchlistItem[]>([])
  const history = ref<InteractionHistory[]>([])
  const profile = ref<UserProfile | null>(null)
  const loading = ref(false)

  // --- NEW: Facts & Conclusions state ---
  const facts = ref<FactOutput[]>([])
  const conclusions = ref<ConclusionOutput[]>([])

  // --- Computed: categorized facts ---

  /** Check if a unix-epoch timestamp (seconds) falls on today. */
  const isToday = (ts: number) => {
    const d = new Date(ts * 1000)
    const now = new Date()
    return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate()
  }

  const dailyFacts = computed(() => facts.value.filter(f => isToday(f.created_at)))

  const longTermFacts = computed(() => {
    const categories = ['risk_preference', 'sector_focus', 'stock_opinion', 'trading_style']
    return facts.value.filter(f => categories.includes(f.category) && f.confidence >= 0.6)
  })

  const scenarioFacts = computed(() => {
    const categories = ['market_signal', 'capital_flow', 'conclusion']
    return facts.value.filter(f => categories.includes(f.category))
  })

  /** Today's conclusions. */
  const dailyConclusions = computed(() => conclusions.value.filter(c => isToday(c.stored_at)))

  /** Summary counters for the profile header. */
  const memoryCounts = computed(() => ({
    facts: facts.value.length,
    conclusions: conclusions.value.length,
    interactions: history.value.length,
  }))

  // --- Existing actions ---
  const fetchPreference = async () => {
    try {
      const data = await memoryApi.getPreference()
      Object.assign(preference, data)
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const updatePreference = async (data: Partial<UserPreference>) => {
    try {
      await memoryApi.updatePreference(data)
      Object.assign(preference, data)
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const fetchWatchlist = async (group?: string) => {
    try {
      watchlist.value = await memoryApi.getWatchlist(group)
    } catch (e) {
      // Error handled by interceptor
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

  // --- NEW: Facts actions ---
  const fetchFacts = async (category?: string, limit?: number, minConfidence?: number) => {
    try {
      facts.value = await memoryApi.getFacts(category, limit || 50, minConfidence)
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const createFact = async (data: { content: string; category: string; confidence?: number; source?: string }) => {
    try {
      const newFact = await memoryApi.createFact(data)
      facts.value.unshift(newFact)
      return newFact
    } catch (e) {
      // Error handled by interceptor
      return null
    }
  }

  const deleteFact = async (factId: string) => {
    try {
      await memoryApi.deleteFact(factId)
      facts.value = facts.value.filter(f => f.id !== factId)
    } catch (e) {
      // Error handled by interceptor
    }
  }

  // --- NEW: Conclusions actions ---
  const fetchConclusions = async (limit?: number) => {
    try {
      conclusions.value = await memoryApi.getConclusions(limit || 20)
    } catch (e) {
      // Error handled by interceptor
    }
  }

  // --- NEW: Load all data at once ---
  const fetchAll = async () => {
    loading.value = true
    try {
      await Promise.all([
        fetchPreference(),
        fetchWatchlist(),
        fetchProfile(),
        fetchHistory(30),
        fetchFacts(undefined, 50, 0.3),
        fetchConclusions(20)
      ])
    } finally {
      loading.value = false
    }
  }

  return {
    // State
    preference,
    watchlist,
    history,
    profile,
    loading,
    facts,
    conclusions,
    // Computed
    dailyFacts,
    longTermFacts,
    scenarioFacts,
    dailyConclusions,
    memoryCounts,
    // Actions
    fetchPreference,
    updatePreference,
    fetchWatchlist,
    addToWatchlist,
    removeFromWatchlist,
    fetchHistory,
    fetchProfile,
    fetchFacts,
    createFact,
    deleteFact,
    fetchConclusions,
    fetchAll
  }
})
