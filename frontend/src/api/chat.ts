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

// SSE event types
export interface ThinkingEvent {
  type: 'thinking'
  intent: string
  agent: string
  stock_codes: string[]
  tool?: string
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
  }
}

export interface ErrorEvent {
  type: 'error'
  error: string
}

export type StreamEvent = ThinkingEvent | ContentEvent | DoneEvent | ErrorEvent

export const chatApi = {
  sendMessage(data: SendMessageRequest): Promise<ChatMessage> {
    return request.post('/chat/message', data)
  },

  getHistory(sessionId: string): Promise<ChatHistoryResponse> {
    return request.get(`/chat/history?session_id=${sessionId}`)
  },

  createSession(): Promise<{ session_id: string }> {
    return request.post('/chat/session')
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
    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
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

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        
        // Parse SSE events
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim()
            if (data && data !== '[DONE]') {
              try {
                const event = JSON.parse(data) as StreamEvent
                onEvent(event)
              } catch (e) {
                console.warn('Failed to parse SSE data:', data)
              }
            }
          }
        }
      }
    } catch (error) {
      if (onError) {
        onError(error as Error)
      } else {
        throw error
      }
    }
  }
}
