/**
 * Arena API Client
 * API functions for Multi-Agent Strategy Arena
 */

import { request } from '@/utils/request';

// Types
export interface ArenaConfig {
  name: string;
  description?: string;
  agent_count?: number;
  symbols?: string[];
  discussion_max_rounds?: number;
  initial_capital?: number;
  backtest_start_date?: string;
  backtest_end_date?: string;
  simulated_duration_days?: number;
}

export interface ArenaStatus {
  id: string;
  name: string;
  state: string;
  active_strategies: number;
  total_strategies: number;
  eliminated_strategies: number;
  discussion_rounds: number;
  last_evaluation: string | null;
  duration_seconds: number;
  error_count: number;
  last_error: string | null;
}

export interface Strategy {
  id: string;
  name: string;
  description: string;
  agent_id: string;
  agent_role: string;
  stage: string;
  is_active: boolean;
  current_score: number;
  current_rank: number;
  logic?: string;
  rules?: Record<string, unknown>;
}

export interface LeaderboardEntry {
  rank: number;
  strategy_id: string;
  name: string;
  agent_id: string;
  agent_role: string;
  score: number;
  stage: string;
}

export interface ThinkingMessage {
  id: string;
  arena_id: string;
  agent_id: string;
  agent_role: string;
  round_id: string;
  message_type: string;
  content: string;
  metadata: Record<string, unknown>;
  timestamp: string;
}

export interface DiscussionRound {
  id: string;
  arena_id: string;
  round_number: number;
  mode: string;
  participants: string[];
  conclusions: Record<string, string>;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number;
}

// API Functions

/**
 * Create a new arena
 */
export function createArena(config: ArenaConfig) {
  return request.post<ArenaStatus>('/api/arena/create', config);
}

/**
 * Get arena status
 */
export function getArenaStatus(arenaId: string) {
  return request.get<ArenaStatus>(`/api/arena/${arenaId}/status`);
}

/**
 * Start arena competition
 */
export function startArena(arenaId: string) {
  return request.post<{ status: string; arena_id: string }>(`/api/arena/${arenaId}/start`);
}

/**
 * Pause arena
 */
export function pauseArena(arenaId: string) {
  return request.post<{ status: string; arena_id: string }>(`/api/arena/${arenaId}/pause`);
}

/**
 * Resume arena
 */
export function resumeArena(arenaId: string) {
  return request.post<{ status: string; arena_id: string }>(`/api/arena/${arenaId}/resume`);
}

/**
 * Delete arena
 */
export function deleteArena(arenaId: string) {
  return request.delete<{ status: string; arena_id: string }>(`/api/arena/${arenaId}`);
}

/**
 * List all arenas
 */
export function listArenas(state?: string, limit = 50) {
  const params = new URLSearchParams();
  if (state) {
    params.set('state', state);
  }
  params.set('limit', limit.toString());
  return request.get<{ total: number; arenas: ArenaStatus[] }>(`/api/arena/list?${params}`);
}

/**
 * Get strategies in an arena
 */
export function getStrategies(arenaId: string, activeOnly = false) {
  const params = new URLSearchParams();
  params.set('active_only', activeOnly.toString());
  return request.get<{ total: number; strategies: Strategy[] }>(`/api/arena/${arenaId}/strategies?${params}`);
}

/**
 * Get strategy detail
 */
export function getStrategyDetail(arenaId: string, strategyId: string) {
  return request.get<Strategy>(`/api/arena/${arenaId}/strategies/${strategyId}`);
}

/**
 * Get leaderboard
 */
export function getLeaderboard(arenaId: string, limit = 10) {
  return request.get<{ total: number; leaderboard: LeaderboardEntry[] }>(`/api/arena/${arenaId}/leaderboard?limit=${limit}`);
}

/**
 * Get discussions
 */
export function getDiscussions(arenaId: string, limit = 10) {
  return request.get<{ total: number; discussions: DiscussionRound[] }>(`/api/arena/${arenaId}/discussions?limit=${limit}`);
}

/**
 * Get discussion detail
 */
export function getDiscussionDetail(arenaId: string, roundId: string) {
  return request.get<DiscussionRound>(`/api/arena/${arenaId}/discussions/${roundId}`);
}

/**
 * Trigger evaluation
 */
export function triggerEvaluation(arenaId: string, period: 'daily' | 'weekly' | 'monthly') {
  return request.post<{ status: string; period: string; arena_id: string }>(
    `/api/arena/${arenaId}/evaluate`,
    { period }
  );
}

/**
 * Get competition history
 */
export function getCompetitionHistory(arenaId: string, limit = 50) {
  return request.get<{
    arena_id: string;
    state: string;
    discussion_rounds: DiscussionRound[];
    evaluations: unknown[];
    eliminated_strategies: Strategy[];
    duration_seconds: number;
  }>(`/api/arena/${arenaId}/history?limit=${limit}`);
}

/**
 * Start a discussion round
 */
export function startDiscussion(arenaId: string, mode: 'debate' | 'collaboration' | 'review') {
  return request.post<{ status: string; mode: string; arena_id: string }>(
    `/api/arena/${arenaId}/discussion/start`,
    { mode }
  );
}

/**
 * Get current discussion status
 */
export function getCurrentDiscussion(arenaId: string) {
  return request.get<{ status: string; round?: DiscussionRound }>(`/api/arena/${arenaId}/discussion/current`);
}

/**
 * Create SSE connection for thinking stream
 */
export function createThinkingStream(arenaId: string, roundId?: string): EventSource {
  let url = `/api/arena/${arenaId}/thinking-stream`;
  if (roundId) {
    url += `?round_id=${roundId}`;
  }
  return new EventSource(url);
}

/**
 * Human intervention in arena
 */
export interface InterventionRequest {
  action: 'inject_message' | 'adjust_score' | 'eliminate_strategy' | 'add_strategy';
  target_strategy_id?: string;
  message?: string;
  score_adjustment?: number;
  reason?: string;
  new_strategy_config?: {
    name?: string;
    description?: string;
    logic?: string;
    rules?: Record<string, unknown>;
  };
}

export function sendIntervention(arenaId: string, interventionRequest: InterventionRequest) {
  return request.post<{
    status: string;
    action: string;
    arena_id: string;
    timestamp: string;
    message?: string;
    old_score?: number;
    new_score?: number;
    strategy_id?: string;
    new_strategy_id?: string;
  }>(`/api/arena/${arenaId}/discussion/intervention`, interventionRequest);
}

/**
 * Get elimination history timeline
 */
export interface EliminationEvent {
  id: string;
  type: 'elimination' | 'supplement' | 'evaluation';
  timestamp: string;
  period?: string;
  strategy_name?: string;
  strategy_id?: string;
  score?: number;
  reason?: string;
  generator?: string;
  total_strategies?: number;
  eliminated_count?: number;
}

export function getEliminationHistory(arenaId: string, limit = 50) {
  return request.get<{ total: number; events: EliminationEvent[] }>(
    `/api/arena/${arenaId}/elimination-history?limit=${limit}`
  );
}

/**
 * Get strategy score breakdown
 */
export interface ScoreBreakdown {
  strategy_id: string;
  total_score: number;
  breakdown: {
    profitability: number;
    risk_control: number;
    stability: number;
    adaptability: number;
  };
  weights: {
    profitability: number;
    risk_control: number;
    stability: number;
    adaptability: number;
  };
}

export function getScoreBreakdown(arenaId: string, strategyId: string) {
  return request.get<ScoreBreakdown>(`/api/arena/${arenaId}/strategies/${strategyId}/score-breakdown`);
}
