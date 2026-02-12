<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { marketApi } from '@/api/market'
import { usePortfolioStore } from '@/stores/portfolio'
import { useScreenerStore } from '@/stores/screener'
import KLineChart from '@/components/charts/KLineChart.vue'
import ChipDistributionChart from '@/components/charts/ChipDistributionChart.vue'
import IndicatorPanel from '@/views/market/components/IndicatorPanel.vue'
import TrendAnalysis from '@/views/market/components/TrendAnalysis.vue'
import type { KLineData, TechnicalSignal, ChipData, ChipStats } from '@/types/common'
import type { StockProfile } from '@/api/screener'

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
const screenerStore = useScreenerStore()

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

// Stock profile (十维画像)
const stockProfile = ref<StockProfile | null>(null)
const profileLoading = ref(false)

// Chart options
const period = ref(365) // 默认365天
const adjustType = ref<'qfq' | 'hfq' | 'none'>('qfq')
const selectedIndicators = ref<string[]>(['MA', 'MACD', 'RSI', 'KDJ'])

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

// 检测是否为港股
const isHKStock = computed(() => props.stockCode?.toUpperCase().endsWith('.HK'))

// 页面整体加载状态：K线数据加载完成才显示页面
const pageLoading = computed(() => loading.value && klineData.value.length === 0)

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

// 货币符号：港股显示 HKD，A 股显示 CNY
const currencySymbol = computed(() => isHKStock.value ? 'HKD' : 'CNY')

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

// AI Analysis with streaming
const streamingContent = ref('')
const analysisStatus = ref('')

const handleAIAnalyze = () => {
  if (!props.stockCode) return
  
  analysisLoading.value = true
  streamingContent.value = ''
  analysisStatus.value = ''
  
  // Initialize trendAnalysis to show component
  trendAnalysis.value = {
    trend: 'AI 智能分析',
    summary: '',
    signals: [],
    disclaimer: '以上分析由 AI 生成，仅供参考，不构成投资建议。'
  }
  
  const eventSource = marketApi.aiAnalyzeStream(props.stockCode, period.value)
  
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      
      switch (data.type) {
        case 'status':
          analysisStatus.value = data.message
          break
        case 'trend':
          if (data.data) {
            trendAnalysis.value = {
              ...trendAnalysis.value,
              trend: data.data.trend || 'AI 智能分析',
              signals: data.data.signals || []
            }
            if (data.data.signals) {
              signals.value = data.data.signals
            }
          }
          break
        case 'content':
          streamingContent.value += data.content
          trendAnalysis.value = {
            ...trendAnalysis.value,
            summary: streamingContent.value
          }
          break
        case 'done':
          analysisLoading.value = false
          analysisStatus.value = ''
          eventSource.close()
          break
        case 'error':
          console.error('AI analysis error:', data.message)
          MessagePlugin.error(data.message || 'AI分析失败')
          analysisLoading.value = false
          analysisStatus.value = ''
          eventSource.close()
          break
      }
    } catch (e) {
      console.error('Failed to parse SSE data:', e)
    }
  }
  
  eventSource.onerror = (error) => {
    console.error('SSE connection error:', error)
    
    // EventSource 会自动重连，检查 readyState
    // 0 = CONNECTING, 1 = OPEN, 2 = CLOSED
    if (eventSource.readyState === EventSource.CLOSED) {
      analysisLoading.value = false
      analysisStatus.value = ''
      
      // 如果没有收到任何内容，才显示错误
      if (!streamingContent.value && !trendAnalysis.value?.summary) {
        MessagePlugin.error('AI分析连接失败，请稍后重试')
      }
    }
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

// Fetch stock profile (十维画像)
const fetchStockProfile = async () => {
  if (!props.stockCode) return
  
  profileLoading.value = true
  try {
    const result = await screenerStore.fetchProfile(props.stockCode)
    stockProfile.value = result
  } catch (error) {
    console.error('Failed to fetch stock profile:', error)
    stockProfile.value = null
  } finally {
    profileLoading.value = false
  }
}

// 评分颜色
const scoreColor = (score: number) => {
  if (score >= 80) return '#52c41a'
  if (score >= 60) return '#1890ff'
  if (score >= 40) return '#faad14'
  return '#ff4d4f'
}

// 等级标签颜色
const levelTheme = (level: string) => {
  switch (level) {
    case '优秀': return 'success'
    case '良好': return 'primary'
    case '中等': return 'warning'
    case '较差': return 'danger'
    default: return 'default'
  }
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
    stockProfile.value = null
    fetchStockData()
    // 港股不加载筹码峰和十维画像
    if (!newCode.toUpperCase().endsWith('.HK')) {
      fetchChipData()
      fetchStockProfile()
    }
  }
})

watch(() => props.visible, (visible) => {
  if (visible && props.stockCode) {
    fetchStockData()
    // 港股不加载筹码峰和十维画像
    if (!props.stockCode.toUpperCase().endsWith('.HK')) {
      fetchChipData()
      fetchStockProfile()
    }
  }
})
</script>

<template>
  <t-dialog
    v-model:visible="dialogVisible"
    :header="`股票详情 - ${stockInfo?.name || stockCode}`"
    width="90vw"
    top="4vh"
    :close-on-overlay-click="false"
    :footer="false"
    class="stock-detail-dialog"
    @close="handleClose"
  >
    <!-- 整页加载状态 -->
    <div v-if="pageLoading" class="page-loading">
      <t-loading size="large" text="加载中..." />
    </div>
    
    <!-- 主内容 -->
    <div v-else class="stock-detail">
      <!-- Stock Info Header -->
      <t-card class="stock-info-card" :class="{ 'hk-stock-card': isHKStock }" :bordered="false">
        <div class="stock-header">
          <div class="stock-basic">
            <h3 v-if="stockInfo">
              {{ stockInfo.name }} ({{ stockInfo.code }})
              <t-tag v-if="isHKStock" theme="warning" size="small" style="margin-left: 8px;">港股</t-tag>
            </h3>
            <h3 v-else>{{ stockCode }}</h3>
            <div v-if="priceInfo" class="price-info" :class="{ up: priceInfo.isUp, down: !priceInfo.isUp }">
              <span class="latest-price">{{ priceInfo.price }}</span>
              <span class="currency-label">{{ currencySymbol }}</span>
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
            </t-space>
          </div>
        </div>
      </t-card>
      
      <!-- Top Row: Indicator Panel + Chip + Profile -->
      <div class="top-row">
        <!-- Indicator Panel (左侧，与K线图宽度一致) -->
        <div class="indicator-collapse">
          <IndicatorPanel 
            :selected-indicators="selectedIndicators"
            @change="handleIndicatorChange"
          />
        </div>
        
        <!-- 筹码峰和十维画像 (右侧，与右面板宽度一致) - 仅 A 股显示 -->
        <div v-if="!isHKStock" class="top-right-cards">
          <!-- Chip Distribution -->
          <t-card title="筹码峰" class="chip-card-top" :bordered="false">
            <template #actions>
              <t-space size="small">
                <t-date-picker
                  v-model="chipDate"
                  placeholder="选择日期"
                  size="small"
                  style="width: 100px"
                  :disabled-date="(date: Date) => date > new Date()"
                  @change="handleChipDateChange"
                />
                <t-button variant="text" size="small" @click="fetchChipData" :loading="chipLoading">
                  <t-icon name="refresh" />
                </t-button>
              </t-space>
            </template>
            
            <div v-if="chipLoading" class="chip-loading-small">
              <t-loading size="small" text="加载中..." />
            </div>
            <ChipDistributionChart
              v-else
              :data="chipData"
              :stats="chipStats"
              :current-price="latestPrice"
              :loading="chipLoading"
              height="100%"
            />
          </t-card>
          
          <!-- Stock Profile (十维画像) -->
          <t-card title="十维画像" class="profile-card-top" :bordered="false">
            <template #actions>
              <div v-if="stockProfile" class="total-score-mini" :style="{ color: scoreColor(stockProfile.total_score) }">
                {{ stockProfile.total_score.toFixed(1) }}分
              </div>
            </template>
            
            <t-loading v-if="profileLoading" size="small" text="加载中..." class="profile-loading" />
            <div v-else-if="stockProfile" class="profile-dimensions">
              <div 
                v-for="dim in stockProfile.dimensions" 
                :key="dim.name"
                class="dimension-row"
              >
                <span class="dim-name">{{ dim.name }}</span>
                <t-progress
                  :percentage="dim.score"
                  :color="scoreColor(dim.score)"
                  :stroke-width="4"
                  size="small"
                  class="dim-progress"
                />
                <span class="dim-score">{{ dim.score.toFixed(0) }}</span>
                <t-tag :theme="levelTheme(dim.level)" size="small">{{ dim.level }}</t-tag>
              </div>
            </div>
            <t-empty v-else description="暂无画像数据" size="small" />
          </t-card>
        </div>
        
        <!-- 港股提示信息 -->
        <div v-else class="top-right-cards hk-notice">
          <t-card title="港股说明" class="hk-notice-card" :bordered="false">
            <t-alert theme="info" :close="false">
              <template #message>
                <div>当前查看的是港股，以下功能暂不支持：</div>
                <ul style="margin: 8px 0 0 16px; padding: 0;">
                  <li>筹码峰分布（港股无数据源）</li>
                  <li>十维画像评分（暂未适配港股）</li>
                </ul>
              </template>
            </t-alert>
          </t-card>
        </div>
      </div>
      
      <!-- Main Content Layout -->
      <div class="main-layout">
        <!-- Left: K-line Chart (flex: 2) -->
        <div class="chart-panel">
          <div class="kline-container">
            <KLineChart
              :data="klineData"
              :indicators="indicators"
              :indicator-dates="indicatorDates"
              :loading="chartLoading"
              height="100%"
            />
          </div>
          
          <!-- Add to Watchlist -->
          <t-card title="加入自选" class="watchlist-card" :bordered="false">
            <t-form :data="addToWatchlistForm" layout="inline" class="watchlist-form">
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
                  style="width: 140px"
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
                  style="width: 160px"
                />
              </t-form-item>
              
              <t-form-item>
                <t-button
                  theme="primary"
                  :loading="portfolioStore.loading"
                  @click="handleAddToWatchlist"
                >
                  <template #icon><t-icon name="star" /></template>
                  加入自选
                </t-button>
              </t-form-item>
            </t-form>
          </t-card>
        </div>
        
        <!-- Right: AI Analysis Panel (flex: 1) -->
        <div class="right-panel">
          <!-- AI Analysis -->
          <t-card title="AI 智能分析" class="analysis-card" :bordered="false">
            <template #actions>
              <t-space size="small">
                <t-button size="small" theme="primary" @click="handleAnalyze" :loading="analysisLoading">
                  技术分析
                </t-button>
                <t-button size="small" variant="outline" @click="handleAIAnalyze" :loading="analysisLoading">
                  AI 智能分析
                </t-button>
              </t-space>
            </template>
            
            <TrendAnalysis
              :summary="trendAnalysis?.summary"
              :disclaimer="trendAnalysis?.disclaimer"
              :loading="analysisLoading"
              :status="analysisStatus"
              class="trend-analysis-compact"
            />
          </t-card>
        </div>
      </div>
    </div>
  </t-dialog>
</template>

<style scoped>
/* Dialog body height control */
:deep(.t-dialog) {
  max-height: 92vh !important;
  height: 92vh !important;
}

:deep(.t-dialog__body) {
  padding-bottom: 12px !important;
  height: calc(92vh - 60px) !important;
  max-height: calc(92vh - 60px) !important;
  overflow: hidden !important;
  display: flex !important;
  flex-direction: column !important;
}

/* 整页加载状态 */
.page-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  flex: 1;
  height: 100%;
}

.stock-detail {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: 100%;
  min-height: 0;
}

.stock-info-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

/* 港股使用不同的渐变色 */
.stock-info-card.hk-stock-card {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
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

.currency-label {
  font-size: 12px;
  opacity: 0.8;
  margin-left: -8px;
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

/* Top Row: Indicator Panel + Chip + Profile */
.top-row {
  display: flex;
  gap: 16px;
  margin-top: 12px;
}

.indicator-collapse {
  flex: 0 0 auto;
}

.top-right-cards {
  flex: 1;
  min-width: 280px;
  display: flex;
  gap: 12px;
}

.chip-card-top,
.profile-card-top {
  flex: 1;
  min-width: 0;
  background: #fafafa;
}

.chip-card-top :deep(.t-card__body) {
  height: 160px;
  overflow: hidden;
}

.profile-card-top :deep(.t-card__body) {
  height: 200px;
  overflow: hidden;
}

/* HK Stock Notice */
.hk-notice {
  flex-direction: column;
}

.hk-notice-card {
  flex: 1;
  background: #fafafa;
}

.hk-notice-card :deep(.t-card__body) {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 120px;
}

/* Main Layout - K-line with right panel */
.main-layout {
  display: flex;
  gap: 16px;
  margin-top: 8px;
  flex: 1;
  min-height: 0;
  height: 0; /* 关键：让 flex: 1 生效 */
}

.chart-panel {
  flex: 2;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.kline-container {
  flex: 1;
  min-height: 480px;
  height: 0; /* 关键：让 flex: 1 生效 */
}

.right-panel {
  flex: 1;
  min-width: 280px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Watchlist Card */
.watchlist-card {
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ed 100%);
  border-radius: 8px;
  flex-shrink: 0; /* 不被压缩 */
}

.watchlist-card :deep(.t-card__body) {
  padding: 12px 16px;
}

.watchlist-form {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.watchlist-form :deep(.t-form__item) {
  margin-bottom: 0;
}

.chip-loading-small {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}

.total-score-mini {
  font-size: 14px;
  font-weight: bold;
}

.profile-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}

.profile-dimensions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 16px;
  overflow: hidden;
  height: 100%;
  align-content: space-evenly;
  padding: 0 8px;
}

.dimension-row {
  display: flex;
  align-items: center;
}

.dim-name {
  width: 32px;
  font-size: 12px;
  color: #666;
  flex-shrink: 0;
}

.dim-progress {
  flex: 1;
  min-width: 0;
  margin-right: 4px;
}

.dim-progress :deep(.t-progress) {
  display: flex;
  align-items: center;
}

.dim-progress :deep(.t-progress__bar) {
  flex: 1;
  height: 5px !important;
}

.dim-progress :deep(.t-progress__info) {
  display: none;
}

.dim-score {
  width: 24px;
  font-size: 11px;
  color: #666;
  text-align: right;
  margin-right: 4px;
}

.dimension-row :deep(.t-tag) {
  flex-shrink: 0;
  font-size: 11px;
  padding: 0 6px;
  height: 18px;
  line-height: 18px;
}

/* Analysis Card */
.analysis-card {
  background: #fafafa;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.analysis-card :deep(.t-card__body) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.trend-analysis-compact {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
</style>

<!-- 全局样式确保 Dialog 高度生效 -->
<style>
.stock-detail-dialog .t-dialog {
  max-height: 92vh !important;
  height: 92vh !important;
}

.stock-detail-dialog .t-dialog__body {
  height: calc(92vh - 60px) !important;
  max-height: calc(92vh - 60px) !important;
  overflow: hidden !important;
  display: flex !important;
  flex-direction: column !important;
}
</style>
