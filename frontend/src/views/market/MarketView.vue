<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useMarketStore } from '@/stores/market'
import { useOverviewStore } from '@/stores/overview'
import StockSearch from '@/components/common/StockSearch.vue'
import KLineChart from '@/components/charts/KLineChart.vue'
import IndicatorPanel from './components/IndicatorPanel.vue'
import MarketOverview from './components/MarketOverview.vue'
import TrendAnalysis from './components/TrendAnalysis.vue'

const marketStore = useMarketStore()
const overviewStore = useOverviewStore()

const selectedStock = ref('')
const dateRange = ref<[string, string]>(['', ''])
<<<<<<< Updated upstream
<<<<<<< Updated upstream
const activeTab = ref('chart')
const aiQuestion = ref('')
=======
const selectedIndicators = ref<string[]>(['MACD', 'MA'])
const showIndicatorPanel = ref(false)
const activeTab = ref('chart')
>>>>>>> Stashed changes
=======
const selectedIndicators = ref<string[]>(['MACD', 'MA'])
const showIndicatorPanel = ref(false)
const activeTab = ref('chart')
>>>>>>> Stashed changes

const handleStockSelect = async (code: string) => {
  selectedStock.value = code
  if (dateRange.value[0] && dateRange.value[1]) {
    await marketStore.fetchKLine(code, dateRange.value[0], dateRange.value[1])
    await marketStore.fetchIndicators(code, selectedIndicators.value)
  }
}

const handleDateChange = async (dates: [string, string]) => {
  dateRange.value = dates
  if (selectedStock.value && dates[0] && dates[1]) {
    await marketStore.fetchKLine(selectedStock.value, dates[0], dates[1])
    await marketStore.fetchIndicators(selectedStock.value, selectedIndicators.value)
  }
}

const handleIndicatorChange = async (indicators: string[]) => {
  selectedIndicators.value = indicators
  if (selectedStock.value) {
    await marketStore.fetchIndicators(selectedStock.value, indicators)
  }
}

const handleAnalyze = () => {
  if (selectedStock.value) {
    marketStore.analyzeStock(selectedStock.value)
  }
}

const handleAIAnalyze = () => {
  if (selectedStock.value) {
    marketStore.aiAnalyzeStock(selectedStock.value)
  }
}

<<<<<<< Updated upstream
<<<<<<< Updated upstream
// Overview computed
const majorIndices = computed(() => overviewStore.majorIndices)
const hotEtfs = computed(() => overviewStore.hotEtfsByAmount.slice(0, 5))
const quickAnalysis = computed(() => overviewStore.quickAnalysis)

// Format helpers
const formatNumber = (val?: number, decimals = 2) => {
  if (val === undefined || val === null) return '-'
  return val.toFixed(decimals)
}

const formatAmount = (val?: number) => {
  if (val === undefined || val === null) return '-'
  if (val >= 100000000) return (val / 100000000).toFixed(2) + '亿'
  if (val >= 10000) return (val / 10000).toFixed(2) + '万'
  return val.toFixed(2)
}

const getPctClass = (val?: number) => {
  if (val === undefined || val === null) return ''
  return val > 0 ? 'text-up' : val < 0 ? 'text-down' : ''
}

// AI analysis
const handleAskAI = async () => {
  if (!aiQuestion.value.trim()) return
  await overviewStore.runAIAnalysis(aiQuestion.value)
  aiQuestion.value = ''
}

const handleClearHistory = async () => {
  await overviewStore.clearConversation()
}
=======
=======
>>>>>>> Stashed changes
// Price display
const priceInfo = computed(() => {
  if (!marketStore.klineData.length) return null
  const latest = marketStore.klineData[marketStore.klineData.length - 1]
  const prev = marketStore.klineData.length > 1 ? marketStore.klineData[marketStore.klineData.length - 2] : latest
  const change = latest.close - prev.close
  const changePct = (change / prev.close) * 100
  return {
    price: latest.close.toFixed(2),
    change: change.toFixed(2),
    changePct: changePct.toFixed(2),
    isUp: change >= 0
  }
})
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes

onMounted(async () => {
  // Set default date range (last 3 months)
  const end = new Date()
  const start = new Date()
  start.setMonth(start.getMonth() - 3)
  dateRange.value = [
    start.toISOString().split('T')[0],
    end.toISOString().split('T')[0]
  ]
  
  // Fetch market overview
<<<<<<< Updated upstream
<<<<<<< Updated upstream
  await overviewStore.fetchDailyOverview()
=======
  await marketStore.fetchMarketOverview()
>>>>>>> Stashed changes
=======
  await marketStore.fetchMarketOverview()
>>>>>>> Stashed changes
})
</script>

<template>
  <div class="market-view">
<<<<<<< Updated upstream
<<<<<<< Updated upstream
    <!-- Market Overview Cards -->
    <div class="overview-section">
      <t-row :gutter="16">
        <!-- Major Indices -->
        <t-col :span="8">
          <t-card title="主要指数" size="small" :loading="overviewStore.loading">
            <div class="indices-grid">
              <div 
                v-for="idx in majorIndices" 
                :key="idx.ts_code" 
                class="index-item"
              >
                <div class="index-name">{{ idx.name || idx.ts_code }}</div>
                <div class="index-price">{{ formatNumber(idx.close) }}</div>
                <div :class="['index-change', getPctClass(idx.pct_chg)]">
                  {{ idx.pct_chg !== undefined ? (idx.pct_chg > 0 ? '+' : '') + formatNumber(idx.pct_chg) + '%' : '-' }}
                </div>
              </div>
            </div>
          </t-card>
        </t-col>
=======
=======
>>>>>>> Stashed changes
    <!-- Market Overview Section -->
    <MarketOverview
      :indices="marketStore.marketOverview?.indices || []"
      :stats="marketStore.marketOverview?.stats || null"
      :loading="marketStore.overviewLoading"
      class="overview-section"
    />
    
    <!-- Main Analysis Card -->
    <t-card class="main-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <StockSearch @select="handleStockSelect" style="width: 240px" />
            <t-date-range-picker
              v-model="dateRange"
              :enable-time-picker="false"
              @change="handleDateChange"
              style="width: 280px"
            />
          </div>
          <div class="header-right">
            <t-button 
              variant="outline" 
              @click="showIndicatorPanel = !showIndicatorPanel"
            >
              <template #icon><t-icon name="setting" /></template>
              指标设置
            </t-button>
<<<<<<< Updated upstream
          </div>
        </div>
      </template>
>>>>>>> Stashed changes

        <!-- Market Stats -->
        <t-col :span="8">
          <t-card title="市场情绪" size="small" :loading="overviewStore.loading">
            <template v-if="quickAnalysis">
              <div class="market-stats">
                <div class="stat-row">
                  <span class="stat-label">涨跌比</span>
                  <span class="stat-value">
                    <span class="text-up">{{ quickAnalysis.market_breadth.up_count || 0 }}</span>
                    /
                    <span class="text-down">{{ quickAnalysis.market_breadth.down_count || 0 }}</span>
                  </span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">涨停/跌停</span>
                  <span class="stat-value">
                    <span class="text-up">{{ quickAnalysis.market_breadth.limit_up_count || 0 }}</span>
                    /
                    <span class="text-down">{{ quickAnalysis.market_breadth.limit_down_count || 0 }}</span>
                  </span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">成交额</span>
                  <span class="stat-value">{{ quickAnalysis.market_breadth.total_amount_yi?.toFixed(0) || '-' }}亿</span>
                </div>
                <div class="stat-row">
                  <span class="stat-label">情绪</span>
                  <t-tag :theme="quickAnalysis.sentiment.score && quickAnalysis.sentiment.score > 50 ? 'success' : 'warning'" size="small">
                    {{ quickAnalysis.sentiment.label || '中性' }}
                  </t-tag>
                </div>
              </div>
            </template>
            <template v-else>
              <t-button size="small" @click="overviewStore.fetchQuickAnalysis()">
                加载市场分析
              </t-button>
            </template>
          </t-card>
        </t-col>

<<<<<<< Updated upstream
        <!-- Hot ETFs -->
        <t-col :span="8">
          <t-card title="热门ETF" size="small" :loading="overviewStore.loading">
            <div class="hot-etf-list">
              <div 
                v-for="etf in hotEtfs" 
                :key="etf.ts_code" 
                class="etf-item"
              >
                <span class="etf-name">{{ etf.name || etf.ts_code }}</span>
                <span :class="['etf-change', getPctClass(etf.pct_chg)]">
                  {{ etf.pct_chg !== undefined ? (etf.pct_chg > 0 ? '+' : '') + formatNumber(etf.pct_chg) + '%' : '-' }}
                </span>
              </div>
            </div>
          </t-card>
        </t-col>
      </t-row>
    </div>

    <!-- Main Content -->
    <t-card class="main-card">
      <t-tabs v-model="activeTab">
        <t-tab-panel value="chart" label="K线图表">
          <div class="chart-toolbar">
            <t-space>
              <StockSearch @select="handleStockSelect" />
              <t-date-range-picker
                v-model="dateRange"
                :enable-time-picker="false"
                @change="handleDateChange"
              />
            </t-space>
          </div>

          <div v-if="!selectedStock" class="empty-state">
            <t-icon name="chart-line" size="64px" style="color: #ddd" />
            <p>请选择股票查看行情</p>
          </div>

          <div v-else class="chart-container">
            <div class="chart-header">
              <h3>{{ marketStore.currentCode }}</h3>
              <t-checkbox-group v-model="selectedIndicators">
                <t-checkbox v-for="ind in indicators" :key="ind" :value="ind">
                  {{ ind }}
                </t-checkbox>
              </t-checkbox-group>
            </div>
            
            <KLineChart
              :data="marketStore.klineData"
              :indicators="marketStore.indicators"
              :loading="marketStore.loading"
            />

            <t-divider />

            <div class="analysis-section">
              <t-button theme="primary" @click="marketStore.analyzeStock(selectedStock)">
                <template #icon><t-icon name="root-list" /></template>
                AI 智能分析
              </t-button>
              
              <div v-if="marketStore.analysis" class="analysis-result">
                <t-alert theme="info" :message="marketStore.analysis" />
              </div>
            </div>
          </div>
        </t-tab-panel>

        <t-tab-panel value="ai" label="AI问答">
          <div class="ai-chat-section">
            <div class="ai-input-area">
              <t-textarea
                v-model="aiQuestion"
                placeholder="输入您的市场分析问题，例如：今天市场表现如何？有哪些热门板块？"
                :autosize="{ minRows: 2, maxRows: 4 }"
              />
              <div class="ai-actions">
                <t-space>
                  <t-button 
                    theme="primary" 
                    :loading="overviewStore.analysisLoading"
                    @click="handleAskAI"
                  >
                    <template #icon><t-icon name="chat" /></template>
                    发送
                  </t-button>
                  <t-button 
                    variant="outline"
                    @click="handleClearHistory"
                  >
                    清空对话
                  </t-button>
                </t-space>
                <span class="history-info" v-if="overviewStore.historyLength > 0">
                  对话轮次: {{ overviewStore.historyLength }}
                </span>
              </div>
            </div>

            <div v-if="overviewStore.aiAnalysisResult" class="ai-response">
              <t-card title="AI 分析结果" size="small">
                <div class="markdown-content" v-html="overviewStore.aiAnalysisResult"></div>
              </t-card>
            </div>

            <div v-if="quickAnalysis && quickAnalysis.signals.length > 0" class="signals-section">
              <t-card title="市场信号" size="small">
                <t-tag 
                  v-for="(signal, idx) in quickAnalysis.signals" 
                  :key="idx"
                  theme="warning"
                  style="margin-right: 8px; margin-bottom: 8px;"
                >
                  {{ signal }}
                </t-tag>
              </t-card>
            </div>
          </div>
        </t-tab-panel>
      </t-tabs>
=======
      <div v-else class="content-container">
        <!-- Stock Header -->
        <div class="stock-header">
          <div class="stock-info">
            <span class="stock-name">{{ marketStore.currentName }}</span>
            <span class="stock-code">{{ marketStore.currentCode }}</span>
          </div>
          <div v-if="priceInfo" class="price-info" :class="{ up: priceInfo.isUp, down: !priceInfo.isUp }">
            <span class="current-price">{{ priceInfo.price }}</span>
            <span class="price-change">
              {{ priceInfo.isUp ? '+' : '' }}{{ priceInfo.change }} 
              ({{ priceInfo.isUp ? '+' : '' }}{{ priceInfo.changePct }}%)
            </span>
          </div>
        </div>
=======
          </div>
        </div>
      </template>

      <div v-if="!selectedStock" class="empty-state">
        <t-icon name="chart-line" size="64px" style="color: #ddd" />
        <p>请选择股票查看行情</p>
      </div>

      <div v-else class="content-container">
        <!-- Stock Header -->
        <div class="stock-header">
          <div class="stock-info">
            <span class="stock-name">{{ marketStore.currentName }}</span>
            <span class="stock-code">{{ marketStore.currentCode }}</span>
          </div>
          <div v-if="priceInfo" class="price-info" :class="{ up: priceInfo.isUp, down: !priceInfo.isUp }">
            <span class="current-price">{{ priceInfo.price }}</span>
            <span class="price-change">
              {{ priceInfo.isUp ? '+' : '' }}{{ priceInfo.change }} 
              ({{ priceInfo.isUp ? '+' : '' }}{{ priceInfo.changePct }}%)
            </span>
          </div>
        </div>
>>>>>>> Stashed changes
        
        <!-- Indicator Panel -->
        <div v-if="showIndicatorPanel" class="indicator-collapse">
          <IndicatorPanel 
            :selected-indicators="selectedIndicators"
            @change="handleIndicatorChange"
          />
        </div>
        
        <!-- Tabs: Chart / Analysis -->
        <t-tabs v-model="activeTab">
          <t-tab-panel value="chart" label="K线图表">
            <KLineChart
              :data="marketStore.klineData"
              :indicators="marketStore.indicators"
              :indicator-dates="marketStore.indicatorDates"
              :loading="marketStore.loading"
              :height="550"
            />
            
            <!-- Signals Display -->
            <div v-if="marketStore.signals.length > 0" class="signals-bar">
              <span class="signals-label">技术信号：</span>
              <t-tag
                v-for="signal in marketStore.signals"
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
                <t-button theme="primary" @click="handleAnalyze" :loading="marketStore.loading">
                  <template #icon><t-icon name="chart-analytics" /></template>
                  技术分析
                </t-button>
                <t-button variant="outline" @click="handleAIAnalyze" :loading="marketStore.loading">
                  <template #icon><t-icon name="lightbulb" /></template>
                  AI 智能分析
                </t-button>
              </div>
              
              <TrendAnalysis
                :trend="marketStore.trendAnalysis?.trend"
                :support="marketStore.trendAnalysis?.support"
                :resistance="marketStore.trendAnalysis?.resistance"
                :signals="marketStore.trendAnalysis?.signals"
                :summary="marketStore.trendAnalysis?.summary"
                :disclaimer="marketStore.trendAnalysis?.disclaimer"
                :loading="marketStore.loading"
                class="trend-analysis-panel"
              />
            </div>
          </t-tab-panel>
        </t-tabs>
      </div>
>>>>>>> Stashed changes
    </t-card>
  </div>
</template>

<style scoped>
.market-view {
<<<<<<< Updated upstream
<<<<<<< Updated upstream
  height: 100%;
=======
  padding: 16px;
>>>>>>> Stashed changes
=======
  padding: 16px;
>>>>>>> Stashed changes
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.overview-section {
  flex-shrink: 0;
}

.main-card {
  flex: 1;
<<<<<<< Updated upstream
<<<<<<< Updated upstream
  min-height: 0;
}

.indices-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.index-item {
  padding: 8px;
  background: var(--td-bg-color-container-hover);
  border-radius: 4px;
}

.index-name {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  margin-bottom: 4px;
}

.index-price {
  font-size: 16px;
  font-weight: 600;
}

.index-change {
  font-size: 12px;
}

.text-up {
  color: var(--td-error-color);
}

.text-down {
  color: var(--td-success-color);
}

.market-stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-label {
  color: var(--td-text-color-secondary);
  font-size: 12px;
}

.stat-value {
  font-weight: 500;
}

.hot-etf-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.etf-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  border-bottom: 1px solid var(--td-component-stroke);
}

.etf-item:last-child {
  border-bottom: none;
}

.etf-name {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 150px;
}

.etf-change {
  font-size: 13px;
  font-weight: 500;
}

.chart-toolbar {
  margin-bottom: 16px;
=======
=======
>>>>>>> Stashed changes
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.header-left {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 400px;
  color: #999;
}

.content-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stock-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f9f9f9;
  border-radius: 8px;
}

.stock-info {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.stock-name {
  font-size: 18px;
  font-weight: 600;
}

.stock-code {
  font-size: 14px;
  color: #666;
}

.price-info {
  text-align: right;
}

.current-price {
  font-size: 24px;
  font-weight: 600;
}

.price-change {
  display: block;
  font-size: 14px;
  margin-top: 2px;
}

.price-info.up .current-price,
.price-info.up .price-change {
  color: #ec0000;
}

.price-info.down .current-price,
.price-info.down .price-change {
  color: #00da3c;
}

.indicator-collapse {
  margin-bottom: 12px;
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
}

.analysis-actions {
  display: flex;
  gap: 12px;
}

.trend-analysis-panel {
  min-height: 300px;
<<<<<<< Updated upstream
<<<<<<< Updated upstream
}

.ai-chat-section {
  padding: 16px 0;
}

.ai-input-area {
  margin-bottom: 16px;
}

.ai-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.history-info {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.ai-response {
  margin-bottom: 16px;
}

.markdown-content {
  line-height: 1.6;
  white-space: pre-wrap;
}

.signals-section {
  margin-top: 16px;
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
}
</style>
