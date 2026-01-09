<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import type { ChatMessage } from '@/api/chat'
import { useChatStore } from '@/stores/chat'

// Configure marked for security
marked.setOptions({
  breaks: true,
  gfm: true
})

const props = defineProps<{
  messages: ChatMessage[]
  loading: boolean
}>()

const chatStore = useChatStore()

// Render markdown to HTML
const renderMarkdown = (content: string): string => {
  if (!content) return ''
  try {
    return marked.parse(content) as string
  } catch (e) {
    return content
  }
}

// Get agent tag color
const getAgentColor = (agent: string): string => {
  const colors: Record<string, string> = {
    'MarketAgent': 'primary',
    'ScreenerAgent': 'success',
    'ReportAgent': 'warning',
    'PortfolioAgent': 'danger',
    'BacktestAgent': 'default',
    'ChatAgent': 'primary',
    'StockDeepAgent': 'primary'
  }
  return colors[agent] || 'default'
}

// Get tool tag color
const getToolColor = (tool: string): string => {
  const colors: Record<string, string> = {
    'get_stock_info': 'primary',
    'get_stock_kline': 'success',
    'get_stock_valuation': 'warning',
    'calculate_technical_indicators': 'danger',
    'screen_stocks': 'success',
    'get_market_overview': 'primary',
    'write_todos': 'default',
    'read_todos': 'default',
  }
  return colors[tool] || 'default'
}
</script>

<template>
  <div class="message-list">
    <div v-if="messages.length === 0" class="empty-state">
      <t-icon name="chat" size="48px" style="color: #ddd" />
      <p>开始与 AI 助手对话</p>
      <p class="hint">我可以帮您分析股票行情、筛选股票、解读财报等</p>
    </div>
    
    <div
      v-for="msg in messages"
      :key="msg.id"
      :class="['message-item', msg.role]"
    >
      <div class="avatar">
        <t-avatar v-if="msg.role === 'user'" size="32px">U</t-avatar>
        <t-avatar v-else size="32px" style="background: #0052d9">AI</t-avatar>
      </div>
      <div class="message-content">
        <!-- Agent info for assistant messages -->
        <div v-if="msg.role === 'assistant' && msg.metadata?.agent" class="agent-info">
          <t-tag 
            :theme="getAgentColor(msg.metadata.agent)" 
            variant="light" 
            size="small"
          >
            {{ chatStore.getAgentDisplayName(msg.metadata.agent) }}
          </t-tag>
          <span v-if="msg.metadata.stock_codes?.length" class="stock-codes">
            <t-tag 
              v-for="code in msg.metadata.stock_codes" 
              :key="code"
              theme="default"
              variant="outline"
              size="small"
            >
              {{ code }}
            </t-tag>
          </span>
        </div>
        
        <!-- Message text with markdown rendering -->
        <div 
          v-if="msg.role === 'assistant'" 
          class="message-text markdown-body"
          v-html="renderMarkdown(msg.content)"
        ></div>
        <div v-else class="message-text">{{ msg.content }}</div>
        
        <div class="message-time">{{ msg.timestamp }}</div>
      </div>
    </div>
    
    <!-- Thinking/Loading state -->
    <div v-if="loading" class="message-item assistant">
      <div class="avatar">
        <t-avatar size="32px" style="background: #0052d9">AI</t-avatar>
      </div>
      <div class="message-content">
        <div v-if="chatStore.thinking" class="thinking-state">
          <div class="thinking-header">
            <t-loading size="small" />
            <span class="thinking-text">{{ chatStore.currentStatus || '思考中...' }}</span>
          </div>
          <div v-if="chatStore.currentAgent" class="thinking-info">
            <t-tag 
              :theme="getAgentColor(chatStore.currentAgent)" 
              variant="light" 
              size="small"
            >
              {{ chatStore.getAgentDisplayName(chatStore.currentAgent) }}
            </t-tag>
            <span class="intent-text">
              正在{{ chatStore.getIntentDisplayName(chatStore.currentIntent) }}
            </span>
            <span v-if="chatStore.currentStockCodes.length" class="stock-codes">
              <t-tag 
                v-for="code in chatStore.currentStockCodes" 
                :key="code"
                theme="default"
                variant="outline"
                size="small"
              >
                {{ code }}
              </t-tag>
            </span>
          </div>
          <!-- Show current tool being called -->
          <div v-if="chatStore.currentTool" class="tool-info">
            <t-tag 
              :theme="getToolColor(chatStore.currentTool)" 
              variant="outline" 
              size="small"
            >
              🔧 {{ chatStore.getToolDisplayName(chatStore.currentTool) }}
            </t-tag>
          </div>
        </div>
        <t-loading v-else size="small" text="生成中..." />
      </div>
    </div>
  </div>
</template>

<style scoped>
.message-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  color: #999;
}

.empty-state .hint {
  font-size: 12px;
  color: #bbb;
  margin-top: 8px;
}

.message-item {
  display: flex;
  gap: 12px;
}

.message-item.user {
  flex-direction: row-reverse;
}

.message-content {
  max-width: 80%;
}

.agent-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.stock-codes {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.message-text {
  padding: 12px 16px;
  border-radius: 8px;
  background: #f5f5f5;
  line-height: 1.6;
}

.message-item.user .message-text {
  background: #0052d9;
  color: #fff;
}

/* Markdown styles */
.message-text.markdown-body {
  font-size: 14px;
}

.message-text.markdown-body :deep(h1),
.message-text.markdown-body :deep(h2),
.message-text.markdown-body :deep(h3),
.message-text.markdown-body :deep(h4) {
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: 600;
}

.message-text.markdown-body :deep(h1) { font-size: 1.5em; }
.message-text.markdown-body :deep(h2) { font-size: 1.3em; }
.message-text.markdown-body :deep(h3) { font-size: 1.1em; }
.message-text.markdown-body :deep(h4) { font-size: 1em; }

.message-text.markdown-body :deep(p) {
  margin: 8px 0;
}

.message-text.markdown-body :deep(ul),
.message-text.markdown-body :deep(ol) {
  padding-left: 20px;
  margin: 8px 0;
}

.message-text.markdown-body :deep(li) {
  margin: 4px 0;
}

.message-text.markdown-body :deep(code) {
  background: #e8e8e8;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 0.9em;
}

.message-text.markdown-body :deep(pre) {
  background: #2d2d2d;
  color: #f8f8f2;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 8px 0;
}

.message-text.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}

.message-text.markdown-body :deep(blockquote) {
  border-left: 4px solid #0052d9;
  padding-left: 12px;
  margin: 8px 0;
  color: #666;
}

.message-text.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}

.message-text.markdown-body :deep(th),
.message-text.markdown-body :deep(td) {
  border: 1px solid #ddd;
  padding: 8px 12px;
  text-align: left;
}

.message-text.markdown-body :deep(th) {
  background: #f5f5f5;
  font-weight: 600;
}

.message-text.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid #ddd;
  margin: 16px 0;
}

.message-text.markdown-body :deep(strong) {
  font-weight: 600;
}

.message-text.markdown-body :deep(em) {
  font-style: italic;
}

.message-time {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.message-item.user .message-time {
  text-align: right;
}

.thinking-state {
  padding: 12px 16px;
  background: #f5f5f5;
  border-radius: 8px;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.thinking-text {
  color: #666;
  font-size: 14px;
}

.thinking-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.tool-info {
  margin-top: 8px;
}

.intent-text {
  font-size: 12px;
  color: #999;
}
</style>
