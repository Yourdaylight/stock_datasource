<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import type { McpUsageStatsResponse } from '@/api/mcpUsage'

const props = defineProps<{
  stats: McpUsageStatsResponse | null
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

  const dates = props.stats.daily_stats.map(d => d.date.slice(5))
  const callData = props.stats.daily_stats.map(d => d.call_count)
  const recordData = props.stats.daily_stats.map(d => d.total_records)

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
      right: 60,
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
    yAxis: [
      {
        type: 'value',
        name: '调用次数',
        nameTextStyle: { color: '#86909c', fontSize: 11 },
        splitLine: { lineStyle: { color: '#f5f5f5' } },
        axisLabel: { color: '#86909c', fontSize: 11 }
      },
      {
        type: 'value',
        name: '记录条数',
        nameTextStyle: { color: '#86909c', fontSize: 11 },
        splitLine: { show: false },
        axisLabel: {
          color: '#86909c',
          fontSize: 11,
          formatter: (v: number) => {
            if (v >= 1000) return (v / 1000) + 'K'
            return v + ''
          }
        }
      }
    ],
    series: [
      {
        name: '调用次数',
        type: 'bar',
        yAxisIndex: 0,
        data: callData,
        barWidth: '40%',
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#0052d9' },
            { offset: 1, color: 'rgba(0, 82, 217, 0.3)' }
          ]),
          borderRadius: [3, 3, 0, 0]
        }
      },
      {
        name: '查询记录数',
        type: 'line',
        yAxisIndex: 1,
        data: recordData,
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
        暂无 MCP 调用数据
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
