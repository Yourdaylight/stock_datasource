<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { useEtfStore } from '@/stores/etf'
import EtfDetailDialog from './components/EtfDetailDialog.vue'
import EtfAnalysisPanel from './components/EtfAnalysisPanel.vue'

const etfStore = useEtfStore()
const searchInput = ref('')

// Dialog state
const showDetailDialog = ref(false)
const selectedEtfCode = ref('')

// Analysis panel state
const showAnalysisPanel = ref(false)
const analysisEtfCode = ref('')
const analysisEtfName = ref('')

// Common ETFs for quick access
const commonEtfs = [
  { code: '510300.SH', name: '沪深300ETF' },
  { code: '510500.SH', name: '中证500ETF' },
  { code: '510050.SH', name: '上证50ETF' },
  { code: '159915.SZ', name: '创业板ETF' },
  { code: '588000.SH', name: '科创50ETF' },
  { code: '518880.SH', name: '黄金ETF' },
]

// Table columns
const columns = [
  { colKey: 'ts_code', title: '代码', width: 110 },
  { colKey: 'csname', title: '名称', width: 160 },
  { colKey: 'index_name', title: '跟踪指数', width: 160, ellipsis: true },
  { colKey: 'trade_date', title: '日期', width: 100 },
  { colKey: 'close', title: '收盘价', width: 90 },
  { colKey: 'pct_chg', title: '涨跌幅', width: 90 },
  { colKey: 'vol', title: '成交量', width: 100 },
  { colKey: 'amount', title: '成交额', width: 110 },
  { colKey: 'exchange', title: '交易所', width: 80 },
  { colKey: 'etf_type', title: '基金类型', width: 100 },
  { colKey: 'mgr_name', title: '管理人', width: 140, ellipsis: true },
  { colKey: 'mgt_fee', title: '管理费率', width: 90 },
  { colKey: 'list_date', title: '上市日期', width: 100 },
  { colKey: 'list_status', title: '状态', width: 70 },
  { colKey: 'operation', title: '操作', width: 150, fixed: 'right' }
]

// Exchange options for filter
const exchangeOptions = computed(() => [
  { value: '', label: '全部交易所' },
  ...etfStore.exchanges.map(e => ({ value: e.value, label: `${e.label} (${e.count})` }))
])

// Type options for filter
const typeOptions = computed(() => [
  { value: '', label: '全部类型' },
  ...etfStore.types.map(t => ({ value: t.value, label: `${t.label} (${t.count})` }))
])

// Invest type options for filter
const investTypeOptions = computed(() => [
  { value: '', label: '全部投资类型' },
  ...etfStore.investTypes.map(t => ({ value: t.value, label: `${t.label} (${t.count})` }))
])

// Status options
const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'L', label: '上市' },
  { value: 'D', label: '退市' },
  { value: 'I', label: '发行' },
]

// Handlers
const handleSearch = () => {
  etfStore.setKeyword(searchInput.value)
}

const handleExchangeChange = (value: string) => {
  etfStore.setExchange(value)
}

const handleTypeChange = (value: string) => {
  etfStore.setType(value)
}

const handleInvestTypeChange = (value: string) => {
  etfStore.setInvestType(value)
}

const handleStatusChange = (value: string) => {
  etfStore.setStatus(value)
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
  selectedEtfCode.value = row.ts_code
  showDetailDialog.value = true
}

const handleAnalyze = (row: any) => {
  analysisEtfCode.value = row.ts_code
  analysisEtfName.value = row.csname || row.ts_code
  showAnalysisPanel.value = true
}

const handleQuickAnalyze = (code: string, name: string) => {
  analysisEtfCode.value = code
  analysisEtfName.value = name
  showAnalysisPanel.value = true
}

const handleDetailDialogClose = () => {
  showDetailDialog.value = false
  selectedEtfCode.value = ''
}

const handleAnalysisPanelClose = () => {
  showAnalysisPanel.value = false
  etfStore.clearAnalysis()
}

const getMarketLabel = (market?: string) => {
  const map: Record<string, string> = {
    'E': '上交所',
    'Z': '深交所',
    'SH': '上交所',
    'SZ': '深交所',
  }
  return market ? map[market] || market : '-'
}

const getStatusLabel = (status?: string) => {
  const map: Record<string, string> = {
    'L': '上市',
    'D': '退市',
    'P': '待上市',
    'I': '发行',
  }
  return status ? map[status] || status : '-'
}

const getStatusTheme = (status?: string) => {
  const map: Record<string, string> = {
    'L': 'success',
    'D': 'default',
    'P': 'warning',
    'I': 'warning',
  }
  return status ? map[status] || 'default' : 'default'
}

const formatVolume = (val?: number) => {
  if (!val) return '-'
  return (val / 10000).toFixed(2) + '万手'
}

const formatAmount = (val?: number) => {
  if (!val) return '-'
  return (val / 10000).toFixed(2) + '万'
}

// Load data on mount
onMounted(() => {
  etfStore.fetchEtfs()
  etfStore.fetchExchanges()
  etfStore.fetchTypes()
  etfStore.fetchInvestTypes()
})
</script>

<template>
  <div class="etf-screener-view">
    <!-- Quick Access Panel -->
    <t-card class="quick-access-card" :bordered="false">
      <div class="quick-access-header">
        <span class="quick-access-title">常用ETF</span>
        <span class="quick-access-hint">点击快速分析</span>
      </div>
      <div class="quick-access-list">
        <t-tag
          v-for="etf in commonEtfs"
          :key="etf.code"
          theme="primary"
          variant="light"
          class="quick-access-tag"
          @click="handleQuickAnalyze(etf.code, etf.name)"
        >
          {{ etf.name }}
        </t-tag>
      </div>
    </t-card>

    <t-row :gutter="16" style="margin-top: 16px">
      <!-- Filter Panel -->
      <t-col :span="3">
        <t-card title="筛选条件">
          <div class="filter-section">
            <div class="filter-item">
              <div class="filter-label">交易所</div>
              <t-select
                :value="etfStore.selectedExchange"
                :options="exchangeOptions"
                placeholder="选择交易所"
                clearable
                @change="handleExchangeChange"
              />
            </div>
            
            <div class="filter-item">
              <div class="filter-label">基金类型</div>
              <t-select
                :value="etfStore.selectedType"
                :options="typeOptions"
                placeholder="选择类型"
                clearable
                @change="handleTypeChange"
              />
            </div>
            
            <div class="filter-item">
              <div class="filter-label">投资类型</div>
              <t-select
                :value="etfStore.selectedInvestType"
                :options="investTypeOptions"
                placeholder="选择投资类型"
                clearable
                @change="handleInvestTypeChange"
              />
            </div>
            
            <div class="filter-item">
              <div class="filter-label">状态</div>
              <t-select
                :value="etfStore.selectedStatus"
                :options="statusOptions"
                placeholder="选择状态"
                clearable
                @change="handleStatusChange"
              />
            </div>
            
            <div class="filter-item">
              <div class="filter-label">搜索</div>
              <t-input
                v-model="searchInput"
                placeholder="输入ETF名称或代码"
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
      
      <!-- ETF List -->
      <t-col :span="9">
        <t-card title="ETF列表">
          <template #actions>
            <span class="result-count">共 {{ etfStore.total }} 只ETF</span>
          </template>
          
          <t-table
            :data="etfStore.etfs"
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
            <template #exchange="{ row }">
              {{ getMarketLabel(row.exchange) }}
            </template>
            <template #mgt_fee="{ row }">
              {{ row.mgt_fee ? (row.mgt_fee * 100).toFixed(2) + '%' : '-' }}
            </template>
            <template #list_status="{ row }">
              <t-tag :theme="getStatusTheme(row.list_status)" size="small">
                {{ getStatusLabel(row.list_status) }}
              </t-tag>
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
    <EtfDetailDialog
      v-model:visible="showDetailDialog"
      :etf-code="selectedEtfCode"
      @close="handleDetailDialogClose"
      @analyze="handleAnalyze"
    />
    
    <!-- Analysis Panel (Drawer) -->
    <t-drawer
      v-model:visible="showAnalysisPanel"
      :header="`${analysisEtfName} 量化分析`"
      size="600px"
      :close-on-overlay-click="true"
      @close="handleAnalysisPanelClose"
    >
      <EtfAnalysisPanel
        v-if="showAnalysisPanel"
        :etf-code="analysisEtfCode"
        :etf-name="analysisEtfName"
      />
    </t-drawer>
  </div>
</template>

<style scoped>
.etf-screener-view {
  height: 100%;
}

.quick-access-card {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
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
