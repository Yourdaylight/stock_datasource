<template>
  <div class="agent-discussion-sidebar" v-if="visible">
    <!-- Header -->
    <div class="sidebar-header">
      <div class="header-title">
        <t-icon name="user-talk" />
        <span>Agent讨论</span>
        <t-tag v-if="stockCode" size="small" theme="primary">{{ stockCode }}</t-tag>
      </div>
      <t-button variant="text" size="small" @click="$emit('close')">
        <t-icon name="close" />
      </t-button>
    </div>

    <!-- Signal Banner -->
    <div
      class="signal-banner"
      v-if="currentSignal"
      :class="`signal-${currentSignal.signal}`"
    >
      <span class="signal-icon">{{ signalIcon }}</span>
      <span class="signal-label">{{ signalLabel }}</span>
      <span class="signal-confidence">{{ (currentSignal.confidence * 100).toFixed(0) }}%</span>
      <div class="signal-votes">
        <span class="bull">{{ currentSignal.bull_count }}多</span>
        <span class="bear">{{ currentSignal.bear_count }}空</span>
      </div>
    </div>

    <!-- Discussion Stream -->
    <div ref="streamContainer" class="discussion-stream">
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="stream-message"
        :class="`msg-${msg.message_type}`"
      >
        <div class="msg-header">
          <span class="msg-role">{{ getRoleLabel(msg.agent_role) }}</span>
          <t-tag
            v-if="msg.metadata?.direction"
            :theme="getDirectionTheme(msg.metadata.direction)"
            size="small"
            variant="light"
          >
            {{ getDirectionLabel(msg.metadata.direction) }}
          </t-tag>
          <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
        </div>
        <div class="msg-content">{{ truncate(msg.content, 150) }}</div>
      </div>
      <div v-if="messages.length === 0 && !loading" class="empty-stream">
        <t-icon name="chat" size="32px" />
        <p>暂无Agent讨论</p>
        <p class="hint" v-if="!stockCode">在聊天中提及股票代码后自动关联</p>
      </div>
    </div>

    <!-- Opinion Bar -->
    <div class="opinion-footer" v-if="totalVotes > 0">
      <div class="opinion-mini-bar">
        <div class="bar-segment bullish" :style="{ width: bullishPct }"></div>
        <div class="bar-segment neutral" :style="{ width: neutralPct }"></div>
        <div class="bar-segment bearish" :style="{ width: bearishPct }"></div>
      </div>
      <div class="opinion-labels">
        <span class="label-bull">多{{ currentSignal?.bull_count || 0 }}</span>
        <span class="label-neutral">中{{ currentSignal?.neutral_count || 0 }}</span>
        <span class="label-bear">空{{ currentSignal?.bear_count || 0 }}</span>
      </div>
    </div>

    <!-- Action -->
    <div class="sidebar-footer">
      <t-button
        v-if="currentSignal?.arena_id"
        variant="text"
        size="small"
        @click="$router.push(`/arena/${currentSignal.arena_id}`)"
      >
        查看完整讨论 →
      </t-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import { getDecisionByStock } from '@/api/decision'
import type { DecisionSummary, KeyArgument } from '@/api/decision'
import type { ThinkingMessage } from '@/api/arena'
import { createThinkingStream } from '@/api/arena'

const props = defineProps<{
  visible: boolean
  stockCode: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const currentSignal = ref<DecisionSummary | null>(null)
const messages = ref<ThinkingMessage[]>([])
const loading = ref(false)
const streamContainer = ref<HTMLElement | null>(null)
let eventSource: EventSource | null = null

// Computed
const signalIcon = computed(() => {
  const icons: Record<string, string> = { buy: '↑', sell: '↓', hold: '→' }
  return icons[currentSignal.value?.signal || 'hold'] || '→'
})

const signalLabel = computed(() => {
  const labels: Record<string, string> = { buy: '买入', sell: '卖出', hold: '持有' }
  return labels[currentSignal.value?.signal || 'hold'] || '持有'
})

const totalVotes = computed(() => {
  if (!currentSignal.value) return 0
  return currentSignal.value.bull_count + currentSignal.value.bear_count + currentSignal.value.neutral_count
})

const bullishPct = computed(() => totalVotes.value ? `${(currentSignal.value!.bull_count / totalVotes.value) * 100}%` : '0%')
const bearishPct = computed(() => totalVotes.value ? `${(currentSignal.value!.bear_count / totalVotes.value) * 100}%` : '0%')
const neutralPct = computed(() => totalVotes.value ? `${(currentSignal.value!.neutral_count / totalVotes.value) * 100}%` : '0%')

// Methods
function getRoleLabel(role: string): string {
  const labels: Record<string, string> = {
    strategy_generator: '策略',
    strategy_reviewer: '评审',
    risk_analyst: '风控',
    market_sentiment: '情绪',
    quant_researcher: '量化',
    system: '系统',
  }
  return labels[role] || role
}

function getDirectionTheme(direction: string): 'success' | 'danger' | 'default' {
  if (direction === 'bullish') return 'success'
  if (direction === 'bearish') return 'danger'
  return 'default'
}

function getDirectionLabel(direction: string): string {
  const labels: Record<string, string> = { bullish: '多', bearish: '空', neutral: '中' }
  return labels[direction] || '中'
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen) + '...'
}

function scrollToBottom() {
  nextTick(() => {
    if (streamContainer.value) {
      streamContainer.value.scrollTop = streamContainer.value.scrollHeight
    }
  })
}

async function fetchSignal(stockCode: string) {
  if (!stockCode) return
  loading.value = true
  try {
    const result = await getDecisionByStock(stockCode)
    currentSignal.value = result
    // If we have an arena, try to connect SSE
    if (result.arena_id) {
      connectStream(result.arena_id)
    }
  } catch (e) {
    console.warn('Failed to fetch stock decision:', e)
  } finally {
    loading.value = false
  }
}

function connectStream(arenaId: string) {
  disconnectStream()
  if (!arenaId) return

  eventSource = createThinkingStream(arenaId)

  const handleMsg = (event: MessageEvent) => {
    try {
      if (event.data.includes('"keepalive":true')) return
      const msg = JSON.parse(event.data) as ThinkingMessage
      messages.value.push(msg)
      if (messages.value.length > 100) {
        messages.value = messages.value.slice(-80)
      }
      scrollToBottom()
    } catch { /* ignore parse errors */ }
  }

  const eventTypes = ['thinking', 'argument', 'conclusion', 'system', 'error', 'intervention']
  eventTypes.forEach(t => eventSource!.addEventListener(t, handleMsg))
  eventSource.onmessage = handleMsg
}

function disconnectStream() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}

// Watch stock code changes
watch(() => props.stockCode, (newCode) => {
  messages.value = []
  currentSignal.value = null
  disconnectStream()
  if (newCode) {
    fetchSignal(newCode)
  }
}, { immediate: true })

watch(messages, scrollToBottom, { deep: true })

onUnmounted(disconnectStream)
</script>

<style scoped>
.agent-discussion-sidebar {
  width: 320px;
  height: 100%;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--td-component-border);
  background: var(--td-bg-color-container);
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--td-component-border);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 14px;
}

.signal-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  font-size: 13px;
}

.signal-banner.signal-buy { background: #e8f5e9; }
.signal-banner.signal-sell { background: #ffebee; }
.signal-banner.signal-hold { background: #fff3e0; }

.signal-icon { font-size: 16px; font-weight: bold; }
.signal-label { font-weight: 600; }
.signal-confidence { color: var(--td-text-color-secondary); font-size: 12px; }
.signal-votes { margin-left: auto; font-size: 11px; display: flex; gap: 6px; }
.signal-votes .bull { color: #4caf50; }
.signal-votes .bear { color: #f44336; }

.discussion-stream {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
}

.stream-message {
  margin-bottom: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: var(--td-bg-color-secondarycontainer);
  font-size: 13px;
}

.stream-message.msg-argument {
  border-left: 2px solid var(--td-warning-color);
}

.stream-message.msg-conclusion {
  border-left: 2px solid var(--td-success-color);
}

.stream-message.msg-system {
  background: transparent;
  font-size: 12px;
  color: var(--td-text-color-secondary);
  padding: 2px 10px;
}

.msg-header {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 2px;
}

.msg-role {
  font-weight: 600;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.msg-time {
  margin-left: auto;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}

.msg-content {
  line-height: 1.4;
  color: var(--td-text-color-primary);
}

.empty-stream {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--td-text-color-placeholder);
  text-align: center;
}

.empty-stream p { margin: 4px 0; }
.empty-stream .hint { font-size: 12px; }

.opinion-footer {
  padding: 8px 16px;
  border-top: 1px solid var(--td-component-border);
}

.opinion-mini-bar {
  display: flex;
  height: 6px;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 4px;
}

.bar-segment { transition: width 0.3s; }
.bar-segment.bullish { background: #4caf50; }
.bar-segment.neutral { background: #9e9e9e; }
.bar-segment.bearish { background: #f44336; }

.opinion-labels {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
}

.label-bull { color: #4caf50; }
.label-neutral { color: #9e9e9e; }
.label-bear { color: #f44336; }

.sidebar-footer {
  padding: 4px 8px;
  border-top: 1px solid var(--td-component-border);
  text-align: center;
}
</style>
