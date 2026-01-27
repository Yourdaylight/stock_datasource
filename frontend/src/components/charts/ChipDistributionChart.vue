<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import * as echarts from 'echarts'
import type { ChipData, ChipStats } from '@/types/common'

const props = defineProps<{
  data: ChipData[]
  stats?: ChipStats | null
  currentPrice?: number
  loading?: boolean
  height?: number | string
}>()

const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

const chartHeight = computed(() => {
  if (typeof props.height === 'string') {
    return props.height
  }
  return props.height ? `${props.height}px` : '400px'
})

// 计算获利盘和套牢盘
const profitData = computed(() => {
  if (!props.data.length || !props.currentPrice) return { profit: 0, loss: 0 }
  let profit = 0
  let loss = 0
  props.data.forEach(item => {
    if (item.price <= props.currentPrice!) {
      profit += item.percent
    } else {
      loss += item.percent
    }
  })
  return { profit, loss }
})

const initChart = () => {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  updateChart()
}

const updateChart = () => {
  if (!chart || !props.data.length) {
    chart?.clear()
    return
  }

  const currentPrice = props.currentPrice || 0
  
  // 按价格排序
  const sortedData = [...props.data].sort((a, b) => a.price - b.price)
  
  // 生成 Y 轴数据（价格）和 X 轴数据（占比）
  const prices = sortedData.map(d => d.price.toFixed(2))
  const percentages = sortedData.map(d => d.percent)
  
  // 颜色数据：低于当前价格为绿色（获利盘），高于为红色（套牢盘）
  const colors = sortedData.map(d => 
    d.price <= currentPrice ? '#26a69a' : '#ef5350'
  )

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      formatter: (params: any) => {
        const data = params[0]
        const price = data.name
        const percent = data.value
        const status = parseFloat(price) <= currentPrice ? '获利盘' : '套牢盘'
        return `
          <div style="font-size: 13px;">
            <div>价格: <b>${price}</b></div>
            <div>占比: <b>${percent.toFixed(2)}%</b></div>
            <div>状态: <span style="color: ${parseFloat(price) <= currentPrice ? '#26a69a' : '#ef5350'}">${status}</span></div>
          </div>
        `
      }
    },
    grid: {
      left: '3%',
      right: '15%',
      bottom: '3%',
      top: '30',
      containLabel: true
    },
    xAxis: {
      type: 'value',
      name: '占比(%)',
      nameLocation: 'end',
      max: 'dataMax',
      axisLabel: {
        formatter: '{value}%'
      }
    },
    yAxis: {
      type: 'category',
      data: prices,
      name: '价格',
      nameLocation: 'end',
      axisLine: { show: true },
      axisTick: { show: false },
      axisLabel: {
        fontSize: 10
      }
    },
    series: [
      {
        name: '筹码占比',
        type: 'bar',
        data: percentages.map((value, index) => ({
          value,
          itemStyle: {
            color: colors[index]
          }
        })),
        barWidth: '60%',
        label: {
          show: false
        }
      }
    ],
    // 当前价格标记线
    ...(currentPrice > 0 ? {
      graphic: [
        {
          type: 'line',
          z: 100,
          shape: {
            x1: 0,
            y1: 0,
            x2: '100%',
            y2: 0
          },
          style: {
            stroke: '#1976d2',
            lineWidth: 2,
            lineDash: [4, 4]
          },
          // @ts-ignore
          position: function(params: any) {
            // 找到当前价格对应的 Y 轴位置
            const priceIndex = prices.findIndex(p => parseFloat(p) >= currentPrice)
            if (priceIndex < 0) return [0, 0]
            return [0, chart!.convertToPixel({ yAxisIndex: 0 }, priceIndex)]
          }
        }
      ]
    } : {})
  }

  chart.setOption(option, true)
  
  // 添加当前价格标记线（使用 markLine）
  if (currentPrice > 0) {
    const priceStr = currentPrice.toFixed(2)
    const markLineOption = {
      series: [{
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: {
            color: '#1976d2',
            type: 'dashed',
            width: 2
          },
          label: {
            show: true,
            position: 'end',
            formatter: `现价: ${priceStr}`,
            fontSize: 12,
            color: '#1976d2'
          },
          data: [
            {
              yAxis: priceStr
            }
          ]
        }
      }]
    }
    chart.setOption(markLineOption)
  }
}

const handleResize = () => {
  chart?.resize()
}

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  chart?.dispose()
  window.removeEventListener('resize', handleResize)
})

watch(() => [props.data, props.currentPrice], () => {
  updateChart()
}, { deep: true })

watch(() => props.loading, (loading) => {
  if (chart) {
    if (loading) {
      chart.showLoading()
    } else {
      chart.hideLoading()
    }
  }
})
</script>

<template>
  <div class="chip-distribution-container" :style="{ height: chartHeight }">
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <t-loading size="large" text="加载中..." />
    </div>
    
    <!-- 空状态：居中显示 -->
    <div v-else-if="!data.length" class="empty-state">
      <t-icon name="chart" size="48" />
      <p>暂无筹码分布数据</p>
      <p class="hint">可能原因：该股票为新股或数据尚未同步</p>
    </div>
    
    <!-- 有数据时显示内容 -->
    <template v-else>
      <!-- 统计面板 -->
      <div v-if="stats || profitData.profit > 0 || profitData.loss > 0" class="stats-panel">
        <div class="stat-item profit">
          <span class="label">获利盘</span>
          <span class="value">{{ profitData.profit.toFixed(1) }}%</span>
        </div>
        <div class="stat-item loss">
          <span class="label">套牢盘</span>
          <span class="value">{{ profitData.loss.toFixed(1) }}%</span>
        </div>
        <div v-if="stats?.weighted_avg_price" class="stat-item">
          <span class="label">平均成本</span>
          <span class="value">¥{{ stats.weighted_avg_price.toFixed(2) }}</span>
        </div>
        <div v-if="currentPrice" class="stat-item">
          <span class="label">当前价格</span>
          <span class="value">¥{{ currentPrice.toFixed(2) }}</span>
        </div>
      </div>
      
      <!-- 图例 -->
      <div class="legend">
        <span class="legend-item">
          <span class="legend-color profit"></span>
          获利盘（价格 ≤ 现价）
        </span>
        <span class="legend-item">
          <span class="legend-color loss"></span>
          套牢盘（价格 > 现价）
        </span>
      </div>
      
      <!-- 图表 -->
      <div 
        ref="chartRef" 
        class="chart"
      ></div>
    </template>
  </div>
</template>

<style scoped>
.chip-distribution-container {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.loading-state {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  background: rgba(255, 255, 255, 0.9);
  z-index: 10;
}

.stats-panel {
  display: flex;
  gap: 24px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ed 100%);
  border-radius: 8px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-item .label {
  font-size: 12px;
  color: #666;
}

.stat-item .value {
  font-size: 18px;
  font-weight: bold;
  color: #333;
}

.stat-item.profit .value {
  color: #26a69a;
}

.stat-item.loss .value {
  color: #ef5350;
}

.legend {
  display: flex;
  gap: 20px;
  padding: 8px 0;
  font-size: 12px;
  color: #666;
  flex-shrink: 0;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-color {
  width: 16px;
  height: 12px;
  border-radius: 2px;
}

.legend-color.profit {
  background: #26a69a;
}

.legend-color.loss {
  background: #ef5350;
}

.chart {
  flex: 1;
  min-height: 0;
  width: 100%;
}

.empty-state {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #999;
}

.empty-state p {
  margin: 8px 0 0;
}

.empty-state .hint {
  font-size: 12px;
  color: #bbb;
}
</style>
