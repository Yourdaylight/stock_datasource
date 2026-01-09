import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { screenerApi, type ScreenerCondition, type StockItem, type MarketSummary } from '@/api/screener'

export const useScreenerStore = defineStore('screener', () => {
  // Stock list data
  const stocks = ref<StockItem[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const totalPages = ref(0)
  const loading = ref(false)
  
  // Sorting
  const sortBy = ref('pct_chg')
  const sortOrder = ref<'asc' | 'desc'>('desc')
  
  // Search
  const searchQuery = ref('')
  
  // Market summary
  const summary = ref<MarketSummary | null>(null)
  
  // Filter conditions
  const conditions = ref<ScreenerCondition[]>([])
  
  // Computed results for backward compatibility
  const results = computed(() => stocks.value.map(s => ({
    ts_code: s.ts_code,
    name: s.ts_code, // We don't have name in current data
    close: s.close,
    pct_chg: s.pct_chg,
    pe: s.pe_ttm,
    pb: s.pb,
    turnover_rate: s.turnover_rate,
  })))

  // Fetch stocks with pagination
  const fetchStocks = async (options: {
    page?: number
    pageSize?: number
    sortBy?: string
    sortOrder?: 'asc' | 'desc'
    search?: string
  } = {}) => {
    loading.value = true
    try {
      const response = await screenerApi.getStocks({
        page: options.page || page.value,
        page_size: options.pageSize || pageSize.value,
        sort_by: options.sortBy || sortBy.value,
        sort_order: options.sortOrder || sortOrder.value,
        search: options.search ?? searchQuery.value,
      })
      
      stocks.value = response.items
      total.value = response.total
      page.value = response.page
      pageSize.value = response.page_size
      totalPages.value = response.total_pages
    } catch (e) {
      console.error('Failed to fetch stocks:', e)
    } finally {
      loading.value = false
    }
  }
  
  // Fetch market summary
  const fetchSummary = async () => {
    try {
      summary.value = await screenerApi.getSummary()
    } catch (e) {
      console.error('Failed to fetch summary:', e)
    }
  }
  
  // Change page
  const changePage = async (newPage: number) => {
    page.value = newPage
    await fetchStocks({ page: newPage })
  }
  
  // Change page size
  const changePageSize = async (newSize: number) => {
    pageSize.value = newSize
    page.value = 1
    await fetchStocks({ page: 1, pageSize: newSize })
  }
  
  // Change sort
  const changeSort = async (field: string, order: 'asc' | 'desc') => {
    sortBy.value = field
    sortOrder.value = order
    page.value = 1
    await fetchStocks({ page: 1, sortBy: field, sortOrder: order })
  }
  
  // Search stocks
  const search = async (query: string) => {
    searchQuery.value = query
    page.value = 1
    await fetchStocks({ page: 1, search: query })
  }

  // Filter with conditions
  const filter = async (conds: ScreenerCondition[]) => {
    loading.value = true
    conditions.value = conds
    try {
      const response = await screenerApi.filter(
        { conditions: conds, sort_by: sortBy.value, sort_order: sortOrder.value },
        1,
        pageSize.value
      )
      stocks.value = response.items
      total.value = response.total
      page.value = response.page
      totalPages.value = response.total_pages
    } catch (e) {
      console.error('Failed to filter stocks:', e)
    } finally {
      loading.value = false
    }
  }

  // Natural language screener
  const nlScreener = async (query: string) => {
    loading.value = true
    try {
      const response = await screenerApi.nlScreener({ query }, 1, pageSize.value)
      stocks.value = response.items
      total.value = response.total
      page.value = response.page
      totalPages.value = response.total_pages
    } catch (e) {
      console.error('Failed to run NL screener:', e)
    } finally {
      loading.value = false
    }
  }

  // Apply preset strategy
  const applyPreset = async (presetId: string) => {
    loading.value = true
    try {
      const presets = await screenerApi.getPresets()
      const preset = presets.find(p => p.id === presetId)
      if (preset) {
        conditions.value = preset.conditions
        const response = await screenerApi.filter(
          { conditions: preset.conditions, sort_by: sortBy.value, sort_order: sortOrder.value },
          1,
          pageSize.value
        )
        stocks.value = response.items
        total.value = response.total
        page.value = response.page
        totalPages.value = response.total_pages
      }
    } catch (e) {
      console.error('Failed to apply preset:', e)
    } finally {
      loading.value = false
    }
  }
  
  // Clear filters and show all stocks
  const clearFilters = async () => {
    conditions.value = []
    searchQuery.value = ''
    page.value = 1
    await fetchStocks({ page: 1, search: '' })
  }

  return {
    // State
    stocks,
    results, // backward compatibility
    total,
    page,
    pageSize,
    totalPages,
    loading,
    sortBy,
    sortOrder,
    searchQuery,
    summary,
    conditions,
    
    // Actions
    fetchStocks,
    fetchSummary,
    changePage,
    changePageSize,
    changeSort,
    search,
    filter,
    nlScreener,
    applyPreset,
    clearFilters,
  }
})
