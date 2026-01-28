import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { 
  newsAPI, 
  type NewsListResponse,
  type HotTopicsResponse,
  type SentimentAnalysisResponse
} from '@/api/news'
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
  
  // Available options
  const availableCategories = ref<string[]>([])
  const availableSources = ref<string[]>([])

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
      
      const response = await newsAPI.getNewsList(requestParams)
      
      if (params?.reset || params?.page === 1) {
        newsItems.value = response.data
      } else {
        newsItems.value.push(...response.data)
      }
      
      total.value = response.total
      hasMore.value = response.has_more
      currentPage.value = response.page
    } catch (e) {
      console.error('Failed to fetch market news:', e)
    } finally {
      loading.value = false
    }
  }
  
  const fetchNewsByStock = async (stockCode: string, days: number = 30) => {
    loading.value = true
    try {
      const response = await newsAPI.getNewsByStock({
        stock_code: stockCode,
        days,
        limit: pageSize.value
      })
      newsItems.value = response.data
      total.value = response.total
      hasMore.value = response.has_more
    } catch (e) {
      console.error('Failed to fetch stock news:', e)
    } finally {
      loading.value = false
    }
  }
  
  const fetchHotTopics = async (limit: number = 10) => {
    hotTopicsLoading.value = true
    try {
      const response = await newsAPI.getHotTopics({ limit })
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
    
    currentPage.value += 1
    await fetchMarketNews({
      page: currentPage.value,
      reset: false
    })
  }
  
  const refreshNews = async () => {
    currentPage.value = 1
    await fetchMarketNews({
      page: 1,
      reset: true
    })
  }
  
  const applyFilters = async (newFilters: Partial<NewsFilters>) => {
    filters.value = { ...filters.value, ...newFilters }
    currentPage.value = 1
    await fetchMarketNews({
      page: 1,
      reset: true
    })
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
    await fetchMarketNews({
      page: 1,
      reset: true
    })
  }
  
  const setSortBy = async (newSortBy: NewsSortBy, newSortOrder: 'asc' | 'desc' = 'desc') => {
    sortBy.value = newSortBy
    sortOrder.value = newSortOrder
    currentPage.value = 1
    await fetchMarketNews({
      page: 1,
      reset: true
    })
  }
  
  const showNewsDetail = (news: NewsItem) => {
    selectedNews.value = news
    detailVisible.value = true
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
    try {
      const [categories, sources] = await Promise.all([
        newsAPI.getCategories(),
        newsAPI.getSources()
      ])
      availableCategories.value = categories
      availableSources.value = sources
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
    addFollowedStock,
    removeFollowedStock,
    fetchFollowedStockNews,
    fetchAvailableOptions,
    favoriteNews,
    unfavoriteNews
  }
})