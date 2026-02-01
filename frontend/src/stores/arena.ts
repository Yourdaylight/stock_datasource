/**
 * Arena Store
 * State management for Multi-Agent Strategy Arena
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import * as arenaApi from '@/api/arena';
import type {
  ArenaStatus,
  Strategy,
  LeaderboardEntry,
  ThinkingMessage,
  DiscussionRound,
  EliminationEvent,
  ScoreBreakdown,
  InterventionRequest,
} from '@/api/arena';

// Local storage key for offline messages
const OFFLINE_MESSAGES_KEY = 'arena_offline_messages';

export const useArenaStore = defineStore('arena', () => {
  // State
  const arenas = ref<ArenaStatus[]>([]);
  const currentArena = ref<ArenaStatus | null>(null);
  const strategies = ref<Strategy[]>([]);
  const leaderboard = ref<LeaderboardEntry[]>([]);
  const discussions = ref<DiscussionRound[]>([]);
  const thinkingMessages = ref<ThinkingMessage[]>([]);
  const eliminationEvents = ref<EliminationEvent[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  // SSE connection
  let eventSource: EventSource | null = null;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 5;
  const lastMessageTimestamp = ref<string | null>(null);

  // Computed
  const activeStrategies = computed(() => strategies.value.filter((s) => s.is_active));
  const isRunning = computed(() => 
    currentArena.value?.state && 
    ['discussing', 'backtesting', 'simulating', 'evaluating'].includes(currentArena.value.state)
  );

  // Actions
  async function fetchArenas(state?: string) {
    loading.value = true;
    error.value = null;
    try {
      const response = await arenaApi.listArenas(state);
      arenas.value = response.arenas;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch arenas';
    } finally {
      loading.value = false;
    }
  }

  async function createArena(config: arenaApi.ArenaConfig) {
    loading.value = true;
    error.value = null;
    try {
      const arena = await arenaApi.createArena(config);
      arenas.value.unshift(arena);
      currentArena.value = arena;
      return arena;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to create arena';
      throw e;
    } finally {
      loading.value = false;
    }
  }

  async function fetchArenaStatus(arenaId: string) {
    loading.value = true;
    error.value = null;
    try {
      const status = await arenaApi.getArenaStatus(arenaId);
      currentArena.value = status;
      return status;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch arena status';
      throw e;
    } finally {
      loading.value = false;
    }
  }

  async function startArena(arenaId: string) {
    try {
      await arenaApi.startArena(arenaId);
      await fetchArenaStatus(arenaId);
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to start arena';
      throw e;
    }
  }

  async function pauseArena(arenaId: string) {
    try {
      await arenaApi.pauseArena(arenaId);
      await fetchArenaStatus(arenaId);
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to pause arena';
      throw e;
    }
  }

  async function resumeArena(arenaId: string) {
    try {
      await arenaApi.resumeArena(arenaId);
      await fetchArenaStatus(arenaId);
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to resume arena';
      throw e;
    }
  }

  async function deleteArena(arenaId: string) {
    try {
      await arenaApi.deleteArena(arenaId);
      arenas.value = arenas.value.filter((a) => a.id !== arenaId);
      if (currentArena.value?.id === arenaId) {
        currentArena.value = null;
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to delete arena';
      throw e;
    }
  }

  async function fetchStrategies(arenaId: string, activeOnly = false) {
    try {
      const response = await arenaApi.getStrategies(arenaId, activeOnly);
      strategies.value = response.strategies;
      return response.strategies;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch strategies';
      throw e;
    }
  }

  async function fetchLeaderboard(arenaId: string) {
    try {
      const response = await arenaApi.getLeaderboard(arenaId);
      leaderboard.value = response.leaderboard;
      return response.leaderboard;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch leaderboard';
      throw e;
    }
  }

  async function fetchDiscussions(arenaId: string) {
    try {
      const response = await arenaApi.getDiscussions(arenaId);
      discussions.value = response.discussions;
      return response.discussions;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch discussions';
      throw e;
    }
  }

  async function triggerEvaluation(arenaId: string, period: 'daily' | 'weekly' | 'monthly') {
    try {
      await arenaApi.triggerEvaluation(arenaId, period);
      await fetchArenaStatus(arenaId);
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to trigger evaluation';
      throw e;
    }
  }

  async function startDiscussion(arenaId: string, mode: 'debate' | 'collaboration' | 'review') {
    try {
      await arenaApi.startDiscussion(arenaId, mode);
      await fetchArenaStatus(arenaId);
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to start discussion';
      throw e;
    }
  }

// SSE Management
  function connectThinkingStream(arenaId: string, roundId?: string) {
    // Close existing connection
    disconnectThinkingStream();

    // Load offline messages first
    loadOfflineMessages(arenaId);

    eventSource = arenaApi.createThinkingStream(arenaId, roundId);
    reconnectAttempts = 0;

    // Handler for processing incoming messages
    const handleMessage = (event: MessageEvent) => {
      try {
        // Skip keepalive messages
        if (event.data.includes('"keepalive":true')) {
          return;
        }
        const message = JSON.parse(event.data) as ThinkingMessage;
        thinkingMessages.value.push(message);
        lastMessageTimestamp.value = message.timestamp;
        
        // Save to offline storage
        saveMessageToOfflineStorage(arenaId, message);
        
        // Limit messages to prevent memory issues
        if (thinkingMessages.value.length > 500) {
          thinkingMessages.value = thinkingMessages.value.slice(-300);
        }
      } catch {
        console.warn('Failed to parse thinking message:', event.data);
      }
    };

    // Listen for all SSE event types that the backend sends
    // Backend sends events with types: thinking, argument, conclusion, system, error, intervention
    const eventTypes = ['thinking', 'argument', 'conclusion', 'system', 'error', 'intervention'];
    eventTypes.forEach((eventType) => {
      eventSource!.addEventListener(eventType, handleMessage);
    });

    // Also listen for generic messages (no event type specified)
    eventSource.onmessage = handleMessage;

    eventSource.onerror = () => {
      console.warn('Thinking stream connection error');
      reconnectAttempts++;
      
      if (reconnectAttempts <= maxReconnectAttempts) {
        // Exponential backoff reconnect
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
        setTimeout(() => {
          if (currentArena.value?.id === arenaId) {
            connectThinkingStream(arenaId, roundId);
          }
        }, delay);
      } else {
        console.error('Max reconnect attempts reached');
        error.value = 'Connection lost. Please refresh the page.';
      }
    };

    eventSource.onopen = () => {
      reconnectAttempts = 0;
      error.value = null;
    };
  }

  function disconnectThinkingStream() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  }

  function clearThinkingMessages() {
    thinkingMessages.value = [];
  }

  // Offline message management
  function loadOfflineMessages(arenaId: string) {
    try {
      const stored = localStorage.getItem(`${OFFLINE_MESSAGES_KEY}_${arenaId}`);
      if (stored) {
        const messages = JSON.parse(stored) as ThinkingMessage[];
        // Only load messages newer than last seen
        if (lastMessageTimestamp.value) {
          const newMessages = messages.filter((m) => m.timestamp > lastMessageTimestamp.value!);
          thinkingMessages.value = [...thinkingMessages.value, ...newMessages];
        } else {
          thinkingMessages.value = messages.slice(-100); // Load last 100 messages
        }
        
        if (messages.length > 0) {
          lastMessageTimestamp.value = messages[messages.length - 1].timestamp;
        }
      }
    } catch (err) {
      console.warn('Failed to load offline messages:', err);
    }
  }

  function saveMessageToOfflineStorage(arenaId: string, message: ThinkingMessage) {
    try {
      const key = `${OFFLINE_MESSAGES_KEY}_${arenaId}`;
      const stored = localStorage.getItem(key);
      let messages: ThinkingMessage[] = stored ? JSON.parse(stored) : [];
      
      messages.push(message);
      
      // Keep only last 200 messages in offline storage
      if (messages.length > 200) {
        messages = messages.slice(-200);
      }
      
      localStorage.setItem(key, JSON.stringify(messages));
    } catch (err) {
      console.warn('Failed to save message to offline storage:', err);
    }
  }

  function clearOfflineMessages(arenaId: string) {
    try {
      localStorage.removeItem(`${OFFLINE_MESSAGES_KEY}_${arenaId}`);
    } catch (err) {
      console.warn('Failed to clear offline messages:', err);
    }
  }

  // Elimination history
  async function fetchEliminationHistory(arenaId: string) {
    try {
      const response = await arenaApi.getEliminationHistory(arenaId);
      eliminationEvents.value = response.events;
      return response.events;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch elimination history';
      throw e;
    }
  }

  // Score breakdown
  async function fetchScoreBreakdown(arenaId: string, strategyId: string) {
    try {
      return await arenaApi.getScoreBreakdown(arenaId, strategyId);
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch score breakdown';
      throw e;
    }
  }

  // Human intervention
  async function sendIntervention(arenaId: string, request: InterventionRequest) {
    try {
      const result = await arenaApi.sendIntervention(arenaId, request);
      // Refresh data after intervention
      await fetchArenaStatus(arenaId);
      await fetchLeaderboard(arenaId);
      return result;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to send intervention';
      throw e;
    }
  }

  // Cleanup
  function $reset() {
    arenas.value = [];
    currentArena.value = null;
    strategies.value = [];
    leaderboard.value = [];
    discussions.value = [];
    thinkingMessages.value = [];
    eliminationEvents.value = [];
    loading.value = false;
    error.value = null;
    lastMessageTimestamp.value = null;
    reconnectAttempts = 0;
    disconnectThinkingStream();
  }

  return {
    // State
    arenas,
    currentArena,
    strategies,
    leaderboard,
    discussions,
    thinkingMessages,
    eliminationEvents,
    loading,
    error,

    // Computed
    activeStrategies,
    isRunning,

    // Actions
    fetchArenas,
    createArena,
    fetchArenaStatus,
    startArena,
    pauseArena,
    resumeArena,
    deleteArena,
    fetchStrategies,
    fetchLeaderboard,
    fetchDiscussions,
    triggerEvaluation,
    startDiscussion,
    connectThinkingStream,
    disconnectThinkingStream,
    clearThinkingMessages,
    fetchEliminationHistory,
    fetchScoreBreakdown,
    sendIntervention,
    clearOfflineMessages,
    $reset,
  };
});
