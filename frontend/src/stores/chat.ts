import { defineStore } from 'pinia'
import { ref } from 'vue'
import { chatApi, type ChatMessage, type StreamEvent } from '@/api/chat'

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
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const sessionId = ref('')
  const loading = ref(false)
  
  // Thinking/Agent status
  const thinking = ref(false)
  const currentAgent = ref('')
  const currentIntent = ref('')
  const currentStockCodes = ref<string[]>([])
  const currentTool = ref('')
  const currentStatus = ref('')
  
  // Streaming content
  const streamingContent = ref('')

  const initSession = async () => {
    try {
      const result = await chatApi.createSession()
      sessionId.value = result.session_id
    } catch (e) {
      sessionId.value = `session_${Date.now()}`
    }
  }

  const getAgentDisplayName = (agent: string) => {
    return AGENT_NAMES[agent] || agent
  }

  const getIntentDisplayName = (intent: string) => {
    return INTENT_NAMES[intent] || intent
  }

  const getToolDisplayName = (tool: string) => {
    return TOOL_NAMES[tool] || tool
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
    loading.value = true
    thinking.value = true
    currentAgent.value = ''
    currentIntent.value = ''
    currentStockCodes.value = []
    currentTool.value = ''
    currentStatus.value = '分析中...'
    streamingContent.value = ''

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

    try {
      await chatApi.streamMessagePost(
        sessionId.value,
        content,
        (event: StreamEvent) => {
          switch (event.type) {
            case 'thinking':
              thinking.value = true
              currentAgent.value = event.agent
              currentIntent.value = event.intent
              currentStockCodes.value = event.stock_codes
              // Handle tool and status from DeepAgent
              if (event.tool) {
                currentTool.value = event.tool
              }
              if (event.status) {
                currentStatus.value = event.status
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
              
            case 'content':
              thinking.value = false
              streamingContent.value += event.content
              // Update message content
              const contentMsg = messages.value.find(m => m.id === assistantMessageId)
              if (contentMsg) {
                contentMsg.content = streamingContent.value
              }
              break
              
            case 'done':
              thinking.value = false
              loading.value = false
              // Final metadata update
              const doneMsg = messages.value.find(m => m.id === assistantMessageId)
              if (doneMsg) {
                doneMsg.metadata = event.metadata
              }
              break
              
            case 'error':
              thinking.value = false
              loading.value = false
              const errorMsg = messages.value.find(m => m.id === assistantMessageId)
              if (errorMsg) {
                errorMsg.content = `抱歉，处理请求时出现错误: ${event.error}`
              }
              break
          }
        },
        (error: Error) => {
          thinking.value = false
          loading.value = false
          const errorMsg = messages.value.find(m => m.id === assistantMessageId)
          if (errorMsg) {
            errorMsg.content = `抱歉，处理您的请求时出现了问题: ${error.message}`
          }
        }
      )
    } catch (e) {
      thinking.value = false
      loading.value = false
      const errorMsg = messages.value.find(m => m.id === assistantMessageId)
      if (errorMsg) {
        errorMsg.content = '抱歉，处理您的请求时出现了问题，请稍后重试。'
      }
    }
  }

  const loadHistory = async () => {
    if (!sessionId.value) return
    try {
      const result = await chatApi.getHistory(sessionId.value)
      messages.value = result.messages
    } catch (e) {
      // Ignore
    }
  }

  return {
    messages,
    sessionId,
    loading,
    thinking,
    currentAgent,
    currentIntent,
    currentStockCodes,
    currentTool,
    currentStatus,
    streamingContent,
    initSession,
    sendMessage,
    loadHistory,
    getAgentDisplayName,
    getIntentDisplayName,
    getToolDisplayName
  }
})
