<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import * as echarts from 'echarts'
import type { FinancialData, CompareResponse } from '@/api/report'

interface Props {
  data: FinancialData[]
  comparisonData?: CompareResponse
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

const trendChartRef = ref<HTMLElement>()
const radarChartRef = ref<HTMLElement>()
const activeTab = ref('trend')

let trendChart: echarts.ECharts | null = null
let radarChart: echarts.ECharts | null = null

// Prepare trend chart data
const trendChartData = computed(() => {
  if (!props.data.length) return null
  
  // Sort data by period
  const sortedData = [...props.data].sort((a, b) => a.period.localeCompare(b.period))
  
  const periods = sortedData.map(item => item.period)
  const roe = sortedData.map(item => item.roe || 0)
  const roa = sortedData.map(item => item.roa || 0)
  const grossMargin = sortedData.map(item => item.gross_margin || 0)
  const netMargin = sortedData.map(item => item.net_margin || 0)
  const debtRatio = sortedData.map(item => item.debt_ratio || 0)
  
  return {
    periods,
    series: [
      { name: 'ROE(%)', data: roe, color: '#1890ff' },
      { name: 'ROA(%)', data: roa, color: '#52c41a' },
      { name: '毛利率(%)', data: grossMargin, color: '#faad14' },
      { name: '净利率(%)', data: netMargin, color: '#f5222d' },
      { name: '资产负债率(%)', data: debtRatio, color: '#722ed1' }
    ]
  }
})

// Prepare radar chart data
const radarChartData = computed(() => {
  if (!props.comparisonData?.comparison) return null
  
  const comparison = props.comparisonData.comparison
  const indicators = []
  const targetData = []
  const industryData = []
  
  const metricsMap = {
    roe: 'ROE',
    roa: 'ROA',
    gross_profit_margin: '毛利率',
    net_profit_margin: '净利率',
    debt_to_assets: '资产负债率',
    current_ratio: '流动比率'
  }
  
  for (const [key, data] of Object.entries(comparison)) {
    const name = metricsMap[key as keyof typeof metricsMap]
    if (name && data.target_value !== undefined && data.industry_median !== undefined) {
      indicators.push({ name, max: Math.max(data.target_value, data.industry_median) * 1.2 })
      targetData.push(data.target_value)
      industryData.push(data.industry_median)
    }
  }
  
  return {
    indicators,
    series: [
      { name: '公司数值', data: targetData, color: '#1890ff' },
      { name: '行业中位数', data: industryData, color: '#52c41a' }
    ]
  }
})

// Initialize trend chart
const initTrendChart = () => {
  if (!trendChartRef.value || !trendChartData.value) return
  
  trendChart = echarts.init(trendChartRef.value)
  
  const option = {
    title: {
      text: '财务指标趋势',
      left: 'center',
      textStyle: { fontSize: 16 }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: trendChartData.value.series.map(s => s.name),
      top: 30
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: 80,
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: trendChartData.value.periods,
      axisLabel: { rotate: 45 }
    },
    yAxis: {
      type: 'value',
      name: '百分比(%)',
      axisLabel: { formatter: '{value}%' }
    },
    series: trendChartData.value.series.map(s => ({
      name: s.name,
      type: 'line',
      data: s.data,
      smooth: true,
      lineStyle: { color: s.color },
      itemStyle: { color: s.color },
      symbol: 'circle',
      symbolSize: 6
    }))
  }
  
  trendChart.setOption(option)
}

// Initialize radar chart
const initRadarChart = () => {
  if (!radarChartRef.value || !radarChartData.value) return
  
  radarChart = echarts.init(radarChartRef.value)
  
  const option = {
    title: {
      text: '同业对比雷达图',
      left: 'center',
      textStyle: { fontSize: 16 }
    },
    tooltip: {
      trigger: 'item'
    },
    legend: {
      data: radarChartData.value.series.map(s => s.name),
      top: 30
    },
    radar: {
      indicator: radarChartData.value.indicators,
      center: ['50%', '60%'],
      radius: '60%'
    },
    series: [{
      type: 'radar',
      data: radarChartData.value.series.map(s => ({
        name: s.name,
        value: s.data,
        itemStyle: { color: s.color },
        lineStyle: { color: s.color },
        areaStyle: { color: s.color, opacity: 0.1 }
      }))
    }]
  }
  
  radarChart.setOption(option)
}

// Handle tab change
const handleTabChange = (tab: string) => {
  activeTab.value = tab
  
  // Wait for DOM update
  setTimeout(() => {
    if (tab === 'trend') {
      initTrendChart()
    } else if (tab === 'radar') {
      initRadarChart()
    }
  }, 100)
}

// Handle window resize
const handleResize = () => {
  trendChart?.resize()
  radarChart?.resize()
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  
  // Initialize default chart
  if (trendChartData.value) {
    setTimeout(initTrendChart, 100)
  }
})

watch(() => props.data, () => {
  if (activeTab.value === 'trend') {
    setTimeout(initTrendChart, 100)
  }
}, { deep: true })

watch(() => props.comparisonData, () => {
  if (activeTab.value === 'radar') {
    setTimeout(initRadarChart, 100)
  }
}, { deep: true })
</script>

<template>
  <div class="trend-chart">
    <t-card title="数据可视化">
      <t-tabs v-model="activeTab" @change="handleTabChange">
        <t-tab-panel value="trend" label="趋势图表">
          <div v-if="loading" class="loading-container">
            <t-loading size="large" text="加载图表数据..." />
          </div>
          <div v-else-if="!trendChartData" class="empty-container">
            <t-empty description="暂无趋势数据" />
          </div>
          <div v-else ref="trendChartRef" class="chart-container" />
        </t-tab-panel>
        
        <t-tab-panel value="radar" label="同业对比">
          <div v-if="loading" class="loading-container">
            <t-loading size="large" text="加载对比数据..." />
          </div>
          <div v-else-if="!radarChartData" class="empty-container">
            <t-empty description="暂无对比数据" />
          </div>
          <div v-else ref="radarChartRef" class="chart-container" />
        </t-tab-panel>
      </t-tabs>
    </t-card>
  </div>
</template>

<style scoped>
.trend-chart {
  height: 100%;
}

.chart-container {
  width: 100%;
  height: 400px;
}

.loading-container,
.empty-container {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 400px;
}

:deep(.t-tabs__content) {
  padding: 16px 0;
}
</style>