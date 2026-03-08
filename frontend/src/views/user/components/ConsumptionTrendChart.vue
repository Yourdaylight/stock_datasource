<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import type { UsageStatsResponse } from '@/api/token'

const props = defineProps<{
  stats: UsageStatsResponse | null
  loading: boolean
}>()

const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const initChart = () => {
  if (!chartRef.value) return
  chartInstance = echarts.init(chartRef.value)
  updateChart()
}

const updateChart = () => {
  if (!chartInstance || !props.stats?.daily_stats) return

  const dates = props.stats.daily_stats.map(d => d.date.slice(5)) // MM-DD
  const promptData = props.stats.daily_stats.map(d => d.prompt_tokens)
  const completionData = props.stats.daily_stats.map(d => d.completion_tokens)

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.96)',
      borderColor: '#e7e7e7',
      borderWidth: 1,
      textStyle: { color: '#262626', fontSize: 13 },
      formatter: (params: any) => {
        const date = params[0]?.axisValue || ''
        let html = `<div style="font-weight:600;margin-bottom:6px">${date}</div>`
        for (const p of params) {
          html += `<div style="display:flex;align-items:center;gap:6px;margin:3px 0">`
          html += `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color}"></span>`
          html += `<span>${p.seriesName}</span>`
          html += `<span style="font-weight:600;margin-left:auto">${p.value.toLocaleString()}</span>`
          html += `</div>`
        }
        const total = params.reduce((s: number, p: any) => s + (p.value || 0), 0)
        html += `<div style="margin-top:6px;padding-top:6px;border-top:1px solid #f0f0f0;font-weight:600">合计 ${total.toLocaleString()}</div>`
        return html
      }
    },
    legend: {
      top: 0,
      right: 0,
      itemWidth: 12,
      itemHeight: 8,
      textStyle: { color: '#86909c', fontSize: 12 }
    },
    grid: {
      left: 60,
      right: 20,
      top: 36,
      bottom: 28
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#e7e7e7' } },
      axisLabel: { color: '#86909c', fontSize: 11 }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f5f5f5' } },
      axisLabel: {
        color: '#86909c',
        fontSize: 11,
        formatter: (v: number) => {
          if (v >= 1000) return (v / 1000) + 'K'
          return v + ''
        }
      }
    },
    series: [
      {
        name: '输入 Token',
        type: 'line',
        data: promptData,
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        showSymbol: false,
        lineStyle: { width: 2, color: '#0052d9' },
        itemStyle: { color: '#0052d9' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0, 82, 217, 0.15)' },
            { offset: 1, color: 'rgba(0, 82, 217, 0.02)' }
          ])
        }
      },
      {
        name: '输出 Token',
        type: 'line',
        data: completionData,
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        showSymbol: false,
        lineStyle: { width: 2, color: '#2ba471' },
        itemStyle: { color: '#2ba471' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(43, 164, 113, 0.15)' },
            { offset: 1, color: 'rgba(43, 164, 113, 0.02)' }
          ])
        }
      }
    ]
  })
}

const handleResize = () => {
  chartInstance?.resize()
}

watch(() => props.stats, () => {
  updateChart()
}, { deep: true })

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  chartInstance = null
})
</script>

<template>
  <div class="chart-wrapper">
    <t-loading :loading="loading">
      <div
        v-if="!stats?.daily_stats?.length && !loading"
        class="empty-state"
      >
        暂无消耗数据
      </div>
      <div ref="chartRef" class="chart" />
    </t-loading>
  </div>
</template>

<style scoped>
.chart-wrapper {
  width: 100%;
}

.chart {
  width: 100%;
  height: 320px;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 320px;
  color: #86909c;
  font-size: 14px;
}
</style>
