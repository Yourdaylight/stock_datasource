import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { 
  screenerApi, 
  type ScreenerCondition, 
  type StockItem, 
  type MarketSummary,
  type StockProfile,
  type Recommendation,
  type RecommendationResponse,
  type SectorInfo,
  type NLScreenerResponse,
} from '@/api/screener'

export const useScreenerStore = defineStore('screener', () => {
  // =============================================================================
  // 股票列表状态
  // =============================================================================
  const stocks = ref<StockItem[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const totalPages = ref(0)
  const loading = ref(false)
  
  // 排序
  const sortBy = ref('pct_chg')
  const sortOrder = ref<'asc' | 'desc'>('desc')
  
  // 搜索
  const searchQuery = ref('')
  
  // 市场概况
  const summary = ref<MarketSummary | null>(null)
  
  // 筛选条件
  const conditions = ref<ScreenerCondition[]>([])
  
  // =============================================================================
  // 十维画像状态
  // =============================================================================
  const currentProfile = ref<StockProfile | null>(null)
  const profileLoading = ref(false)
  const profileCache = ref<Record<string, StockProfile>>({})
  
  // =============================================================================
  // 推荐状态
  // =============================================================================
  const recommendations = ref<RecommendationResponse | null>(null)
  const recommendationsLoading = ref(false)
  
  // =============================================================================
  // 行业状态
  // =============================================================================
  const sectors = ref<SectorInfo[]>([])
  const selectedSector = ref<string | null>(null)
  const sectorsLoading = ref(false)
  
  // =============================================================================
  // NL选股状态
  // =============================================================================
  const nlExplanation = ref('')
  const parsedConditions = ref<ScreenerCondition[]>([])
  
  // =============================================================================
  // 兼容性计算属性
  // =============================================================================
  const results = computed(() => stocks.value.map(s => ({
    ts_code: s.ts_code,
    name: s.stock_name || s.ts_code,
    close: s.close,
    pct_chg: s.pct_chg,
    pe: s.pe_ttm,
    pb: s.pb,
    turnover_rate: s.turnover_rate,
    industry: s.industry,
  })))

  // =============================================================================
  // 股票列表操作
  // =============================================================================

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
  
  const fetchSummary = async () => {
    try {
      summary.value = await screenerApi.getSummary()
    } catch (e) {
      console.error('Failed to fetch summary:', e)
    }
  }
  
  const changePage = async (newPage: number) => {
    page.value = newPage
    await fetchStocks({ page: newPage })
  }
  
  const changePageSize = async (newSize: number) => {
    pageSize.value = newSize
    page.value = 1
    await fetchStocks({ page: 1, pageSize: newSize })
  }
  
  const changeSort = async (field: string, order: 'asc' | 'desc') => {
    sortBy.value = field
    sortOrder.value = order
    page.value = 1
    await fetchStocks({ page: 1, sortBy: field, sortOrder: order })
  }
  
  const search = async (query: string) => {
    searchQuery.value = query
    page.value = 1
    await fetchStocks({ page: 1, search: query })
  }

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

  const nlScreener = async (query: string) => {
    loading.value = true
    try {
      const response: NLScreenerResponse = await screenerApi.nlScreener({ query }, 1, pageSize.value)
      stocks.value = response.items
      total.value = response.total
      page.value = response.page
      totalPages.value = response.total_pages
      nlExplanation.value = response.explanation
      parsedConditions.value = response.parsed_conditions
    } catch (e) {
      console.error('Failed to run NL screener:', e)
    } finally {
      loading.value = false
    }
  }

  const applyPreset = async (presetId: string) => {
    loading.value = true
    try {
      const response = await screenerApi.applyPreset(presetId, 1, pageSize.value)
      stocks.value = response.items
      total.value = response.total
      page.value = response.page
      totalPages.value = response.total_pages
    } catch (e) {
      console.error('Failed to apply preset:', e)
    } finally {
      loading.value = false
    }
  }
  
  const clearFilters = async () => {
    conditions.value = []
    searchQuery.value = ''
    nlExplanation.value = ''
    parsedConditions.value = []
    page.value = 1
    await fetchStocks({ page: 1, search: '' })
  }

  // =============================================================================
  // 十维画像操作
  // =============================================================================

  const fetchProfile = async (tsCode: string) => {
    // 检查缓存
    if (profileCache.value[tsCode]) {
      currentProfile.value = profileCache.value[tsCode]
      return currentProfile.value
    }
    
    profileLoading.value = true
    try {
      const profile = await screenerApi.getProfile(tsCode)
      currentProfile.value = profile
      profileCache.value[tsCode] = profile
      return profile
    } catch (e) {
      console.error('Failed to fetch profile:', e)
      return null
    } finally {
      profileLoading.value = false
    }
  }

  const batchFetchProfiles = async (tsCodes: string[]) => {
    profileLoading.value = true
    try {
      const profiles = await screenerApi.batchGetProfiles(tsCodes)
      // 更新缓存
      profiles.forEach(p => {
        profileCache.value[p.ts_code] = p
      })
      return profiles
    } catch (e) {
      console.error('Failed to batch fetch profiles:', e)
      return []
    } finally {
      profileLoading.value = false
    }
  }

  const clearCurrentProfile = () => {
    currentProfile.value = null
  }

  // =============================================================================
  // 推荐操作
  // =============================================================================

  const fetchRecommendations = async () => {
    recommendationsLoading.value = true
    try {
      recommendations.value = await screenerApi.getRecommendations()
    } catch (e) {
      console.error('Failed to fetch recommendations:', e)
    } finally {
      recommendationsLoading.value = false
    }
  }

  // =============================================================================
  // 行业操作
  // =============================================================================

  const fetchSectors = async () => {
    sectorsLoading.value = true
    try {
      const response = await screenerApi.getSectors()
      sectors.value = response.sectors
    } catch (e) {
      console.error('Failed to fetch sectors:', e)
    } finally {
      sectorsLoading.value = false
    }
  }

  const filterBySector = async (sector: string) => {
    selectedSector.value = sector
    loading.value = true
    try {
      const response = await screenerApi.getSectorStocks(sector, {
        page: 1,
        page_size: pageSize.value,
        sort_by: sortBy.value,
        sort_order: sortOrder.value,
      })
      stocks.value = response.items
      total.value = response.total
      page.value = response.page
      totalPages.value = response.total_pages
    } catch (e) {
      console.error('Failed to filter by sector:', e)
    } finally {
      loading.value = false
    }
  }

  const clearSectorFilter = async () => {
    selectedSector.value = null
    await fetchStocks({ page: 1 })
  }

  return {
    // 股票列表状态
    stocks,
    results,
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
    
    // 画像状态
    currentProfile,
    profileLoading,
    profileCache,
    
    // 推荐状态
    recommendations,
    recommendationsLoading,
    
    // 行业状态
    sectors,
    selectedSector,
    sectorsLoading,
    
    // NL选股状态
    nlExplanation,
    parsedConditions,
    
    // 股票列表操作
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
    
    // 画像操作
    fetchProfile,
    batchFetchProfiles,
    clearCurrentProfile,
    
    // 推荐操作
    fetchRecommendations,
    
    // 行业操作
    fetchSectors,
    filterBySector,
    clearSectorFilter,
  }
})
