<script setup lang="ts">
import { computed } from 'vue'
import type { FinancialData, FinancialSummary } from '@/api/report'

interface Props {
  data: FinancialData[]
  summary?: FinancialSummary & { health_score: number }
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

// Format number with units
const formatNumber = (num?: number) => {
  if (num === null || num === undefined) return '-'
  if (Math.abs(num) >= 100000000) return (num / 100000000).toFixed(2) + '亿'
  if (Math.abs(num) >= 10000) return (num / 10000).toFixed(2) + '万'
  return num.toFixed(2)
}

// Format percentage
const formatPercent = (num?: number) => {
  if (num === null || num === undefined) return '-'
  return num.toFixed(2) + '%'
}

// Format ratio
const formatRatio = (num?: number) => {
  if (num === null || num === undefined) return '-'
  return num.toFixed(2)
}

// Get health score color
const getHealthScoreColor = (score: number) => {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'error'
}

// Get trend indicator
const getTrend = (current?: number, previous?: number) => {
  if (!current || !previous) return null
  const change = ((current - previous) / Math.abs(previous)) * 100
  if (Math.abs(change) < 1) return 'stable'
  return change > 0 ? 'up' : 'down'
}

// Table columns for financial data
const columns = [
  { colKey: 'period', title: '报告期', width: 120, fixed: 'left' },
  { colKey: 'revenue', title: '营业收入', width: 120 },
  { colKey: 'net_profit', title: '净利润', width: 120 },
  { colKey: 'roe', title: 'ROE(%)', width: 100 },
  { colKey: 'roa', title: 'ROA(%)', width: 100 },
  { colKey: 'gross_margin', title: '毛利率(%)', width: 100 },
  { colKey: 'net_margin', title: '净利率(%)', width: 100 },
  { colKey: 'debt_ratio', title: '资产负债率(%)', width: 120 },
  { colKey: 'current_ratio', title: '流动比率', width: 100 }
]

// Summary metrics for display
const summaryMetrics = computed(() => {
  if (!props.summary) return []
  
  const { profitability, solvency, efficiency, growth, health_score } = props.summary
  
  return [
    {
      category: '盈利能力',
      metrics: [
        { label: 'ROE', value: formatPercent(profitability.roe), trend: null },
        { label: 'ROA', value: formatPercent(profitability.roa), trend: null },
        { label: '毛利率', value: formatPercent(profitability.gross_profit_margin), trend: null },
        { label: '净利率', value: formatPercent(profitability.net_profit_margin), trend: null }
      ]
    },
    {
      category: '偿债能力',
      metrics: [
        { label: '资产负债率', value: formatPercent(solvency.debt_to_assets), trend: null },
        { label: '流动比率', value: formatRatio(solvency.current_ratio), trend: null },
        { label: '速动比率', value: formatRatio(solvency.quick_ratio), trend: null }
      ]
    },
    {
      category: '成长性',
      metrics: [
        { label: '营收增长率', value: formatPercent(growth.revenue_growth), trend: getTrend(growth.revenue_growth, 0) },
        { label: '利润增长率', value: formatPercent(growth.profit_growth), trend: getTrend(growth.profit_growth, 0) }
      ]
    }
  ]
})
</script>

<template>
  <div class="financial-table">
    <!-- Health Score Card -->
    <div v-if="summary" class="health-score-card">
      <t-card title="财务健康度评分" :bordered="false">
        <div class="health-score">
          <t-progress
            :percentage="summary.health_score"
            :theme="getHealthScoreColor(summary.health_score)"
            :stroke-width="12"
            size="large"
          />
          <div class="score-text">
            <span class="score">{{ summary.health_score }}</span>
            <span class="total">/100</span>
          </div>
        </div>
      </t-card>
    </div>

    <!-- Summary Metrics -->
    <div v-if="summary" class="summary-metrics">
      <t-row :gutter="16">
        <t-col v-for="category in summaryMetrics" :key="category.category" :span="4">
          <t-card :title="category.category" :bordered="false" size="small">
            <div class="metrics-list">
              <div v-for="metric in category.metrics" :key="metric.label" class="metric-item">
                <span class="metric-label">{{ metric.label }}</span>
                <div class="metric-value">
                  <span>{{ metric.value }}</span>
                  <t-icon
                    v-if="metric.trend === 'up'"
                    name="arrow-up"
                    class="trend-icon trend-up"
                  />
                  <t-icon
                    v-else-if="metric.trend === 'down'"
                    name="arrow-down"
                    class="trend-icon trend-down"
                  />
                </div>
              </div>
            </div>
          </t-card>
        </t-col>
      </t-row>
    </div>

    <!-- Financial Data Table -->
    <t-card title="财务数据明细" class="data-table-card">
      <t-table
        :data="data"
        :columns="columns"
        :loading="loading"
        row-key="period"
        :scroll="{ x: 1000 }"
        :pagination="false"
        size="small"
      >
        <template #revenue="{ row }">
          <span class="number-cell">{{ formatNumber(row.revenue) }}</span>
        </template>
        
        <template #net_profit="{ row }">
          <span class="number-cell">{{ formatNumber(row.net_profit) }}</span>
        </template>
        
        <template #roe="{ row }">
          <span class="percent-cell" :class="{ 'positive': (row.roe || 0) > 15, 'negative': (row.roe || 0) < 5 }">
            {{ formatPercent(row.roe) }}
          </span>
        </template>
        
        <template #roa="{ row }">
          <span class="percent-cell" :class="{ 'positive': (row.roa || 0) > 5, 'negative': (row.roa || 0) < 2 }">
            {{ formatPercent(row.roa) }}
          </span>
        </template>
        
        <template #gross_margin="{ row }">
          <span class="percent-cell">{{ formatPercent(row.gross_margin) }}</span>
        </template>
        
        <template #net_margin="{ row }">
          <span class="percent-cell">{{ formatPercent(row.net_margin) }}</span>
        </template>
        
        <template #debt_ratio="{ row }">
          <span class="percent-cell" :class="{ 'negative': (row.debt_ratio || 0) > 70, 'positive': (row.debt_ratio || 0) < 40 }">
            {{ formatPercent(row.debt_ratio) }}
          </span>
        </template>
        
        <template #current_ratio="{ row }">
          <span class="ratio-cell" :class="{ 'positive': (row.current_ratio || 0) > 1.5, 'negative': (row.current_ratio || 0) < 1 }">
            {{ formatRatio(row.current_ratio) }}
          </span>
        </template>
      </t-table>
    </t-card>
  </div>
</template>

<style scoped>
.financial-table {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.health-score-card {
  margin-bottom: 16px;
}

.health-score {
  display: flex;
  align-items: center;
  gap: 16px;
}

.score-text {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.score {
  font-size: 32px;
  font-weight: bold;
  color: var(--td-brand-color);
}

.total {
  font-size: 16px;
  color: var(--td-text-color-secondary);
}

.summary-metrics {
  margin-bottom: 16px;
}

.metrics-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.metric-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
}

.metric-label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.metric-value {
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
}

.trend-icon {
  font-size: 12px;
}

.trend-up {
  color: var(--td-success-color);
}

.trend-down {
  color: var(--td-error-color);
}

.data-table-card {
  flex: 1;
}

.number-cell {
  font-family: 'Monaco', 'Menlo', monospace;
  text-align: right;
}

.percent-cell,
.ratio-cell {
  font-family: 'Monaco', 'Menlo', monospace;
  text-align: right;
}

.positive {
  color: var(--td-success-color);
  font-weight: 500;
}

.negative {
  color: var(--td-error-color);
  font-weight: 500;
}

:deep(.t-table__content) {
  font-size: 12px;
}

:deep(.t-table th) {
  background-color: var(--td-bg-color-container-select);
  font-weight: 500;
}
</style>