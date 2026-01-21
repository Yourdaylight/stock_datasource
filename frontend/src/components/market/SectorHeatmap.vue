<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { thsIndexApi, type THSRankingItem } from '@/api/thsIndex'

const props = defineProps<{
  maxItems?: number
}>()

const emit = defineEmits<{
  (e: 'select', tsCode: string, name: string): void
}>()

const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null
let isUnmounted = false

const rankingList = ref<THSRankingItem[]>([])
const tradeDate = ref('')
const loading = ref(false)

const selectedType = ref('N') // Default to concept (most popular)

const typeOptions = [
  { value: 'N', label: '概念' },
  { value: 'I', label: '行业' },
  { value: 'R', label: '地域' },
  { value: 'S', label: '特色' },
]

// Get color based on pct_change - use gradient colors
const getColor = (value: number): string => {
  if (value >= 5) return '#b71c1c'       // Deep red
  if (value >= 3) return '#c62828'       // Red
  if (value >= 2) return '#e53935'       // Light red
  if (value >= 1) return '#ef5350'       // Lighter red
  if (value > 0) return '#ff8a80'        // Very light red
  if (value === 0) return '#9e9e9e'      // Gray
  if (value > -1) return '#a5d6a7'       // Very light green
  if (value > -2) return '#66bb6a'       // Lighter green
  if (value > -3) return '#43a047'       // Light green
  if (value > -5) return '#2e7d32'       // Green
  return '#1b5e20'                        // Deep green
}

const heatmapData = computed(() => {
  const data = rankingList.value.slice(0, props.maxItems || 50)
  return data.map(item => ({
    name: item.name,
    value: item.pct_change || 0,
    ts_code: item.ts_code,
    count: item.count,
    close: item.close,
    vol: item.vol,
    turnover_rate: item.turnover_rate,
    itemStyle: {
      color: getColor(item.pct_change || 0)
    }
  }))
})

const initChart = () => {
  if (!chartRef.value) return
  
  chartInstance = echarts.init(chartRef.value)
  updateChart()
  
  chartInstance.on('click', (params: any) => {
    if (params.data && params.data.ts_code) {
      emit('select', params.data.ts_code, params.data.name)
    }
  })
}

const updateChart = () => {
  if (!chartInstance) return
  
  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const data = params.data
        if (!data) return ''
        const pctStr = data.value >= 0 ? `+${data.value.toFixed(2)}%` : `${data.value.toFixed(2)}%`
        return `
          <div style="font-weight: bold; margin-bottom: 4px;">${data.name}</div>
          <div>涨跌幅: <span style="color: ${data.value >= 0 ? '#c23531' : '#388e3c'}">${pctStr}</span></div>
          <div>成分股: ${data.count || '-'}</div>
          <div>收盘: ${data.close?.toFixed(2) || '-'}</div>
          <div>换手率: ${data.turnover_rate?.toFixed(2) || '-'}%</div>
        `
      }
    },
    series: [{
      type: 'treemap',
      width: '100%',
      height: '100%',
      roam: false,
      nodeClick: 'zoomToNode',
      breadcrumb: { show: false },
      label: {
        show: true,
        formatter: (params: any) => {
          const pct = params.data.value
          const pctStr = pct >= 0 ? `+${pct.toFixed(2)}%` : `${pct.toFixed(2)}%`
          // 根据区块大小决定是否显示涨跌幅
          if (params.data.value !== undefined) {
            return `{name|${params.name}}\n{pct|${pctStr}}`
          }
          return `{name|${params.name}}`
        },
        rich: {
          name: {
            fontSize: 10,
            color: '#fff',
            lineHeight: 14,
            textShadowColor: 'rgba(0,0,0,0.4)',
            textShadowBlur: 2
          },
          pct: {
            fontSize: 9,
            color: 'rgba(255,255,255,0.9)',
            lineHeight: 12,
            textShadowColor: 'rgba(0,0,0,0.4)',
            textShadowBlur: 2
          }
        }
      },
      itemStyle: {
        borderColor: '#fff',
        borderWidth: 1,
        gapWidth: 1
      },
      data: heatmapData.value
    }]
  }
  
  chartInstance.setOption(option)
}

const handleResize = () => {
  chartInstance?.resize()
}

const fetchData = async () => {
  if (isUnmounted) return
  loading.value = true
  try {
    const result = await thsIndexApi.getRanking({
      type: selectedType.value,
      sort_by: 'pct_change',
      order: 'desc',
      limit: props.maxItems || 50
    })
    if (isUnmounted) return
    rankingList.value = result.data
    tradeDate.value = result.trade_date
  } catch (e) {
    if (isUnmounted) return
    console.error('Failed to fetch heatmap data:', e)
    rankingList.value = []
  } finally {
    if (!isUnmounted) {
      loading.value = false
    }
  }
}

let fetchTimer: number | undefined
const scheduleFetch = () => {
  if (isUnmounted) return
  if (fetchTimer) window.clearTimeout(fetchTimer)
  fetchTimer = window.setTimeout(() => {
    if (!isUnmounted) {
      fetchData()
    }
  }, 250)
}

watch(selectedType, () => {
  scheduleFetch()
})

watch(rankingList, () => {
  updateChart()
}, { deep: true })

onMounted(async () => {
  await fetchData()
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  isUnmounted = true
  chartInstance?.dispose()
  chartInstance = null
  window.removeEventListener('resize', handleResize)
  if (fetchTimer) window.clearTimeout(fetchTimer)
})
</script>

<template>
  <div class="sector-heatmap">
    <div class="heatmap-header">
      <t-radio-group v-model="selectedType" variant="default-filled" size="small">
        <t-radio-button 
          v-for="opt in typeOptions" 
          :key="opt.value" 
          :value="opt.value"
        >
          {{ opt.label }}
        </t-radio-button>
      </t-radio-group>
      <span class="trade-date" v-if="tradeDate">
        {{ tradeDate }}
      </span>
    </div>
    <div 
      ref="chartRef" 
      class="heatmap-chart"
      :class="{ loading }"
    >
      <t-loading v-if="loading" size="small" />
    </div>
  </div>
</template>

<style scoped>
.sector-heatmap {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.heatmap-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  flex-shrink: 0;
  gap: 8px;
}

.heatmap-header :deep(.t-radio-group) {
  display: flex;
  gap: 6px;
}

.heatmap-header :deep(.t-radio-button) {
  padding: 0 10px;
  border-radius: 6px;
}

.heatmap-header :deep(.t-radio-button.t-is-checked) {
  background: var(--td-brand-color);
  border-color: var(--td-brand-color);
  color: #fff;
}

.trade-date {
  font-size: 11px;
  color: var(--td-text-color-secondary);
}

.heatmap-chart {
  flex: 1;
  min-height: 220px;
  position: relative;
}

.heatmap-chart.loading {
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
