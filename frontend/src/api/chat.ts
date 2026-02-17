import { request } from '@/utils/request'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  metadata?: {
    intent?: string
    agent?: string
    stock_codes?: string[]
    tool_calls?: string[]
    rationale?: string
    [key: string]: any
  }
}

export interface SendMessageRequest {
  session_id: string
  content: string
}

export interface ChatHistoryResponse {
  messages: ChatMessage[]
  session_id: string
}

export interface ChatSessionSummary {
  session_id: string
  title: string
  created_at: string
  last_message_at: string
  message_count: number
}

export interface SessionListResponse {
  sessions: ChatSessionSummary[]
  total: number
}

// SSE event types
export interface ThinkingEvent {
  type: 'thinking'
  intent: string
  agent: string
  stock_codes: string[]
  tool?: string
  status?: string
  plan?: string[]
  rationale?: string
}

export interface ToolEvent {
  type: 'tool'
  tool: string
  args?: any
  agent?: string
  status?: string
}

export interface ContentEvent {
  type: 'content'
  content: string
}

export interface DoneEvent {
  type: 'done'
  metadata: {
    intent: string
    agent: string
    stock_codes: string[]
    tool_calls?: string[]
    rationale?: string
    react_steps?: Array<{ thought: string; action: string }>
    sub_agents?: string[]
  }
}

export interface ErrorEvent {
  type: 'error'
  error: string
}

export interface DebugEvent {
  type: 'debug'
  debug_type: 'classification' | 'routing' | 'agent_start' | 'agent_end' | 'tool_result' | 'handoff' | 'data_sharing'
  agent: string
  timestamp: number
  data: {
    // classification
    intent?: string
    selected_agent?: string
    rationale?: string
    available_agents?: string[]
    // routing
    from_agent?: string
    to_agent?: string
    is_parallel?: boolean
    plan?: string[]
    // agent_start
    input_summary?: string
    tools_available?: string[]
    parent_agent?: string
    // agent_end
    duration_ms?: number
    tool_calls_count?: number
    success?: boolean
    error?: string
    // tool_result
    tool?: string
    args?: Record<string, string>
    result_summary?: string
    // data_sharing
    data_summary?: Record<string, string>
    // handoff
    shared_data_summary?: Record<string, string>
    [key: string]: any
  }
}

export interface VisualizationEvent {
  type: 'visualization'
  visualization: {
    type: 'kline' | 'financial_trend' | 'profit_curve' | 'index_compare'
    title: string
    props: Record<string, any>
  }
  agent?: string
  tool?: string
}

export type StreamEvent = ThinkingEvent | ToolEvent | ContentEvent | DoneEvent | ErrorEvent | DebugEvent | VisualizationEvent

export const chatApi = {
  sendMessage(data: SendMessageRequest): Promise<ChatMessage> {
    return request.post('/api/chat/message', data)
  },

  getHistory(sessionId: string): Promise<ChatHistoryResponse> {
    return request.get(`/api/chat/history?session_id=${sessionId}`)
  },

  createSession(): Promise<{ session_id: string }> {
    return request.post('/api/chat/session')
  },

  // Get user's chat sessions
  getSessions(limit = 50, offset = 0): Promise<SessionListResponse> {
    return request.get(`/api/chat/sessions?limit=${limit}&offset=${offset}`)
  },

  // Delete a session
  deleteSession(sessionId: string): Promise<{ success: boolean; message: string }> {
    return request.delete(`/api/chat/session/${sessionId}`)
  },

  // Update session title
  updateSessionTitle(sessionId: string, title: string): Promise<{ success: boolean; message: string }> {
    return request.put(`/api/chat/session/${sessionId}/title?title=${encodeURIComponent(title)}`)
  },

  // Stream message via EventSource (GET)
  streamMessageGet(sessionId: string, content: string): EventSource {
    const params = new URLSearchParams({ session_id: sessionId, content })
    return new EventSource(`/api/chat/stream?${params}`)
  },

  // Stream message via fetch (POST) - better for longer messages
  async streamMessagePost(
    sessionId: string, 
    content: string,
    onEvent: (event: StreamEvent) => void,
    onError?: (error: Error) => void
  ): Promise<void> {
    let terminalReceived = false
    let jsonBuffer = '' // Buffer for incomplete JSON data
    
    try {
      const token = localStorage.getItem('token')
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }
      
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          session_id: sessionId,
          content: content
        })
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

      // Helper function to safely parse JSON with incomplete data handling
      const tryParseJSON = (data: string): StreamEvent | null => {
        try {
          return JSON.parse(data) as StreamEvent
        } catch (e) {
          return null
        }
      }

      // Helper function to check if JSON is complete
      const isCompleteJSON = (str: string): boolean => {
        let depth = 0
        let inString = false
        let escape = false
        
        for (const char of str) {
          if (escape) {
            escape = false
            continue
          }
          if (char === '\\') {
            escape = true
            continue
          }
          if (char === '"') {
            inString = !inString
            continue
          }
          if (inString) continue
          
          if (char === '{' || char === '[') depth++
          if (char === '}' || char === ']') depth--
        }
        
        return depth === 0 && str.trim().length > 0
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        
        // Parse SSE events - split by double newline (SSE event separator)
        const events = buffer.split('\n\n')
        buffer = events.pop() || '' // Keep incomplete event in buffer

        for (const eventBlock of events) {
          const lines = eventBlock.split('\n')
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6).trim()
              if (!data || data === '[DONE]') continue
              
              // Combine with any previous incomplete JSON
              const fullData = jsonBuffer + data
              jsonBuffer = ''
              
              // Check if we have complete JSON
              if (!isCompleteJSON(fullData)) {
                // Incomplete JSON, buffer it for next iteration
                jsonBuffer = fullData
                console.debug('[SSE] Buffering incomplete JSON:', fullData.substring(0, 50) + '...')
                continue
              }
              
              const event = tryParseJSON(fullData)
              if (event) {
                if (event.type === 'done' || event.type === 'error') {
                  terminalReceived = true
                }
                onEvent(event)
              } else {
                console.warn('[SSE] Failed to parse complete JSON:', fullData.substring(0, 100))
              }
            }
          }
        }
      }
      
      // Process any remaining buffer
      if (buffer.trim()) {
        const lines = buffer.split('\n')
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim()
            if (data && data !== '[DONE]') {
              const fullData = jsonBuffer + data
              const event = tryParseJSON(fullData)
              if (event) {
                if (event.type === 'done' || event.type === 'error') {
                  terminalReceived = true
                }
                onEvent(event)
              }
            }
          }
        }
      }
      
      if (!terminalReceived) {
        console.warn('[SSE] Stream closed without terminal event')
        // Don't throw error, just notify via error callback
        if (onError) {
          onError(new Error('SSE stream closed without terminal event'))
        }
      }
    } catch (error) {
      console.error('[SSE] Stream error:', error)
      if (onError) {
        onError(error as Error)
      } else {
        throw error
      }
    }
  }
}
