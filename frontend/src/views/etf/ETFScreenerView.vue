<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { useETFStore } from '@/stores/etf'
import ETFDetailDialog from './components/ETFDetailDialog.vue'
import ETFAnalysisPanel from './components/ETFAnalysisPanel.vue'

const etfStore = useETFStore()
const searchInput = ref('')

// Dialog state
const showDetailDialog = ref(false)
const selectedIndexCode = ref('')

// Analysis panel state
const showAnalysisPanel = ref(false)
const analysisIndexCode = ref('')
const analysisIndexName = ref('')

// Common indices for quick access
const commonIndices = [
  { code: '000300.SH', name: '沪深300' },
  { code: '000905.SH', name: '中证500' },
  { code: '000016.SH', name: '上证50' },
  { code: '399006.SZ', name: '创业板指' },
  { code: '000852.SH', name: '中证1000' },
  { code: '000001.SH', name: '上证指数' },
]

// Table columns
const columns = [
  { colKey: 'ts_code', title: '代码', width: 110 },
  { colKey: 'name', title: '名称', width: 150 },
  { colKey: 'market', title: '市场', width: 80 },
  { colKey: 'category', title: '类别', width: 100 },
  { colKey: 'publisher', title: '发布方', width: 100 },
  { colKey: 'weight_rule', title: '加权方式', width: 120 },
  { colKey: 'list_date', title: '发布日期', width: 100 },
  { colKey: 'operation', title: '操作', width: 150, fixed: 'right' }
]

// Market options for filter
const marketOptions = computed(() => [
  { value: '', label: '全部市场' },
  ...etfStore.markets.map(m => ({ value: m.market, label: `${m.market} (${m.count})` }))
])

// Category options for filter
const categoryOptions = computed(() => [
  { value: '', label: '全部类别' },
  ...etfStore.categories.map(c => ({ value: c.category, label: `${c.category} (${c.count})` }))
])

// Pagination
const pagination = computed(() => ({
  current: etfStore.page,
  pageSize: etfStore.pageSize,
  total: etfStore.total,
  showJumper: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50, 100],
}))

// Handlers
const handleSearch = () => {
  etfStore.setKeyword(searchInput.value)
}

const handleMarketChange = (value: string) => {
  etfStore.setMarket(value)
}

const handleCategoryChange = (value: string) => {
  etfStore.setCategory(value)
}

const handlePageChange = (current: number) => {
  etfStore.changePage(current)
}

const handlePageSizeChange = (size: number) => {
  etfStore.changePageSize(size)
}

const handleClearFilters = () => {
  searchInput.value = ''
  etfStore.clearFilters()
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
  etfStore.clearAnalysis()
}

// Load data on mount
onMounted(() => {
  etfStore.fetchIndices()
  etfStore.fetchMarkets()
  etfStore.fetchCategories()
})
</script>

<template>
  <div class="etf-screener-view">
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
              <div class="filter-label">市场</div>
              <t-select
                :value="etfStore.selectedMarket"
                :options="marketOptions"
                placeholder="选择市场"
                clearable
                @change="handleMarketChange"
              />
            </div>
            
            <div class="filter-item">
              <div class="filter-label">类别</div>
              <t-select
                :value="etfStore.selectedCategory"
                :options="categoryOptions"
                placeholder="选择类别"
                clearable
                @change="handleCategoryChange"
              />
            </div>
            
            <div class="filter-item">
              <div class="filter-label">搜索</div>
              <t-input
                v-model="searchInput"
                placeholder="输入指数名称"
                clearable
                @enter="handleSearch"
              >
                <template #suffix-icon>
                  <t-icon name="search" @click="handleSearch" style="cursor: pointer" />
                </template>
              </t-input>
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
            <span class="result-count">共 {{ etfStore.total }} 个指数</span>
          </template>
          
          <t-table
            :data="etfStore.indices"
            :columns="columns"
            :loading="etfStore.loading"
            row-key="ts_code"
            max-height="calc(100vh - 300px)"
          >
            <template #ts_code="{ row }">
              <t-link theme="primary" @click="handleViewDetail(row)">
                {{ row.ts_code }}
              </t-link>
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
              :current="etfStore.page"
              :page-size="etfStore.pageSize"
              :total="etfStore.total"
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
    <ETFDetailDialog
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
      <ETFAnalysisPanel
        v-if="showAnalysisPanel"
        :index-code="analysisIndexCode"
        :index-name="analysisIndexName"
      />
    </t-drawer>
  </div>
</template>

<style scoped>
.etf-screener-view {
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
