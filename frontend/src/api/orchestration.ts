import { request } from '@/utils/request'

/** Pipeline node */
export interface PipelineNode {
  id: string
  type: 'agent' | 'input' | 'output' | 'condition' | 'aggregator'
  label: string
  position: { x: number; y: number }
  data: Record<string, any>
}

/** Pipeline edge */
export interface PipelineEdge {
  id: string
  source: string
  target: string
  source_handle?: string
  target_handle?: string
  label?: string
}

/** Pipeline response */
export interface Pipeline {
  id: string
  user_id: string
  name: string
  description: string
  nodes: PipelineNode[]
  edges: PipelineEdge[]
  input_schema: Record<string, any>
  output_config: Record<string, any>
  tags: string[]
  is_public: boolean
  status: 'draft' | 'active' | 'archived' | 'deleted'
  version: number
  created_at: string
  updated_at: string
}

/** Create pipeline request */
export interface PipelineCreateRequest {
  name: string
  description?: string
  nodes?: PipelineNode[]
  edges?: PipelineEdge[]
  input_schema?: Record<string, any>
  output_config?: Record<string, any>
  tags?: string[]
}

/** Update pipeline request */
export interface PipelineUpdateRequest {
  name?: string
  description?: string
  nodes?: PipelineNode[]
  edges?: PipelineEdge[]
  input_schema?: Record<string, any>
  output_config?: Record<string, any>
  tags?: string[]
  status?: string
}

/** List pipelines */
export function listPipelines() {
  return request.get<Pipeline[]>('/api/orchestrations/')
}

/** Get pipeline */
export function getPipeline(id: string) {
  return request.get<Pipeline>(`/api/orchestrations/${id}`)
}

/** Create pipeline */
export function createPipeline(data: PipelineCreateRequest) {
  return request.post<Pipeline>('/api/orchestrations/', data)
}

/** Update pipeline */
export function updatePipeline(id: string, data: PipelineUpdateRequest) {
  return request.put<Pipeline>(`/api/orchestrations/${id}`, data)
}

/** Delete pipeline */
export function deletePipeline(id: string) {
  return request.delete(`/api/orchestrations/${id}`)
}

/** Execute pipeline — returns SSE URL */
export function getExecuteUrl(id: string) {
  return `/api/orchestrations/${id}/execute`
}

/** List executions */
export function listExecutions(pipelineId: string, limit = 20) {
  return request.get(`/api/orchestrations/${pipelineId}/executions`, { params: { limit } })
}
