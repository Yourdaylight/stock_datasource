<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import type { IndicatorData } from '@/types/common'

const props = defineProps<{
  data: IndicatorData[]
  loading?: boolean
}>()

const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

const initChart = () => {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  updateChart()
}

const updateChart = () => {
  if (!chart || !props.data.length) return

  const dates = props.data.map(d => d.date)
  const kData = props.data.map(d => d.values.K || 0)
  const dData = props.data.map(d => d.values.D || 0)
  const jData = props.data.map(d => d.values.J || 0)

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any) => {
        const date = params[0].axisValue
        let result = `${date}<br/>`
        params.forEach((param: any) => {
          result += `${param.seriesName}: ${param.value.toFixed(2)}<br/>`
        })
        return result
      }
    },
    legend: {
      data: ['K', 'D', 'J'],
      top: 10
    },
    grid: {
      left: '10%',
      right: '10%',
      top: '20%',
      bottom: '15%'
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        formatter: (value: string) => {
          // Format date for display
          return value.slice(5) // Show MM-DD
        }
      }
    },
    yAxis: {
      type: 'value',
      scale: true,
      min: 0,
      max: 100,
      axisLabel: {
        formatter: '{value}'
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: ['#e6e6e6']
        }
      }
    },
    dataZoom: [
      {
        type: 'inside',
        start: 50,
        end: 100
      }
    ],
    series: [
      {
        name: 'K',
        type: 'line',
        data: kData,
        smooth: true,
        lineStyle: {
          color: '#5470c6',
          width: 2
        },
        itemStyle: {
          color: '#5470c6'
        }
      },
      {
        name: 'D',
        type: 'line',
        data: dData,
        smooth: true,
        lineStyle: {
          color: '#91cc75',
          width: 2
        },
        itemStyle: {
          color: '#91cc75'
        }
      },
      {
        name: 'J',
        type: 'line',
        data: jData,
        smooth: true,
        lineStyle: {
          color: '#fac858',
          width: 2
        },
        itemStyle: {
          color: '#fac858'
        }
      }
    ],
    // Add reference lines for overbought/oversold levels
    markLine: {
      silent: true,
      data: [
        { yAxis: 80, lineStyle: { color: '#ff4757', type: 'dashed' } },
        { yAxis: 20, lineStyle: { color: '#2ed573', type: 'dashed' } }
      ]
    }
  }

  chart.setOption(option)
}

const handleResize = () => {
  chart?.resize()
}

watch(() => props.data, updateChart, { deep: true })

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  chart?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div class="kdj-chart-container">
    <t-loading v-if="loading" size="large" />
    <div ref="chartRef" class="chart" />
    
    <!-- KDJ Explanation -->
    <div class="kdj-info">
      <div class="info-item">
        <span class="label">超买区:</span>
        <span class="value">K、D > 80</span>
      </div>
      <div class="info-item">
        <span class="label">超卖区:</span>
        <span class="value">K、D < 20</span>
      </div>
      <div class="info-item">
        <span class="label">金叉:</span>
        <span class="value">K线上穿D线</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kdj-chart-container {
  position: relative;
  width: 100%;
  height: 400px;
}

.chart {
  width: 100%;
  height: 350px;
}

.kdj-info {
  display: flex;
  justify-content: space-around;
  padding: 8px;
  background: #f8f9fa;
  border-radius: 4px;
  margin-top: 8px;
}

.info-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  font-size: 12px;
}

.label {
  color: #666;
  margin-bottom: 2px;
}

.value {
  color: #333;
  font-weight: 500;
}
</style>