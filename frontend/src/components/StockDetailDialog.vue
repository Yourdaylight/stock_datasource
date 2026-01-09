<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { marketApi } from '@/api/market'
import { usePortfolioStore } from '@/stores/portfolio'
import KLineChart from '@/components/charts/KLineChart.vue'
import KDJChart from '@/components/charts/KDJChart.vue'
import type { KLineData, IndicatorData } from '@/types/common'

interface Props {
  visible: boolean
  stockCode: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:visible': [value: boolean]
  close: []
}>()

const portfolioStore = usePortfolioStore()

// Data
const stockInfo = ref<{ code: string; name: string } | null>(null)
const klineData = ref<KLineData[]>([])
const kdjData = ref<IndicatorData[]>([])
const loading = ref(false)
const chartLoading = ref(false)

// Chart options
const period = ref(60) // 默认60天
const adjustType = ref<'qfq' | 'hfq' | 'none'>('qfq')
const showIndicators = ref(['KDJ'])

// Add to watchlist form
const addToWatchlistForm = ref({
  quantity: 100,
  cost_price: 0,
  buy_date: new Date().toISOString().split('T')[0],
  notes: ''
})

const periodOptions = [
  { label: '30天', value: 30 },
  { label: '60天', value: 60 },
  { label: '90天', value: 90 },
  { label: '180天', value: 180 },
  { label: '365天', value: 365 }
]

const adjustOptions = [
  { label: '前复权', value: 'qfq' },
  { label: '后复权', value: 'hfq' },
  { label: '不复权', value: 'none' }
]

const indicatorOptions = [
  { label: 'KDJ', value: 'KDJ' },
  { label: 'MACD', value: 'MACD' },
  { label: 'RSI', value: 'RSI' },
  { label: 'BOLL', value: 'BOLL' }
]

// Computed
const dialogVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value)
})

const latestPrice = computed(() => {
  if (klineData.value.length === 0) return 0
  return klineData.value[klineData.value.length - 1]?.close || 0
})

// Methods
const fetchStockData = async () => {
  if (!props.stockCode) return
  
  loading.value = true
  chartLoading.value = true
  
  try {
    // Calculate date range
    const endDate = new Date()
    const startDate = new Date()
    startDate.setDate(endDate.getDate() - period.value)
    
    const formatDate = (date: Date) => {
      return date.toISOString().split('T')[0].replace(/-/g, '')
    }
    
    // Fetch K-line data
    const klineResponse = await marketApi.getKLine({
      code: props.stockCode,
      start_date: formatDate(startDate),
      end_date: formatDate(endDate),
      adjust: adjustType.value
    })
    
    stockInfo.value = {
      code: klineResponse.code,
      name: klineResponse.name
    }
    klineData.value = klineResponse.data
    
    // Set default cost price to latest close price
    addToWatchlistForm.value.cost_price = latestPrice.value
    
    // Fetch indicators if needed
    if (showIndicators.value.includes('KDJ')) {
      await fetchKDJData()
    }
    
  } catch (error) {
    console.error('Failed to fetch stock data:', error)
    MessagePlugin.error('获取股票数据失败')
  } finally {
    loading.value = false
    chartLoading.value = false
  }
}

const fetchKDJData = async () => {
  if (!props.stockCode) return
  
  try {
    const response = await marketApi.getIndicators({
      code: props.stockCode,
      indicators: ['KDJ'],
      period: period.value
    })
    kdjData.value = response.indicators
  } catch (error) {
    console.error('Failed to fetch KDJ data:', error)
  }
}

const handlePeriodChange = () => {
  fetchStockData()
}

const handleAdjustChange = () => {
  fetchStockData()
}

const handleIndicatorChange = () => {
  if (showIndicators.value.includes('KDJ')) {
    fetchKDJData()
  } else {
    kdjData.value = []
  }
}

const handleAddToWatchlist = async () => {
  if (!stockInfo.value) return
  
  try {
    await portfolioStore.addPosition({
      ts_code: stockInfo.value.code,
      quantity: addToWatchlistForm.value.quantity,
      cost_price: addToWatchlistForm.value.cost_price,
      buy_date: addToWatchlistForm.value.buy_date,
      notes: addToWatchlistForm.value.notes || `从智能选股添加 - ${stockInfo.value.name}`
    })
    
    MessagePlugin.success(`已将 ${stockInfo.value.name} 添加到自选股`)
    emit('close')
  } catch (error) {
    console.error('Failed to add to watchlist:', error)
    MessagePlugin.error('添加自选股失败')
  }
}

const handleClose = () => {
  emit('close')
}

// Watch for stock code changes
watch(() => props.stockCode, (newCode) => {
  if (newCode && props.visible) {
    fetchStockData()
  }
})

watch(() => props.visible, (visible) => {
  if (visible && props.stockCode) {
    fetchStockData()
  }
})
</script>

<template>
  <t-dialog
    v-model:visible="dialogVisible"
    :header="`股票详情 - ${stockInfo?.name || stockCode}`"
    width="1200px"
    :close-on-overlay-click="false"
    @close="handleClose"
  >
    <div v-if="loading" class="loading-container">
      <t-loading size="large" text="加载中..." />
    </div>
    
    <div v-else class="stock-detail">
      <!-- Stock Info Header -->
      <t-card v-if="stockInfo" class="stock-info-card" :bordered="false">
        <div class="stock-header">
          <div class="stock-basic">
            <h3>{{ stockInfo.name }} ({{ stockInfo.code }})</h3>
            <div class="price-info">
              <span class="latest-price">{{ latestPrice.toFixed(2) }}</span>
              <span v-if="klineData.length >= 2" class="price-change">
                {{ (latestPrice - klineData[klineData.length - 2]?.close || 0).toFixed(2) }}
                ({{ (((latestPrice - (klineData[klineData.length - 2]?.close || 0)) / (klineData[klineData.length - 2]?.close || 1)) * 100).toFixed(2) }}%)
              </span>
            </div>
          </div>
          
          <div class="chart-controls">
            <t-space>
              <t-select
                v-model="period"
                :options="periodOptions"
                style="width: 100px"
                @change="handlePeriodChange"
              />
              <t-select
                v-model="adjustType"
                :options="adjustOptions"
                style="width: 100px"
                @change="handleAdjustChange"
              />
              <t-checkbox-group
                v-model="showIndicators"
                :options="indicatorOptions"
                @change="handleIndicatorChange"
              />
            </t-space>
          </div>
        </div>
      </t-card>
      
      <!-- Charts -->
      <t-row :gutter="16" style="margin-top: 16px">
        <t-col :span="8">
          <t-card title="K线图" :bordered="false">
            <KLineChart
              :data="klineData"
              :loading="chartLoading"
            />
          </t-card>
        </t-col>
        
        <t-col :span="4" v-if="showIndicators.includes('KDJ')">
          <t-card title="KDJ指标" :bordered="false">
            <KDJChart
              :data="kdjData"
              :loading="chartLoading"
            />
          </t-card>
        </t-col>
      </t-row>
      
      <!-- Add to Watchlist Form -->
      <t-card title="添加到自选股" style="margin-top: 16px" :bordered="false">
        <t-form :data="addToWatchlistForm" layout="inline">
          <t-form-item label="股数" name="quantity">
            <t-input-number
              v-model="addToWatchlistForm.quantity"
              :min="1"
              :step="100"
              style="width: 120px"
            />
          </t-form-item>
          
          <t-form-item label="成本价" name="cost_price">
            <t-input-number
              v-model="addToWatchlistForm.cost_price"
              :min="0"
              :step="0.01"
              :decimal-places="2"
              style="width: 120px"
            />
          </t-form-item>
          
          <t-form-item label="买入日期" name="buy_date">
            <t-date-picker
              v-model="addToWatchlistForm.buy_date"
              style="width: 140px"
            />
          </t-form-item>
          
          <t-form-item label="备注" name="notes">
            <t-input
              v-model="addToWatchlistForm.notes"
              placeholder="可选"
              style="width: 200px"
            />
          </t-form-item>
          
          <t-form-item>
            <t-button
              theme="primary"
              :loading="portfolioStore.loading"
              @click="handleAddToWatchlist"
            >
              加入自选
            </t-button>
          </t-form-item>
        </t-form>
      </t-card>
    </div>
    
    <template #footer>
      <t-space>
        <t-button variant="outline" @click="handleClose">关闭</t-button>
      </t-space>
    </template>
  </t-dialog>
</template>

<style scoped>
.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 400px;
}

.stock-detail {
  min-height: 600px;
}

.stock-info-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.stock-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stock-basic h3 {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: bold;
}

.price-info {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.latest-price {
  font-size: 32px;
  font-weight: bold;
}

.price-change {
  font-size: 16px;
  opacity: 0.9;
}

.chart-controls {
  display: flex;
  align-items: center;
}

.chart-controls :deep(.t-select),
.chart-controls :deep(.t-checkbox-group) {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
}

.chart-controls :deep(.t-select .t-input) {
  background: transparent;
  border: none;
  color: white;
}

.chart-controls :deep(.t-checkbox-group .t-checkbox) {
  color: white;
}
</style>