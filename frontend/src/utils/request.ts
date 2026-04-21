import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { MessagePlugin } from 'tdesign-vue-next'

const baseURL = import.meta.env.VITE_API_BASE_URL || ''

const instance: AxiosInstance = axios.create({
  baseURL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor
instance.interceptors.request.use(
  (config) => {
    console.log('发送API请求:', config.method?.toUpperCase(), config.url)
    console.log('请求配置:', config)
    
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    console.error('请求拦截器错误:', error)
    return Promise.reject(error)
  }
)

// Response interceptor
instance.interceptors.response.use(
  (response: AxiosResponse) => {
    console.log('收到API响应:', response.status, response.config.url)
    console.log('响应数据:', response.data)
    
    const { data } = response
    // Check for error response format (status code, not stock code)
    if (data.status !== undefined && data.status === 'error') {
      console.error('API返回错误状态:', data)
      MessagePlugin.error(data.message || '请求失败')
      return Promise.reject(new Error(data.message))
    }
    // For successful responses, return the data directly
    return data
  },
  (error) => {
    console.error('响应拦截器错误:', error)
    console.error('错误响应:', error.response)
    
    const status = error.response?.status
    const detail = error.response?.data?.detail
    
    // Handle 401 Unauthorized
    if (status === 401) {
      // Clear auth state
      localStorage.removeItem('token')
      localStorage.removeItem('user')

      // Show message
      MessagePlugin.warning(detail || '登录已过期，请重新登录')

      // Redirect to login page if not already there
      const currentPath = window.location.pathname
      if (currentPath !== '/login') {
        window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`
      }

      return Promise.reject(error)
    }

    // Handle 429 Too Many Requests (rate limit)
    if (status === 429) {
      MessagePlugin.warning(detail || '请求太频繁，请稍后再试')
      return Promise.reject(error)
    }

    // Handle 403 Forbidden (quota exhausted or insufficient tier)
    if (status === 403) {
      const isQuotaExhausted = error.response?.headers?.['x-quota-exhausted'] === 'true'
      if (isQuotaExhausted) {
        MessagePlugin.error('Token 配额已用完，请联系管理员升级账户')
      } else {
        MessagePlugin.warning(detail || '权限不足')
      }
      return Promise.reject(error)
    }
    
    const message = detail || error.response?.data?.message || error.message || '网络错误'
    MessagePlugin.error(message)
    return Promise.reject(error)
  }
)

// Type-safe request wrapper that supports both request(config) and request.get(url) patterns
function typedRequest<T = any>(config: AxiosRequestConfig): Promise<T> {
  return instance(config) as Promise<T>
}

typedRequest.get = <T = any>(url: string, config?: AxiosRequestConfig): Promise<T> => {
  return instance.get(url, config) as Promise<T>
}

typedRequest.post = <T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> => {
  return instance.post(url, data, config) as Promise<T>
}

typedRequest.put = <T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> => {
  return instance.put(url, data, config) as Promise<T>
}

typedRequest.delete = <T = any>(url: string, config?: AxiosRequestConfig): Promise<T> => {
  return instance.delete(url, config) as Promise<T>
}

type TypedRequest = typeof typedRequest

export const request: TypedRequest = typedRequest
export default typedRequest
