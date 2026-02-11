<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue'
import { useOverviewStore } from '@/stores/overview'
import { overviewApi, type HotEtf } from '@/api/overview'
import { request } from '@/utils/request'
import SectorHeatmap from '@/components/market/SectorHeatmap.vue'
import SectorDetailDialog from '@/components/market/SectorDetailDialog.vue'
import SectorRankingTable from '@/components/market/SectorRankingTable.vue'
import IndexCompareChart from '@/components/market/IndexCompareChart.vue'
import MarketAiFloatButton from '@/components/market/MarketAiFloatButton.vue'
import MarketAiDialog from '@/components/market/MarketAiDialog.vue'
// TopListPanel removed - 龙虎榜功能已移除

// 热门股票数据类型
interface HotStockItem {
  ts_code: string
  name: string
  close?: number
  pct_chg?: number
  amount?: number
  turnover_rate?: number
}

const overviewStore = useOverviewStore()

// Main tab state
const activeMainTab = ref('overview')

const hotEtfList = ref<HotEtf[]>([])
const hotEtfLoading = ref(false)
const hotStocksData = ref<HotStockItem[]>([])
const hotStocksLoading = ref(false)
let hotEtfTimer: number | undefined
let isUnmounted = false

const scheduleHotEtfRefresh = () => {
  if (isUnmounted) return
  if (hotEtfTimer) window.clearTimeout(hotEtfTimer)
  hotEtfTimer = window.setTimeout(async () => {
    if (isUnmounted) return
    hotEtfLoading.value = true
    try {
      const result = await overviewApi.getHotEtfs({ sort_by: 'amount', limit: 10 })
      if (isUnmounted) return
      hotEtfList.value = result.data
    } catch (e) {
      if (isUnmounted) return
      console.error('Failed to fetch hot ETFs:', e)
      hotEtfList.value = []
    } finally {
      if (!isUnmounted) {
        hotEtfLoading.value = false
      }
    }
  }, 300)
}

// 获取热门股票数据（按成交额排序）
const fetchHotStocks = async () => {
  hotStocksLoading.value = true
  try {
    const result = await request.get('/api/market/hot-stocks?sort_by=amount&limit=10')
    if (isUnmounted) return
    hotStocksData.value = result.data || []
  } catch (e) {
    if (isUnmounted) return
    console.error('Failed to fetch hot stocks:', e)
    hotStocksData.value = []
  } finally {
    if (!isUnmounted) {
      hotStocksLoading.value = false
    }
  }
}

// 格式化成交额
const formatAmount = (val?: number) => {
  if (val === undefined || val === null) return '-'
  // amount 单位是千元，转换为亿
  const amountYi = val / 100000
  if (amountYi >= 1) {
    return amountYi.toFixed(1) + '亿'
  }
  return (val / 100).toFixed(0) + '万'
}

// Sector detail dialog
const sectorDialogVisible = ref(false)
const selectedSectorCode = ref('')
const selectedSectorName = ref('')

// AI dialog
const aiDialogVisible = ref(false)

// Overview computed
const majorIndices = computed(() => overviewStore.majorIndices)
const hotEtfs = computed(() => hotEtfList.value)
const quickAnalysis = computed(() => overviewStore.quickAnalysis)

const sentimentLabel = computed(() => {
  const label = quickAnalysis.value?.sentiment?.label
  if (label) return label
  const summary = quickAnalysis.value?.market_summary || ''
  if (summary.includes('悲观') || summary.includes('偏空')) return '偏空'
  if (summary.includes('乐观') || summary.includes('偏多')) return '偏多'
  return '中性'
})

// Format helpers
const formatNumber = (val?: number, decimals = 2) => {
  if (val === undefined || val === null) return '-'
  return val.toFixed(decimals)
}

const getPctClass = (val?: number) => {
  if (val === undefined || val === null) return ''
  return val > 0 ? 'text-up' : val < 0 ? 'text-down' : ''
}

// Sector handlers
const handleSectorSelect = (tsCode: string, name: string) => {
  selectedSectorCode.value = tsCode
  selectedSectorName.value = name
  sectorDialogVisible.value = true
}

// AI dialog handler
const handleAiClick = () => {
  aiDialogVisible.value = true
}

onMounted(async () => {
  // Fetch market overview & sentiment
  await Promise.all([
    overviewStore.fetchDailyOverview(),
    overviewStore.fetchQuickAnalysis()
  ])
  scheduleHotEtfRefresh()
  fetchHotStocks()
})

onUnmounted(() => {
  isUnmounted = true
  if (hotEtfTimer) window.clearTimeout(hotEtfTimer)
})
</script>

<template>
  <div class="market-view">
    <!-- Main Tabs -->
    <t-tabs v-model="activeMainTab" size="large" class="market-tabs" :lazy="true">
      <t-tab-panel value="overview" label="市场概览">
        <template v-if="activeMainTab === 'overview'">
        <!-- Top Section: Major Indices (one row) -->
        <div class="indices-section">
          <div class="indices-row" :class="{ loading: overviewStore.loading }">
            <div 
              v-for="idx in majorIndices" 
              :key="idx.ts_code" 
              class="index-card"
              :class="getPctClass(idx.pct_chg)"
            >
              <div class="index-name">{{ idx.name || idx.ts_code }}</div>
              <div class="index-price">{{ formatNumber(idx.close) }}</div>
              <div :class="['index-change', getPctClass(idx.pct_chg)]">
                {{ idx.pct_chg !== undefined ? (idx.pct_chg > 0 ? '+' : '') + formatNumber(idx.pct_chg) + '%' : '-' }}
              </div>
            </div>
            <t-loading v-if="overviewStore.loading && majorIndices.length === 0" size="small" />
          </div>
        </div>

        <!-- Second Row: Four columns - 市场情绪 | 板块热力图 | 龙虎榜 | 热门ETF -->
        <div class="overview-section">
          <t-row :gutter="16">
            <!-- Market Sentiment -->
            <t-col :span="2">
              <t-card title="市场情绪" size="small" :bordered="false" class="overview-card">
                <div class="market-stats">
                  <div class="stat-item">
                    <div class="stat-main">
                      <span class="text-up">{{ quickAnalysis?.market_breadth.up_count ?? '—' }}</span>
                      <span class="stat-divider">/</span>
                      <span class="text-down">{{ quickAnalysis?.market_breadth.down_count ?? '—' }}</span>
                    </div>
                    <div class="stat-label">涨跌家数</div>
                  </div>
                  <div class="stat-item">
                    <div class="stat-main">
                      <span class="text-up">{{ quickAnalysis?.market_breadth.limit_up_count ?? '—' }}</span>
                      <span class="stat-divider">/</span>
                      <span class="text-down">{{ quickAnalysis?.market_breadth.limit_down_count ?? '—' }}</span>
                    </div>
                    <div class="stat-label">涨停 / 跌停</div>
                  </div>
                  <div class="stat-item">
                    <div class="stat-main">{{ quickAnalysis?.market_breadth.total_amount_yi?.toFixed(0) ?? '—' }}亿</div>
                    <div class="stat-label">成交额</div>
                  </div>
                  <div class="stat-item">
                    <t-skeleton v-if="overviewStore.analysisLoading && !quickAnalysis" theme="text" :row-col="[{ width: '80px' }]" />
                    <t-tag 
                      v-else
                      :theme="quickAnalysis?.sentiment.score && quickAnalysis?.sentiment.score > 50 ? 'success' : quickAnalysis?.sentiment.score && quickAnalysis?.sentiment.score < 40 ? 'danger' : 'warning'" 
                      size="medium"
                      variant="light"
                    >
                      {{ sentimentLabel }}
                    </t-tag>
                    <div class="stat-label">市场情绪</div>
                  </div>
                </div>
                <div class="market-summary">
                  <t-skeleton v-if="overviewStore.analysisLoading && !quickAnalysis" theme="text" :row-col="[{ width: '90%' }, { width: '80%' }]" />
                  <p v-else>{{ quickAnalysis?.market_summary || '暂无分析结论' }}</p>
                </div>
              </t-card>
            </t-col>

            <!-- Sector Heatmap -->
            <t-col :span="5">
              <t-card title="板块热力图" size="small" :bordered="false" class="overview-card heatmap-card">
                <SectorHeatmap :max-items="24" @select="handleSectorSelect" />
              </t-card>
            </t-col>

            <!-- Hot Stocks (热门股票) -->
            <t-col :span="2.5">
              <t-card size="small" :bordered="false" class="overview-card toplist-card">
                <template #title>
                  <span>热门股票</span>
                  <t-tag size="small" theme="primary" variant="light" style="margin-left: 8px">成交额</t-tag>
                </template>
                <div class="hot-list">
                  <div 
                    v-for="(item, index) in hotStocksData" 
                    :key="item.ts_code" 
                    class="list-item"
                  >
                    <span class="item-rank" :class="{ 'top-rank': index < 3 }">{{ index + 1 }}</span>
                    <span class="item-name">{{ item.name }}</span>
                    <span :class="['item-value', getPctClass(item.pct_chg)]">
                      {{ item.pct_chg !== undefined ? (item.pct_chg > 0 ? '+' : '') + formatNumber(item.pct_chg) + '%' : '-' }}
                    </span>
                  </div>
                  <div v-if="hotStocksData.length === 0 && !hotStocksLoading" class="empty-list">
                    暂无数据
                  </div>
                  <t-loading v-if="hotStocksLoading && hotStocksData.length === 0" size="small" />
                </div>
              </t-card>
            </t-col>

            <!-- Hot ETFs -->
            <t-col :span="2.5">
              <t-card title="热门ETF" size="small" :bordered="false" class="overview-card etf-card">
                <div class="hot-list">
                  <div 
                    v-for="(etf, index) in hotEtfs" 
                    :key="etf.ts_code" 
                    class="list-item"
                  >
                    <span class="item-rank" :class="{ 'top-rank': index < 3 }">{{ index + 1 }}</span>
                    <span class="item-name">{{ etf.name || etf.ts_code }}</span>
                    <span :class="['item-value', getPctClass(etf.pct_chg)]">
                      {{ etf.pct_chg !== undefined ? (etf.pct_chg > 0 ? '+' : '') + formatNumber(etf.pct_chg) + '%' : '-' }}
                    </span>
                  </div>
                  <div v-if="hotEtfs.length === 0 && !hotEtfLoading" class="empty-list">
                    暂无数据
                  </div>
                </div>
              </t-card>
            </t-col>
          </t-row>
        </div>

        <!-- Main Content: Two columns (板块排行 | 指数对比) -->
        <div class="main-section">
          <t-row :gutter="16">
            <!-- Sector Ranking -->
            <t-col :span="7">
              <t-card title="板块涨跌排行" size="small" :bordered="false" class="main-card">
                <SectorRankingTable @select="handleSectorSelect" />
              </t-card>
            </t-col>

            <!-- Index Compare -->
            <t-col :span="5">
              <t-card title="指数走势对比" size="small" :bordered="false" class="main-card">
                <IndexCompareChart />
              </t-card>
            </t-col>
          </t-row>
        </div>
        </template>
      </t-tab-panel>

    </t-tabs>

    <!-- Sector Detail Dialog -->
    <SectorDetailDialog
      v-model:visible="sectorDialogVisible"
      :ts-code="selectedSectorCode"
      :name="selectedSectorName"
    />

    <!-- AI Float Button & Dialog -->
    <MarketAiFloatButton @click="handleAiClick" />
    <MarketAiDialog v-model:visible="aiDialogVisible" />
  </div>
</template>

<style scoped>
.market-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px;
  background: #e4e7ed;
}

.market-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.market-tabs :deep(.t-tabs__content) {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 16px;
  overflow-y: auto;
}

/* Indices Section */
.indices-section {
  flex-shrink: 0;
}

.indices-row {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding: 4px;
}

.indices-row.loading {
  justify-content: center;
  padding: 20px;
}

.index-card {
  flex: 1;
  min-width: 120px;
  max-width: 160px;
  padding: 16px;
  background: #ffffff;
  border-radius: 8px;
  text-align: center;
  transition: all 0.2s;
  border: 1px solid #e8e8e8;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.index-card:hover {
  box-shadow: var(--td-shadow-2);
  transform: translateY(-2px);
}

.index-card.text-up {
  border-bottom: 3px solid var(--td-error-color);
}

.index-card.text-down {
  border-bottom: 3px solid var(--td-success-color);
}

.index-name {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  margin-bottom: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.index-price {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 4px;
}

.index-change {
  font-size: 14px;
  font-weight: 500;
}

/* Overview Section */
.overview-section {
  flex-shrink: 0;
}

.overview-card {
  min-height: 260px;
  height: auto;
  background: #ffffff;
  border: 1px solid #e8e8e8;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.overview-card :deep(.t-card__body) {
  padding-top: 8px;
}

.heatmap-card :deep(.t-card__body) {
  padding: 8px;
}

.etf-card :deep(.t-card__body) {
  overflow-y: auto;
}

/* Market Stats */
.market-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.market-summary {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--td-component-stroke);
  color: var(--td-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.market-summary p {
  margin: 0;
}

.stat-item {
  text-align: center;
}

.stat-main {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 4px;
}

.stat-divider {
  color: var(--td-text-color-placeholder);
  margin: 0 4px;
}

.stat-label {
  font-size: 11px;
  color: var(--td-text-color-secondary);
  margin-top: 4px;
}

.empty-sentiment {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

/* Hot ETF List */
.hot-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 100%;
}

.list-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px solid var(--td-component-stroke);
}

.list-item:last-child {
  border-bottom: none;
}

.item-rank {
  width: 16px;
  height: 16px;
  border-radius: 3px;
  background: var(--td-bg-color-component);
  color: var(--td-text-color-secondary);
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.item-rank.top-rank {
  background: var(--td-brand-color);
  color: white;
}

.item-name {
  flex: 1;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-value {
  font-size: 12px;
  font-weight: 500;
  flex-shrink: 0;
}

.toplist-card :deep(.t-card__body) {
  overflow-y: auto;
}

.empty-list {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--td-text-color-placeholder);
  font-size: 12px;
}

/* Main Section */
.main-section {
  flex: 1;
  min-height: 0;
}

.main-card {
  height: 100%;
  min-height: 360px;
  background: #ffffff;
  border: 1px solid #e8e8e8;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.main-card :deep(.t-card__body) {
  min-height: 320px;
  overflow: auto;
}

/* Common */
.text-up {
  color: var(--td-error-color);
}

.text-down {
  color: var(--td-success-color);
}
</style>
