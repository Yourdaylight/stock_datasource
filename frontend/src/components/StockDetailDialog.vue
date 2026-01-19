<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { marketApi } from '@/api/market'
import { usePortfolioStore } from '@/stores/portfolio'
import KLineChart from '@/components/charts/KLineChart.vue'
import ChipDistributionChart from '@/components/charts/ChipDistributionChart.vue'
import IndicatorPanel from '@/views/market/components/IndicatorPanel.vue'
import TrendAnalysis from '@/views/market/components/TrendAnalysis.vue'
import type { KLineData, TechnicalSignal, ChipData, ChipStats } from '@/types/common'

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
const indicators = ref<Record<string, number[]>>({})
const indicatorDates = ref<string[]>([])
const signals = ref<TechnicalSignal[]>([])
const trendAnalysis = ref<any>(null)
const loading = ref(false)
const chartLoading = ref(false)
const analysisLoading = ref(false)

// Chip distribution data (筹码峰)
const chipData = ref<ChipData[]>([])
const chipStats = ref<ChipStats | null>(null)
const chipLoading = ref(false)
const chipDate = ref<string>('')

// Chart options
const period = ref(90) // 默认90天
const adjustType = ref<'qfq' | 'hfq' | 'none'>('qfq')
const selectedIndicators = ref<string[]>(['MACD', 'MA'])
const showIndicatorPanel = ref(false)
const activeTab = ref('chart')

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

// Computed
const dialogVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value)
})

const latestPrice = computed(() => {
  if (klineData.value.length === 0) return 0
  return klineData.value[klineData.value.length - 1]?.close || 0
})

const priceInfo = computed(() => {
  if (klineData.value.length < 2) return null
  const latest = klineData.value[klineData.value.length - 1]
  const prev = klineData.value[klineData.value.length - 2]
  const change = latest.close - prev.close
  const changePct = (change / prev.close) * 100
  return {
    price: latest.close.toFixed(2),
    change: change.toFixed(2),
    changePct: changePct.toFixed(2),
    isUp: change >= 0
  }
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
    
    // Fetch indicators
    await fetchIndicators()
    
  } catch (error) {
    console.error('Failed to fetch stock data:', error)
    MessagePlugin.error('获取股票数据失败')
  } finally {
    loading.value = false
    chartLoading.value = false
  }
}

const fetchIndicators = async () => {
  if (!props.stockCode) return
  
  try {
    const response = await marketApi.getIndicatorsV2({
      code: props.stockCode,
      indicators: selectedIndicators.value,
      period: period.value
    })
    indicators.value = response.indicators
    indicatorDates.value = response.dates
    signals.value = response.signals || []
  } catch (error) {
    console.error('Failed to fetch indicators:', error)
  }
}

const handlePeriodChange = () => {
  fetchStockData()
}

const handleAdjustChange = () => {
  fetchStockData()
}

const handleIndicatorChange = async (newIndicators: string[]) => {
  selectedIndicators.value = newIndicators
  await fetchIndicators()
}

const handleAnalyze = async () => {
  if (!props.stockCode) return
  
  analysisLoading.value = true
  try {
    const response = await marketApi.analyzeTrend({ 
      code: props.stockCode, 
      period: period.value 
    })
    trendAnalysis.value = response
  } catch (error) {
    console.error('Failed to analyze stock:', error)
    MessagePlugin.error('分析失败，请稍后重试')
  } finally {
    analysisLoading.value = false
  }
}

const handleAIAnalyze = async () => {
  if (!props.stockCode) return
  
  analysisLoading.value = true
  try {
    const response = await marketApi.aiAnalyze({ 
      code: props.stockCode, 
      period: period.value 
    })
    trendAnalysis.value = {
      trend: response.trend || 'AI 智能分析',  // 确保 trend 有值，否则组件不显示
      summary: response.analysis,
      signals: response.signals || [],
      disclaimer: '以上分析由 AI 生成，仅供参考，不构成投资建议。'
    }
    if (response.signals) {
      signals.value = response.signals
    }
  } catch (error) {
    console.error('Failed to AI analyze stock:', error)
    MessagePlugin.error('AI分析失败，请稍后重试')
  } finally {
    analysisLoading.value = false
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

// Fetch chip distribution data (筹码峰)
const fetchChipData = async () => {
  if (!props.stockCode) return
  
  chipLoading.value = true
  try {
    const formatDate = (date: Date) => {
      return date.toISOString().split('T')[0].replace(/-/g, '')
    }
    
    // 获取筹码分布数据
    const params: { ts_code: string; trade_date?: string } = { ts_code: props.stockCode }
    if (chipDate.value) {
      params.trade_date = chipDate.value.replace(/-/g, '')
    }
    
    const data = await marketApi.getChipDistribution(params)
    chipData.value = data
    
    // 获取筹码统计信息
    if (data.length > 0) {
      const tradeDate = data[0].trade_date
      chipDate.value = tradeDate.replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3')
      
      const stats = await marketApi.getChipStats({
        ts_code: props.stockCode,
        trade_date: tradeDate
      })
      chipStats.value = stats
    }
  } catch (error) {
    console.error('Failed to fetch chip data:', error)
    chipData.value = []
    chipStats.value = null
  } finally {
    chipLoading.value = false
  }
}

const handleChipDateChange = () => {
  fetchChipData()
}

const handleClose = () => {
  emit('close')
}

// Watch for stock code changes
watch(() => props.stockCode, (newCode) => {
  if (newCode && props.visible) {
    // Reset state
    indicators.value = {}
    indicatorDates.value = []
    signals.value = []
    trendAnalysis.value = null
    chipData.value = []
    chipStats.value = null
    chipDate.value = ''
    activeTab.value = 'chart'
    fetchStockData()
  }
})

watch(() => props.visible, (visible) => {
  if (visible && props.stockCode) {
    fetchStockData()
  }
})

// Watch for tab change to load chip data lazily
watch(() => activeTab.value, (tab) => {
  if (tab === 'chip' && chipData.value.length === 0 && !chipLoading.value) {
    fetchChipData()
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
            <div v-if="priceInfo" class="price-info" :class="{ up: priceInfo.isUp, down: !priceInfo.isUp }">
              <span class="latest-price">{{ priceInfo.price }}</span>
              <span class="price-change">
                {{ priceInfo.isUp ? '+' : '' }}{{ priceInfo.change }} 
                ({{ priceInfo.isUp ? '+' : '' }}{{ priceInfo.changePct }}%)
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
              <t-button 
                variant="outline" 
                size="small"
                @click="showIndicatorPanel = !showIndicatorPanel"
              >
                <template #icon><t-icon name="setting" /></template>
                指标设置
              </t-button>
            </t-space>
          </div>
        </div>
      </t-card>
      
      <!-- Indicator Panel -->
      <div v-if="showIndicatorPanel" class="indicator-collapse">
        <IndicatorPanel 
          :selected-indicators="selectedIndicators"
          @change="handleIndicatorChange"
        />
      </div>
      
      <!-- Tabs: Chart / Analysis / Add to Watchlist -->
      <t-tabs v-model="activeTab" style="margin-top: 16px">
        <t-tab-panel value="chart" label="K线图表">
          <KLineChart
            :data="klineData"
            :indicators="indicators"
            :indicator-dates="indicatorDates"
            :loading="chartLoading"
            :height="450"
          />
          
          <!-- Signals Display -->
          <div v-if="signals.length > 0" class="signals-bar">
            <span class="signals-label">技术信号：</span>
            <t-tag
              v-for="signal in signals"
              :key="signal.signal"
              :theme="signal.type === 'bullish' ? 'success' : signal.type === 'bearish' ? 'danger' : 'default'"
              variant="light"
              size="small"
            >
              {{ signal.signal }}
            </t-tag>
          </div>
        </t-tab-panel>
        
        <t-tab-panel value="analysis" label="AI 分析">
          <div class="analysis-section">
            <div class="analysis-actions">
              <t-button theme="primary" @click="handleAnalyze" :loading="analysisLoading">
                <template #icon><t-icon name="chart-analytics" /></template>
                技术分析
              </t-button>
              <t-button variant="outline" @click="handleAIAnalyze" :loading="analysisLoading">
                <template #icon><t-icon name="lightbulb" /></template>
                AI 智能分析
              </t-button>
            </div>
            
            <TrendAnalysis
              :trend="trendAnalysis?.trend"
              :support="trendAnalysis?.support"
              :resistance="trendAnalysis?.resistance"
              :signals="trendAnalysis?.signals"
              :summary="trendAnalysis?.summary"
              :disclaimer="trendAnalysis?.disclaimer"
              :loading="analysisLoading"
              class="trend-analysis-panel"
            />
          </div>
        </t-tab-panel>
        
        <t-tab-panel value="chip" label="筹码峰">
          <div class="chip-section">
            <div class="chip-controls">
              <t-date-picker
                v-model="chipDate"
                placeholder="选择交易日"
                style="width: 160px"
                :disabled-date="(date: Date) => date > new Date()"
                @change="handleChipDateChange"
              />
              <t-button variant="outline" size="small" @click="fetchChipData" :loading="chipLoading">
                刷新
              </t-button>
            </div>
            
            <div v-if="chipLoading" class="chip-loading">
              <t-loading size="medium" text="加载筹码数据..." />
            </div>
            
            <ChipDistributionChart
              v-else
              :data="chipData"
              :stats="chipStats"
              :current-price="latestPrice"
              :loading="chipLoading"
              :height="400"
            />
          </div>
        </t-tab-panel>
        
        <t-tab-panel value="watchlist" label="加入自选">
          <!-- Add to Watchlist Form -->
          <t-card :bordered="false">
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
        </t-tab-panel>
      </t-tabs>
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
  flex-wrap: wrap;
  gap: 12px;
}

.stock-basic h3 {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: bold;
}

.price-info {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.latest-price {
  font-size: 28px;
  font-weight: bold;
}

.price-change {
  font-size: 14px;
  opacity: 0.9;
}

.price-info.up .latest-price,
.price-info.up .price-change {
  color: #ff6b6b;
}

.price-info.down .latest-price,
.price-info.down .price-change {
  color: #51cf66;
}

.chart-controls {
  display: flex;
  align-items: center;
}

.chart-controls :deep(.t-select),
.chart-controls :deep(.t-button) {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
}

.chart-controls :deep(.t-select .t-input) {
  background: transparent;
  border: none;
  color: white;
}

.chart-controls :deep(.t-button) {
  color: white;
  border-color: rgba(255, 255, 255, 0.3);
}

.indicator-collapse {
  margin-top: 12px;
}

.signals-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 8px 12px;
  background: #f5f5f5;
  border-radius: 6px;
  flex-wrap: wrap;
}

.signals-label {
  font-size: 13px;
  color: #666;
}

.analysis-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 0;
}

.analysis-actions {
  display: flex;
  gap: 12px;
}

.trend-analysis-panel {
  min-height: 250px;
}

.chip-section {
  padding: 16px 0;
}

.chip-controls {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.chip-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 300px;
}
</style>
