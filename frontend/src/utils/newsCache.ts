import type { NewsItem, HotTopic } from '@/types/news'

// 缓存配置
interface CacheConfig {
  maxAge: number // 缓存最大存活时间（毫秒）
  maxSize: number // 缓存最大条目数
}

interface CacheItem<T> {
  data: T
  timestamp: number
  key: string
}

// 默认缓存配置
const DEFAULT_CACHE_CONFIG: CacheConfig = {
  maxAge: 5 * 60 * 1000, // 5分钟
  maxSize: 100
}

// 新闻缓存管理器
export class NewsCacheManager {
  private cache = new Map<string, CacheItem<any>>()
  private config: CacheConfig

  constructor(config: Partial<CacheConfig> = {}) {
    this.config = { ...DEFAULT_CACHE_CONFIG, ...config }
  }

  // 生成缓存键
  private generateKey(prefix: string, params: Record<string, any>): string {
    const sortedParams = Object.keys(params)
      .sort()
      .map(key => `${key}=${JSON.stringify(params[key])}`)
      .join('&')
    return `${prefix}:${sortedParams}`
  }

  // 检查缓存是否过期
  private isExpired(item: CacheItem<any>): boolean {
    return Date.now() - item.timestamp > this.config.maxAge
  }

  // 清理过期缓存
  private cleanup(): void {
    const now = Date.now()
    for (const [key, item] of this.cache.entries()) {
      if (now - item.timestamp > this.config.maxAge) {
        this.cache.delete(key)
      }
    }
  }

  // 限制缓存大小
  private enforceMaxSize(): void {
    if (this.cache.size <= this.config.maxSize) return

    // 按时间戳排序，删除最旧的条目
    const entries = Array.from(this.cache.entries())
      .sort((a, b) => a[1].timestamp - b[1].timestamp)

    const toDelete = entries.slice(0, this.cache.size - this.config.maxSize)
    toDelete.forEach(([key]) => this.cache.delete(key))
  }

  // 设置缓存
  set<T>(prefix: string, params: Record<string, any>, data: T): void {
    const key = this.generateKey(prefix, params)
    
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      key
    })

    this.cleanup()
    this.enforceMaxSize()
  }

  // 获取缓存
  get<T>(prefix: string, params: Record<string, any>): T | null {
    const key = this.generateKey(prefix, params)
    const item = this.cache.get(key)

    if (!item) return null

    if (this.isExpired(item)) {
      this.cache.delete(key)
      return null
    }

    return item.data as T
  }

  // 删除特定缓存
  delete(prefix: string, params: Record<string, any>): boolean {
    const key = this.generateKey(prefix, params)
    return this.cache.delete(key)
  }

  // 删除前缀匹配的所有缓存
  deleteByPrefix(prefix: string): number {
    let deleted = 0
    for (const [key] of this.cache.entries()) {
      if (key.startsWith(prefix + ':')) {
        this.cache.delete(key)
        deleted++
      }
    }
    return deleted
  }

  // 清空所有缓存
  clear(): void {
    this.cache.clear()
  }

  // 获取缓存统计信息
  getStats(): {
    size: number
    maxSize: number
    maxAge: number
    keys: string[]
  } {
    return {
      size: this.cache.size,
      maxSize: this.config.maxSize,
      maxAge: this.config.maxAge,
      keys: Array.from(this.cache.keys())
    }
  }

  // 手动清理过期缓存
  cleanupExpired(): number {
    const initialSize = this.cache.size
    this.cleanup()
    return initialSize - this.cache.size
  }
}

// 新闻专用缓存方法
export class NewsCache {
  private cacheManager: NewsCacheManager

  constructor(config?: Partial<CacheConfig>) {
    this.cacheManager = new NewsCacheManager(config)
  }

  // 缓存新闻列表
  setNewsList(params: Record<string, any>, data: NewsItem[]): void {
    this.cacheManager.set('news-list', params, data)
  }

  getNewsList(params: Record<string, any>): NewsItem[] | null {
    return this.cacheManager.get('news-list', params)
  }

  // 缓存股票新闻
  setStockNews(stockCode: string, days: number, data: NewsItem[]): void {
    this.cacheManager.set('stock-news', { stockCode, days }, data)
  }

  getStockNews(stockCode: string, days: number): NewsItem[] | null {
    return this.cacheManager.get('stock-news', { stockCode, days })
  }

  // 缓存热点话题
  setHotTopics(data: HotTopic[]): void {
    this.cacheManager.set('hot-topics', {}, data)
  }

  getHotTopics(): HotTopic[] | null {
    return this.cacheManager.get('hot-topics', {})
  }

  // 缓存搜索结果
  setSearchResults(keyword: string, filters: Record<string, any>, data: NewsItem[]): void {
    this.cacheManager.set('search-results', { keyword, ...filters }, data)
  }

  getSearchResults(keyword: string, filters: Record<string, any>): NewsItem[] | null {
    return this.cacheManager.get('search-results', { keyword, ...filters })
  }

  // 缓存新闻详情
  setNewsDetail(newsId: string, data: NewsItem): void {
    this.cacheManager.set('news-detail', { newsId }, data)
  }

  getNewsDetail(newsId: string): NewsItem | null {
    return this.cacheManager.get('news-detail', { newsId })
  }

  // 清除特定股票的缓存
  clearStockCache(stockCode: string): void {
    this.cacheManager.deleteByPrefix(`stock-news:stockCode="${stockCode}"`)
    this.cacheManager.deleteByPrefix(`news-list:stock_codes=["${stockCode}"]`)
  }

  // 清除所有新闻缓存
  clearAllNews(): void {
    this.cacheManager.deleteByPrefix('news-list')
    this.cacheManager.deleteByPrefix('stock-news')
    this.cacheManager.deleteByPrefix('search-results')
  }

  // 清除热点话题缓存
  clearHotTopics(): void {
    this.cacheManager.deleteByPrefix('hot-topics')
  }

  // 获取缓存统计
  getStats() {
    return this.cacheManager.getStats()
  }

  // 清理过期缓存
  cleanup(): number {
    return this.cacheManager.cleanupExpired()
  }
}

// 全局新闻缓存实例
export const newsCache = new NewsCache({
  maxAge: 5 * 60 * 1000, // 新闻缓存5分钟
  maxSize: 200 // 最多缓存200个条目
})

// 热点话题缓存（更短的过期时间）
export const hotTopicsCache = new NewsCache({
  maxAge: 2 * 60 * 1000, // 热点话题缓存2分钟
  maxSize: 50
})

// 缓存装饰器
export function withCache<T extends any[], R>(
  cache: NewsCache,
  cacheKey: string,
  keyGenerator: (...args: T) => Record<string, any>
) {
  return function (target: any, propertyName: string, descriptor: PropertyDescriptor) {
    const method = descriptor.value

    descriptor.value = async function (...args: T) {
      const cacheParams = keyGenerator(...args)
      
      // 尝试从缓存获取
      const cached = cache.cacheManager.get(cacheKey, cacheParams)
      if (cached !== null) {
        console.log(`Cache hit for ${cacheKey}:`, cacheParams)
        return cached
      }

      // 缓存未命中，调用原方法
      console.log(`Cache miss for ${cacheKey}:`, cacheParams)
      const result = await method.apply(this, args)
      
      // 缓存结果
      if (result !== null && result !== undefined) {
        cache.cacheManager.set(cacheKey, cacheParams, result)
      }

      return result
    }
  }
}

// 自动清理过期缓存的定时器
let cleanupInterval: NodeJS.Timeout | null = null

export const startCacheCleanup = (intervalMs: number = 60000) => {
  if (cleanupInterval) {
    clearInterval(cleanupInterval)
  }

  cleanupInterval = setInterval(() => {
    const newsCleanup = newsCache.cleanup()
    const hotTopicsCleanup = hotTopicsCache.cleanup()
    
    if (newsCleanup > 0 || hotTopicsCleanup > 0) {
      console.log(`Cache cleanup: removed ${newsCleanup + hotTopicsCleanup} expired items`)
    }
  }, intervalMs)
}

export const stopCacheCleanup = () => {
  if (cleanupInterval) {
    clearInterval(cleanupInterval)
    cleanupInterval = null
  }
}