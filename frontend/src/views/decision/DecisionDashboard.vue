<template>
  <div class="decision-dashboard">
    <!-- Page Header -->
    <div class="page-header">
      <h1>决策看板</h1>
      <p class="subtitle">投研团队讨论决策汇总 — 实时追踪多角色共识与分歧</p>
      <t-button theme="default" variant="outline" @click="refreshAll" :loading="loading">
        <template #icon><t-icon name="refresh" /></template>
        刷新
      </t-button>
    </div>

    <!-- Signal Cards Grid -->
    <div class="signal-grid" v-if="decisions.length > 0">
      <div
        v-for="item in decisions"
        :key="item.id"
        class="signal-card-wrapper"
        @click="selectDecision(item)"
        :class="{ active: selectedDecision?.id === item.id }"
      >
        <div class="signal-card" :class="`signal-${item.signal}`">
          <div class="card-stock">{{ item.stock_code || '未指定' }}</div>
          <div class="card-signal">
            <span class="card-signal-icon">{{ getSignalIcon(item.signal) }}</span>
            <span class="card-signal-text">{{ getSignalLabel(item.signal) }}</span>
          </div>
          <div class="card-confidence">
            置信{{ (item.confidence * 100).toFixed(0) }}%
          </div>
          <div class="card-votes">
            <span class="vote-bull">{{ item.bull_count }}多</span>
            <span class="vote-bear">{{ item.bear_count }}空</span>
            <span class="vote-neutral" v-if="item.neutral_count">{{ item.neutral_count }}中</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <t-card v-if="!loading && decisions.length === 0" class="empty-card">
      <t-empty description="暂无活跃的Agent讨论决策">
        <template #extra>
          <p>请先在竞技场中启动Agent讨论，讨论结束后将自动生成决策信号</p>
          <t-button theme="primary" @click="$router.push('/arena')">
            前往竞技场
          </t-button>
        </template>
      </t-empty>
    </t-card>

    <!-- Detail Section -->
    <div class="detail-section" v-if="selectedDecision">
      <t-card>
        <template #header>
          <div class="detail-header">
            <span>{{ selectedDecision.stock_code }} 决策详情</span>
            <t-tag :theme="getSignalTheme(selectedDecision.signal)" size="large">
              {{ getSignalLabel(selectedDecision.signal) }}
              ({{ (selectedDecision.confidence * 100).toFixed(0) }}%)
            </t-tag>
          </div>
        </template>

        <div class="detail-content">
          <!-- Suggested Action -->
          <div class="detail-action" v-if="selectedDecision.suggested_action">
            <t-icon name="lightbulb" />
            <span>{{ selectedDecision.suggested_action }}</span>
          </div>

          <!-- Opinion Distribution -->
          <div class="detail-opinion">
            <h4>Agent观点分布</h4>
            <div class="opinion-bar-large">
              <div
                class="segment bullish"
                :style="{ width: getBullishWidth(selectedDecision) }"
              ></div>
              <div
                class="segment neutral"
                :style="{ width: getNeutralWidth(selectedDecision) }"
              ></div>
              <div
                class="segment bearish"
                :style="{ width: getBearishWidth(selectedDecision) }"
              ></div>
            </div>
          </div>

          <!-- Key Arguments -->
          <div class="detail-arguments" v-if="selectedDecision.key_arguments?.length">
            <h4>各Agent观点</h4>
            <div class="arg-grid">
              <div
                v-for="(arg, index) in selectedDecision.key_arguments"
                :key="index"
                class="arg-item"
                :class="`arg-${arg.direction}`"
              >
                <div class="arg-top">
                  <t-tag
                    :theme="getDirectionTheme(arg.direction)"
                    size="small"
                    variant="light"
                  >
                    {{ getDirectionLabel(arg.direction) }}
                  </t-tag>
                  <span class="arg-role">{{ getRoleLabel(arg.agent_role) }}</span>
                </div>
                <div class="arg-point">{{ arg.key_point }}</div>
              </div>
            </div>
          </div>

          <!-- Dissent Points -->
          <div class="detail-dissent" v-if="selectedDecision.dissent_points?.length">
            <h4>主要分歧</h4>
            <ul>
              <li v-for="(point, index) in selectedDecision.dissent_points" :key="index">
                {{ point }}
              </li>
            </ul>
          </div>

          <!-- Meta -->
          <div class="detail-meta">
            <span>竞技场: {{ selectedDecision.arena_id }}</span>
            <span>共识度: {{ (selectedDecision.consensus_ratio * 100).toFixed(0) }}%</span>
            <span>更新: {{ formatTime(selectedDecision.generated_at) }}</span>
          </div>
        </div>
      </t-card>
    </div>

    <!-- Decisions Table -->
    <t-card class="decisions-table-card" v-if="decisions.length > 0">
      <template #header>
        <span>全部决策信号</span>
      </template>
      <t-table
        :data="decisions"
        row-key="id"
        size="medium"
        @row-click="({ row }: any) => selectDecision(row)"
        style="cursor: pointer;"
      >
        <t-table-column prop="stock_code" title="标的" width="120" />
        <t-table-column prop="signal" title="信号" width="100">
          <template #cell="{ row }">
            <t-tag :theme="getSignalTheme(row.signal)" size="small">
              {{ getSignalIcon(row.signal) }} {{ getSignalLabel(row.signal) }}
            </t-tag>
          </template>
        </t-table-column>
        <t-table-column prop="confidence" title="置信度" width="100">
          <template #cell="{ row }">
            {{ (row.confidence * 100).toFixed(0) }}%
          </template>
        </t-table-column>
        <t-table-column title="观点分布" width="180">
          <template #cell="{ row }">
            <span class="vote-bull">{{ row.bull_count }}多</span>
            <span class="vote-separator">/</span>
            <span class="vote-bear">{{ row.bear_count }}空</span>
            <span class="vote-separator">/</span>
            <span class="vote-neutral-text">{{ row.neutral_count }}中</span>
          </template>
        </t-table-column>
        <t-table-column prop="suggested_action" title="建议" ellipsis />
        <t-table-column prop="generated_at" title="更新时间" width="140">
          <template #cell="{ row }">
            {{ formatTime(row.generated_at) }}
          </template>
        </t-table-column>
      </t-table>
    </t-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getAllDecisions } from '@/api/decision'
import type { DecisionSummary } from '@/api/decision'

const decisions = ref<DecisionSummary[]>([])
const selectedDecision = ref<DecisionSummary | null>(null)
const loading = ref(false)

// Methods
function getSignalIcon(signal: string): string {
  const icons: Record<string, string> = { buy: '↑', sell: '↓', hold: '→' }
  return icons[signal] || '→'
}

function getSignalLabel(signal: string): string {
  const labels: Record<string, string> = { buy: '买入', sell: '卖出', hold: '持有' }
  return labels[signal] || '持有'
}

function getSignalTheme(signal: string): 'success' | 'danger' | 'warning' {
  if (signal === 'buy') return 'success'
  if (signal === 'sell') return 'danger'
  return 'warning'
}

function getDirectionTheme(direction: string): 'success' | 'danger' | 'default' {
  if (direction === 'bullish') return 'success'
  if (direction === 'bearish') return 'danger'
  return 'default'
}

function getDirectionLabel(direction: string): string {
  const labels: Record<string, string> = { bullish: '看多', bearish: '看空', neutral: '中性' }
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

function getBullishWidth(d: DecisionSummary): string {
  const total = d.bull_count + d.bear_count + d.neutral_count || 1
  return `${(d.bull_count / total) * 100}%`
}

function getBearishWidth(d: DecisionSummary): string {
  const total = d.bull_count + d.bear_count + d.neutral_count || 1
  return `${(d.bear_count / total) * 100}%`
}

function getNeutralWidth(d: DecisionSummary): string {
  const total = d.bull_count + d.bear_count + d.neutral_count || 1
  return `${(d.neutral_count / total) * 100}%`
}

function formatTime(timestamp: string): string {
  if (!timestamp) return '-'
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function selectDecision(item: DecisionSummary) {
  selectedDecision.value = item
}

async function refreshAll() {
  loading.value = true
  try {
    const response = await getAllDecisions()
    decisions.value = response.decisions || []
    if (decisions.value.length > 0 && !selectedDecision.value) {
      selectedDecision.value = decisions.value[0]
    }
  } catch (e) {
    console.error('Failed to fetch decisions:', e)
  } finally {
    loading.value = false
  }
}

onMounted(refreshAll)
</script>

<style scoped>
.decision-dashboard {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 22px;
  margin: 0;
}

.page-header .subtitle {
  flex: 1;
  font-size: 14px;
  color: var(--td-text-color-secondary);
  margin: 0;
}

.signal-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.signal-card-wrapper {
  cursor: pointer;
  border-radius: 8px;
  transition: transform 0.2s, box-shadow 0.2s;
}

.signal-card-wrapper:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.signal-card-wrapper.active {
  box-shadow: 0 0 0 2px var(--td-brand-color);
}

.signal-card {
  padding: 16px;
  border-radius: 8px;
  text-align: center;
}

.signal-card.signal-buy {
  background: linear-gradient(135deg, #e8f5e9, #c8e6c9);
  border: 1px solid #a5d6a7;
}

.signal-card.signal-sell {
  background: linear-gradient(135deg, #ffebee, #ffcdd2);
  border: 1px solid #ef9a9a;
}

.signal-card.signal-hold {
  background: linear-gradient(135deg, #fff3e0, #ffe0b2);
  border: 1px solid #ffcc80;
}

.card-stock {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
  color: var(--td-text-color-primary);
}

.card-signal {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-bottom: 4px;
}

.card-signal-icon {
  font-size: 20px;
  font-weight: bold;
}

.card-signal-text {
  font-size: 18px;
  font-weight: 700;
}

.card-confidence {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  margin-bottom: 8px;
}

.card-votes {
  display: flex;
  justify-content: center;
  gap: 8px;
  font-size: 11px;
}

.vote-bull { color: #4caf50; font-weight: 600; }
.vote-bear { color: #f44336; font-weight: 600; }
.vote-neutral { color: #9e9e9e; }
.vote-neutral-text { color: #9e9e9e; }
.vote-separator { color: var(--td-text-color-placeholder); margin: 0 2px; }

.empty-card {
  margin-bottom: 24px;
}

.detail-section {
  margin-bottom: 24px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-action {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--td-brand-color-light);
  border-radius: 6px;
  font-size: 14px;
}

.detail-opinion h4,
.detail-arguments h4,
.detail-dissent h4 {
  font-size: 14px;
  margin: 0 0 8px 0;
}

.opinion-bar-large {
  display: flex;
  height: 24px;
  border-radius: 4px;
  overflow: hidden;
}

.opinion-bar-large .segment {
  transition: width 0.3s;
}

.opinion-bar-large .segment.bullish { background: #4caf50; }
.opinion-bar-large .segment.neutral { background: #9e9e9e; }
.opinion-bar-large .segment.bearish { background: #f44336; }

.arg-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 8px;
}

.arg-item {
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--td-bg-color-container);
  border-left: 3px solid;
}

.arg-item.arg-bullish { border-left-color: #4caf50; }
.arg-item.arg-bearish { border-left-color: #f44336; }
.arg-item.arg-neutral { border-left-color: #9e9e9e; }

.arg-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.arg-role {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.arg-point {
  font-size: 13px;
  line-height: 1.4;
}

.detail-dissent ul {
  margin: 0;
  padding-left: 20px;
}

.detail-dissent li {
  font-size: 13px;
  color: var(--td-text-color-secondary);
  margin-bottom: 4px;
}

.detail-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
  border-top: 1px solid var(--td-component-border);
  padding-top: 8px;
}

.decisions-table-card {
  margin-bottom: 24px;
}
</style>
