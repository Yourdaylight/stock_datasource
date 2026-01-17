import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  thsIndexApi,
  type THSIndexItem,
  type THSRankingItem,
  type THSDailyItem,
  type THSStatsItem,
  INDEX_TYPE_LABELS,
} from '@/api/thsIndex'

export const useThsIndexStore = defineStore('thsIndex', () => {
  // State
  const indexList = ref<THSIndexItem[]>([])
  const indexTotal = ref(0)
  const rankingList = ref<THSRankingItem[]>([])
  const tradeDate = ref('')
  const selectedIndex = ref<THSIndexItem | null>(null)
  const selectedIndexDaily = ref<THSDailyItem[]>([])
  const stats = ref<THSStatsItem[]>([])
  
  const loading = ref(false)
  const rankingLoading = ref(false)
  const dailyLoading = ref(false)

  // Filter state
  const currentExchange = ref<string>('A')
  const currentType = ref<string>('')
  const currentSortBy = ref<'pct_change' | 'vol' | 'turnover_rate'>('pct_change')
  const currentOrder = ref<'desc' | 'asc'>('desc')

  // Computed
  const typeLabel = computed(() => (type: string) => {
    return INDEX_TYPE_LABELS[type] || type || '未知'
  })

  // Get heatmap data (top N by absolute pct_change)
  const heatmapData = computed(() => {
    return rankingList.value.map(item => ({
      name: item.name,
      value: item.pct_change || 0,
      ts_code: item.ts_code,
      type: item.type,
      count: item.count,
      close: item.close,
      vol: item.vol,
      turnover_rate: item.turnover_rate,
    }))
  })

  // Actions
  const fetchIndexList = async (params: {
    exchange?: string
    type?: string
    limit?: number
    offset?: number
  } = {}) => {
    loading.value = true
    try {
      const result = await thsIndexApi.getIndexList({
        exchange: params.exchange || currentExchange.value || undefined,
        type: params.type || currentType.value || undefined,
        limit: params.limit || 100,
        offset: params.offset || 0,
      })
      indexList.value = result.data
      indexTotal.value = result.total
      if (params.exchange) currentExchange.value = params.exchange
      if (params.type) currentType.value = params.type
    } catch (e) {
      console.error('Failed to fetch index list:', e)
    } finally {
      loading.value = false
    }
  }

  const fetchRanking = async (params: {
    date?: string
    type?: string
    sort_by?: 'pct_change' | 'vol' | 'turnover_rate'
    order?: 'desc' | 'asc'
    limit?: number
  } = {}) => {
    rankingLoading.value = true
    try {
      const result = await thsIndexApi.getRanking({
        date: params.date,
        type: params.type || currentType.value || undefined,
        sort_by: params.sort_by || currentSortBy.value,
        order: params.order || currentOrder.value,
        limit: params.limit || 50,
      })
      rankingList.value = result.data
      tradeDate.value = result.trade_date
      if (params.sort_by) currentSortBy.value = params.sort_by
      if (params.order) currentOrder.value = params.order
      if (params.type !== undefined) currentType.value = params.type
    } catch (e) {
      console.error('Failed to fetch ranking:', e)
    } finally {
      rankingLoading.value = false
    }
  }

  const fetchIndexDetail = async (tsCode: string) => {
    try {
      selectedIndex.value = await thsIndexApi.getIndexDetail(tsCode)
    } catch (e) {
      console.error('Failed to fetch index detail:', e)
      selectedIndex.value = null
    }
  }

  const fetchDailyData = async (tsCode: string, params: {
    start_date?: string
    end_date?: string
    limit?: number
  } = {}) => {
    dailyLoading.value = true
    try {
      const result = await thsIndexApi.getDailyData(tsCode, {
        limit: params.limit || 30,
        start_date: params.start_date,
        end_date: params.end_date,
      })
      selectedIndexDaily.value = result.data
      // Update selected index name if available
      if (result.name && selectedIndex.value) {
        selectedIndex.value.name = result.name
      }
    } catch (e) {
      console.error('Failed to fetch daily data:', e)
      selectedIndexDaily.value = []
    } finally {
      dailyLoading.value = false
    }
  }

  const searchIndex = async (keyword: string) => {
    loading.value = true
    try {
      const result = await thsIndexApi.searchIndex(keyword)
      indexList.value = result.data
      indexTotal.value = result.data.length
    } catch (e) {
      console.error('Failed to search index:', e)
    } finally {
      loading.value = false
    }
  }

  const fetchStats = async () => {
    try {
      const result = await thsIndexApi.getStats()
      stats.value = result.data
    } catch (e) {
      console.error('Failed to fetch stats:', e)
    }
  }

  const setFilters = (params: {
    exchange?: string
    type?: string
    sort_by?: 'pct_change' | 'vol' | 'turnover_rate'
    order?: 'desc' | 'asc'
  }) => {
    if (params.exchange !== undefined) currentExchange.value = params.exchange
    if (params.type !== undefined) currentType.value = params.type
    if (params.sort_by !== undefined) currentSortBy.value = params.sort_by
    if (params.order !== undefined) currentOrder.value = params.order
  }

  const clearSelectedIndex = () => {
    selectedIndex.value = null
    selectedIndexDaily.value = []
  }

  return {
    // State
    indexList,
    indexTotal,
    rankingList,
    tradeDate,
    selectedIndex,
    selectedIndexDaily,
    stats,
    loading,
    rankingLoading,
    dailyLoading,
    currentExchange,
    currentType,
    currentSortBy,
    currentOrder,

    // Computed
    typeLabel,
    heatmapData,

    // Actions
    fetchIndexList,
    fetchRanking,
    fetchIndexDetail,
    fetchDailyData,
    searchIndex,
    fetchStats,
    setFilters,
    clearSelectedIndex,
  }
})
