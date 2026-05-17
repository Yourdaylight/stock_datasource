<template>
  <div class="decision-signal-panel">
    <!-- Signal Card -->
    <div class="signal-card" :class="`signal-${decision?.signal || 'hold'}`">
      <div class="signal-main">
        <span class="signal-icon">{{ signalIcon }}</span>
        <span class="signal-text">{{ signalLabel }}</span>
      </div>
      <div class="signal-confidence">
        <span class="confidence-label">置信度</span>
        <div class="confidence-bar">
          <div
            class="confidence-fill"
            :style="{ width: `${(decision?.confidence || 0) * 100}%` }"
          ></div>
        </div>
        <span class="confidence-value">{{ ((decision?.confidence || 0) * 100).toFixed(0) }}%</span>
      </div>
      <div class="signal-action" v-if="decision?.suggested_action">
        {{ decision.suggested_action }}
      </div>
    </div>

    <!-- Opinion Distribution -->
    <div class="opinion-section">
      <h4 class="section-title">观点分布</h4>
      <div class="opinion-bar">
        <div
          class="opinion-segment bullish"
          :style="{ width: bullishWidth }"
          :title="`看多: ${decision?.bull_count || 0}`"
        >
          <span v-if="(decision?.bull_count || 0) > 0">{{ decision?.bull_count }}</span>
        </div>
        <div
          class="opinion-segment neutral"
          :style="{ width: neutralWidth }"
          :title="`中性: ${decision?.neutral_count || 0}`"
        >
          <span v-if="(decision?.neutral_count || 0) > 0">{{ decision?.neutral_count }}</span>
        </div>
        <div
          class="opinion-segment bearish"
          :style="{ width: bearishWidth }"
          :title="`看空: ${decision?.bear_count || 0}`"
        >
          <span v-if="(decision?.bear_count || 0) > 0">{{ decision?.bear_count }}</span>
        </div>
      </div>
      <div class="opinion-legend">
        <span class="legend-item bullish-text">看多 {{ decision?.bull_count || 0 }}</span>
        <span class="legend-item neutral-text">中性 {{ decision?.neutral_count || 0 }}</span>
        <span class="legend-item bearish-text">看空 {{ decision?.bear_count || 0 }}</span>
      </div>
    </div>

    <!-- Key Arguments -->
    <div class="arguments-section">
      <h4 class="section-title">关键论点</h4>
      <div class="arguments-list" v-if="decision?.key_arguments?.length">
        <div
          v-for="(arg, index) in decision.key_arguments.slice(0, 6)"
          :key="index"
          class="argument-item"
          :class="`direction-${arg.direction}`"
        >
          <div class="argument-header">
            <t-tag
              :theme="getDirectionTheme(arg.direction)"
              size="small"
              variant="light"
            >
              {{ getDirectionLabel(arg.direction) }}
            </t-tag>
            <span class="argument-role">{{ getRoleLabel(arg.agent_role) }}</span>
          </div>
          <div class="argument-content">{{ arg.key_point }}</div>
        </div>
      </div>
      <t-empty v-else description="暂无讨论数据" size="small" />
    </div>

    <!-- Dissent Points -->
    <div class="dissent-section" v-if="decision?.dissent_points?.length">
      <h4 class="section-title">主要分歧</h4>
      <ul class="dissent-list">
        <li v-for="(point, index) in decision.dissent_points" :key="index">
          {{ point }}
        </li>
      </ul>
    </div>

    <!-- Consensus -->
    <div class="consensus-section" v-if="decision">
      <div class="consensus-info">
        <span>共识度: {{ ((decision.consensus_ratio || 0) * 100).toFixed(0) }}%</span>
        <span class="update-time" v-if="decision.generated_at">
          更新: {{ formatTime(decision.generated_at) }}
        </span>
      </div>
    </div>

    <!-- Loading / Empty state -->
    <div v-if="loading" class="loading-state">
      <t-loading />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { getDecisionSummary, getOpinionDistribution } from '@/api/decision'
import type { DecisionSummary } from '@/api/decision'

const props = defineProps<{
  arenaId: string
}>()

const decision = ref<DecisionSummary | null>(null)
const loading = ref(false)

// Computed
const signalIcon = computed(() => {
  const icons: Record<string, string> = {
    buy: '↑',
    sell: '↓',
    hold: '→',
  }
  return icons[decision.value?.signal || 'hold'] || '→'
})

const signalLabel = computed(() => {
  const labels: Record<string, string> = {
    buy: '买入',
    sell: '卖出',
    hold: '持有',
  }
  return labels[decision.value?.signal || 'hold'] || '持有'
})

const totalVotes = computed(() => {
  if (!decision.value) return 1
  return (decision.value.bull_count + decision.value.bear_count + decision.value.neutral_count) || 1
})

const bullishWidth = computed(() =>
  `${(decision.value?.bull_count || 0) / totalVotes.value * 100}%`
)

const bearishWidth = computed(() =>
  `${(decision.value?.bear_count || 0) / totalVotes.value * 100}%`
)

const neutralWidth = computed(() =>
  `${(decision.value?.neutral_count || 0) / totalVotes.value * 100}%`
)

// Methods
function getDirectionTheme(direction: string): 'success' | 'danger' | 'default' {
  if (direction === 'bullish') return 'success'
  if (direction === 'bearish') return 'danger'
  return 'default'
}

function getDirectionLabel(direction: string): string {
  const labels: Record<string, string> = {
    bullish: '看多',
    bearish: '看空',
    neutral: '中性',
  }
  return labels[direction] || '中性'
}

function getRoleLabel(role: string): string {
  const labels: Record<string, string> = {
    strategy_generator: '策略生成',
    strategy_reviewer: '策略评审',
    risk_analyst: '风险分析',
    market_sentiment: '情绪分析',
    quant_researcher: '量化研究',
  }
  return labels[role] || role
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

async function fetchDecision() {
  if (!props.arenaId) return
  loading.value = true
  try {
    const result = await getDecisionSummary(props.arenaId)
    decision.value = result
  } catch (e) {
    console.warn('Failed to fetch decision summary:', e)
  } finally {
    loading.value = false
  }
}

// Lifecycle
onMounted(fetchDecision)
watch(() => props.arenaId, fetchDecision)

// Expose refresh method
defineExpose({ refresh: fetchDecision })
</script>

<style scoped>
.decision-signal-panel {
  padding: 8px 0;
}

.signal-card {
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  text-align: center;
}

.signal-card.signal-buy {
  background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
  border: 1px solid #4caf50;
}

.signal-card.signal-sell {
  background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
  border: 1px solid #f44336;
}

.signal-card.signal-hold {
  background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
  border: 1px solid #ff9800;
}

.signal-main {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 12px;
}

.signal-icon {
  font-size: 28px;
  font-weight: bold;
}

.signal-text {
  font-size: 24px;
  font-weight: 700;
}

.signal-card.signal-buy .signal-icon,
.signal-card.signal-buy .signal-text {
  color: #2e7d32;
}

.signal-card.signal-sell .signal-icon,
.signal-card.signal-sell .signal-text {
  color: #c62828;
}

.signal-card.signal-hold .signal-icon,
.signal-card.signal-hold .signal-text {
  color: #e65100;
}

.signal-confidence {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.confidence-label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  white-space: nowrap;
}

.confidence-bar {
  flex: 1;
  height: 8px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 4px;
  overflow: hidden;
}

.confidence-fill {
  height: 100%;
  background: var(--td-brand-color);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.confidence-value {
  font-size: 14px;
  font-weight: 600;
  min-width: 36px;
  text-align: right;
}

.signal-action {
  font-size: 13px;
  color: var(--td-text-color-secondary);
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed rgba(0, 0, 0, 0.1);
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 8px 0;
  color: var(--td-text-color-primary);
}

.opinion-section {
  margin-bottom: 16px;
}

.opinion-bar {
  display: flex;
  height: 28px;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.opinion-segment {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: white;
  min-width: 0;
  transition: width 0.3s ease;
}

.opinion-segment.bullish {
  background: #4caf50;
}

.opinion-segment.neutral {
  background: #9e9e9e;
}

.opinion-segment.bearish {
  background: #f44336;
}

.opinion-legend {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.bullish-text { color: #4caf50; }
.neutral-text { color: #9e9e9e; }
.bearish-text { color: #f44336; }

.arguments-section {
  margin-bottom: 16px;
}

.arguments-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.argument-item {
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--td-bg-color-container);
  border-left: 3px solid;
}

.argument-item.direction-bullish {
  border-left-color: #4caf50;
}

.argument-item.direction-bearish {
  border-left-color: #f44336;
}

.argument-item.direction-neutral {
  border-left-color: #9e9e9e;
}

.argument-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.argument-role {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.argument-content {
  font-size: 13px;
  line-height: 1.4;
  color: var(--td-text-color-primary);
}

.dissent-section {
  margin-bottom: 16px;
}

.dissent-list {
  padding-left: 16px;
  margin: 0;
}

.dissent-list li {
  font-size: 13px;
  color: var(--td-text-color-secondary);
  margin-bottom: 4px;
  line-height: 1.4;
}

.consensus-section {
  border-top: 1px solid var(--td-component-border);
  padding-top: 8px;
}

.consensus-info {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.loading-state {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
</style>
