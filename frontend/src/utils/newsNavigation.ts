import { Router } from 'vue-router'
import type { NewsFilters } from '@/types/news'

// 新闻页面跳转工具类
export class NewsNavigationHelper {
  private router: Router

  constructor(router: Router) {
    this.router = router
  }

  // 跳转到新闻页面
  toNewsPage(filters?: Partial<NewsFilters>) {
    const query: Record<string, string> = {}
    
    if (filters) {
      if (filters.stock_codes && filters.stock_codes.length > 0) {
        query.stocks = filters.stock_codes.join(',')
      }
      if (filters.keywords) {
        query.keyword = filters.keywords
      }
      if (filters.categories && filters.categories.length > 0) {
        query.categories = filters.categories.join(',')
      }
      if (filters.sentiments && filters.sentiments.length > 0) {
        query.sentiments = filters.sentiments.join(',')
      }
      if (filters.date_range && filters.date_range[0] && filters.date_range[1]) {
        query.start_date = filters.date_range[0]
        query.end_date = filters.date_range[1]
      }
    }

    this.router.push({
      name: 'News',
      query
    })
  }

  // 跳转到股票相关新闻
  toStockNews(stockCode: string, days: number = 30) {
    this.toNewsPage({
      stock_codes: [stockCode],
      date_range: [
        new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        new Date().toISOString().split('T')[0]
      ]
    })
  }

  // 跳转到特定情绪的新闻
  toSentimentNews(sentiment: 'positive' | 'negative' | 'neutral', stockCode?: string) {
    this.toNewsPage({
      sentiments: [sentiment],
      stock_codes: stockCode ? [stockCode] : undefined
    })
  }

  // 跳转到热点话题相关新闻
  toTopicNews(topic: string, relatedStocks?: string[]) {
    this.toNewsPage({
      keywords: topic,
      stock_codes: relatedStocks
    })
  }

  // 跳转到特定类型的新闻
  toCategoryNews(category: string, stockCode?: string) {
    this.toNewsPage({
      categories: [category],
      stock_codes: stockCode ? [stockCode] : undefined
    })
  }

  // 从URL查询参数解析筛选条件
  parseFiltersFromQuery(query: Record<string, any>): Partial<NewsFilters> {
    const filters: Partial<NewsFilters> = {}

    if (query.stocks) {
      filters.stock_codes = query.stocks.split(',').filter(Boolean)
    }

    if (query.keyword) {
      filters.keywords = query.keyword
    }

    if (query.categories) {
      filters.categories = query.categories.split(',').filter(Boolean)
    }

    if (query.sentiments) {
      filters.sentiments = query.sentiments.split(',').filter(Boolean)
    }

    if (query.start_date && query.end_date) {
      filters.date_range = [query.start_date, query.end_date]
    }

    return filters
  }

  // 更新URL查询参数（不触发页面跳转）
  updateQuery(filters: Partial<NewsFilters>) {
    const query: Record<string, string> = {}
    
    if (filters.stock_codes && filters.stock_codes.length > 0) {
      query.stocks = filters.stock_codes.join(',')
    }
    if (filters.keywords) {
      query.keyword = filters.keywords
    }
    if (filters.categories && filters.categories.length > 0) {
      query.categories = filters.categories.join(',')
    }
    if (filters.sentiments && filters.sentiments.length > 0) {
      query.sentiments = filters.sentiments.join(',')
    }
    if (filters.date_range && filters.date_range[0] && filters.date_range[1]) {
      query.start_date = filters.date_range[0]
      query.end_date = filters.date_range[1]
    }

    this.router.replace({
      name: 'News',
      query
    })
  }
}

// 全局导航助手实例
let navigationHelper: NewsNavigationHelper | null = null

export const initNewsNavigation = (router: Router) => {
  navigationHelper = new NewsNavigationHelper(router)
  return navigationHelper
}

export const getNewsNavigation = (): NewsNavigationHelper => {
  if (!navigationHelper) {
    throw new Error('News navigation helper not initialized. Call initNewsNavigation first.')
  }
  return navigationHelper
}

// 便捷的导航函数
export const navigateToStockNews = (stockCode: string, days?: number) => {
  getNewsNavigation().toStockNews(stockCode, days)
}

export const navigateToSentimentNews = (sentiment: 'positive' | 'negative' | 'neutral', stockCode?: string) => {
  getNewsNavigation().toSentimentNews(sentiment, stockCode)
}

export const navigateToTopicNews = (topic: string, relatedStocks?: string[]) => {
  getNewsNavigation().toTopicNews(topic, relatedStocks)
}

export const navigateToCategoryNews = (category: string, stockCode?: string) => {
  getNewsNavigation().toCategoryNews(category, stockCode)
}

// 新闻页面组合式函数
export const useNewsNavigation = () => {
  const helper = getNewsNavigation()
  
  return {
    toNewsPage: helper.toNewsPage.bind(helper),
    toStockNews: helper.toStockNews.bind(helper),
    toSentimentNews: helper.toSentimentNews.bind(helper),
    toTopicNews: helper.toTopicNews.bind(helper),
    toCategoryNews: helper.toCategoryNews.bind(helper),
    parseFiltersFromQuery: helper.parseFiltersFromQuery.bind(helper),
    updateQuery: helper.updateQuery.bind(helper)
  }
}