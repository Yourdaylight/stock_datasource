<template>
  <el-card class="profit-chart-card">
    <template #header>
      <div class="card-header">
        <span>盈亏趋势</span>
        <el-select v-model="selectedPeriod" size="small" @change="handlePeriodChange">
          <el-option label="7天" value="7" />
          <el-option label="30天" value="30" />
          <el-option label="90天" value="90" />
        </el-select>
      </div>
    </template>

    <div v-loading="loading" class="chart-container">
      <div ref="chartRef" class="chart" />
      
      <div v-if="!loading && (!profitHistory || profitHistory.length === 0)" class="empty-chart">
        <el-empty description="暂无盈亏数据" />
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { ProfitHistoryItem } from '@/types/portfolio'

interface Props {
  profitHistory: ProfitHistoryItem[]
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

// Reactive data
const chartRef = ref<HTMLDivElement>()
const selectedPeriod = ref('30')
let chartInstance: echarts.ECharts | null = null

// Methods
const initChart = () => {
  if (!chartRef.value) return

  chartInstance = echarts.init(chartRef.value)
  updateChart()
  
  // Handle resize
  window.addEventListener('resize', handleResize)
}

const updateChart = () => {
  if (!chartInstance || !props.profitHistory) return

  const data = props.profitHistory.slice(-parseInt(selectedPeriod.value))
  
  const dates = data.map(item => item.record_date)
  const profits = data.map(item => item.total_profit)
  const values = data.map(item => item.total_value)
  const costs = data.map(item => item.total_cost)

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      },
      formatter: (params: any) => {
        const date = params[0].axisValue
        let tooltip = `<div style="margin-bottom: 5px;">${date}</div>`
        
        params.forEach((param: any) => {
          const value = param.value
          const formattedValue = typeof value === 'number' 
            ? `¥${value.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`
            : value
          
          tooltip += `
            <div style="display: flex; align-items: center; margin-bottom: 3px;">
              <span style="display: inline-block; width: 10px; height: 10px; background-color: ${param.color}; border-radius: 50%; margin-right: 8px;"></span>
              <span style="margin-right: 20px;">${param.seriesName}:</span>
              <span style="font-weight: bold;">${formattedValue}</span>
            </div>
          `
        })
        
        return tooltip
      }
    },
    legend: {
      data: ['总市值', '总成本', '盈亏金额'],
      top: 10
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
      axisLabel: {
        formatter: (value: string) => {
          const date = new Date(value)
          return `${date.getMonth() + 1}/${date.getDate()}`
        }
      }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (value: number) => {
          if (value >= 10000) {
            return `${(value / 10000).toFixed(1)}万`
          }
          return value.toString()
        }
      }
    },
    series: [
      {
        name: '总市值',
        type: 'line',
        data: values,
        smooth: true,
        lineStyle: {
          color: '#409EFF',
          width: 2
        },
        itemStyle: {
          color: '#409EFF'
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
            { offset: 1, color: 'rgba(64, 158, 255, 0.1)' }
          ])
        }
      },
      {
        name: '总成本',
        type: 'line',
        data: costs,
        smooth: true,
        lineStyle: {
          color: '#909399',
          width: 2,
          type: 'dashed'
        },
        itemStyle: {
          color: '#909399'
        }
      },
      {
        name: '盈亏金额',
        type: 'line',
        data: profits,
        smooth: true,
        lineStyle: {
          color: '#67C23A',
          width: 2
        },
        itemStyle: {
          color: '#67C23A'
        },
        markLine: {
          data: [
            {
              yAxis: 0,
              lineStyle: {
                color: '#E6A23C',
                type: 'solid',
                width: 1
              },
              label: {
                formatter: '盈亏平衡线'
              }
            }
          ]
        }
      }
    ]
  }

  chartInstance.setOption(option, true)
}

const handleResize = () => {
  if (chartInstance) {
    chartInstance.resize()
  }
}

const handlePeriodChange = () => {
  updateChart()
}

// Lifecycle
onMounted(async () => {
  await nextTick()
  initChart()
})

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
  window.removeEventListener('resize', handleResize)
})

// Watch for data changes
watch(() => props.profitHistory, () => {
  if (chartInstance) {
    updateChart()
  }
}, { deep: true })

watch(() => props.loading, (loading) => {
  if (!loading && chartInstance) {
    nextTick(() => {
      updateChart()
    })
  }
})
</script>

<style scoped>
.profit-chart-card {
  height: 400px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-container {
  height: 320px;
  position: relative;
}

.chart {
  width: 100%;
  height: 100%;
}

.empty-chart {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}
</style>