<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { useIndexStore } from '@/stores/index'
import IndexDetailDialog from './components/IndexDetailDialog.vue'
import IndexAnalysisPanel from './components/IndexAnalysisPanel.vue'
import DataUpdateDialog from '@/components/DataUpdateDialog.vue'

const indexStore = useIndexStore()
const searchInput = ref('')

// Dialog state
const showDetailDialog = ref(false)
const selectedIndexCode = ref('')

// Analysis panel state
const showAnalysisPanel = ref(false)
const analysisIndexCode = ref('')
const analysisIndexName = ref('')

// Data update dialog state
const showDataUpdateDialog = ref(false)
const noDataDate = ref('')

// Common indices for quick access
const commonIndices = [
  { code: '000300.SH', name: '沪深300' },
  { code: '000905.SH', name: '中证500' },
  { code: '000016.SH', name: '上证50' },
  { code: '399006.SZ', name: '创业板指' },
  { code: '000852.SH', name: '中证1000' },
  { code: '000001.SH', name: '上证指数' },
]

// Table columns with daily data
const columns = [
  { colKey: 'ts_code', title: '代码', width: 110 },
  { colKey: 'name', title: '名称', width: 150 },
  { colKey: 'trade_date', title: '日期', width: 100 },
  { colKey: 'close', title: '收盘点位', width: 100 },
  { colKey: 'pct_chg', title: '涨跌幅', width: 90 },
  { colKey: 'vol', title: '成交量', width: 100 },
  { colKey: 'amount', title: '成交额', width: 110 },
  { colKey: 'market', title: '市场', width: 80 },
  { colKey: 'category', title: '类别', width: 100 },
  { colKey: 'publisher', title: '发布方', width: 100 },
  { colKey: 'list_date', title: '发布日期', width: 100 },
  { colKey: 'operation', title: '操作', width: 150, fixed: 'right' }
]

// Market options for filter
const marketOptions = computed(() => [
  { value: '', label: '全部市场' },
  ...indexStore.markets.map(m => ({ value: m.market, label: `${m.market} (${m.count})` }))
])

// Category options for filter
const categoryOptions = computed(() => [
  { value: '', label: '全部类别' },
  ...indexStore.categories.map(c => ({ value: c.category, label: `${c.category} (${c.count})` }))
])

// Publisher options for filter
const publisherOptions = computed(() => [
  { value: '', label: '全部发布方' },
  ...indexStore.publishers.map(p => ({ value: p.value, label: `${p.label} (${p.count})` }))
])

// Date options for filter
const dateOptions = computed(() => {
  return indexStore.tradeDates.map(d => ({
    value: d,
    label: formatDateDisplay(d)
  }))
})

// Pct change range options
const pctChgRangeOptions = [
  { value: '', label: '全部涨跌' },
  { value: 'up', label: '上涨' },
  { value: 'down', label: '下跌' },
  { value: 'up1+', label: '涨幅>1%' },
  { value: 'up2+', label: '涨幅>2%' },
  { value: 'down1+', label: '跌幅>1%' },
  { value: 'down2+', label: '跌幅>2%' },
]

// Format date for display (handles both YYYYMMDD and YYYY-MM-DD)
const formatDateDisplay = (date: string) => {
  if (!date) return date
  // Already has dashes (YYYY-MM-DD format)
  if (date.includes('-')) return date
  // YYYYMMDD format -> YYYY-MM-DD
  if (date.length === 8) {
    return `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`
  }
  return date
}

// Pagination
const pagination = computed(() => ({
  current: indexStore.page,
  pageSize: indexStore.pageSize,
  total: indexStore.total,
  showJumper: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50, 100],
}))

// Handlers
const handleSearch = () => {
  indexStore.setKeyword(searchInput.value)
}

const handleMarketChange = (value: string) => {
  indexStore.setMarket(value)
}

const handleCategoryChange = (value: string) => {
  indexStore.setCategory(value)
}

const handleDateChange = async (value: string) => {
  await indexStore.setDate(value)
  // Check if no data for this date
  if (indexStore.total === 0 && value) {
    noDataDate.value = value
    showDataUpdateDialog.value = true
  }
}

const handlePublisherChange = (value: string) => {
  indexStore.setPublisher(value)
}

const handlePctChgRangeChange = (value: string) => {
  indexStore.setPctChgRange(value)
}

const handlePageChange = (current: number) => {
  indexStore.changePage(current)
}

const handlePageSizeChange = (size: number) => {
  indexStore.changePageSize(size)
}

const handleClearFilters = () => {
  searchInput.value = ''
  indexStore.clearFilters()
}

const handleViewDetail = (row: any) => {
  selectedIndexCode.value = row.ts_code
  showDetailDialog.value = true
}

const handleAnalyze = (row: any) => {
  analysisIndexCode.value = row.ts_code
  analysisIndexName.value = row.name || row.ts_code
  showAnalysisPanel.value = true
}

const handleQuickAnalyze = (code: string, name: string) => {
  analysisIndexCode.value = code
  analysisIndexName.value = name
  showAnalysisPanel.value = true
}

const handleDetailDialogClose = () => {
  showDetailDialog.value = false
  selectedIndexCode.value = ''
}

const handleAnalysisPanelClose = () => {
  showAnalysisPanel.value = false
  indexStore.clearAnalysis()
}

// Load data on mount
onMounted(() => {
  indexStore.fetchTradeDates()
  indexStore.fetchIndices()
  indexStore.fetchMarkets()
  indexStore.fetchCategories()
  indexStore.fetchPublishers()
})

// Watch for no data scenario when date changes
watch(() => indexStore.total, (newTotal) => {
  if (newTotal === 0 && indexStore.selectedDate && !indexStore.loading) {
    noDataDate.value = indexStore.selectedDate
    showDataUpdateDialog.value = true
  }
})

// Format helpers for table display
const formatVolume = (val?: number) => {
  if (!val) return '-'
  return (val / 10000).toFixed(2) + '万手'
}

const formatAmount = (val?: number) => {
  if (!val) return '-'
  return (val / 10000).toFixed(2) + '万'
}
</script>

<template>
  <div class="index-screener-view">
    <!-- Quick Access Panel -->
    <t-card class="quick-access-card" :bordered="false">
      <div class="quick-access-header">
        <span class="quick-access-title">常用指数</span>
        <span class="quick-access-hint">点击快速分析</span>
      </div>
      <div class="quick-access-list">
        <t-tag
          v-for="idx in commonIndices"
          :key="idx.code"
          theme="primary"
          variant="light"
          class="quick-access-tag"
          @click="handleQuickAnalyze(idx.code, idx.name)"
        >
          {{ idx.name }}
        </t-tag>
      </div>
    </t-card>

    <t-row :gutter="16" style="margin-top: 16px">
      <!-- Filter Panel -->
      <t-col :span="3">
        <t-card title="筛选条件">
          <div class="filter-section">
            <div class="filter-item">
              <div class="filter-label">交易日期</div>
              <t-date-picker
                :value="indexStore.selectedDate"
                placeholder="选择日期"
                format="YYYY-MM-DD"
                value-type="YYYYMMDD"
                :enable-time-picker="false"
                @change="handleDateChange"
              />
            </div>
            
            <div class="filter-item">
              <div class="filter-label">搜索</div>
              <t-input
                v-model="searchInput"
                placeholder="输入指数名称或代码"
                clearable
                @enter="handleSearch"
              >
                <template #suffix-icon>
                  <t-icon name="search" @click="handleSearch" style="cursor: pointer" />
                </template>
              </t-input>
            </div>
            
            <div class="filter-item">
              <div class="filter-label">市场</div>
              <t-select
                :value="indexStore.selectedMarket"
                :options="marketOptions"
                placeholder="选择市场"
                clearable
                @change="handleMarketChange"
              />
            </div>
            
            <div class="filter-item">
              <div class="filter-label">类别</div>
              <t-select
                :value="indexStore.selectedCategory"
                :options="categoryOptions"
                placeholder="选择类别"
                clearable
                @change="handleCategoryChange"
              />
            </div>
            
            <div class="filter-item">
              <div class="filter-label">发布方</div>
              <t-select
                :value="indexStore.selectedPublisher"
                :options="publisherOptions"
                placeholder="选择发布方"
                clearable
                filterable
                @change="handlePublisherChange"
              />
            </div>
            
            <div class="filter-item">
              <div class="filter-label">涨跌幅</div>
              <t-select
                :value="indexStore.selectedPctChgRange"
                :options="pctChgRangeOptions"
                placeholder="选择涨跌幅范围"
                clearable
                @change="handlePctChgRangeChange"
              />
            </div>
            
            <t-button variant="outline" block @click="handleClearFilters" style="margin-top: 16px">
              清除筛选
            </t-button>
          </div>
        </t-card>
      </t-col>
      
      <!-- Index List -->
      <t-col :span="9">
        <t-card title="指数列表">
          <template #actions>
            <span class="result-count">共 {{ indexStore.total }} 个指数</span>
          </template>
          
          <t-table
            :data="indexStore.indices"
            :columns="columns"
            :loading="indexStore.loading"
            row-key="ts_code"
            max-height="calc(100vh - 300px)"
          >
            <template #ts_code="{ row }">
              <t-link theme="primary" @click="handleViewDetail(row)">
                {{ row.ts_code }}
              </t-link>
            </template>
            <template #close="{ row }">
              {{ row.close?.toFixed(2) || '-' }}
            </template>
            <template #pct_chg="{ row }">
              <span :style="{ color: (row.pct_chg || 0) >= 0 ? '#e34d59' : '#00a870' }">
                {{ row.pct_chg?.toFixed(2) || '0.00' }}%
              </span>
            </template>
            <template #vol="{ row }">
              {{ formatVolume(row.vol) }}
            </template>
            <template #amount="{ row }">
              {{ formatAmount(row.amount) }}
            </template>
            <template #operation="{ row }">
              <t-space>
                <t-link theme="primary" @click="handleViewDetail(row)">详情</t-link>
                <t-link theme="primary" @click="handleAnalyze(row)">分析</t-link>
              </t-space>
            </template>
          </t-table>
          
          <!-- Pagination -->
          <div class="pagination-wrapper">
            <t-pagination
              :current="indexStore.page"
              :page-size="indexStore.pageSize"
              :total="indexStore.total"
              :page-size-options="[10, 20, 50, 100]"
              show-jumper
              @current-change="handlePageChange"
              @page-size-change="handlePageSizeChange"
            />
          </div>
        </t-card>
      </t-col>
    </t-row>
    
    <!-- Detail Dialog -->
    <IndexDetailDialog
      v-model:visible="showDetailDialog"
      :index-code="selectedIndexCode"
      @close="handleDetailDialogClose"
      @analyze="handleAnalyze"
    />
    
    <!-- Analysis Panel (Drawer) -->
    <t-drawer
      v-model:visible="showAnalysisPanel"
      :header="`${analysisIndexName} 量化分析`"
      size="600px"
      :close-on-overlay-click="true"
      @close="handleAnalysisPanelClose"
    >
      <IndexAnalysisPanel
        v-if="showAnalysisPanel"
        :index-code="analysisIndexCode"
        :index-name="analysisIndexName"
      />
    </t-drawer>
    
    <!-- Data Update Dialog -->
    <DataUpdateDialog
      v-model:visible="showDataUpdateDialog"
      :date="noDataDate"
      plugin-name="tushare_index_daily"
      data-type="指数"
    />
  </div>
</template>

<style scoped>
.index-screener-view {
  height: 100%;
}

.quick-access-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.quick-access-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.quick-access-title {
  font-size: 16px;
  font-weight: 600;
}

.quick-access-hint {
  font-size: 12px;
  opacity: 0.8;
}

.quick-access-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.quick-access-tag {
  cursor: pointer;
  font-size: 14px;
  padding: 4px 12px;
}

.quick-access-tag:hover {
  transform: scale(1.05);
}

.filter-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-label {
  font-size: 14px;
  color: var(--td-text-color-secondary);
}

.result-count {
  color: var(--td-text-color-secondary);
  font-size: 14px;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
