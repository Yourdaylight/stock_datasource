import { request } from '@/utils/request'

/** Runtime configuration */
export interface RuntimeConfig {
  type: 'langgraph' | 'claude' | 'codebuddy'
  command: string
  working_dir: string
  env_vars: Record<string, string>
}

/** Agent configuration */
export interface AgentConfig {
  id: string
  user_id: string
  name: string
  description: string
  avatar: string
  system_prompt: string
  skills: string[]
  user_skills: string[]
  model_config_data: {
    model: string
    temperature: number
    max_tokens: number
    min_tokens: number
  }
  runtime_config: RuntimeConfig
  tags: string[]
  is_public: boolean
  status: 'active' | 'archived' | 'deleted'
  version: number
  created_at: string
  updated_at: string
}

/** Skill info from catalog (platform tools) */
export interface SkillInfo {
  id: string
  name: string
  description: string
  category: string
  parameters_schema?: Record<string, any>
}

/** User/Project skill info */
export interface UserSkillInfo {
  id: string
  name: string
  description: string
  source: 'claude' | 'codebuddy' | 'project'
  path: string
  emoji?: string
}

/** Create agent request */
export interface AgentCreateRequest {
  name: string
  description?: string
  avatar?: string
  system_prompt: string
  skills?: string[]
  user_skills?: string[]
  model_config_data?: {
    model?: string
    temperature?: number
    max_tokens?: number
    min_tokens?: number
  }
  runtime_config?: Partial<RuntimeConfig>
  tags?: string[]
  is_public?: boolean
}

/** Update agent request */
export interface AgentUpdateRequest {
  name?: string
  description?: string
  avatar?: string
  system_prompt?: string
  skills?: string[]
  user_skills?: string[]
  model_config_data?: {
    model?: string
    temperature?: number
    max_tokens?: number
    min_tokens?: number
  }
  runtime_config?: Partial<RuntimeConfig>
  tags?: string[]
  is_public?: boolean
  status?: 'active' | 'archived' | 'deleted'
}

/** List agents */
export function listAgents() {
  return request.get<AgentConfig[]>('/api/agents/')
}

/** Get single agent */
export function getAgent(id: string) {
  return request.get<AgentConfig>(`/api/agents/${id}`)
}

/** Create agent */
export function createAgent(data: AgentCreateRequest) {
  return request.post<AgentConfig>('/api/agents/', data)
}

/** Update agent */
export function updateAgent(id: string, data: AgentUpdateRequest) {
  return request.put<AgentConfig>(`/api/agents/${id}`, data)
}

/** Delete agent */
export function deleteAgent(id: string) {
  return request.delete(`/api/agents/${id}`)
}

/** List platform tools (MCP) */
export function listSkills() {
  return request.get<SkillInfo[]>('/api/agents/skills/catalog')
}

/** List user skills (~/.claude/skills, ~/.codebuddy/skills) */
export function listUserSkills() {
  return request.get<UserSkillInfo[]>('/api/agents/skills/user-skills')
}

/** List project skills */
export function listProjectSkills() {
  return request.get<UserSkillInfo[]>('/api/agents/skills/project-skills')
}

/** Get agent call history */
export function getAgentHistory(id: string) {
  return request.get<any[]>(`/api/agents/${id}/history`)
}

/** Get SSE test URL */
export function getAgentTestUrl(id: string, message: string) {
  const base = import.meta.env.VITE_API_BASE_URL || ''
  return `${base}/api/agents/${id}/test?message=${encodeURIComponent(message)}`
}
