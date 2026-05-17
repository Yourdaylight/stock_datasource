/**
 * Decision API Client
 * API functions for Agent decision summaries and opinion distribution
 */

import { request } from '@/utils/request'

// Types
export interface DecisionSummary {
  id: string
  arena_id: string
  round_id: string
  stock_code: string
  signal: 'buy' | 'sell' | 'hold'
  confidence: number
  consensus_ratio: number
  bull_count: number
  bear_count: number
  neutral_count: number
  key_arguments: KeyArgument[]
  dissent_points: string[]
  suggested_action: string
  generated_at: string
}

export interface KeyArgument {
  agent_id: string
  agent_role: string
  direction: 'bullish' | 'bearish' | 'neutral'
  confidence: number
  key_point: string
}

export interface OpinionDistribution {
  arena_id: string
  round_id: string
  bullish: KeyArgument[]
  bearish: KeyArgument[]
  neutral: KeyArgument[]
  total_agents: number
}

export interface AllDecisionsResponse {
  total: number
  decisions: DecisionSummary[]
}

// API Functions

/**
 * Get decision summary for an arena
 */
export function getDecisionSummary(arenaId: string, roundId?: string) {
  const params = new URLSearchParams()
  if (roundId) params.set('round_id', roundId)
  const query = params.toString()
  return request.get<DecisionSummary>(
    `/api/arena/${arenaId}/decision-summary${query ? '?' + query : ''}`
  )
}

/**
 * Get opinion distribution for an arena
 */
export function getOpinionDistribution(arenaId: string) {
  return request.get<OpinionDistribution>(
    `/api/arena/${arenaId}/opinion-distribution`
  )
}

/**
 * Get all active arena decisions (for dashboard)
 */
export function getAllDecisions() {
  return request.get<AllDecisionsResponse>('/api/arena/decisions/all')
}

/**
 * Get decision summary by stock code (finds relevant arena)
 */
export function getDecisionByStock(stockCode: string) {
  return request.get<DecisionSummary>(
    `/api/arena/decisions/stock/${stockCode}`
  )
}
