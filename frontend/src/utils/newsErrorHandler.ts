import { MessagePlugin } from 'tdesign-vue-next'
import type { NewsItem, NewsSentiment, HotTopic } from '@/types/news'

// 错误类型定义
export enum NewsErrorType {
  NETWORK_ERROR = 'NETWORK_ERROR',
  TIMEOUT_ERROR = 'TIMEOUT_ERROR',
  DATA_VALIDATION_ERROR = 'DATA_VALIDATION_ERROR',
  API_ERROR = 'API_ERROR',
  UNKNOWN_ERROR = 'UNKNOWN_ERROR'
}

export interface NewsError {
  type: NewsErrorType
  message: string
  originalError?: any
  retryable: boolean
}

// 重试配置
export interface RetryConfig {
  maxRetries: number
  retryDelay: number
  backoffMultiplier: number
  retryableErrors: NewsErrorType[]
}

const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  retryDelay: 1000,
  backoffMultiplier: 2,
  retryableErrors: [NewsErrorType.NETWORK_ERROR, NewsErrorType.TIMEOUT_ERROR]
}

// 数据验证函数
export const validateNewsItem = (item: any): item is NewsItem => {
  return (
    typeof item === 'object' &&
    typeof item.id === 'string' &&
    typeof item.title === 'string' &&
    typeof item.content === 'string' &&
    typeof item.source === 'string' &&
    typeof item.publish_time === 'string' &&
    Array.isArray(item.stock_codes) &&
    typeof item.category === 'string'
  )
}

export const validateNewsSentiment = (sentiment: any): sentiment is NewsSentiment => {
  return (
    typeof sentiment === 'object' &&
    typeof sentiment.news_id === 'string' &&
    ['positive', 'negative', 'neutral'].includes(sentiment.sentiment) &&
    typeof sentiment.score === 'number' &&
    typeof sentiment.reasoning === 'string' &&
    ['high', 'medium', 'low'].includes(sentiment.impact_level)
  )
}

export const validateHotTopic = (topic: any): topic is HotTopic => {
  return (
    typeof topic === 'object' &&
    typeof topic.topic === 'string' &&
    Array.isArray(topic.keywords) &&
    typeof topic.heat_score === 'number' &&
    Array.isArray(topic.related_stocks) &&
    typeof topic.news_count === 'number'
  )
}

// 错误分类函数
export const classifyError = (error: any): NewsError => {
  // 网络错误
  if (error.code === 'NETWORK_ERROR' || error.message?.includes('Network Error')) {
    return {
      type: NewsErrorType.NETWORK_ERROR,
      message: '网络连接失败，请检查网络设置',
      originalError: error,
      retryable: true
    }
  }

  // 超时错误
  if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
    return {
      type: NewsErrorType.TIMEOUT_ERROR,
      message: '请求超时，请稍后重试',
      originalError: error,
      retryable: true
    }
  }

  // API错误
  if (error.response) {
    const status = error.response.status
    const data = error.response.data

    if (status >= 400 && status < 500) {
      return {
        type: NewsErrorType.API_ERROR,
        message: data?.message || `请求错误 (${status})`,
        originalError: error,
        retryable: false
      }
    }

    if (status >= 500) {
      return {
        type: NewsErrorType.API_ERROR,
        message: data?.message || '服务器错误，请稍后重试',
        originalError: error,
        retryable: true
      }
    }
  }

  // 数据验证错误
  if (error.message?.includes('validation')) {
    return {
      type: NewsErrorType.DATA_VALIDATION_ERROR,
      message: '数据格式错误',
      originalError: error,
      retryable: false
    }
  }

  // 未知错误
  return {
    type: NewsErrorType.UNKNOWN_ERROR,
    message: error.message || '未知错误',
    originalError: error,
    retryable: false
  }
}

// 重试函数
export const withRetry = async <T>(
  fn: () => Promise<T>,
  config: Partial<RetryConfig> = {}
): Promise<T> => {
  const retryConfig = { ...DEFAULT_RETRY_CONFIG, ...config }
  let lastError: NewsError

  for (let attempt = 0; attempt <= retryConfig.maxRetries; attempt++) {
    try {
      return await fn()
    } catch (error) {
      lastError = classifyError(error)

      // 如果是最后一次尝试或错误不可重试，直接抛出
      if (attempt === retryConfig.maxRetries || !lastError.retryable) {
        throw lastError
      }

      // 如果错误类型不在可重试列表中，直接抛出
      if (!retryConfig.retryableErrors.includes(lastError.type)) {
        throw lastError
      }

      // 计算延迟时间
      const delay = retryConfig.retryDelay * Math.pow(retryConfig.backoffMultiplier, attempt)
      
      console.warn(`新闻API请求失败，${delay}ms后进行第${attempt + 1}次重试:`, lastError.message)
      
      // 等待后重试
      await new Promise(resolve => setTimeout(resolve, delay))
    }
  }

  throw lastError!
}

// 数据验证包装器
export const withValidation = <T>(
  validator: (data: any) => data is T,
  errorMessage: string = '数据格式验证失败'
) => {
  return (data: any): T => {
    if (!validator(data)) {
      throw new Error(`${errorMessage}: ${JSON.stringify(data)}`)
    }
    return data
  }
}

// 批量数据验证
export const validateNewsItems = (items: any[]): NewsItem[] => {
  if (!Array.isArray(items)) {
    throw new Error('新闻数据必须是数组格式')
  }

  const validItems: NewsItem[] = []
  const invalidItems: any[] = []

  items.forEach((item, index) => {
    if (validateNewsItem(item)) {
      validItems.push(item)
    } else {
      invalidItems.push({ index, item })
    }
  })

  if (invalidItems.length > 0) {
    console.warn('发现无效的新闻数据项:', invalidItems)
  }

  return validItems
}

export const validateHotTopics = (topics: any[]): HotTopic[] => {
  if (!Array.isArray(topics)) {
    throw new Error('热点话题数据必须是数组格式')
  }

  const validTopics: HotTopic[] = []
  const invalidTopics: any[] = []

  topics.forEach((topic, index) => {
    if (validateHotTopic(topic)) {
      validTopics.push(topic)
    } else {
      invalidTopics.push({ index, topic })
    }
  })

  if (invalidTopics.length > 0) {
    console.warn('发现无效的热点话题数据项:', invalidTopics)
  }

  return validTopics
}

// 错误处理中间件
export const handleNewsError = (error: NewsError, showMessage: boolean = true) => {
  console.error('新闻API错误:', error)

  if (showMessage) {
    switch (error.type) {
      case NewsErrorType.NETWORK_ERROR:
        MessagePlugin.error('网络连接失败，请检查网络设置')
        break
      case NewsErrorType.TIMEOUT_ERROR:
        MessagePlugin.error('请求超时，请稍后重试')
        break
      case NewsErrorType.DATA_VALIDATION_ERROR:
        MessagePlugin.warning('数据格式异常，已自动过滤无效数据')
        break
      case NewsErrorType.API_ERROR:
        MessagePlugin.error(error.message)
        break
      default:
        MessagePlugin.error('操作失败，请稍后重试')
    }
  }

  return error
}

// 安全的API调用包装器
export const safeApiCall = async <T>(
  apiCall: () => Promise<T>,
  options: {
    retryConfig?: Partial<RetryConfig>
    showError?: boolean
    fallbackValue?: T
  } = {}
): Promise<T | null> => {
  const { retryConfig, showError = true, fallbackValue } = options

  try {
    return await withRetry(apiCall, retryConfig)
  } catch (error) {
    const newsError = error instanceof Error && 'type' in error 
      ? error as NewsError 
      : classifyError(error)
    
    handleNewsError(newsError, showError)
    
    return fallbackValue ?? null
  }
}