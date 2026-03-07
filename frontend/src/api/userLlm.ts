import { request } from '@/utils/request'

export interface LlmConfig {
  provider: string
  api_key_masked: string
  base_url: string
  model_name: string
  is_active: boolean
  updated_at: string
}

export interface LlmConfigCreateRequest {
  provider: string
  api_key: string
  base_url?: string
  model_name?: string
}

export interface LlmConfigTestRequest {
  provider: string
  api_key: string
  base_url?: string
  model_name?: string
}

export interface LlmConfigTestResponse {
  success: boolean
  message: string
  model_name: string
}

export const userLlmApi = {
  getConfigs(): Promise<{ configs: LlmConfig[] }> {
    return request.get('/api/user-llm/configs')
  },

  saveConfig(data: LlmConfigCreateRequest): Promise<LlmConfig> {
    return request.post('/api/user-llm/configs', data)
  },

  deleteConfig(provider: string): Promise<{ success: boolean }> {
    return request.delete(`/api/user-llm/configs/${provider}`)
  },

  testConfig(data: LlmConfigTestRequest): Promise<LlmConfigTestResponse> {
    return request.post('/api/user-llm/test', data)
  }
}
