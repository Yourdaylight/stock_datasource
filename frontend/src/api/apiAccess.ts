import { request } from '@/utils/request'

// ---- Policy types ----

export interface PolicyInfo {
  policy_id: string
  api_path: string
  api_type: string
  is_enabled: boolean
  rate_limit_per_min: number
  rate_limit_per_day: number
  max_records: number
  description: string
  created_at: string | null
  updated_at: string | null
}

export interface PolicyListResponse {
  policies: PolicyInfo[]
  total: number
}

export interface UpdatePolicyRequest {
  is_enabled?: boolean
  rate_limit_per_min?: number
  rate_limit_per_day?: number
  max_records?: number
  description?: string
}

export interface BatchToggleRequest {
  api_paths: string[]
  is_enabled: boolean
}

// ---- Endpoint types ----

export interface EndpointParam {
  name: string
  type: string
  description: string
  required: boolean
  default: any
}

export interface EndpointInfo {
  plugin_name: string
  method_name: string
  api_path: string
  description: string
  parameters: EndpointParam[]
  is_enabled: boolean
}

export interface EndpointListResponse {
  endpoints: EndpointInfo[]
  total: number
}

// ---- Usage types ----

export interface UsageStatItem {
  api_path: string
  total_calls: number
  success_calls: number
  error_calls: number
  avg_response_ms: number
  total_records: number
}

export interface UsageStatsResponse {
  stats: UsageStatItem[]
  period: string
  total_calls: number
}

// ---- Message response ----

export interface MessageResponse {
  success: boolean
  message: string
}

// ---- API ----

export const apiAccessApi = {
  // Policy management
  getPolicies(): Promise<PolicyListResponse> {
    return request.get('/api/open-api-admin/policies')
  },

  updatePolicy(apiPath: string, data: UpdatePolicyRequest): Promise<MessageResponse> {
    return request.put(`/api/open-api-admin/policies/${apiPath}`, data)
  },

  batchToggle(data: BatchToggleRequest): Promise<MessageResponse> {
    return request.post('/api/open-api-admin/policies/batch-toggle', data)
  },

  syncPolicies(): Promise<MessageResponse> {
    return request.post('/api/open-api-admin/policies/sync')
  },

  // Endpoint discovery
  getEndpoints(): Promise<EndpointListResponse> {
    return request.get('/api/open-api-admin/endpoints')
  },

  // Usage statistics
  getUsageStats(params?: {
    days?: number
    api_path?: string
    api_key_id?: string
  }): Promise<UsageStatsResponse> {
    return request.get('/api/open-api-admin/usage', { params })
  },

  // Public docs (no admin auth needed)
  getOpenDocs(): Promise<EndpointListResponse> {
    return request.get('/api/open/docs')
  },
}
