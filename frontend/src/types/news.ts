// 新闻条目接口（与后端保持一致）
export interface NewsItem {
  id: string
  title: string
  content: string
  source: string
  publish_time: string
  stock_codes: string[]
  category: string
  url?: string
  sentiment?: NewsSentiment
}

// 情绪分析结果
export interface NewsSentiment {
  news_id: string
  sentiment: 'positive' | 'negative' | 'neutral'
  score: number // -1.0 到 1.0
  reasoning: string
  impact_level: 'high' | 'medium' | 'low'
}

// 热点话题
export interface HotTopic {
  topic: string
  keywords: string[]
  heat_score: number
  related_stocks: string[]
  news_count: number
}

// 筛选条件
export interface NewsFilters {
  stock_codes: string[]
  date_range: [string, string]
  categories: string[]
  sentiments: string[]
  sources: string[]
  keywords: string
}

// 用户偏好设置
export interface UserPreferences {
  followed_stocks: string[]
  default_filters: NewsFilters
  notification_settings: {
    hot_topics: boolean
    followed_stocks: boolean
    sentiment_alerts: boolean
  }
}

// API 请求参数接口
export interface GetNewsByStockParams {
  stock_code: string
  days?: number
  limit?: number
}

export interface GetMarketNewsParams {
  category?: string
  limit?: number
  offset?: number
}

export interface GetHotTopicsParams {
  limit?: number
  stock_code?: string
  days?: number
}

export interface AnalyzeSentimentParams {
  news_items: NewsItem[]
  stock_context?: string
}

export interface SearchNewsParams {
  keyword: string
  filters?: NewsFilters
  limit?: number
}

// 情绪统计数据
export interface SentimentStats {
  positive: number
  negative: number
  neutral: number
}

// 新闻排序方式
export type NewsSortBy = 'time' | 'heat' | 'sentiment'

// 新闻类别
export type NewsCategory = 'announcement' | 'news' | 'analysis' | 'research'

// 情绪类型
export type SentimentType = 'positive' | 'negative' | 'neutral'