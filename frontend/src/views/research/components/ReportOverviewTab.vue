<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  analysis: Record<string, any> | null
  company: Record<string, any> | null
  period: string
}>()

// ========== Format Helpers ==========

const parseNum = (val: any): number | null => {
  if (val === null || val === undefined || val === '' || val === 'N/A' || val === '\\N') return null
  const n = Number(val)
  return isNaN(n) ? null : n
}

const formatValue = (val: any): string => {
  const n = parseNum(val)
  if (n === null) return '-'
  return n.toFixed(2)
}

const formatPct = (val: any): string => {
  const n = parseNum(val)
  if (n === null) return '-'
  return n.toFixed(2) + '%'
}

const formatAmount = (val: any): string => {
  const n = parseNum(val)
  if (n === null) return '-'
  const abs = Math.abs(n)
  if (abs >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (abs >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n.toFixed(2)
}

const getValueColor = (val: any): string => {
  const n = parseNum(val)
  if (n === null) return ''
  if (n > 20) return 'var(--td-success-color)'
  if (n < 0) return 'var(--td-error-color)'
  return ''
}

// ========== Computed Data ==========

const summary = computed(() => props.analysis?.summary || {})
const healthAnalysis = computed(() => props.analysis?.health_analysis || {})
const healthScore = computed(() => healthAnalysis.value?.health_score || 0)

const profitability = computed(() => summary.value?.profitability || {})
const solvency = computed(() => summary.value?.solvency || {})
const efficiency = computed(() => summary.value?.efficiency || {})
const growth = computed(() => summary.value?.growth || {})
const rawData = computed<any[]>(() => summary.value?.raw_data || [])

const sortedData = computed(() => {
  return [...rawData.value].sort((a, b) => {
    const pa = a.period || a.end_date || ''
    const pb = b.period || b.end_date || ''
    return pa.localeCompare(pb)
  })
})

const chartPeriods = computed(() =>
  sortedData.value.map(d => {
    const p = d.period || d.end_date || ''
    // Format: 20231231 -> 2023Q4
    if (p.length === 8) {
      const m = p.substring(4, 6)
      const y = p.substring(0, 4)
      if (m === '03' || m === '12' && p.endsWith('0331')) return `${y}Q1`
      if (m === '06') return `${y}H1`
      if (m === '09') return `${y}Q3`
      if (m === '12') return `${y}`
      return y + '-' + m
    }
    return p
  })
)

const scoreColor = computed(() => {
  if (healthScore.value >= 70) return '#2ba471'
  if (healthScore.value >= 50) return '#e37318'
  return '#d54941'
})

const scoreTheme = computed(() => {
  if (healthScore.value >= 70) return 'success'
  if (healthScore.value >= 50) return 'warning'
  return 'danger'
})

// ========== ECharts ==========

let charts: echarts.ECharts[] = []

const disposeCharts = () => {
  charts.forEach(c => c.dispose())
  charts = []
}

const getBaseOption = (title: string) => ({
  title: { text: title, left: 'center', textStyle: { fontSize: 14, fontWeight: 500, color: '#1D2129' } },
  tooltip: { trigger: 'axis' as const, axisPointer: { type: 'cross' as const } },
  grid: { left: '3%', right: '4%', bottom: '3%', top: 60, containLabel: true },
  xAxis: {
    type: 'category' as const,
    data: chartPeriods.value,
    axisLabel: { rotate: 30, fontSize: 11 },
  },
})

const initRevenueChart = () => {
  const el = document.getElementById('overview-revenue-chart')
  if (!el) return
  const chart = echarts.init(el)
  charts.push(chart)

  const revenue = sortedData.value.map(d => parseNum(d.revenue))
  const netProfit = sortedData.value.map(d => parseNum(d.net_profit) ?? parseNum(d.net_profit_attr_p))

  chart.setOption({
    ...getBaseOption('营业收入 & 净利润'),
    legend: { top: 28, data: ['营业收入', '净利润'] },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (v: number) => formatAmount(v),
      },
    },
    series: [
      {
        name: '营业收入',
        type: 'bar',
        data: revenue,
        itemStyle: { color: '#0052D9', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 35,
      },
      {
        name: '净利润',
        type: 'bar',
        data: netProfit,
        itemStyle: { color: '#2ba471', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 35,
      },
    ],
  })
}

const initProfitabilityChart = () => {
  const el = document.getElementById('overview-profitability-chart')
  if (!el) return
  const chart = echarts.init(el)
  charts.push(chart)

  const roe = sortedData.value.map(d => parseNum(d.roe) ?? parseNum(d.roe_avg))
  const roa = sortedData.value.map(d => parseNum(d.roa))

  chart.setOption({
    ...getBaseOption('ROE & ROA 趋势'),
    legend: { top: 28, data: ['ROE', 'ROA'] },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    series: [
      {
        name: 'ROE',
        type: 'line',
        data: roe,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2 },
        itemStyle: { color: '#0052D9' },
        areaStyle: { color: 'rgba(0, 82, 217, 0.06)' },
      },
      {
        name: 'ROA',
        type: 'line',
        data: roa,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2 },
        itemStyle: { color: '#2ba471' },
        areaStyle: { color: 'rgba(43, 164, 113, 0.06)' },
      },
    ],
  })
}

const initMarginChart = () => {
  const el = document.getElementById('overview-margin-chart')
  if (!el) return
  const chart = echarts.init(el)
  charts.push(chart)

  const grossMargin = sortedData.value.map(d => parseNum(d.gross_margin) ?? parseNum(d.gross_profit_margin) ?? parseNum(d.gross_profit_ratio))
  const netMargin = sortedData.value.map(d => parseNum(d.net_margin) ?? parseNum(d.net_profit_margin) ?? parseNum(d.net_profit_ratio))

  chart.setOption({
    ...getBaseOption('毛利率 & 净利率'),
    legend: { top: 28, data: ['毛利率', '净利率'] },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    series: [
      {
        name: '毛利率',
        type: 'line',
        data: grossMargin,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2 },
        itemStyle: { color: '#e37318' },
        areaStyle: { color: 'rgba(227, 115, 24, 0.06)' },
      },
      {
        name: '净利率',
        type: 'line',
        data: netMargin,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2 },
        itemStyle: { color: '#d54941' },
        areaStyle: { color: 'rgba(213, 73, 65, 0.06)' },
      },
    ],
  })
}

const initDebtChart = () => {
  const el = document.getElementById('overview-debt-chart')
  if (!el) return
  const chart = echarts.init(el)
  charts.push(chart)

  const debtRatio = sortedData.value.map(d => parseNum(d.debt_ratio) ?? parseNum(d.debt_to_assets))
  const currentRatio = sortedData.value.map(d => parseNum(d.current_ratio))

  chart.setOption({
    ...getBaseOption('资产负债率 & 流动比率'),
    legend: { top: 28, data: ['资产负债率', '流动比率'] },
    yAxis: [
      { type: 'value', name: '资产负债率(%)', axisLabel: { formatter: '{value}%' } },
      { type: 'value', name: '流动比率', position: 'right' },
    ],
    series: [
      {
        name: '资产负债率',
        type: 'bar',
        data: debtRatio,
        itemStyle: { color: '#722ed1', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 35,
      },
      {
        name: '流动比率',
        type: 'line',
        yAxisIndex: 1,
        data: currentRatio,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2 },
        itemStyle: { color: '#13c2c2' },
      },
    ],
  })
}

const initAllCharts = async () => {
  disposeCharts()
  await nextTick()
  if (!sortedData.value.length) return
  initRevenueChart()
  initProfitabilityChart()
  initMarginChart()
  initDebtChart()
}

const handleResize = () => {
  charts.forEach(c => c.resize())
}

// Init charts when data arrives or changes
watch(() => props.analysis, () => {
  if (sortedData.value.length) {
    setTimeout(initAllCharts, 200)
  }
}, { deep: true })

onMounted(() => {
  window.addEventListener('resize', handleResize)
  if (sortedData.value.length) {
    setTimeout(initAllCharts, 300)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  disposeCharts()
})
</script>

<template>
  <div class="report-overview-tab">
    <!-- Health Score + Strengths/Weaknesses -->
    <div class="health-section" v-if="healthAnalysis.health_score">
      <div class="score-card" :class="'score-' + scoreTheme">
        <div class="score-circle">
          <t-progress
            theme="circle"
            :percentage="healthScore"
            :color="scoreColor"
            :stroke-width="8"
            size="110px"
          >
            <div class="score-text">
              <span class="score-number">{{ healthScore }}</span>
              <span class="score-unit">/100</span>
            </div>
          </t-progress>
        </div>
        <div class="score-label">财务健康度评分</div>
      </div>

      <div class="health-details">
        <div class="health-card strengths-card" v-if="healthAnalysis.strengths?.length">
          <div class="health-card-title">
            <span class="health-icon">💪</span>
            <span>财务优势</span>
          </div>
          <ul class="health-list">
            <li v-for="(item, idx) in healthAnalysis.strengths" :key="idx">{{ item }}</li>
          </ul>
        </div>
        <div class="health-card weaknesses-card" v-if="healthAnalysis.weaknesses?.length">
          <div class="health-card-title">
            <span class="health-icon">⚠️</span>
            <span>需关注项</span>
          </div>
          <ul class="health-list">
            <li v-for="(item, idx) in healthAnalysis.weaknesses" :key="idx">{{ item }}</li>
          </ul>
        </div>
        <div class="health-card recommend-card" v-if="healthAnalysis.recommendations?.length">
          <div class="health-card-title">
            <span class="health-icon">💡</span>
            <span>投资建议</span>
          </div>
          <ul class="health-list">
            <li v-for="(item, idx) in healthAnalysis.recommendations" :key="idx">{{ item }}</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Indicator Section Cards -->
    <div class="section-grid">
      <!-- Profitability -->
      <div class="section-card theme-primary">
        <div class="section-title">
          <span class="section-icon">📈</span>
          <span>盈利能力指标</span>
        </div>
        <div class="kv-list">
          <div class="kv-item">
            <span class="kv-key">ROE</span>
            <span class="kv-value" :style="{ color: getValueColor(profitability.roe) }">
              {{ formatPct(profitability.roe) }}
            </span>
          </div>
          <div class="kv-item">
            <span class="kv-key">ROA</span>
            <span class="kv-value" :style="{ color: getValueColor(profitability.roa) }">
              {{ formatPct(profitability.roa) }}
            </span>
          </div>
          <div class="kv-item">
            <span class="kv-key">毛利率</span>
            <span class="kv-value" :style="{ color: getValueColor(profitability.gross_profit_margin) }">
              {{ formatPct(profitability.gross_profit_margin) }}
            </span>
          </div>
          <div class="kv-item">
            <span class="kv-key">净利率</span>
            <span class="kv-value" :style="{ color: getValueColor(profitability.net_profit_margin) }">
              {{ formatPct(profitability.net_profit_margin) }}
            </span>
          </div>
          <div class="kv-item">
            <span class="kv-key">每股收益(EPS)</span>
            <span class="kv-value">{{ formatValue(profitability.eps) }}</span>
          </div>
        </div>
      </div>

      <!-- Solvency -->
      <div class="section-card theme-default">
        <div class="section-title">
          <span class="section-icon">🏦</span>
          <span>偿债能力指标</span>
        </div>
        <div class="kv-list">
          <div class="kv-item">
            <span class="kv-key">资产负债率</span>
            <span class="kv-value">{{ formatPct(solvency.debt_to_assets) }}</span>
          </div>
          <div class="kv-item">
            <span class="kv-key">产权比率</span>
            <span class="kv-value">{{ formatValue(solvency.debt_to_equity) }}</span>
          </div>
          <div class="kv-item">
            <span class="kv-key">流动比率</span>
            <span class="kv-value">{{ formatValue(solvency.current_ratio) }}</span>
          </div>
          <div class="kv-item">
            <span class="kv-key">速动比率</span>
            <span class="kv-value">{{ formatValue(solvency.quick_ratio) }}</span>
          </div>
        </div>
      </div>

      <!-- Efficiency -->
      <div class="section-card theme-success">
        <div class="section-title">
          <span class="section-icon">⚙️</span>
          <span>运营效率指标</span>
        </div>
        <div class="kv-list">
          <div class="kv-item">
            <span class="kv-key">资产周转率</span>
            <span class="kv-value">{{ formatValue(efficiency.asset_turnover) }}</span>
          </div>
          <div class="kv-item">
            <span class="kv-key">存货周转率</span>
            <span class="kv-value">{{ formatValue(efficiency.inventory_turnover) }}</span>
          </div>
          <div class="kv-item">
            <span class="kv-key">应收账款周转率</span>
            <span class="kv-value">{{ formatValue(efficiency.receivable_turnover) }}</span>
          </div>
        </div>
      </div>

      <!-- Growth -->
      <div class="section-card theme-warning">
        <div class="section-title">
          <span class="section-icon">🚀</span>
          <span>成长能力指标</span>
        </div>
        <div class="kv-list">
          <div class="kv-item">
            <span class="kv-key">营收增长率</span>
            <span class="kv-value" :style="{ color: getValueColor(growth.revenue_growth) }">
              {{ formatPct(growth.revenue_growth) }}
            </span>
          </div>
          <div class="kv-item">
            <span class="kv-key">净利润增长率</span>
            <span class="kv-value" :style="{ color: getValueColor(growth.profit_growth) }">
              {{ formatPct(growth.profit_growth) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Trend Charts -->
    <div class="charts-section" v-if="sortedData.length > 0">
      <h3 class="charts-title">📊 多期趋势对比</h3>
      <div class="charts-grid">
        <div class="chart-item">
          <div id="overview-revenue-chart" class="chart-container"></div>
        </div>
        <div class="chart-item">
          <div id="overview-profitability-chart" class="chart-container"></div>
        </div>
        <div class="chart-item">
          <div id="overview-margin-chart" class="chart-container"></div>
        </div>
        <div class="chart-item">
          <div id="overview-debt-chart" class="chart-container"></div>
        </div>
      </div>
    </div>

    <!-- Raw Data Table -->
    <div class="data-table-section" v-if="sortedData.length > 0">
      <h3 class="table-title">📋 历史财务数据</h3>
      <t-table
        :data="sortedData.slice().reverse()"
        :columns="[
          { colKey: 'period', title: '报告期', fixed: 'left', width: 100, cell: (h: any, { row }: any) => row.period || row.end_date || '-' },
          { colKey: 'revenue', title: '营业收入', width: 130, cell: (h: any, { row }: any) => formatAmount(row.revenue) },
          { colKey: 'net_profit', title: '净利润', width: 130, cell: (h: any, { row }: any) => formatAmount(row.net_profit ?? row.net_profit_attr_p) },
          { colKey: 'roe', title: 'ROE(%)', width: 100, cell: (h: any, { row }: any) => formatPct(row.roe ?? row.roe_avg) },
          { colKey: 'gross_margin', title: '毛利率(%)', width: 100, cell: (h: any, { row }: any) => formatPct(row.gross_margin ?? row.gross_profit_margin ?? row.gross_profit_ratio) },
          { colKey: 'net_margin', title: '净利率(%)', width: 100, cell: (h: any, { row }: any) => formatPct(row.net_margin ?? row.net_profit_margin ?? row.net_profit_ratio) },
          { colKey: 'debt_ratio', title: '资产负债率(%)', width: 120, cell: (h: any, { row }: any) => formatPct(row.debt_ratio ?? row.debt_to_assets) },
          { colKey: 'current_ratio', title: '流动比率', width: 100, cell: (h: any, { row }: any) => formatValue(row.current_ratio) },
          { colKey: 'basic_eps', title: 'EPS', width: 80, cell: (h: any, { row }: any) => formatValue(row.basic_eps ?? row.eps) },
        ]"
        size="small"
        bordered
        :scroll="{ x: 960 }"
        row-key="period"
      />
    </div>

    <t-empty v-if="!analysis" description="暂无分析数据" />
  </div>
</template>

<style scoped>
.report-overview-tab {
  padding: 4px 0;
}

/* ========== Health Section ========== */
.health-section {
  display: flex;
  gap: 20px;
  margin-bottom: 24px;
  align-items: flex-start;
}

.score-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 28px;
  border-radius: 12px;
  background: linear-gradient(135deg, #f0f7ff 0%, #e8f3ff 100%);
  box-shadow: 0 2px 8px rgba(0, 82, 217, 0.08);
  min-width: 170px;
  flex-shrink: 0;
  transition: transform 0.25s ease;
}

.score-card:hover {
  transform: translateY(-2px);
}

.score-card.score-success {
  background: linear-gradient(135deg, #e8f8f0 0%, #d4f0e2 100%);
}

.score-card.score-warning {
  background: linear-gradient(135deg, #fff7e6 0%, #fff1cc 100%);
}

.score-card.score-danger {
  background: linear-gradient(135deg, #fff0ee 0%, #ffe3e0 100%);
}

.score-circle {
  margin-bottom: 10px;
}

.score-text {
  text-align: center;
}

.score-number {
  font-size: 28px;
  font-weight: 700;
  font-family: 'DIN Alternate', 'SF Mono', monospace;
}

.score-unit {
  font-size: 13px;
  color: var(--td-text-color-secondary);
}

.score-label {
  font-size: 13px;
  color: var(--td-text-color-secondary);
  font-weight: 500;
}

.health-details {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.health-card {
  padding: 14px 18px;
  border-radius: 10px;
  background: var(--td-bg-color-container);
  border-left: 3px solid var(--td-brand-color);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.strengths-card {
  border-left-color: var(--td-success-color);
}

.weaknesses-card {
  border-left-color: var(--td-warning-color);
}

.recommend-card {
  border-left-color: var(--td-brand-color);
}

.health-card-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--td-text-color-primary);
}

.health-icon {
  font-size: 16px;
}

.health-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--td-text-color-secondary);
  line-height: 1.8;
}

.health-list li {
  margin-bottom: 2px;
}

/* ========== Section Grid ========== */
.section-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
  margin-bottom: 24px;
}

@media (max-width: 768px) {
  .section-grid {
    grid-template-columns: 1fr;
  }
  .health-section {
    flex-direction: column;
  }
}

.section-card {
  padding: 16px 18px;
  border-radius: 10px;
  background: var(--td-bg-color-container);
  border-left: 3px solid var(--td-brand-color);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  transition: box-shadow 0.2s ease;
}

.section-card:hover {
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
}

.section-card.theme-primary {
  border-left-color: #0052D9;
}

.section-card.theme-default {
  border-left-color: #366EF4;
}

.section-card.theme-success {
  border-left-color: #2ba471;
}

.section-card.theme-warning {
  border-left-color: #e37318;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--td-text-color-primary);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.section-icon {
  font-size: 16px;
}

.kv-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.kv-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 7px 0;
  border-bottom: 1px dashed var(--td-border-level-1-color);
}

.kv-item:last-child {
  border-bottom: none;
}

.kv-key {
  font-size: 13px;
  color: var(--td-text-color-secondary);
}

.kv-value {
  font-size: 14px;
  font-weight: 600;
  font-family: 'DIN Alternate', 'SF Mono', 'Monaco', monospace;
  color: var(--td-text-color-primary);
}

/* ========== Charts Section ========== */
.charts-section {
  margin-bottom: 24px;
}

.charts-title,
.table-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--td-text-color-primary);
  margin-bottom: 14px;
  padding-left: 2px;
}

.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

@media (max-width: 960px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }
}

.chart-item {
  background: var(--td-bg-color-container);
  border-radius: 10px;
  padding: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.chart-container {
  height: 320px;
  width: 100%;
}

/* ========== Data Table ========== */
.data-table-section {
  margin-bottom: 12px;
}

:deep(.t-table th) {
  background: var(--td-bg-color-secondarycontainer) !important;
  font-weight: 600;
}
</style>
