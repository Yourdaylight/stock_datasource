<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { FinancialData } from '@/api/report'

interface Props {
  data: FinancialData[]
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

// Chart refs
const profitabilityChartRef = ref<HTMLElement>()
const marginChartRef = ref<HTMLElement>()
const debtChartRef = ref<HTMLElement>()
const revenueChartRef = ref<HTMLElement>()

let charts: echarts.ECharts[] = []

// Sorted data (ascending by period)
const sortedData = computed(() => {
  if (!props.data.length) return []
  return [...props.data].sort((a, b) => a.period.localeCompare(b.period))
})

const periods = computed(() => sortedData.value.map(item => item.period))

const hasAnyData = computed(() => sortedData.value.length > 0)

// Check if a metric has meaningful data (not all null/zero)
const hasMetricData = (values: (number | null | undefined)[]) => {
  return values.some(v => v !== null && v !== undefined && v !== 0)
}

// Format large numbers (亿/万)
const formatAmount = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return '-'
  const abs = Math.abs(val)
  if (abs >= 1e8) return (val / 1e8).toFixed(2) + '亿'
  if (abs >= 1e4) return (val / 1e4).toFixed(2) + '万'
  return val.toFixed(2)
}

// Common chart options
const baseOption = (title: string): echarts.EChartsOption => ({
  title: {
    text: title,
    left: 'center',
    textStyle: { fontSize: 14, fontWeight: 500 }
  },
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'cross' }
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    top: 60,
    containLabel: true
  },
  xAxis: {
    type: 'category',
    data: periods.value,
    axisLabel: { rotate: 30, fontSize: 11 }
  }
})

// 1. Revenue & Net Profit (bar chart)
const initRevenueChart = () => {
  if (!revenueChartRef.value) return
  const revenue = sortedData.value.map(item => item.revenue)
  const netProfit = sortedData.value.map(item => item.net_profit)

  if (!hasMetricData(revenue) && !hasMetricData(netProfit)) return

  const chart = echarts.init(revenueChartRef.value)
  charts.push(chart)

  chart.setOption({
    ...baseOption('营业收入 & 净利润'),
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        let result = params[0]?.axisValue + '<br/>'
        for (const p of params) {
          result += `${p.marker} ${p.seriesName}: ${formatAmount(p.value)}<br/>`
        }
        return result
      }
    },
    legend: {
      data: ['营业收入', '净利润'],
      top: 28
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (val: number) => {
          if (Math.abs(val) >= 1e8) return (val / 1e8).toFixed(0) + '亿'
          if (Math.abs(val) >= 1e4) return (val / 1e4).toFixed(0) + '万'
          return val.toString()
        }
      }
    },
    series: [
      {
        name: '营业收入',
        type: 'bar',
        data: revenue,
        itemStyle: { color: '#1890ff', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 40
      },
      {
        name: '净利润',
        type: 'bar',
        data: netProfit,
        itemStyle: { color: '#52c41a', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 40
      }
    ]
  })
}

// 2. ROE & ROA (profitability line chart)
const initProfitabilityChart = () => {
  if (!profitabilityChartRef.value) return
  const roe = sortedData.value.map(item => item.roe ?? null)
  const roa = sortedData.value.map(item => item.roa ?? null)

  if (!hasMetricData(roe) && !hasMetricData(roa)) return

  const chart = echarts.init(profitabilityChartRef.value)
  charts.push(chart)

  chart.setOption({
    ...baseOption('盈利能力：ROE & ROA'),
    legend: {
      data: ['ROE(%)', 'ROA(%)'],
      top: 28
    },
    yAxis: {
      type: 'value',
      name: '%',
      axisLabel: { formatter: '{value}%' }
    },
    series: [
      {
        name: 'ROE(%)',
        type: 'line',
        data: roe,
        smooth: true,
        lineStyle: { color: '#1890ff', width: 2 },
        itemStyle: { color: '#1890ff' },
        symbol: 'circle',
        symbolSize: 6,
        areaStyle: { color: 'rgba(24,144,255,0.08)' }
      },
      {
        name: 'ROA(%)',
        type: 'line',
        data: roa,
        smooth: true,
        lineStyle: { color: '#52c41a', width: 2 },
        itemStyle: { color: '#52c41a' },
        symbol: 'circle',
        symbolSize: 6,
        areaStyle: { color: 'rgba(82,196,26,0.08)' }
      }
    ]
  })
}

// 3. Gross Margin & Net Margin (line chart)
const initMarginChart = () => {
  if (!marginChartRef.value) return
  const grossMargin = sortedData.value.map(item => item.gross_margin ?? null)
  const netMargin = sortedData.value.map(item => item.net_margin ?? null)

  if (!hasMetricData(grossMargin) && !hasMetricData(netMargin)) return

  const chart = echarts.init(marginChartRef.value)
  charts.push(chart)

  chart.setOption({
    ...baseOption('利润率：毛利率 & 净利率'),
    legend: {
      data: ['毛利率(%)', '净利率(%)'],
      top: 28
    },
    yAxis: {
      type: 'value',
      name: '%',
      axisLabel: { formatter: '{value}%' }
    },
    series: [
      {
        name: '毛利率(%)',
        type: 'line',
        data: grossMargin,
        smooth: true,
        lineStyle: { color: '#faad14', width: 2 },
        itemStyle: { color: '#faad14' },
        symbol: 'circle',
        symbolSize: 6,
        areaStyle: { color: 'rgba(250,173,20,0.08)' }
      },
      {
        name: '净利率(%)',
        type: 'line',
        data: netMargin,
        smooth: true,
        lineStyle: { color: '#f5222d', width: 2 },
        itemStyle: { color: '#f5222d' },
        symbol: 'circle',
        symbolSize: 6,
        areaStyle: { color: 'rgba(245,34,45,0.08)' }
      }
    ]
  })
}

// 4. Debt Ratio & Current Ratio (combined axis)
const initDebtChart = () => {
  if (!debtChartRef.value) return
  const debtRatio = sortedData.value.map(item => item.debt_ratio ?? null)
  const currentRatio = sortedData.value.map(item => item.current_ratio ?? null)

  if (!hasMetricData(debtRatio) && !hasMetricData(currentRatio)) return

  const chart = echarts.init(debtChartRef.value)
  charts.push(chart)

  chart.setOption({
    ...baseOption('偿债能力：资产负债率 & 流动比率'),
    legend: {
      data: ['资产负债率(%)', '流动比率'],
      top: 28
    },
    yAxis: [
      {
        type: 'value',
        name: '%',
        position: 'left',
        axisLabel: { formatter: '{value}%' }
      },
      {
        type: 'value',
        name: '倍',
        position: 'right',
        axisLabel: { formatter: '{value}' },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: '资产负债率(%)',
        type: 'bar',
        yAxisIndex: 0,
        data: debtRatio,
        itemStyle: { color: '#722ed1', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 40
      },
      {
        name: '流动比率',
        type: 'line',
        yAxisIndex: 1,
        data: currentRatio,
        smooth: true,
        lineStyle: { color: '#13c2c2', width: 2 },
        itemStyle: { color: '#13c2c2' },
        symbol: 'circle',
        symbolSize: 6
      }
    ]
  })
}

// Initialize all charts
const initAllCharts = async () => {
  disposeCharts()
  await nextTick()
  if (!hasAnyData.value) return
  initRevenueChart()
  initProfitabilityChart()
  initMarginChart()
  initDebtChart()
}

// Dispose all charts
const disposeCharts = () => {
  charts.forEach(c => c.dispose())
  charts = []
}

// Handle window resize
const handleResize = () => {
  charts.forEach(c => c.resize())
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  if (hasAnyData.value) {
    setTimeout(initAllCharts, 100)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  disposeCharts()
})

watch(() => props.data, () => {
  setTimeout(initAllCharts, 100)
}, { deep: true })
</script>

<template>
  <div class="trend-chart">
    <t-card title="数据可视化">
      <div v-if="loading" class="loading-container">
        <t-loading size="large" text="加载图表数据..." />
      </div>
      <div v-else-if="!hasAnyData" class="empty-container">
        <t-empty description="暂无趋势数据" />
      </div>
      <div v-else class="charts-grid">
        <div class="chart-item">
          <div ref="revenueChartRef" class="chart-container" />
        </div>
        <div class="chart-item">
          <div ref="profitabilityChartRef" class="chart-container" />
        </div>
        <div class="chart-item">
          <div ref="marginChartRef" class="chart-container" />
        </div>
        <div class="chart-item">
          <div ref="debtChartRef" class="chart-container" />
        </div>
      </div>
    </t-card>
  </div>
</template>

<style scoped>
.trend-chart {
  height: 100%;
}

.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.chart-item {
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-border-level-1-color);
  border-radius: 6px;
  padding: 8px;
}

.chart-container {
  width: 100%;
  height: 320px;
}

.loading-container,
.empty-container {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 400px;
}

@media (max-width: 960px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }
}
</style>
