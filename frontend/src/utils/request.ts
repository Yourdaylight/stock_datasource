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
    
    const message = error.response?.data?.message || error.message || '网络错误'
    MessagePlugin.error(message)
    return Promise.reject(error)
  }
)

export const request = {
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return instance.get(url, config)
  },
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return instance.post(url, data, config)
  },
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return instance.put(url, data, config)
  },
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return instance.delete(url, config)
  }
}

export default instance
