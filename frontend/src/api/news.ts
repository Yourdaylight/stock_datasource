import { request } from '@/utils/request'
import { 
  safeApiCall, 
  withRetry, 
  validateNewsItems, 
  validateHotTopics,
  validateNewsSentiment,
  NewsErrorType
} from '@/utils/newsErrorHandler'
import type {
  NewsItem,
  NewsSentiment,
  HotTopic,
  NewsFilters,
  GetNewsByStockParams,
  GetMarketNewsParams,
  GetHotTopicsParams,
  AnalyzeSentimentParams,
  SearchNewsParams
} from '@/types/news'

export interface NewsListResponse {
  total: number
  page: number
  page_size: number
  data: NewsItem[]
  has_more: boolean
}

export interface HotTopicsResponse {
  data: HotTopic[]
  update_time: string
}

export interface SentimentAnalysisResponse {
  data: NewsSentiment[]
  success: boolean
}

export const newsAPI = {
  // 获取股票相关新闻
  getNewsByStock(params: GetNewsByStockParams): Promise<NewsListResponse> {
    const queryParams = new URLSearchParams()
    if (params.days) queryParams.append('days', params.days.toString())
    if (params.limit) queryParams.append('limit', params.limit.toString())
    
    const queryString = queryParams.toString()
    const url = `/api/news/stock/${params.stock_code}${queryString ? '?' + queryString : ''}`
    
    return safeApiCall(
      async () => {
        const response = await withRetry(() => request.get(url), {
          maxRetries: 2,
          retryableErrors: [NewsErrorType.NETWORK_ERROR, NewsErrorType.TIMEOUT_ERROR]
        })
        
        // 验证数据格式
        if (response.data) {
          response.data = validateNewsItems(response.data)
        }
        
        return response
      },
      { showError: true }
    ) as Promise<NewsListResponse>
  },

  // 获取市场新闻
  getMarketNews(params: GetMarketNewsParams = {}): Promise<NewsListResponse> {
    const queryParams = new URLSearchParams()
    if (params.category) queryParams.append('category', params.category)
    if (params.limit) queryParams.append('limit', params.limit.toString())
    if (params.offset) queryParams.append('offset', params.offset.toString())
    
    const queryString = queryParams.toString()
    const url = `/api/news/market${queryString ? '?' + queryString : ''}`
    
    return safeApiCall(
      async () => {
        const response = await withRetry(() => request.get(url))
        
        // 验证数据格式
        if (response.data) {
          response.data = validateNewsItems(response.data)
        }
        
        return response
      },
      { 
        showError: true,
        fallbackValue: { total: 0, page: 1, page_size: 20, data: [], has_more: false }
      }
    ) as Promise<NewsListResponse>
  },

  // 获取热点话题
  getHotTopics(params: GetHotTopicsParams = {}): Promise<HotTopicsResponse> {
    const queryParams = new URLSearchParams()
    if (params.limit) queryParams.append('limit', params.limit.toString())
    
    const queryString = queryParams.toString()
    const url = `/api/news/hot-topics${queryString ? '?' + queryString : ''}`
    
    return safeApiCall(
      async () => {
        const response = await withRetry(() => request.get(url))
        
        // 验证数据格式
        if (response.data) {
          response.data = validateHotTopics(response.data)
        }
        
        return response
      },
      { 
        showError: true,
        fallbackValue: { data: [], update_time: new Date().toISOString() }
      }
    ) as Promise<HotTopicsResponse>
  },

  // 分析新闻情绪
  analyzeSentiment(data: AnalyzeSentimentParams): Promise<SentimentAnalysisResponse> {
    return safeApiCall(
      async () => {
        const response = await withRetry(() => request.post('/api/news/analyze-sentiment', data), {
          maxRetries: 1, // 情绪分析重试次数较少
          retryableErrors: [NewsErrorType.NETWORK_ERROR]
        })
        
        // 验证情绪分析结果
        if (response.data && Array.isArray(response.data)) {
          const validSentiments = response.data.filter((sentiment: any) => {
            try {
              return validateNewsSentiment(sentiment)
            } catch {
              return false
            }
          })
          response.data = validSentiments
        }
        
        return response
      },
      { 
        showError: true,
        fallbackValue: { data: [], success: false }
      }
    ) as Promise<SentimentAnalysisResponse>
  },

  // 搜索新闻
  searchNews(params: SearchNewsParams): Promise<NewsListResponse> {
    const queryParams = new URLSearchParams()
    queryParams.append('keyword', params.keyword)
    if (params.limit) queryParams.append('limit', params.limit.toString())
    
    // 处理筛选条件
    if (params.filters) {
      if (params.filters.stock_codes.length > 0) {
        queryParams.append('stock_codes', params.filters.stock_codes.join(','))
      }
      if (params.filters.date_range[0] && params.filters.date_range[1]) {
        queryParams.append('start_date', params.filters.date_range[0])
        queryParams.append('end_date', params.filters.date_range[1])
      }
      if (params.filters.categories.length > 0) {
        queryParams.append('categories', params.filters.categories.join(','))
      }
      if (params.filters.sentiments.length > 0) {
        queryParams.append('sentiments', params.filters.sentiments.join(','))
      }
      if (params.filters.sources.length > 0) {
        queryParams.append('sources', params.filters.sources.join(','))
      }
    }
    
    const url = `/api/news/search?${queryParams.toString()}`
    
    return safeApiCall(
      async () => {
        const response = await withRetry(() => request.get(url))
        
        // 验证数据格式
        if (response.data) {
          response.data = validateNewsItems(response.data)
        }
        
        return response
      },
      { 
        showError: true,
        fallbackValue: { total: 0, page: 1, page_size: 20, data: [], has_more: false }
      }
    ) as Promise<NewsListResponse>
  },

  // 获取新闻详情
  getNewsDetail(newsId: string): Promise<NewsItem> {
    return request.get(`/api/news/${newsId}`)
  },

  // 获取新闻分类列表
  getCategories(): Promise<string[]> {
    return request.get('/api/news/categories')
  },

  // 获取新闻来源列表
  getSources(): Promise<string[]> {
    return request.get('/api/news/sources')
  },

  // 批量获取新闻（支持分页）
  getNewsList(params: {
    page?: number
    page_size?: number
    category?: string
    source?: string
    sentiment?: string
    stock_codes?: string[]
    start_date?: string
    end_date?: string
    sort_by?: 'time' | 'heat' | 'sentiment'
    sort_order?: 'asc' | 'desc'
  } = {}): Promise<NewsListResponse> {
    const queryParams = new URLSearchParams()
    
    if (params.page) queryParams.append('page', params.page.toString())
    if (params.page_size) queryParams.append('page_size', params.page_size.toString())
    if (params.category) queryParams.append('category', params.category)
    if (params.source) queryParams.append('source', params.source)
    if (params.sentiment) queryParams.append('sentiment', params.sentiment)
    if (params.stock_codes && params.stock_codes.length > 0) {
      queryParams.append('stock_codes', params.stock_codes.join(','))
    }
    if (params.start_date) queryParams.append('start_date', params.start_date)
    if (params.end_date) queryParams.append('end_date', params.end_date)
    if (params.sort_by) queryParams.append('sort_by', params.sort_by)
    if (params.sort_order) queryParams.append('sort_order', params.sort_order)
    
    return request.get(`/api/news/list?${queryParams.toString()}`)
  },

  // 获取用户关注的股票新闻
  getFollowedStockNews(params: {
    stock_codes: string[]
    limit?: number
    days?: number
  }): Promise<NewsListResponse> {
    return request.post('/api/news/followed-stocks', params)
  },

  // 标记新闻为已读
  markAsRead(newsIds: string[]): Promise<{ success: boolean }> {
    return request.post('/api/news/mark-read', { news_ids: newsIds })
  },

  // 收藏新闻
  favoriteNews(newsId: string): Promise<{ success: boolean }> {
    return request.post(`/api/news/${newsId}/favorite`)
  },

  // 取消收藏新闻
  unfavoriteNews(newsId: string): Promise<{ success: boolean }> {
    return request.delete(`/api/news/${newsId}/favorite`)
  },

  // 获取收藏的新闻列表
  getFavoriteNews(params: {
    page?: number
    page_size?: number
  } = {}): Promise<NewsListResponse> {
    const queryParams = new URLSearchParams()
    if (params.page) queryParams.append('page', params.page.toString())
    if (params.page_size) queryParams.append('page_size', params.page_size.toString())
    
    return request.get(`/api/news/favorites?${queryParams.toString()}`)
  }
}