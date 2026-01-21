<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, computed, nextTick } from 'vue'
import * as echarts from 'echarts'
import { thsIndexApi, type THSDailyItem, type THSIndexItem } from '@/api/thsIndex'

interface IndexData {
  ts_code: string
  name: string
  data: THSDailyItem[]
  color: string
}

const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null

const loading = ref(false)
const searchKeyword = ref('')
const searchResults = ref<THSIndexItem[]>([])
const searchLoading = ref(false)

const selectedIndices = ref<IndexData[]>([])
const dateRange = ref<'7' | '30' | '90'>('30')

// Default colors for lines
const colors = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272']

// Default indices to compare (major A-share indices)
const defaultIndices = [
  { ts_code: '885001.TI', name: '同花顺全A', color: colors[0] },
  { ts_code: '885050.TI', name: '同花顺科技', color: colors[1] },
  { ts_code: '885036.TI', name: '同花顺消费', color: colors[2] },
]

const dateRangeOptions = [
  { value: '7', label: '近7日' },
  { value: '30', label: '近30日' },
  { value: '90', label: '近90日' },
]

const normalizeData = (data: THSDailyItem[]) => {
  if (data.length === 0) return []
  const baseClose = data[0].close || 1
  return data.map(d => ({
    date: d.trade_date,
    value: ((d.close || 0) / baseClose - 1) * 100
  }))
}

const initChart = () => {
  if (!chartRef.value) return
  chartInstance = echarts.init(chartRef.value)
  updateChart()
}

const updateChart = () => {
  if (!chartInstance || selectedIndices.value.length === 0) return

  // Get all dates union
  const allDates = new Set<string>()
  selectedIndices.value.forEach(idx => {
    idx.data.forEach(d => allDates.add(d.trade_date))
  })
  const dates = Array.from(allDates).sort()

  const series = selectedIndices.value.map(idx => {
    const normalized = normalizeData(idx.data)
    const dataMap = new Map(normalized.map(d => [d.date, d.value]))
    
    return {
      name: idx.name,
      type: 'line' as const,
      data: dates.map(date => dataMap.get(date) ?? null),
      smooth: true,
      symbol: 'none',
      lineStyle: { color: idx.color, width: 2 },
      itemStyle: { color: idx.color }
    }
  })

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        if (!params || params.length === 0) return ''
        let result = `<div style="margin-bottom: 4px;">${params[0].axisValue}</div>`
        params.forEach((p: any) => {
          if (p.value !== null) {
            const sign = p.value >= 0 ? '+' : ''
            result += `<div>${p.marker} ${p.seriesName}: <b>${sign}${p.value.toFixed(2)}%</b></div>`
          }
        })
        return result
      }
    },
    legend: {
      data: selectedIndices.value.map(idx => idx.name),
      bottom: 0,
      type: 'scroll'
    },
    grid: {
      left: '3%',
      right: '4%',
      top: '10%',
      bottom: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (val: number) => `${val >= 0 ? '+' : ''}${val.toFixed(1)}%`
      },
      splitLine: { lineStyle: { type: 'dashed' } }
    },
    series
  }

  chartInstance.setOption(option, true)
}

const fetchIndexData = async (tsCode: string, name: string): Promise<IndexData | null> => {
  const days = parseInt(dateRange.value)

  try {
    const result = await thsIndexApi.getDailyData(tsCode, {
      limit: days + 10
    })

    // Skip if no data returned
    if (!result.data || result.data.length === 0) {
      console.warn(`No data for index ${tsCode}`)
      return null
    }

    return {
      ts_code: tsCode,
      name: name || result.name || tsCode,
      data: result.data.slice(-days),
      color: colors[selectedIndices.value.length % colors.length]
    }
  } catch (e) {
    console.error(`Failed to fetch data for ${tsCode}:`, e)
    return null
  }
}

const addIndex = async (item: THSIndexItem) => {
  // Check if already added
  if (selectedIndices.value.some(idx => idx.ts_code === item.ts_code)) {
    return
  }

  loading.value = true
  try {
    const indexData = await fetchIndexData(item.ts_code, item.name)
    if (indexData) {
      selectedIndices.value.push(indexData)
      updateChart()
    }
  } catch (e) {
    console.error('Failed to fetch index data:', e)
  } finally {
    loading.value = false
    searchKeyword.value = ''
    searchResults.value = []
  }
}

const removeIndex = (tsCode: string) => {
  selectedIndices.value = selectedIndices.value.filter(idx => idx.ts_code !== tsCode)
  updateChart()
}

const handleSearch = async () => {
  if (!searchKeyword.value.trim()) {
    searchResults.value = []
    return
  }

  searchLoading.value = true
  try {
    const result = await thsIndexApi.searchIndex(searchKeyword.value, 10)
    searchResults.value = result.data.filter(
      item => !selectedIndices.value.some(idx => idx.ts_code === item.ts_code)
    )
  } catch (e) {
    console.error('Search failed:', e)
    searchResults.value = []
  } finally {
    searchLoading.value = false
  }
}

const handleDateRangeChange = async () => {
  loading.value = true
  try {
    const days = parseInt(dateRange.value)
    // Refresh all selected indices
    const promises = selectedIndices.value.map(async (idx) => {
      const result = await thsIndexApi.getDailyData(idx.ts_code, { limit: days + 10 })
      return {
        ...idx,
        data: result.data.slice(-days)
      }
    })
    selectedIndices.value = await Promise.all(promises)
    updateChart()
  } catch (e) {
    console.error('Failed to refresh data:', e)
  } finally {
    loading.value = false
  }
}

const handleResize = () => {
  chartInstance?.resize()
}

// Debounce search
let searchTimer: number
watch(searchKeyword, () => {
  clearTimeout(searchTimer)
  searchTimer = window.setTimeout(handleSearch, 300)
})

onMounted(async () => {
  loading.value = true
  try {
    // Load data first before initializing chart
    const loadedIndices: IndexData[] = []
    for (const idx of defaultIndices) {
      const data = await fetchIndexData(idx.ts_code, idx.name)
      if (data) {
        loadedIndices.push(data)
      }
    }
    
    // If no data from defaults, try ranking
    if (loadedIndices.length === 0) {
      try {
        const ranking = await thsIndexApi.getRanking({ type: 'N', sort_by: 'pct_change', order: 'desc', limit: 3 })
        for (const item of ranking.data.slice(0, 3)) {
          const data = await fetchIndexData(item.ts_code, item.name)
          if (data) {
            loadedIndices.push(data)
          }
        }
      } catch (e) {
        console.error('Failed to load ranking fallback', e)
      }
    }
    
    // Set data and then initialize chart
    selectedIndices.value = loadedIndices
    
    // Initialize chart after data is ready
    await nextTick()
    initChart()
  } catch (e) {
    console.error('init chart failed', e)
  } finally {
    loading.value = false
  }

  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  chartInstance?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div class="index-compare">
    <div class="compare-header">
      <t-space>
        <t-input
          v-model="searchKeyword"
          placeholder="搜索添加指数..."
          size="small"
          style="width: 200px"
          clearable
        >
          <template #suffix-icon>
            <t-icon name="search" />
          </template>
        </t-input>
        <t-radio-group 
          v-model="dateRange" 
          variant="default-filled" 
          size="small"
          @change="handleDateRangeChange"
        >
          <t-radio-button 
            v-for="opt in dateRangeOptions" 
            :key="opt.value" 
            :value="opt.value"
          >
            {{ opt.label }}
          </t-radio-button>
        </t-radio-group>
      </t-space>
    </div>

    <!-- Search Results Dropdown -->
    <div v-if="searchResults.length > 0" class="search-results">
      <div 
        v-for="item in searchResults" 
        :key="item.ts_code" 
        class="search-item"
        @click="addIndex(item)"
      >
        <span class="item-name">{{ item.name }}</span>
        <span class="item-code">{{ item.ts_code }}</span>
      </div>
    </div>

    <!-- Selected Indices Tags -->
    <div class="selected-tags" v-if="selectedIndices.length > 0">
      <t-tag
        v-for="idx in selectedIndices"
        :key="idx.ts_code"
        closable
        :style="{ borderColor: idx.color, color: idx.color }"
        @close="removeIndex(idx.ts_code)"
      >
        {{ idx.name }}
      </t-tag>
    </div>

    <!-- Chart -->
    <div ref="chartRef" class="chart-container" :class="{ loading }">
      <t-loading v-if="loading" size="small" />
      <div v-else-if="selectedIndices.length === 0" class="empty-chart">
        暂无数据，自动加载热门概念/行业指数对比中...
      </div>
    </div>
  </div>
</template>

<style scoped>
.index-compare {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.compare-header {
  margin-bottom: 8px;
  flex-shrink: 0;
}

.search-results {
  position: absolute;
  z-index: 100;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-stroke);
  border-radius: 4px;
  max-height: 200px;
  overflow-y: auto;
  width: 250px;
  box-shadow: var(--td-shadow-2);
}

.search-item {
  padding: 8px 12px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-item:hover {
  background: var(--td-bg-color-container-hover);
}

.item-name {
  font-size: 13px;
}

.item-code {
  font-size: 11px;
  color: var(--td-text-color-secondary);
}

.selected-tags {
  margin-bottom: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  flex-shrink: 0;
}

.chart-container {
  flex: 1;
  min-height: 320px;
  position: relative;
  background: var(--td-bg-color-container);
  border: 1px dashed var(--td-component-stroke);
  border-radius: 8px;
  padding: 4px;
}

.chart-container.loading {
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-chart {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--td-text-color-secondary);
  font-size: 13px;
}
</style>
