<template>
  <div class="agent-discussion-sidebar" v-if="visible">
    <!-- Header -->
    <div class="sidebar-header">
      <div class="header-title">
        <t-icon name="user-talk" />
        <span>多智能体决策</span>
        <t-tag v-if="stockCode" size="small" theme="primary">{{ stockCode }}</t-tag>
      </div>
      <t-button variant="text" size="small" @click="$emit('close')">
        <t-icon name="close" />
      </t-button>
    </div>

    <!-- Preview Signal (fast rule-based) -->
    <div
      class="signal-banner signal-preview"
      v-if="previewSignal && !decisionSignal"
    >
      <div class="signal-row">
        <span :class="['signal-icon', `icon-${previewSignal.signal.toLowerCase()}`]">
          {{ previewSignal.signal === 'BUY' ? '↑' : previewSignal.signal === 'SELL' ? '↓' : '→' }}
        </span>
        <span class="signal-label">
          {{ previewSignal.signal === 'BUY' ? '买入' : previewSignal.signal === 'SELL' ? '卖出' : '持有' }}
        </span>
        <span class="signal-confidence">{{ (previewSignal.confidence * 100).toFixed(0) }}%</span>
        <t-tag size="small" variant="outline" theme="warning">预览</t-tag>
      </div>
      <div class="signal-votes">
        <span class="vote-bull">多{{ previewSignal.bull_count }}</span>
        <span class="vote-bear">空{{ previewSignal.bear_count }}</span>
        <span class="vote-neutral">中{{ previewSignal.neutral_count }}</span>
      </div>
      <div class="signal-loading">
        <t-loading size="small" />
        <span>完整分析生成中...</span>
      </div>
    </div>

    <!-- Final Decision Signal -->
    <div
      class="signal-banner"
      v-if="decisionSignal"
      :class="`signal-${decisionSignal.signal.toLowerCase()}`"
    >
      <div class="signal-row">
        <span :class="['signal-icon', `icon-${decisionSignal.signal.toLowerCase()}`]">
          {{ decisionSignal.signal === 'BUY' ? '↑' : decisionSignal.signal === 'SELL' ? '↓' : '→' }}
        </span>
        <span class="signal-label">
          {{ decisionSignal.signal === 'BUY' ? '买入' : decisionSignal.signal === 'SELL' ? '卖出' : '持有' }}
        </span>
        <span class="signal-confidence">{{ (decisionSignal.confidence * 100).toFixed(0) }}%</span>
      </div>
      <div class="signal-votes">
        <span class="vote-bull">多{{ decisionSignal.bull_count }}</span>
        <span class="vote-bear">空{{ decisionSignal.bear_count }}</span>
        <span class="vote-neutral">中{{ decisionSignal.neutral_count }}</span>
      </div>
      <div v-if="decisionSignal.suggested_action" class="signal-action">
        {{ decisionSignal.suggested_action }}
      </div>
    </div>

    <!-- Decision Trace Stream -->
    <div ref="streamContainer" class="discussion-stream">
      <template v-if="hasDecisionEvents">
        <section v-if="orchestratorTraces.length" class="trace-section">
          <div class="section-title">调度决策</div>
          <div v-for="msg in orchestratorTraces" :key="msg.id" class="stream-message decision-orchestrator">
            <div class="msg-header">
              <span class="msg-role">{{ msg.data?.title || '调度决策' }}</span>
              <t-tag v-if="msg.data?.intent" size="small" variant="light">{{ msg.data.intent }}</t-tag>
            </div>
            <div class="msg-content">{{ msg.data?.rationale || '正在选择合适的投研路径' }}</div>
            <div v-if="msg.data?.selected_team || msg.data?.selected_agent" class="trace-meta">
              <span v-if="msg.data?.selected_team">团队：{{ msg.data.selected_team }}</span>
              <span v-if="msg.data?.selected_agent">Agent：{{ msg.data.selected_agent }}</span>
            </div>
          </div>
        </section>

        <section v-if="agentTraces.length || discussionMessages.length" class="trace-section">
          <div class="section-title">Agent 决策流</div>
          <div
            v-for="msg in agentTraces"
            :key="msg.id"
            class="stream-message"
            :class="`direction-${msg.data?.direction || 'neutral'}`"
          >
            <div class="msg-header">
              <span class="msg-role">{{ msg.data?.role || getAgentLabel(msg.agent) }}</span>
              <t-tag
                v-if="msg.data?.direction && msg.data.direction !== 'neutral'"
                :theme="msg.data.direction === 'bullish' ? 'success' : 'danger'"
                size="small"
                variant="light"
              >
                {{ msg.data.direction === 'bullish' ? '看多' : '看空' }}
              </t-tag>
              <span v-if="msg.data?.confidence" class="msg-confidence">
                {{ (msg.data.confidence * 100).toFixed(0) }}%
              </span>
            </div>
            <div class="msg-content">{{ msg.data?.rationale || msg.data?.title || '已进入分析' }}</div>
            <ul v-if="msg.data?.key_points?.length" class="key-points">
              <li v-for="point in msg.data.key_points" :key="point">{{ point }}</li>
            </ul>
          </div>
          <div
            v-for="msg in discussionMessages"
            :key="msg.id"
            class="stream-message"
            :class="`direction-${msg.data?.direction || 'neutral'}`"
          >
            <div class="msg-header">
              <span class="msg-role">{{ getAgentLabel(msg.agent) }}</span>
              <t-tag
                v-if="msg.data?.direction && msg.data.direction !== 'neutral'"
                :theme="msg.data.direction === 'bullish' ? 'success' : 'danger'"
                size="small"
                variant="light"
              >
                {{ msg.data.direction === 'bullish' ? '看多' : '看空' }}
              </t-tag>
              <span v-if="msg.data?.confidence" class="msg-confidence">
                {{ (msg.data.confidence * 100).toFixed(0) }}%
              </span>
            </div>
            <div class="msg-content">
              {{ msg.data?.key_point || msg.data?.content || '' }}
            </div>
          </div>
        </section>

        <section v-if="summaryTraces.length" class="trace-section">
          <div class="section-title">最终汇总</div>
          <div v-for="msg in summaryTraces" :key="msg.id" class="stream-message decision-summary-card">
            <div class="msg-header">
              <span class="msg-role">{{ msg.data?.title || '最终决策' }}</span>
              <t-tag v-if="msg.data?.signal" size="small" theme="primary">{{ msg.data.signal }}</t-tag>
              <span v-if="msg.data?.confidence" class="msg-confidence">
                {{ (msg.data.confidence * 100).toFixed(0) }}%
              </span>
            </div>
            <div class="msg-content">{{ msg.data?.suggested_action || msg.data?.rationale || '等待最终汇总' }}</div>
          </div>
        </section>
      </template>
      <div v-else class="empty-stream">
        <t-icon name="chat" size="32px" />
        <p>暂无Agent讨论记录</p>
        <p class="hint">发送消息后，调度与Agent决策逻辑将在此展示</p>
      </div>
    </div>

    <!-- Opinion Distribution Bar -->
    <div class="opinion-footer" v-if="totalVotes > 0">
      <div class="opinion-mini-bar">
        <div class="bar-segment bullish" :style="{ width: bullishPct }"></div>
        <div class="bar-segment neutral" :style="{ width: neutralPct }"></div>
        <div class="bar-segment bearish" :style="{ width: bearishPct }"></div>
      </div>
      <div class="opinion-labels">
        <span class="label-bull">看多 {{ bullCount }}</span>
        <span class="label-neutral">中性 {{ neutralCount }}</span>
        <span class="label-bear">看空 {{ bearCount }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch, ref, nextTick } from 'vue'
import { useChatStore, type DebugMessage } from '@/stores/chat'

const props = defineProps<{
  visible: boolean
  stockCode: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const chatStore = useChatStore()
const streamContainer = ref<HTMLElement | null>(null)

const decisionTraceMessages = computed<DebugMessage[]>(() => {
  return chatStore.debugMessages.filter(m => m.debugType === 'decision_trace')
})

const orchestratorTraces = computed<DebugMessage[]>(() => {
  return decisionTraceMessages.value.filter(m => m.data?.stage === 'orchestrator')
})

const agentTraces = computed<DebugMessage[]>(() => {
  return decisionTraceMessages.value.filter(m => m.data?.stage === 'team_agent' || m.data?.stage === 'agent')
})

const summaryTraces = computed<DebugMessage[]>(() => {
  return decisionTraceMessages.value.filter(m => m.data?.stage === 'team_summary')
})

// Get discussion-related messages from the store's live debugMessages
const discussionMessages = computed<DebugMessage[]>(() => {
  return chatStore.debugMessages.filter(
    m => m.debugType === 'discussion_argument'
  )
})

const hasDecisionEvents = computed(() => {
  return decisionTraceMessages.value.length > 0 || discussionMessages.value.length > 0
})

// Preview signal from store
const previewSignal = computed(() => chatStore.previewSignal)

// Full decision signal from store
const decisionSignal = computed(() => chatStore.decisionSummary)

// Vote counts from decision or preview
const activeSignal = computed(() => decisionSignal.value || previewSignal.value)
const bullCount = computed(() => activeSignal.value?.bull_count || 0)
const bearCount = computed(() => activeSignal.value?.bear_count || 0)
const neutralCount = computed(() => activeSignal.value?.neutral_count || 0)
const totalVotes = computed(() => bullCount.value + bearCount.value + neutralCount.value)

const bullishPct = computed(() => totalVotes.value ? `${(bullCount.value / totalVotes.value) * 100}%` : '0%')
const bearishPct = computed(() => totalVotes.value ? `${(bearCount.value / totalVotes.value) * 100}%` : '0%')
const neutralPct = computed(() => totalVotes.value ? `${(neutralCount.value / totalVotes.value) * 100}%` : '0%')

// Agent label mapping
const AGENT_LABELS: Record<string, string> = {
  'MarketAgent': '行情',
  'ReportAgent': '财报',
  'NewsAnalystAgent': '新闻',
  'ScreenerAgent': '选股',
  'BacktestAgent': '回测',
  'EtfAgent': 'ETF',
  'IndexAgent': '指数',
  'OverviewAgent': '概览',
  'ChatArenaAdapter': '系统',
}

function getAgentLabel(agent: string): string {
  return AGENT_LABELS[agent] || agent?.replace?.('Agent', '') || '分析师'
}

// Auto-scroll when new messages arrive
watch([decisionTraceMessages, discussionMessages], () => {
  nextTick(() => {
    if (streamContainer.value) {
      streamContainer.value.scrollTop = streamContainer.value.scrollHeight
    }
  })
}, { deep: true })
</script>

<style scoped>
.agent-discussion-sidebar {
  width: 320px;
  height: 100%;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--td-component-border);
  background: var(--td-bg-color-container);
  flex-shrink: 0;
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

/* Signal Banner */
.signal-banner {
  padding: 12px 16px;
  border-bottom: 1px solid var(--td-component-border);
}

.signal-banner.signal-buy { background: #e8f5e9; }
.signal-banner.signal-sell { background: #ffebee; }
.signal-banner.signal-hold { background: #fff3e0; }
.signal-banner.signal-preview { background: var(--td-bg-color-secondarycontainer); border: 1px dashed var(--td-component-border); border-left: none; border-right: none; }

.signal-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.signal-icon {
  font-size: 18px;
  font-weight: bold;
}

.icon-buy { color: var(--td-success-color); }
.icon-sell { color: var(--td-error-color); }
.icon-hold { color: var(--td-warning-color); }

.signal-label { font-weight: 600; font-size: 15px; }
.signal-confidence { color: var(--td-text-color-secondary); font-size: 13px; }

.signal-votes {
  display: flex;
  gap: 12px;
  font-size: 12px;
  margin-top: 4px;
}

.vote-bull { color: #4caf50; }
.vote-bear { color: #f44336; }
.vote-neutral { color: #9e9e9e; }

.signal-action {
  margin-top: 6px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
  padding: 4px 8px;
  background: rgba(0,0,0,0.03);
  border-radius: 4px;
}

.signal-loading {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}

/* Discussion Stream */
.discussion-stream {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
}

.trace-section {
  margin-bottom: 14px;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--td-text-color-secondary);
  margin: 4px 0 8px;
}

.stream-message {
  margin-bottom: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--td-bg-color-secondarycontainer);
  font-size: 13px;
  border-left: 3px solid transparent;
}

.stream-message.direction-bullish { border-left-color: #4caf50; }
.stream-message.direction-bearish { border-left-color: #f44336; }
.stream-message.direction-neutral { border-left-color: #9e9e9e; }
.stream-message.decision-orchestrator { border-left-color: var(--td-brand-color); }
.stream-message.decision-summary-card { border-left-color: var(--td-warning-color); }

.trace-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}

.key-points {
  margin: 6px 0 0;
  padding-left: 16px;
  color: var(--td-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.msg-header {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 4px;
}

.msg-role {
  font-weight: 600;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.msg-confidence {
  margin-left: auto;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
}

.msg-content {
  line-height: 1.5;
  color: var(--td-text-color-primary);
  font-size: 13px;
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

.empty-stream p { margin: 4px 0; font-size: 13px; }
.empty-stream .hint { font-size: 12px; }

/* Opinion Footer */
.opinion-footer {
  padding: 10px 16px;
  border-top: 1px solid var(--td-component-border);
}

.opinion-mini-bar {
  display: flex;
  height: 6px;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 6px;
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
</style>
