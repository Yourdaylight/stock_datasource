/**
 * Akinator API client - 猜你所想 A股版
 */
import request from '@/utils/request'

export type AnswerType = 'yes' | 'no' | 'unknown'

export interface Predicate {
  field: string
  op: string
  value: any
}

export interface QuestionDTO {
  question: string
  predicate: Predicate
  reasoning?: string
}

export interface StockDTO {
  ts_code: string
  name?: string
  industry?: string
  total_mv?: number
  pe_ttm?: number
  concepts?: string[]
}

export interface StartResponse {
  session_id: string
  question: QuestionDTO
  question_count: number
  candidates_remaining: number
}

export interface AnswerResponse {
  session_id: string
  status: 'continue' | 'finished'
  question: QuestionDTO | null
  final_candidates: StockDTO[] | null
  question_count: number
  candidates_remaining: number
  tokens_used: number
}

export const akinatorApi = {
  start(): Promise<StartResponse> {
    return request.post('/api/akinator/start', {}, { timeout: 90_000 })
  },

  answer(session_id: string, answer: AnswerType): Promise<AnswerResponse> {
    return request.post('/api/akinator/answer', { session_id, answer }, { timeout: 90_000 })
  },

  /** Stream `/answer/stream` via fetch+ReadableStream. Each callback event is one SSE `data: ...` line. */
  async answerStream(
    session_id: string,
    answer: AnswerType,
    onEvent: (ev: any) => void,
    signal?: AbortSignal,
  ): Promise<void> {
    const token = localStorage.getItem('token') || ''
    const resp = await fetch('/api/akinator/answer/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: token ? `Bearer ${token}` : '',
      },
      body: JSON.stringify({ session_id, answer }),
      signal,
    })
    if (!resp.ok || !resp.body) {
      throw new Error(`stream HTTP ${resp.status}`)
    }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      // Split on SSE event boundary (blank line)
      let idx
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const raw = buffer.slice(0, idx).trim()
        buffer = buffer.slice(idx + 2)
        if (!raw.startsWith('data:')) continue
        const json = raw.slice(5).trim()
        if (!json) continue
        try {
          onEvent(JSON.parse(json))
        } catch (e) {
          console.warn('bad SSE chunk:', json, e)
        }
      }
    }
  },

  candidates(session_id: string): Promise<{
    session_id: string
    candidates: StockDTO[]
    candidates_remaining: number
    question_count: number
  }> {
    return request.get(`/api/akinator/candidates/${session_id}`)
  },

  confirm(session_id: string, ts_code: string): Promise<{ success: boolean; message: string }> {
    return request.post('/api/akinator/confirm', { session_id, ts_code })
  },

  abandon(session_id: string): Promise<{ success: boolean; message: string }> {
    return request.post('/api/akinator/abandon', { session_id })
  },
}
