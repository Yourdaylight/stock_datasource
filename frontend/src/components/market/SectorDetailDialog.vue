<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import * as echarts from 'echarts'
import { useThsIndexStore } from '@/stores/thsIndex'
import { INDEX_TYPE_LABELS } from '@/api/thsIndex'

const props = defineProps<{
  visible: boolean
  tsCode: string
  name?: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const thsStore = useThsIndexStore()
const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const indexInfo = computed(() => thsStore.selectedIndex)
const dailyData = computed(() => thsStore.selectedIndexDaily)

const initChart = () => {
  if (!chartRef.value) return
  
  chartInstance = echarts.init(chartRef.value)
  updateChart()
}

const updateChart = () => {
  if (!chartInstance || dailyData.value.length === 0) return
  
  const dates = dailyData.value.map(d => d.trade_date)
  const prices = dailyData.value.map(d => [d.open, d.close, d.low, d.high])
  const volumes = dailyData.value.map(d => d.vol || 0)
  const pctChanges = dailyData.value.map(d => d.pct_change || 0)
  
  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    grid: [
      { left: '10%', right: '10%', top: '5%', height: '55%' },
      { left: '10%', right: '10%', top: '68%', height: '20%' }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        gridIndex: 0,
        axisLabel: { show: false }
      },
      {
        type: 'category',
        data: dates,
        gridIndex: 1,
        axisLabel: { fontSize: 10 }
      }
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true },
      { type: 'value', gridIndex: 1, scale: true, splitNumber: 2 }
    ],
    series: [
      {
        name: '价格',
        type: 'candlestick',
        data: prices,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: '#ef5350',
          color0: '#26a69a',
          borderColor: '#ef5350',
          borderColor0: '#26a69a'
        }
      },
      {
        name: '成交量',
        type: 'bar',
        data: volumes.map((v, i) => ({
          value: v,
          itemStyle: {
            color: pctChanges[i] >= 0 ? '#ef5350' : '#26a69a'
          }
        })),
        xAxisIndex: 1,
        yAxisIndex: 1
      }
    ]
  }
  
  chartInstance.setOption(option)
}

const handleClose = () => {
  thsStore.clearSelectedIndex()
  chartInstance?.dispose()
  chartInstance = null
}

const handleOpened = async () => {
  if (props.tsCode) {
    await Promise.all([
      thsStore.fetchIndexDetail(props.tsCode),
      thsStore.fetchDailyData(props.tsCode, { limit: 30 })
    ])
    
    setTimeout(() => {
      initChart()
    }, 100)
  }
}

const formatNumber = (val?: number, decimals = 2) => {
  if (val === undefined || val === null) return '-'
  return val.toFixed(decimals)
}

const typeLabel = computed(() => {
  if (!indexInfo.value?.type) return '-'
  return INDEX_TYPE_LABELS[indexInfo.value.type] || indexInfo.value.type
})
</script>

<template>
  <t-dialog
    v-model:visible="dialogVisible"
    :header="name || tsCode"
    width="700px"
    :footer="false"
    @opened="handleOpened"
    @close="handleClose"
  >
    <div class="sector-detail">
      <!-- Basic Info -->
      <div class="info-section" v-if="indexInfo">
        <t-descriptions :column="3" size="small">
          <t-descriptions-item label="代码">{{ indexInfo.ts_code }}</t-descriptions-item>
          <t-descriptions-item label="类型">{{ typeLabel }}</t-descriptions-item>
          <t-descriptions-item label="成分股">{{ indexInfo.count || '-' }}</t-descriptions-item>
          <t-descriptions-item label="市场">{{ indexInfo.exchange || '-' }}</t-descriptions-item>
          <t-descriptions-item label="上市日期">{{ indexInfo.list_date || '-' }}</t-descriptions-item>
        </t-descriptions>
      </div>

      <!-- Latest Quote -->
      <div class="quote-section" v-if="dailyData.length > 0">
        <t-row :gutter="16">
          <t-col :span="3">
            <div class="quote-item">
              <div class="quote-label">最新价</div>
              <div class="quote-value">{{ formatNumber(dailyData[dailyData.length - 1]?.close) }}</div>
            </div>
          </t-col>
          <t-col :span="3">
            <div class="quote-item">
              <div class="quote-label">涨跌幅</div>
              <div 
                class="quote-value"
                :class="{ 
                  'text-up': (dailyData[dailyData.length - 1]?.pct_change || 0) > 0,
                  'text-down': (dailyData[dailyData.length - 1]?.pct_change || 0) < 0
                }"
              >
                {{ dailyData[dailyData.length - 1]?.pct_change ? 
                   ((dailyData[dailyData.length - 1]?.pct_change || 0) > 0 ? '+' : '') + 
                   formatNumber(dailyData[dailyData.length - 1]?.pct_change) + '%' : '-' }}
              </div>
            </div>
          </t-col>
          <t-col :span="3">
            <div class="quote-item">
              <div class="quote-label">换手率</div>
              <div class="quote-value">{{ formatNumber(dailyData[dailyData.length - 1]?.turnover_rate) }}%</div>
            </div>
          </t-col>
          <t-col :span="3">
            <div class="quote-item">
              <div class="quote-label">成交量</div>
              <div class="quote-value">{{ formatNumber((dailyData[dailyData.length - 1]?.vol || 0) / 10000, 0) }}万</div>
            </div>
          </t-col>
        </t-row>
      </div>

      <!-- Chart -->
      <div class="chart-section">
        <div class="chart-title">近30日走势</div>
        <div ref="chartRef" class="chart-container">
          <t-loading v-if="thsStore.dailyLoading" size="small" />
        </div>
      </div>
    </div>
  </t-dialog>
</template>

<style scoped>
.sector-detail {
  padding: 8px 0;
}

.info-section {
  margin-bottom: 16px;
}

.quote-section {
  margin-bottom: 16px;
  padding: 12px;
  background: var(--td-bg-color-container-hover);
  border-radius: 6px;
}

.quote-item {
  text-align: center;
}

.quote-label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  margin-bottom: 4px;
}

.quote-value {
  font-size: 16px;
  font-weight: 600;
}

.text-up {
  color: var(--td-error-color);
}

.text-down {
  color: var(--td-success-color);
}

.chart-section {
  margin-top: 16px;
}

.chart-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 8px;
}

.chart-container {
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
