<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { MessagePlugin } from 'tdesign-vue-next'
import { useFinancialAnalysisStore } from '@/stores/financial-analysis'
import ReportOverviewTab from './components/ReportOverviewTab.vue'
import ReportStatementTab from './components/ReportStatementTab.vue'
import ReportAIAnalysisTab from './components/ReportAIAnalysisTab.vue'

const props = defineProps<{ code: string; period: string }>()
const route = useRoute()
const store = useFinancialAnalysisStore()

const market = computed(() => (route.query.market as string) || 'A')
const activeTab = ref('overview')

// Format helpers
const formatAmount = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return '-'
  const abs = Math.abs(val)
  if (abs >= 1e8) return (val / 1e8).toFixed(2) + '亿'
  if (abs >= 1e4) return (val / 1e4).toFixed(2) + '万'
  return val.toFixed(2)
}

const formatPct = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return '-'
  return val.toFixed(2) + '%'
}

// Extract summary from analysis data
const summary = computed(() => store.reportDetail?.analysis?.summary || {})
const healthScore = computed(() => store.reportDetail?.analysis?.health_analysis?.health_score || 0)
const companyName = computed(() => store.reportDetail?.company?.name || props.code)
const reportTypeLabel = computed(() => store.reportDetail?.report_type_label || '')

const profitability = computed(() => summary.value?.profitability || {})
const solvency = computed(() => summary.value?.solvency || {})
const growth = computed(() => summary.value?.growth || {})

const scoreColor = computed(() => {
  if (healthScore.value >= 70) return '#2ba471'
  if (healthScore.value >= 50) return '#e37318'
  return '#d54941'
})

// Key indicators for top cards
const topIndicators = computed(() => [
  {
    label: 'ROE',
    value: formatPct(profitability.value?.roe),
    color: (profitability.value?.roe ?? 0) >= 10 ? '#2ba471' : undefined,
  },
  {
    label: '净利率',
    value: formatPct(profitability.value?.net_profit_margin),
  },
  {
    label: '资产负债率',
    value: formatPct(solvency.value?.debt_to_assets),
    color: (solvency.value?.debt_to_assets ?? 0) > 70 ? '#d54941' : undefined,
  },
  {
    label: '健康评分',
    value: `${healthScore.value}/100`,
    color: scoreColor.value,
  },
])

// Load data
const loadData = async () => {
  try {
    await store.fetchReportDetail(props.code, props.period, market.value)
  } catch {
    MessagePlugin.error('加载财报详情失败')
  }
}

onMounted(loadData)
</script>

<template>
  <div class="report-detail-view">
    <!-- Breadcrumb -->
    <t-breadcrumb class="breadcrumb">
      <t-breadcrumb-item>
        <router-link to="/research">财报分析</router-link>
      </t-breadcrumb-item>
      <t-breadcrumb-item>
        <router-link :to="{ name: 'ReportList', params: { code }, query: { market } }">
          {{ companyName }}
        </router-link>
      </t-breadcrumb-item>
      <t-breadcrumb-item>
        {{ period }} {{ reportTypeLabel }}
      </t-breadcrumb-item>
    </t-breadcrumb>

    <t-loading :loading="store.detailLoading" text="加载财报数据...">
      <!-- Top Indicator Cards -->
      <div class="indicator-cards" v-if="store.reportDetail">
        <div
          v-for="indicator in topIndicators"
          :key="indicator.label"
          class="indicator-card"
        >
          <div class="indicator-label">{{ indicator.label }}</div>
          <div
            class="indicator-value"
            :style="indicator.color ? { color: indicator.color } : {}"
          >
            {{ indicator.value }}
          </div>
        </div>
      </div>

      <!-- Tab Navigation -->
      <div class="detail-tabs" v-if="store.reportDetail">
        <t-tabs v-model="activeTab" size="large">
          <t-tab-panel value="overview" label="综合概览">
            <ReportOverviewTab
              :analysis="store.reportDetail.analysis"
              :company="store.reportDetail.company"
              :period="period"
            />
          </t-tab-panel>

          <t-tab-panel value="income" label="利润表">
            <ReportStatementTab
              :data="store.reportDetail.statements?.income || []"
              statement-type="income"
              :market="market"
            />
          </t-tab-panel>

          <t-tab-panel value="balance" label="资产负债表">
            <ReportStatementTab
              :data="store.reportDetail.statements?.balance || []"
              statement-type="balance"
              :market="market"
            />
          </t-tab-panel>

          <t-tab-panel value="cashflow" label="现金流量表">
            <ReportStatementTab
              :data="store.reportDetail.statements?.cashflow || []"
              statement-type="cashflow"
              :market="market"
            />
          </t-tab-panel>

          <t-tab-panel value="ai" label="AI分析">
            <ReportAIAnalysisTab
              :code="code"
              :period="period"
              :market="market"
              :company-name="companyName"
            />
          </t-tab-panel>
        </t-tabs>
      </div>

      <t-empty v-else-if="!store.detailLoading" description="暂无财报数据" />
    </t-loading>
  </div>
</template>

<style scoped>
.report-detail-view {
  padding: 16px 24px;
  min-height: 100%;
}

.breadcrumb {
  margin-bottom: 16px;
}

.indicator-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

@media (max-width: 768px) {
  .indicator-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}

.indicator-card {
  background: var(--td-bg-color-container);
  border-radius: 10px;
  padding: 18px 20px;
  box-shadow: var(--td-shadow-1);
  transition: transform 0.2s, box-shadow 0.2s;
}

.indicator-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--td-shadow-2);
}

.indicator-label {
  font-size: 13px;
  color: var(--td-text-color-secondary);
  margin-bottom: 8px;
}

.indicator-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--td-text-color-primary);
  font-family: 'DIN Alternate', 'SF Mono', 'Monaco', monospace;
}

.detail-tabs {
  background: var(--td-bg-color-container);
  border-radius: 10px;
  padding: 16px 20px;
  box-shadow: var(--td-shadow-1);
}

:deep(.t-tabs__content) {
  padding-top: 16px;
}
</style>
