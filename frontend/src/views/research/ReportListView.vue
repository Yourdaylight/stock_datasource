<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { MessagePlugin } from 'tdesign-vue-next'
import { useFinancialAnalysisStore } from '@/stores/financial-analysis'

const props = defineProps<{ code: string }>()
const router = useRouter()
const route = useRoute()
const store = useFinancialAnalysisStore()

const market = computed(() => (route.query.market as string) || 'A')

// Format amount
const formatAmount = (val: number | null): string => {
  if (val === null || val === undefined) return '-'
  const abs = Math.abs(val)
  if (abs >= 1e8) return (val / 1e8).toFixed(2) + '亿'
  if (abs >= 1e4) return (val / 1e4).toFixed(2) + '万'
  return val.toFixed(2)
}

const formatPct = (val: number | null): string => {
  if (val === null || val === undefined) return '-'
  return val.toFixed(2) + '%'
}

// Compute yoy change sign
const changeClass = (val: number | null): string => {
  if (val === null || val === undefined) return ''
  return val >= 0 ? 'positive' : 'negative'
}

const changeArrow = (val: number | null): string => {
  if (val === null || val === undefined) return ''
  return val >= 0 ? '↑' : '↓'
}

// Report type color
const reportTypeTheme = (type: string): string => {
  const map: Record<string, string> = {
    annual: 'primary',
    semi_annual: 'success',
    q1: 'warning',
    q3: 'warning',
  }
  return map[type] || 'default'
}

// Navigate to report detail
const goToDetail = (endDate: string) => {
  router.push({
    name: 'ReportDetail',
    params: { code: props.code, period: endDate },
    query: { market: market.value },
  })
}

// Load data
const loadData = async () => {
  try {
    await store.fetchReportPeriods(props.code, market.value)
  } catch {
    MessagePlugin.error('加载财报列表失败')
  }
}

onMounted(loadData)
</script>

<template>
  <div class="report-list-view">
    <!-- Breadcrumb -->
    <t-breadcrumb class="breadcrumb">
      <t-breadcrumb-item>
        <router-link to="/research">财报分析</router-link>
      </t-breadcrumb-item>
      <t-breadcrumb-item>
        {{ store.currentCompany?.name || code }}
      </t-breadcrumb-item>
    </t-breadcrumb>

    <!-- Company Info Header -->
    <div class="company-header" v-if="store.currentCompany">
      <div class="company-main">
        <div class="company-name-row">
          <h2 class="company-name">{{ store.currentCompany.name }}</h2>
          <t-tag theme="primary" variant="outline" size="medium" class="code-tag">
            {{ store.currentCompany.ts_code }}
          </t-tag>
          <t-tag v-if="store.currentCompany.industry" theme="default" variant="light" size="small">
            {{ store.currentCompany.industry }}
          </t-tag>
          <t-tag v-if="market === 'HK'" theme="warning" variant="light" size="small">港股</t-tag>
          <t-tag v-else theme="primary" variant="light" size="small">A股</t-tag>
        </div>
        <div class="company-meta">
          <span v-if="store.currentCompany.area">{{ store.currentCompany.area }}</span>
          <span v-if="store.currentCompany.list_date">
            上市日期：{{ store.currentCompany.list_date }}
          </span>
        </div>
      </div>
    </div>

    <!-- Period Stats -->
    <div class="period-stats" v-if="store.reportPeriods.length > 0">
      <span class="stats-text">
        共 <strong>{{ store.reportPeriods.length }}</strong> 个报告期
      </span>
    </div>

    <!-- Report Period Cards -->
    <t-loading :loading="store.periodsLoading" text="加载中...">
      <div class="period-cards" v-if="store.reportPeriods.length > 0">
        <div
          v-for="period in store.reportPeriods"
          :key="period.end_date"
          class="period-card"
          @click="goToDetail(period.end_date)"
        >
          <div class="card-header">
            <div class="card-title-row">
              <span class="card-period">{{ period.end_date }}</span>
              <t-tag
                :theme="reportTypeTheme(period.report_type) as any"
                variant="light"
                size="small"
              >
                {{ period.report_type_label }}
              </t-tag>
              <t-tag
                v-if="period.has_analysis"
                theme="success"
                variant="outline"
                size="small"
                class="analysis-badge"
              >
                ✓ 已分析
              </t-tag>
            </div>
          </div>

          <div class="card-metrics">
            <div class="metric-item">
              <span class="metric-label">营收</span>
              <span class="metric-value">{{ formatAmount(period.revenue) }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">净利润</span>
              <span class="metric-value" :class="changeClass(period.net_profit)">
                {{ formatAmount(period.net_profit) }}
              </span>
            </div>
            <div class="metric-item">
              <span class="metric-label">ROE</span>
              <span class="metric-value" :class="changeClass(period.roe)">
                {{ formatPct(period.roe) }}
              </span>
            </div>
            <div class="metric-item">
              <span class="metric-label">毛利率</span>
              <span class="metric-value">{{ formatPct(period.gross_margin) }}</span>
            </div>
            <div class="metric-item" v-if="period.eps !== null">
              <span class="metric-label">EPS</span>
              <span class="metric-value">{{ period.eps?.toFixed(2) ?? '-' }}</span>
            </div>
          </div>

          <div class="card-footer">
            <t-button theme="primary" variant="text" size="small">
              查看详情 →
            </t-button>
          </div>
        </div>
      </div>

      <t-empty v-else-if="!store.periodsLoading" description="暂无财报数据" />
    </t-loading>
  </div>
</template>

<style scoped>
.report-list-view {
  padding: 16px 24px;
  min-height: 100%;
}

.breadcrumb {
  margin-bottom: 16px;
}

.company-header {
  background: var(--td-bg-color-container);
  border-radius: 10px;
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: var(--td-shadow-1);
}

.company-name-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.company-name {
  font-size: 22px;
  font-weight: 600;
  color: var(--td-text-color-primary);
  margin: 0;
}

.code-tag {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-weight: 500;
}

.company-meta {
  display: flex;
  gap: 16px;
  margin-top: 8px;
  font-size: 13px;
  color: var(--td-text-color-secondary);
}

.period-stats {
  margin-bottom: 12px;
}

.stats-text {
  font-size: 14px;
  color: var(--td-text-color-secondary);
}

.stats-text strong {
  color: var(--td-brand-color);
}

.period-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.period-card {
  background: var(--td-bg-color-container);
  border-radius: 10px;
  padding: 18px 20px;
  cursor: pointer;
  transition: all 0.25s ease;
  border: 1px solid var(--td-border-level-1-color);
  position: relative;
}

.period-card:hover {
  border-color: var(--td-brand-color-hover);
  box-shadow: 0 4px 16px rgba(0, 82, 217, 0.1);
  transform: translateY(-2px);
}

.card-header {
  margin-bottom: 14px;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-period {
  font-size: 16px;
  font-weight: 600;
  color: var(--td-text-color-primary);
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
}

.analysis-badge {
  margin-left: auto;
}

.card-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  margin-bottom: 12px;
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 72px;
}

.metric-label {
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}

.metric-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.metric-value.positive {
  color: var(--td-success-color);
}

.metric-value.negative {
  color: var(--td-error-color);
}

.card-footer {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--td-border-level-1-color);
  padding-top: 10px;
  margin-top: 2px;
}
</style>
