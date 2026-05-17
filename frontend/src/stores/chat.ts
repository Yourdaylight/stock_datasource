import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { chatApi, type ChatMessage, type StreamEvent, type ChatSessionSummary, type DebugEvent, type VisualizationEvent } from '@/api/chat'

// LocalStorage keys
const MESSAGES_STORAGE_KEY = 'chat_messages'
const SESSION_STORAGE_KEY = 'chat_session_id'
const MAX_STORED_MESSAGES = 100

// Agent display names
const AGENT_NAMES: Record<string, string> = {
  'MarketAgent': '行情分析',
  'ScreenerAgent': '智能选股',
  'ReportAgent': '财报解读',
  'PortfolioAgent': '持仓管理',
  'BacktestAgent': '策略回测',
  'MemoryAgent': '记忆管理',
  'DataManageAgent': '数据管理',
  'ChatAgent': '智能对话',
  'StockDeepAgent': 'DeepAgent',
  'OrchestratorAgent': '智能调度',
  'MCPFallback': 'MCP工具',
  'IndexAgent': '指数分析',
  'EtfAgent': 'ETF分析',
  'OverviewAgent': '市场概览',
  'TopListAgent': '龙虎榜分析',
  'NewsAnalystAgent': '新闻分析',
}

// Tool display names
const TOOL_NAMES: Record<string, string> = {
  'get_stock_info': '查询股票信息',
  'get_stock_kline': '获取K线数据',
  'get_stock_valuation': '获取估值指标',
  'calculate_technical_indicators': '计算技术指标',
  'screen_stocks': '股票筛选',
  'get_market_overview': '市场概况',
  'write_todos': '规划任务',
  'read_todos': '检查进度',
  'write_file': '保存分析',
  'read_file': '读取文件',
  'get_daily_data': '获取日线数据',
  'get_latest_daily': '获取最新行情',
  'get_index_daily': '获取指数数据',
  'get_index_weight': '获取指数权重',
  'get_etf_daily': '获取ETF数据',
  'get_financial_report': '获取财务数据',
}

// Intent display names
const INTENT_NAMES: Record<string, string> = {
  'market_analysis': '行情分析',
  'stock_screening': '股票筛选',
  'financial_report': '财报分析',
  'portfolio_management': '持仓管理',
  'strategy_backtest': '策略回测',
  'memory_management': '记忆管理',
  'data_management': '数据管理',
  'general_chat': '智能对话',
  'index_analysis': '指数分析',
  'etf_analysis': 'ETF分析',
  'market_overview': '市场概览',
  'news_analysis': '新闻分析',
  'unknown': '分析需求',
}

// Plan step interface
interface PlanStep {
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'error'
  detail?: string
}

// Debug message for sidebar display
export interface DebugMessage {
  id: string
  debugType: DebugEvent['debug_type']
  agent: string
  timestamp: number
  data: DebugEvent['data']
  // A2A fields
  targetAgent?: string
  parentAgent?: string
  laneId?: string
  arenaId?: string
  // Display role
  role: 'orchestrator' | 'agent' | 'tool' | 'system' | 'handoff' | 'discussion'
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const sessionId = ref('')
  const loading = ref(false)
  
  // Session history management
  const sessions = ref<ChatSessionSummary[]>([])
  const sessionsLoading = ref(false)
  const sessionsTotal = ref(0)
  const currentSessionTitle = ref('')
  
  // Thinking/Agent status
  const thinking = ref(false)
  const currentAgent = ref('')
  const currentIntent = ref('')
  const currentStockCodes = ref<string[]>([])
  const currentTool = ref('')
  const currentStatus = ref('')
  
  // Plan-to-do tracking
  const currentPlan = ref<PlanStep[]>([])
  const currentPlanStep = ref(0)
  
  // ReAct mode tracking
  const reactSteps = ref<Array<{ thought: string; action: string; observation: string }>>([])
  
  // Streaming content
  const streamingContent = ref('')

  // Debug sidebar state
  const debugMessages = ref<DebugMessage[]>([])
  const debugSidebarOpen = ref(false)
  const messageDebugMap = ref<Record<string, DebugMessage[]>>({})
  let debugMsgCounter = 0
  let parallelLaneCounter = 0

  // Visualization state: maps message ID to array of visualization payloads
  const messageVisualizations = ref<Record<string, VisualizationEvent['visualization'][]>>({})
  // Accumulator for current streaming message's visualizations
  let pendingVisualizations: VisualizationEvent['visualization'][] = []

  // Decision Summary state (from arena discussions)
  const decisionSummary = ref<{
    signal: 'BUY' | 'SELL' | 'HOLD' | 'NONE'
    confidence: number
    bull_count: number
    bear_count: number
    neutral_count: number
    suggested_action: string
  } | null>(null)
  const decisionSidebarOpen = ref(false)

  // Preview signal state (instant rule-based, before full LLM synthesis)
  const previewSignal = ref<{
    signal: 'BUY' | 'SELL' | 'HOLD'
    confidence: number
    bull_count: number
    bear_count: number
    neutral_count: number
    stock_code: string
    is_preview: true
  } | null>(null)

  // AbortController for cancelling in-flight streams on session switch
  let streamAbortController: AbortController | null = null

  // Last session reference for returning user "继续上次对话" chip
  const lastSessionRef = ref<{ session_id: string; title: string } | null>(null)

  // ============ LocalStorage Persistence Functions ============
  
  // Save messages to localStorage for current session
  const saveMessagesToStorage = () => {
    if (!sessionId.value) return
    
    try {
      // Get all stored messages
      const storedData = localStorage.getItem(MESSAGES_STORAGE_KEY)
      const allMessages: Record<string, ChatMessage[]> = storedData ? JSON.parse(storedData) : {}
      
      // Save current session messages (limit to last MAX_STORED_MESSAGES)
      const messagesToSave = messages.value.slice(-MAX_STORED_MESSAGES)
      allMessages[sessionId.value] = messagesToSave
      
      // Clean up old sessions (keep only last 20 sessions)
      const sessionIds = Object.keys(allMessages)
      if (sessionIds.length > 20) {
        const sessionsToRemove = sessionIds.slice(0, sessionIds.length - 20)
        sessionsToRemove.forEach(sid => delete allMessages[sid])
      }
      
      localStorage.setItem(MESSAGES_STORAGE_KEY, JSON.stringify(allMessages))
    } catch (e) {
      console.warn('Failed to save messages to localStorage:', e)
    }
  }
  
  // Load messages from localStorage for current session
  const loadMessagesFromStorage = (): ChatMessage[] => {
    if (!sessionId.value) return []
    
    try {
      const storedData = localStorage.getItem(MESSAGES_STORAGE_KEY)
      if (!storedData) return []
      
      const allMessages: Record<string, ChatMessage[]> = JSON.parse(storedData)
      return allMessages[sessionId.value] || []
    } catch (e) {
      console.warn('Failed to load messages from localStorage:', e)
      return []
    }
  }
  
  // Clear messages for a specific session from localStorage
  const clearSessionFromStorage = (sid: string) => {
    try {
      const storedData = localStorage.getItem(MESSAGES_STORAGE_KEY)
      if (!storedData) return
      
      const allMessages: Record<string, ChatMessage[]> = JSON.parse(storedData)
      delete allMessages[sid]
      localStorage.setItem(MESSAGES_STORAGE_KEY, JSON.stringify(allMessages))
    } catch (e) {
      console.warn('Failed to clear session from localStorage:', e)
    }
  }
  
  // Save current session ID to localStorage
  const saveSessionToStorage = () => {
    if (sessionId.value) {
      localStorage.setItem(SESSION_STORAGE_KEY, sessionId.value)
    }
  }
  
  // Load last session ID from localStorage
  const loadSessionFromStorage = (): string | null => {
    return localStorage.getItem(SESSION_STORAGE_KEY)
  }
  
  // Watch for message changes and auto-save (debounced)
  let saveTimeout: ReturnType<typeof setTimeout> | null = null
  watch(messages, () => {
    if (saveTimeout) clearTimeout(saveTimeout)
    saveTimeout = setTimeout(() => {
      saveMessagesToStorage()
    }, 1000) // Debounce 1 second
  }, { deep: true })

  // ============ Session Management Functions ============

  const applyActiveSession = (targetSessionId: string, title = '') => {
    sessionId.value = targetSessionId
    currentSessionTitle.value = title
    saveSessionToStorage()
  }

  // Initialize or create a new session
  const initSession = async () => {
    const result = await chatApi.createSession()
    sessionId.value = result.session_id
    currentSessionTitle.value = ''
    messages.value = []
    saveSessionToStorage()
    await loadSessions()
  }
  
  // Restore session from localStorage or create new one
  // For returning users: start fresh with a "继续上次对话" chip
  // For first-time users (or explicit URL): load that session
  const restoreOrInitSession = async () => {
    const savedSessionId = loadSessionFromStorage()
    await loadSessions()

    // Record the last session for "继续上次对话" chip
    if (sessions.value.length > 0) {
      const latest = sessions.value[0]
      if (latest.message_count > 0) {
        lastSessionRef.value = {
          session_id: latest.session_id,
          title: latest.title || `会话 ${latest.session_id.slice(-6)}`,
        }
      }
    }

    // If user has sessions with messages, start fresh (new empty session)
    // so they see the welcome screen + "继续上次对话"
    const hasExistingSessions = sessions.value.some(s => s.message_count > 0)
    if (hasExistingSessions && !savedSessionId) {
      // No explicit saved session — returning user gets fresh start
      await initSession()
      return
    }

    if (savedSessionId) {
      const savedSession = sessions.value.find(s => s.session_id === savedSessionId)
      if (savedSession) {
        applyActiveSession(savedSession.session_id, savedSession.title || '')

        const localMessages = loadMessagesFromStorage()
        if (localMessages.length > 0) {
          messages.value = localMessages
        }

        try {
          await loadHistory(savedSession.session_id)
          return
        } catch (e) {
          console.warn('Failed to restore saved session from server:', e)
          clearSessionFromStorage(savedSession.session_id)
        }
      } else {
        localStorage.removeItem(SESSION_STORAGE_KEY)
      }
    }

    const latestSession = sessions.value[0]
    if (latestSession) {
      applyActiveSession(latestSession.session_id, latestSession.title || '')

      const localMessages = loadMessagesFromStorage()
      if (localMessages.length > 0) {
        messages.value = localMessages
      }

      try {
        await loadHistory(latestSession.session_id)
      } catch (e) {
        console.warn('Failed to load latest session from server:', e)
        messages.value = localMessages
      }
      return
    }

    await initSession()
  }

  // Load user's sessions
  const loadSessions = async (limit = 50, offset = 0) => {
    sessionsLoading.value = true
    try {
      const result = await chatApi.getSessions(limit, offset)
      sessions.value = result.sessions
      sessionsTotal.value = result.total
      return true
    } catch (e) {
      console.warn('Failed to load sessions:', e)
      return false
    } finally {
      sessionsLoading.value = false
    }
  }

  // Switch to a different session
  const switchSession = async (newSessionId: string) => {
    if (newSessionId === sessionId.value) return

    // CRITICAL: Abort any in-flight stream BEFORE changing session
    // This prevents the old stream's callbacks from writing into the new session
    if (streamAbortController) {
      streamAbortController.abort()
      streamAbortController = null
    }

    const previousSessionId = sessionId.value
    const previousMessages = [...messages.value]
    const previousTitle = currentSessionTitle.value
    const session = sessions.value.find(s => s.session_id === newSessionId)

    // Reset all streaming state immediately
    loading.value = false
    thinking.value = false
    streamingContent.value = ''
    currentAgent.value = ''
    currentIntent.value = ''
    currentTool.value = ''
    currentStatus.value = ''

    applyActiveSession(newSessionId, session?.title || '')
    messages.value = []

    const localMessages = loadMessagesFromStorage()
    if (localMessages.length > 0) {
      messages.value = localMessages
    }

    try {
      await loadHistory(newSessionId)
      return true
    } catch (e) {
      console.error('Failed to switch session:', e)
      sessionId.value = previousSessionId
      currentSessionTitle.value = previousTitle
      messages.value = previousMessages
      saveSessionToStorage()
      return false
    }
  }

  // Delete a session
  const deleteSession = async (targetSessionId: string) => {
    try {
      await chatApi.deleteSession(targetSessionId)
      // Remove from list
      sessions.value = sessions.value.filter(s => s.session_id !== targetSessionId)
      sessionsTotal.value = Math.max(0, sessionsTotal.value - 1)
      
      // Clear from localStorage
      clearSessionFromStorage(targetSessionId)
      
      // If current session was deleted, create new one
      if (targetSessionId === sessionId.value) {
        await initSession()
      }
      return true
    } catch (e) {
      console.error('Failed to delete session:', e)
      return false
    }
  }

  // Update session title
  const updateSessionTitle = async (targetSessionId: string, title: string) => {
    try {
      await chatApi.updateSessionTitle(targetSessionId, title)
      // Update in list
      const session = sessions.value.find(s => s.session_id === targetSessionId)
      if (session) {
        session.title = title
      }
      if (targetSessionId === sessionId.value) {
        currentSessionTitle.value = title
      }
      return true
    } catch (e) {
      console.error('Failed to update session title:', e)
      return false
    }
  }

  // Create new conversation (clear current and start fresh)
  const newConversation = async () => {
    await initSession()
  }

  // Clear current conversation messages (but keep session)
  const clearCurrentConversation = () => {
    messages.value = []
    streamingContent.value = ''
  }

  const getAgentDisplayName = (agent: string) => {
    return AGENT_NAMES[agent] || agent
  }

  const getIntentDisplayName = (intent: string) => {
    return INTENT_NAMES[intent] || intent
  }

  const getToolDisplayName = (tool: string) => {
    // Handle prefixed tool names like tushare_daily_get_daily_data
    const shortName = tool.replace(/^tushare_\w+_/, '').replace(/^etf_/, '')
    return TOOL_NAMES[shortName] || TOOL_NAMES[tool] || tool
  }

  const resetStreamingState = () => {
    loading.value = true
    thinking.value = true
    currentAgent.value = ''
    currentIntent.value = ''
    currentStockCodes.value = []
    currentTool.value = ''
    currentStatus.value = '分析中...'
    currentPlan.value = []
    currentPlanStep.value = 0
    reactSteps.value = []
    streamingContent.value = ''
    // Reset debug state for new message
    debugMessages.value = []
    debugMsgCounter = 0
    parallelLaneCounter = 0
    // Reset visualization accumulator
    pendingVisualizations = []
    // Reset decision/preview state
    previewSignal.value = null
    decisionSummary.value = null
  }

  // Convert a debug SSE event into a DebugMessage for sidebar display
  const processDebugEvent = (event: DebugEvent) => {
    const debugType = event.debug_type
    const data = event.data

    // Determine role
    let role: DebugMessage['role'] = 'system'
    if (debugType === 'classification' || debugType === 'routing') {
      role = 'orchestrator'
    } else if (debugType === 'agent_start' || debugType === 'agent_end') {
      role = 'agent'
    } else if (debugType === 'tool_result') {
      role = 'tool'
    } else if (debugType === 'handoff') {
      role = 'handoff'
    } else if (debugType === 'data_sharing') {
      role = 'system'
    } else if (debugType === 'discussion_argument' || debugType === 'decision_summary' || debugType === 'preview_signal' || debugType === 'arena_error') {
      role = 'discussion'
    }

    // Determine laneId for parallel routing
    let laneId: string | undefined
    if (debugType === 'routing' && data.is_parallel && data.to_agent) {
      laneId = `lane_${parallelLaneCounter++}`
    }
    // For agent_start, inherit lane from matching routing event
    if (debugType === 'agent_start' && data.parent_agent) {
      const matchingRoute = debugMessages.value.find(
        m => m.debugType === 'routing' && m.data.to_agent === event.agent && m.laneId
      )
      if (matchingRoute) {
        laneId = matchingRoute.laneId
      }
    }

    const msg: DebugMessage = {
      id: `debug_${debugMsgCounter++}`,
      debugType,
      agent: event.agent,
      timestamp: event.timestamp,
      data,
      targetAgent: data.to_agent,
      parentAgent: data.parent_agent,
      laneId,
      arenaId: event.arena_id,
      role,
    }

    debugMessages.value.push(msg)

    // Special handling for preview_signal: show fast preview before full LLM summary
    if (debugType === 'preview_signal' && data.signal) {
      previewSignal.value = {
        signal: data.signal as 'BUY' | 'SELL' | 'HOLD',
        confidence: data.confidence || 0,
        bull_count: data.bull_count || 0,
        bear_count: data.bear_count || 0,
        neutral_count: data.neutral_count || 0,
        stock_code: data.stock_code || '',
        is_preview: true,
      }
      decisionSidebarOpen.value = true
      console.log('[Chat] Preview signal received:', previewSignal.value)
    }

    // Special handling for decision_summary: update decision state (upgrades preview)
    if (debugType === 'decision_summary' && data.signal) {
      // Clear preview signal — the full summary replaces it
      previewSignal.value = null
      decisionSummary.value = {
        signal: data.signal as 'BUY' | 'SELL' | 'HOLD' | 'NONE',
        confidence: data.confidence || 0,
        bull_count: data.bull_count || 0,
        bear_count: data.bear_count || 0,
        neutral_count: data.neutral_count || 0,
        suggested_action: data.suggested_action || '',
      }
      decisionSidebarOpen.value = true
      console.log('[Chat] Decision summary received:', decisionSummary.value)
    }
  }

  // Save debug messages snapshot for a completed message (for history playback)
  const saveDebugSnapshot = (messageId: string) => {
    if (debugMessages.value.length > 0) {
      messageDebugMap.value[messageId] = [...debugMessages.value]
    }
  }

  // Load debug messages for a historical message
  const viewDebug = (messageId: string) => {
    const saved = messageDebugMap.value[messageId]
    if (saved) {
      debugMessages.value = [...saved]
      debugSidebarOpen.value = true
    } else {
      // Try to load from message metadata
      const msg = messages.value.find(m => m.id === messageId)
      if (msg?.metadata?.debug_events) {
        debugMessages.value = []
        debugMsgCounter = 0
        parallelLaneCounter = 0
        for (const evt of msg.metadata.debug_events as DebugEvent[]) {
          processDebugEvent(evt)
        }
        debugSidebarOpen.value = true
      }
    }
  }

  const sendMessage = async (content: string) => {
    if (!sessionId.value) {
      await initSession()
    }

    // Add user message
    const userMessage: ChatMessage = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date().toLocaleTimeString()
    }
    messages.value.push(userMessage)

    // Reset streaming state
    resetStreamingState()

    // Create placeholder for assistant message
    const assistantMessageId = `msg_${Date.now() + 1}`
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toLocaleTimeString(),
      metadata: {}
    }
    messages.value.push(assistantMessage)

    // Capture the session ID at the time of sending — used as a guard
    // to prevent stale callbacks from writing into a different session
    const sendingSessionId = sessionId.value

    // Create AbortController for this stream
    if (streamAbortController) {
      streamAbortController.abort()
    }
    streamAbortController = new AbortController()
    const currentController = streamAbortController

    try {
      await chatApi.streamMessagePost(
        sendingSessionId,
        content,
        (event: StreamEvent) => {
          // SESSION GUARD: If user switched sessions, discard stale events
          if (sessionId.value !== sendingSessionId) {
            return
          }

          // Debug log for event tracking
          console.debug('[Chat] Received event:', event.type, event)

          switch (event.type) {
            case 'thinking':
              thinking.value = true
              currentAgent.value = event.agent || currentAgent.value
              currentIntent.value = event.intent || currentIntent.value
              currentStockCodes.value = event.stock_codes || currentStockCodes.value
              // Handle tool and status from DeepAgent
              if (event.tool) {
                currentTool.value = event.tool
              }
              if (event.status) {
                currentStatus.value = event.status
              }
              // Handle plan steps if present
              if ((event as any).plan) {
                currentPlan.value = (event as any).plan.map((step: string, idx: number) => ({
                  id: `step_${idx}`,
                  name: step,
                  status: idx === 0 ? 'running' : 'pending'
                }))
              }
              // Update message metadata
              const thinkingMsg = messages.value.find(m => m.id === assistantMessageId)
              if (thinkingMsg) {
                thinkingMsg.metadata = {
                  intent: event.intent,
                  agent: event.agent,
                  stock_codes: event.stock_codes,
                  tool: event.tool,
                  status: event.status
                }
              }
              break

            case 'tool':
              thinking.value = true
              if (event.agent) {
                currentAgent.value = event.agent
              }
              currentTool.value = event.tool
              currentStatus.value = event.status || `正在调用: ${getToolDisplayName(event.tool)}`
              const toolMsg = messages.value.find(m => m.id === assistantMessageId)
              if (toolMsg) {
                toolMsg.metadata = {
                  ...(toolMsg.metadata || {}),
                  agent: event.agent || toolMsg.metadata?.agent,
                  tool: event.tool,
                  status: currentStatus.value
                }
              }
              break

            case 'content':
              thinking.value = false
              // Validate content before appending - prevent displaying partial/garbage data
              if (event.content && typeof event.content === 'string') {
                // Filter out obvious garbage like partial JSON or control characters
                const cleanContent = event.content.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '')
                if (cleanContent.length > 0) {
                  streamingContent.value += cleanContent
                  // Update message content
                  const contentMsg = messages.value.find(m => m.id === assistantMessageId)
                  if (contentMsg) {
                    contentMsg.content = streamingContent.value
                  }
                }
              }
              break

            case 'debug':
              // Process debug events for sidebar
              processDebugEvent(event as DebugEvent)
              break

            case 'visualization':
              // Accumulate visualization events for current message
              {
                const vizEvent = event as VisualizationEvent
                if (vizEvent.visualization) {
                  pendingVisualizations.push(vizEvent.visualization)
                  // Also store immediately so chart renders during streaming
                  if (!messageVisualizations.value[assistantMessageId]) {
                    messageVisualizations.value[assistantMessageId] = []
                  }
                  messageVisualizations.value[assistantMessageId].push(vizEvent.visualization)
                }
              }
              break

            case 'done':
              thinking.value = false
              loading.value = false
              currentTool.value = ''
              currentStatus.value = ''
              // Final metadata update
              const doneMsg = messages.value.find(m => m.id === assistantMessageId)
              if (doneMsg) {
                doneMsg.metadata = event.metadata
                // If no content was received but we have metadata, show a fallback message
                if (!doneMsg.content && event.metadata) {
                  doneMsg.content = '处理完成，但未生成回复内容。'
                }
              }
              // Save debug snapshot for this message
              saveDebugSnapshot(assistantMessageId)
              // Auto-generate session title after first assistant response
              autoGenerateTitle(sendingSessionId, content)
              console.debug('[Chat] Stream completed with metadata:', event.metadata)
              break

            case 'error':
              thinking.value = false
              loading.value = false
              currentTool.value = ''
              currentStatus.value = ''
              const errorMsg = messages.value.find(m => m.id === assistantMessageId)
              if (errorMsg) {
                // Show more user-friendly error messages
                const errorDetail = event.error || '未知错误'
                console.error('[Chat] Stream error:', errorDetail)
                errorMsg.content = `抱歉，处理请求时出现错误: ${errorDetail}`
              }
              break

            default:
              console.warn('[Chat] Unknown event type:', (event as any).type)
          }
        },
        (error: Error) => {
          // SESSION GUARD: Ignore errors from aborted/stale streams
          if (sessionId.value !== sendingSessionId) {
            return
          }
          console.error('[Chat] Stream connection error:', error)
          thinking.value = false
          loading.value = false
          currentStatus.value = ''
          const errorMsg = messages.value.find(m => m.id === assistantMessageId)
          if (errorMsg) {
            // If we have some content, keep it and add error note
            if (errorMsg.content && errorMsg.content.length > 10) {
              errorMsg.content += '\n\n> ⚠️ 响应可能不完整，连接中断。'
            } else {
              errorMsg.content = `抱歉，处理您的请求时出现了问题: ${error.message}`
            }
          }
        },
        currentController
      )
    } catch (e) {
      // SESSION GUARD
      if (sessionId.value !== sendingSessionId) return
      console.error('[Chat] Unexpected error:', e)
      thinking.value = false
      loading.value = false
      currentStatus.value = ''
      const errorMsg = messages.value.find(m => m.id === assistantMessageId)
      if (errorMsg) {
        errorMsg.content = '抱歉，处理您的请求时出现了问题，请稍后重试。'
      }
    }
  }

  // Auto-generate session title using LLM after first assistant response
  const autoGenerateTitle = async (targetSessionId: string, userMessage: string) => {
    // Only generate title for sessions that don't have one yet
    const session = sessions.value.find(s => s.session_id === targetSessionId)
    if (!session) return
    if (session.title && session.title.trim() !== '') return

    // Only trigger on first exchange (message_count ≤ 2 means first user + first assistant)
    if (session.message_count > 2) return

    try {
      const result = await chatApi.generateSessionTitle(targetSessionId)
      if (result.title) {
        // Update in sessions list
        session.title = result.title
        // Update current title if it's the active session
        if (targetSessionId === sessionId.value) {
          currentSessionTitle.value = result.title
        }
      }
    } catch (e) {
      console.warn('Failed to auto-generate session title:', e)
    }
  }

  const loadHistory = async (targetSessionId = sessionId.value) => {
    if (!targetSessionId) return false

    const result = await chatApi.getHistory(targetSessionId)
    messages.value = result.messages
    messageVisualizations.value = {}

    // Reset debug/decision state before restoring from history
    debugMessages.value = []
    debugMsgCounter = 0
    parallelLaneCounter = 0
    previewSignal.value = null
    decisionSummary.value = null

    for (const msg of result.messages) {
      if (msg.role !== 'assistant') continue

      // Restore visualizations
      if (msg.metadata?.visualizations) {
        const vizList = msg.metadata.visualizations as VisualizationEvent['visualization'][]
        if (vizList.length > 0) {
          messageVisualizations.value[msg.id] = vizList
        }
      }

      // Restore debug events (chain trace + discussion + decision signals)
      if (msg.metadata?.debug_events) {
        const events = msg.metadata.debug_events as DebugEvent[]
        for (const evt of events) {
          processDebugEvent(evt)
        }
        // Save the snapshot for per-message "查看调试" button
        saveDebugSnapshot(msg.id)
      }
    }

    return true
  }

  const clearMessages = () => {
    messages.value = []
    streamingContent.value = ''
  }

  return {
    // State
    messages,
    sessionId,
    loading,
    sessions,
    sessionsLoading,
    sessionsTotal,
    currentSessionTitle,
    thinking,
    currentAgent,
    currentIntent,
    currentStockCodes,
    currentTool,
    currentStatus,
    currentPlan,
    currentPlanStep,
    reactSteps,
    streamingContent,
    // Debug state
    debugMessages,
    debugSidebarOpen,
    messageDebugMap,
    // Visualization state
    messageVisualizations,
    // Decision summary state
    decisionSummary,
    decisionSidebarOpen,
    previewSignal,
    lastSessionRef,
    // Actions
    initSession,
    restoreOrInitSession,
    loadSessions,
    switchSession,
    deleteSession,
    updateSessionTitle,
    newConversation,
    clearCurrentConversation,
    sendMessage,
    loadHistory,
    clearMessages,
    viewDebug,
    // Helpers
    getAgentDisplayName,
    getIntentDisplayName,
    getToolDisplayName
  }
})
