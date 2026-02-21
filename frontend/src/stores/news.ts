import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { 
  newsAPI, 
  type NewsListResponse,
  type HotTopicsResponse,
  type SentimentAnalysisResponse
} from '@/api/news'
import { NewsCacheManager } from '@/utils/newsCache'
import type { 
  NewsItem, 
  NewsSentiment, 
  HotTopic, 
  NewsFilters, 
  UserPreferences,
  SentimentStats,
  NewsSortBy
} from '@/types/news'

export const useNewsStore = defineStore('news', () => {
  // State
  const newsItems = ref<NewsItem[]>([])
  const hotTopics = ref<HotTopic[]>([])
  const filters = ref<NewsFilters>({
    stock_codes: [],
    date_range: ['', ''],
    categories: [],
    sentiments: [],
    sources: [],
    keywords: ''
  })
  const userPreferences = ref<UserPreferences>({
    followed_stocks: [],
    default_filters: {
      stock_codes: [],
      date_range: ['', ''],
      categories: [],
      sentiments: [],
      sources: [],
      keywords: ''
    },
    notification_settings: {
      hot_topics: true,
      followed_stocks: true,
      sentiment_alerts: false
    }
  })
  
  // Loading states
  const loading = ref(false)
  const hotTopicsLoading = ref(false)
  const sentimentLoading = ref(false)
  
  // Pagination
  const currentPage = ref(1)
  const pageSize = ref(20)
  const total = ref(0)
  const hasMore = ref(true)
  
  // Sorting
  const sortBy = ref<NewsSortBy>('time')
  const sortOrder = ref<'asc' | 'desc'>('desc')
  
  // Selected news for detail view
  const selectedNews = ref<NewsItem | null>(null)
  const detailVisible = ref(false)

  // Stock mode
  const activeStockCode = ref<string | null>(null)
  const isStockMode = computed(() => !!activeStockCode.value)
  
  // Available options
  const availableCategories = ref<string[]>([])
  const availableSources = ref<string[]>([])

  // Cache
  const newsCache = new NewsCacheManager({
    maxAge: 5 * 60 * 1000,
    maxSize: 50
  })

  const normalizeStockCode = (code: string) => {
    const normalized = code.trim().toUpperCase()
    if (/^\d{6}$/.test(normalized)) {
      if (normalized.startsWith('6') || normalized.startsWith('9')) {
        return `${normalized}.SH`
      }
      return `${normalized}.SZ`
    }
    if (/^\d{5}$/.test(normalized)) {
      return `${normalized}.HK`
    }
    return normalized
  }

  // Computed
  const filteredNews = computed(() => {
    return newsItems.value.filter(item => {
      // 应用筛选逻辑
      if (filters.value.stock_codes.length > 0) {
        const hasMatchingStock = item.stock_codes.some(code => 
          filters.value.stock_codes.includes(code)
        )
        if (!hasMatchingStock) return false
      }
      
      if (filters.value.categories.length > 0) {
        if (!filters.value.categories.includes(item.category)) {
          return false
        }
      }
      
      if (filters.value.sentiments.length > 0) {
        if (!item.sentiment || !filters.value.sentiments.includes(item.sentiment.sentiment)) {
          return false
        }
      }
      
      if (filters.value.sources.length > 0) {
        if (!filters.value.sources.includes(item.source)) {
          return false
        }
      }
      
      if (filters.value.keywords) {
        const keyword = filters.value.keywords.toLowerCase()
        if (!item.title.toLowerCase().includes(keyword) && 
            !item.content.toLowerCase().includes(keyword)) {
          return false
        }
      }
      
      if (filters.value.date_range[0] && filters.value.date_range[1]) {
        const newsDate = new Date(item.publish_time)
        const startDate = new Date(filters.value.date_range[0])
        const endDate = new Date(filters.value.date_range[1])
        if (newsDate < startDate || newsDate > endDate) {
          return false
        }
      }
      
      return true
    })
  })
  
  const sentimentStats = computed((): SentimentStats => {
    const stats = { positive: 0, negative: 0, neutral: 0 }
    filteredNews.value.forEach(item => {
      if (item.sentiment) {
        stats[item.sentiment.sentiment]++
      }
    })
    return stats
  })
  
  const trendingTopics = computed(() => {
    return hotTopics.value
      .sort((a, b) => b.heat_score - a.heat_score)
      .slice(0, 10)
  })

  const getPrimaryStockCode = () => {
    return activeStockCode.value || filters.value.stock_codes[0] || null
  }

  const clearNewsResults = () => {
    newsItems.value = []
    total.value = 0
    hasMore.value = false
    currentPage.value = 1
  }

  const clearHotTopics = () => {
    hotTopics.value = []
  }

  // Actions
  const fetchMarketNews = async (params?: {
    page?: number
    page_size?: number
    category?: string
    reset?: boolean
  }) => {
    loading.value = true
    try {
      const requestParams = {
        page: params?.page || currentPage.value,
        page_size: params?.page_size || pageSize.value,
        category: params?.category,
        sort_by: sortBy.value,
        sort_order: sortOrder.value,
        ...filters.value
      }

      const isFirstPage = (params?.page || currentPage.value) === 1
      const shouldBypassCache = params?.reset === true

      if (isFirstPage && !shouldBypassCache) {
        const cached = newsCache.get<NewsListResponse>('market-news', requestParams)
        if (cached) {
          newsItems.value = cached.data
          total.value = cached.total
          hasMore.value = cached.has_more
          currentPage.value = cached.page
          return
        }
      }
      
      const response = await newsAPI.getNewsList(requestParams)
      
      if (params?.reset || params?.page === 1) {
        newsItems.value = response.data
      } else {
        newsItems.value.push(...response.data)
      }
      
      total.value = response.total
      hasMore.value = response.has_more
      currentPage.value = response.page

      if (isFirstPage) {
        newsCache.set('market-news', requestParams, response)
      }
    } catch (e) {
      console.error('Failed to fetch market news:', e)
    } finally {
      loading.value = false
    }
  }
  
  const fetchNewsByStock = async (stockCode: string, days: number = 30) => {
    loading.value = true
    try {
      const normalizedCode = normalizeStockCode(stockCode)
      const response = await newsAPI.getNewsByStock({
        stock_code: normalizedCode,
        days,
        limit: pageSize.value
      })
      newsItems.value = response.data
      total.value = response.total
      hasMore.value = false
      currentPage.value = 1
      activeStockCode.value = normalizedCode
      filters.value.stock_codes = [normalizedCode]
    } catch (e) {
      console.error('Failed to fetch stock news:', e)
    } finally {
      loading.value = false
    }
  }
  
  const fetchHotTopics = async (limit: number = 10, stockCode?: string) => {
    hotTopicsLoading.value = true
    try {
      const normalizedCode = stockCode ? normalizeStockCode(stockCode) : activeStockCode.value
      const response = await newsAPI.getHotTopics({
        limit,
        stock_code: normalizedCode || undefined,
        days: 7
      })
      hotTopics.value = response.data
    } catch (e) {
      console.error('Failed to fetch hot topics:', e)
    } finally {
      hotTopicsLoading.value = false
    }
  }
  
  const searchNews = async (keyword: string, reset: boolean = true) => {
    loading.value = true
    try {
      const response = await newsAPI.searchNews({
        keyword,
        filters: filters.value,
        limit: pageSize.value
      })
      
      if (reset) {
        newsItems.value = response.data
        currentPage.value = 1
      } else {
        newsItems.value.push(...response.data)
      }
      
      total.value = response.total
      hasMore.value = response.has_more
    } catch (e) {
      console.error('Failed to search news:', e)
    } finally {
      loading.value = false
    }
  }
  
  const analyzeSentiment = async (newsItems: NewsItem[], stockContext?: string) => {
    sentimentLoading.value = true
    try {
      const response = await newsAPI.analyzeSentiment({
        news_items: newsItems,
        stock_context: stockContext
      })
      return response.data
    } catch (e) {
      console.error('Failed to analyze sentiment:', e)
      return []
    } finally {
      sentimentLoading.value = false
    }
  }
  
  const loadMoreNews = async () => {
    if (!hasMore.value || loading.value) return
    if (activeStockCode.value) return
    
    currentPage.value += 1
    await fetchMarketNews({
      page: currentPage.value,
      reset: false
    })
  }
  
  const refreshNews = async () => {
    currentPage.value = 1
    const stockCode = getPrimaryStockCode()
    if (stockCode) {
      await fetchNewsByStock(stockCode, 30)
      return
    }
    await fetchMarketNews({ page: 1, reset: true })
  }
  
  const applyFilters = async (newFilters: Partial<NewsFilters>) => {
    const mergedFilters = { ...filters.value, ...newFilters }
    if (mergedFilters.stock_codes.length > 0) {
      mergedFilters.stock_codes = mergedFilters.stock_codes
        .map(code => (code ? normalizeStockCode(code) : code))
        .filter(code => !!code) as string[]
    }
    filters.value = mergedFilters
    currentPage.value = 1

    const nextStockCode = mergedFilters.stock_codes[0]
    if (nextStockCode) {
      await fetchNewsByStock(nextStockCode, 30)
      return
    }

    setActiveStockCode(null)
    clearNewsResults()
  }
  
  const clearFilters = async () => {
    filters.value = {
      stock_codes: [],
      date_range: ['', ''],
      categories: [],
      sentiments: [],
      sources: [],
      keywords: ''
    }
    currentPage.value = 1
    setActiveStockCode(null)
    clearNewsResults()
  }
  
  const setSortBy = async (newSortBy: NewsSortBy, newSortOrder: 'asc' | 'desc' = 'desc') => {
    sortBy.value = newSortBy
    sortOrder.value = newSortOrder
    currentPage.value = 1

    const stockCode = getPrimaryStockCode()
    if (stockCode) {
      await fetchNewsByStock(stockCode, 30)
      return
    }

    clearNewsResults()
  }
  
  const showNewsDetail = (news: NewsItem) => {
    selectedNews.value = news
    detailVisible.value = true
  }

  const setActiveStockCode = (stockCode?: string | null) => {
    if (!stockCode) {
      activeStockCode.value = null
      filters.value.stock_codes = []
      return
    }
    const normalized = normalizeStockCode(stockCode)
    activeStockCode.value = normalized
    if (filters.value.stock_codes.length !== 1 || filters.value.stock_codes[0] !== normalized) {
      filters.value.stock_codes = [normalized]
    }
  }
  
  const hideNewsDetail = () => {
    selectedNews.value = null
    detailVisible.value = false
  }
  
  const addFollowedStock = (stockCode: string) => {
    if (!userPreferences.value.followed_stocks.includes(stockCode)) {
      userPreferences.value.followed_stocks.push(stockCode)
      // TODO: 保存到后端
    }
  }
  
  const removeFollowedStock = (stockCode: string) => {
    const index = userPreferences.value.followed_stocks.indexOf(stockCode)
    if (index > -1) {
      userPreferences.value.followed_stocks.splice(index, 1)
      // TODO: 保存到后端
    }
  }
  
  const fetchFollowedStockNews = async () => {
    if (userPreferences.value.followed_stocks.length === 0) return
    
    loading.value = true
    try {
      const response = await newsAPI.getFollowedStockNews({
        stock_codes: userPreferences.value.followed_stocks,
        limit: pageSize.value,
        days: 7
      })
      newsItems.value = response.data
      total.value = response.total
      hasMore.value = response.has_more
    } catch (e) {
      console.error('Failed to fetch followed stock news:', e)
    } finally {
      loading.value = false
    }
  }
  
  const fetchAvailableOptions = async () => {
    const extractValues = (resp: any): string[] => {
      const data = resp?.data ?? resp
      if (!Array.isArray(data)) return []
      return data
        .map((item: any) => (typeof item === 'string' ? item : item?.value))
        .filter((v: any) => typeof v === 'string' && v.length > 0)
    }

    try {
      const [categoriesResp, sourcesResp] = await Promise.all([
        newsAPI.getCategories(),
        newsAPI.getSources()
      ])

      availableCategories.value = extractValues(categoriesResp).filter((v) => v !== 'all')
      availableSources.value = extractValues(sourcesResp).filter((v) => v !== 'all')
    } catch (e) {
      console.error('Failed to fetch available options:', e)
    }
  }
  
  const favoriteNews = async (newsId: string) => {
    try {
      await newsAPI.favoriteNews(newsId)
      // 更新本地状态
      const news = newsItems.value.find(item => item.id === newsId)
      if (news) {
        // TODO: 添加 favorited 字段到 NewsItem 接口
      }
    } catch (e) {
      console.error('Failed to favorite news:', e)
    }
  }
  
  const unfavoriteNews = async (newsId: string) => {
    try {
      await newsAPI.unfavoriteNews(newsId)
      // 更新本地状态
      const news = newsItems.value.find(item => item.id === newsId)
      if (news) {
        // TODO: 移除 favorited 字段
      }
    } catch (e) {
      console.error('Failed to unfavorite news:', e)
    }
  }

  return {
    // State
    newsItems,
    hotTopics,
    filters,
    userPreferences,
    loading,
    hotTopicsLoading,
    sentimentLoading,
    currentPage,
    pageSize,
    total,
    hasMore,
    sortBy,
    sortOrder,
    selectedNews,
    detailVisible,
    availableCategories,
    availableSources,
    activeStockCode,
    isStockMode,
    
    // Computed
    filteredNews,
    sentimentStats,
    trendingTopics,
    
    // Actions
    fetchMarketNews,
    fetchNewsByStock,
    fetchHotTopics,
    searchNews,
    analyzeSentiment,
    loadMoreNews,
    refreshNews,
    applyFilters,
    clearFilters,
    setSortBy,
    showNewsDetail,
    hideNewsDetail,
    setActiveStockCode,
    addFollowedStock,
    removeFollowedStock,
    fetchFollowedStockNews,
    fetchAvailableOptions,
    favoriteNews,
    unfavoriteNews,
    clearNewsResults,
    clearHotTopics
  }
})
