/**
 * AI工作流API模块
 */

import request from '@/utils/request'

// 类型定义
export interface WorkflowVariable {
  name: string
  label: string
  type: 'string' | 'number' | 'date' | 'stock_code' | 'stock_list'
  required: boolean
  default?: string
  description?: string
}

export interface AIWorkflow {
  id: string
  name: string
  description: string
  system_prompt: string
  user_prompt_template: string
  selected_tools: string[]
  variables: WorkflowVariable[]
  is_template: boolean
  category: string
  tags: string[]
  created_at: string
  updated_at: string
}

export interface ToolInfo {
  name: string
  description: string
  parameters: Record<string, any>
  category: string
}

export interface WorkflowCreateRequest {
  name: string
  description?: string
  system_prompt?: string
  user_prompt_template?: string
  selected_tools?: string[]
  variables?: WorkflowVariable[]
  is_template?: boolean
  category?: string
  tags?: string[]
}

export interface WorkflowUpdateRequest {
  name?: string
  description?: string
  system_prompt?: string
  user_prompt_template?: string
  selected_tools?: string[]
  variables?: WorkflowVariable[]
  is_template?: boolean
  category?: string
  tags?: string[]
}

export interface WorkflowExecuteRequest {
  variables: Record<string, any>
  stream?: boolean
}

export interface WorkflowGenerateRequest {
  description: string
  stream?: boolean
}

export interface WorkflowListResponse {
  workflows: AIWorkflow[]
  total: number
}

// API函数

/**
 * 获取工作流列表
 */
export function getWorkflowList(includeTemplates: boolean = true): Promise<WorkflowListResponse> {
  return request({
    url: '/api/workflows/',
    method: 'get',
    params: { include_templates: includeTemplates }
  })
}

/**
 * 创建工作流
 */
export function createWorkflow(data: WorkflowCreateRequest): Promise<AIWorkflow> {
  return request({
    url: '/api/workflows/',
    method: 'post',
    data
  })
}

/**
 * 获取工作流详情
 */
export function getWorkflow(workflowId: string): Promise<AIWorkflow> {
  return request({
    url: `/api/workflows/${workflowId}`,
    method: 'get'
  })
}

/**
 * 更新工作流
 */
export function updateWorkflow(workflowId: string, data: WorkflowUpdateRequest): Promise<AIWorkflow> {
  return request({
    url: `/api/workflows/${workflowId}`,
    method: 'put',
    data
  })
}

/**
 * 删除工作流
 */
export function deleteWorkflow(workflowId: string): Promise<{ success: boolean; message: string }> {
  return request({
    url: `/api/workflows/${workflowId}`,
    method: 'delete'
  })
}

/**
 * 获取预置模板列表
 */
export function getWorkflowTemplates(): Promise<AIWorkflow[]> {
  return request({
    url: '/api/workflows/templates',
    method: 'get'
  })
}

/**
 * 获取可用工具列表
 */
export function getAvailableTools(): Promise<ToolInfo[]> {
  return request({
    url: '/api/workflows/tools',
    method: 'get'
  })
}

/**
 * 从模板克隆工作流
 */
export function cloneFromTemplate(templateId: string, name: string): Promise<AIWorkflow> {
  return request({
    url: `/api/workflows/${templateId}/clone`,
    method: 'post',
    params: { name }
  })
}

/**
 * 执行工作流（非流式）
 */
export function executeWorkflow(
  workflowId: string, 
  variables: Record<string, any>
): Promise<{ success: boolean; content?: string; error?: string }> {
  return request({
    url: `/api/workflows/${workflowId}/execute`,
    method: 'post',
    data: { variables, stream: false }
  })
}

/**
 * 执行工作流（流式）- 返回EventSource URL
 */
export function getWorkflowExecuteStreamUrl(workflowId: string): string {
  return `/api/workflows/${workflowId}/execute`
}

/**
 * 执行工作流流式请求
 */
export async function executeWorkflowStream(
  workflowId: string,
  variables: Record<string, any>,
  onThinking?: (content: string) => void,
  onContent?: (content: string) => void,
  onDone?: () => void,
  onError?: (error: string) => void
): Promise<void> {
  const response = await fetch(`/api/workflows/${workflowId}/execute`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ variables, stream: true })
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('No response body')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    
    // 处理SSE事件
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('event:')) {
        // 下一行应该是data
        continue
      }
      if (line.startsWith('data:')) {
        const data = line.slice(5).trim()
        if (data) {
          try {
            const event = JSON.parse(data)
            const eventType = event.type
            
            if (eventType === 'thinking' && onThinking) {
              onThinking(event.status || event.content || '')
            } else if (eventType === 'content' && onContent) {
              onContent(event.content || '')
            } else if (eventType === 'done' && onDone) {
              onDone()
            } else if (eventType === 'error' && onError) {
              onError(event.error || '未知错误')
            }
          } catch (e) {
            console.warn('Failed to parse SSE data:', data)
          }
        }
      }
    }
  }
}

/**
 * AI生成工作流（非流式）
 */
export function generateWorkflow(
  description: string
): Promise<{ success: boolean; workflow?: any; error?: string }> {
  return request({
    url: '/api/workflows/generate',
    method: 'post',
    data: { description, stream: false }
  })
}

/**
 * AI生成工作流（流式）
 */
export async function generateWorkflowStream(
  description: string,
  onThinking?: (content: string) => void,
  onGenerating?: (content: string) => void,
  onWorkflow?: (workflow: any) => void,
  onDone?: () => void,
  onError?: (error: string) => void
): Promise<void> {
  const response = await fetch('/api/workflows/generate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ description, stream: true })
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('No response body')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data:')) {
        const data = line.slice(5).trim()
        if (data) {
          try {
            const event = JSON.parse(data)
            const eventType = event.type
            
            if (eventType === 'thinking' && onThinking) {
              onThinking(event.content || '')
            } else if (eventType === 'generating' && onGenerating) {
              onGenerating(event.content || '')
            } else if (eventType === 'workflow' && onWorkflow) {
              onWorkflow(event.workflow)
            } else if (eventType === 'done' && onDone) {
              onDone()
            } else if (eventType === 'error' && onError) {
              onError(event.error || '未知错误')
            }
          } catch (e) {
            console.warn('Failed to parse SSE data:', data)
          }
        }
      }
    }
  }
}
