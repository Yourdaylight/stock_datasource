<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { useScreenerStore } from '@/stores/screener'
import { usePortfolioStore } from '@/stores/portfolio'
import StockDetailDialog from '@/components/StockDetailDialog.vue'
import type { ScreenerCondition } from '@/api/screener'

const screenerStore = useScreenerStore()
const portfolioStore = usePortfolioStore()
const nlQuery = ref('')
const activeTab = ref('condition')
const searchInput = ref('')

// Stock detail dialog
const showDetailDialog = ref(false)
const selectedStockCode = ref('')

const presetStrategies = [
  { id: 'low_pe', name: '低估值策略', description: 'PE < 15, PB < 2' },
  { id: 'high_turnover', name: '活跃股策略', description: '换手率 > 5%' },
  { id: 'large_cap', name: '大盘股策略', description: '总市值 > 1000亿' },
  { id: 'strong_momentum', name: '强势股策略', description: '涨幅 > 5%' }
]

const conditions = ref<ScreenerCondition[]>([
  { field: 'pe', operator: 'lt', value: 30 }
])

const fieldOptions = [
  { value: 'pe', label: 'PE (市盈率)' },
  { value: 'pb', label: 'PB (市净率)' },
  { value: 'turnover_rate', label: '换手率 (%)' },
  { value: 'pct_chg', label: '涨跌幅 (%)' },
  { value: 'close', label: '收盘价' },
  { value: 'total_mv', label: '总市值 (万元)' },
  { value: 'vol', label: '成交量 (手)' },
  { value: 'amount', label: '成交额 (千元)' }
]

const operatorOptions = [
  { value: 'gt', label: '>' },
  { value: 'gte', label: '>=' },
  { value: 'lt', label: '<' },
  { value: 'lte', label: '<=' },
  { value: 'eq', label: '=' }
]

const addCondition = () => {
  conditions.value.push({ field: 'pe', operator: 'lt', value: 0 })
}

const removeCondition = (index: number) => {
  conditions.value.splice(index, 1)
}

const handleFilter = () => {
  screenerStore.filter(conditions.value)
}

const handleNLScreener = () => {
  if (nlQuery.value.trim()) {
    screenerStore.nlScreener(nlQuery.value)
  }
}

const handlePreset = (id: string) => {
  screenerStore.applyPreset(id)
}

const handleSearch = () => {
  screenerStore.search(searchInput.value)
}

const handleClearFilters = () => {
  conditions.value = [{ field: 'pe', operator: 'lt', value: 30 }]
  searchInput.value = ''
  screenerStore.clearFilters()
}

const handlePageChange = (current: number) => {
  screenerStore.changePage(current)
}

const handlePageSizeChange = (size: number) => {
  screenerStore.changePageSize(size)
}

const handleSortChange = (sortInfo: { sortBy: string; descending: boolean }) => {
  screenerStore.changeSort(sortInfo.sortBy, sortInfo.descending ? 'desc' : 'asc')
}

const handleViewDetail = (stockCode: string) => {
  selectedStockCode.value = stockCode
  showDetailDialog.value = true
}

const handleAddToWatchlist = async (row: any) => {
  try {
    // Use close price, or fallback to a reasonable default
    const costPrice = row.close || row.current_price || 10.0
    
    await portfolioStore.addPosition({
      ts_code: row.ts_code,
      quantity: 100, // Default quantity
      cost_price: costPrice,
      buy_date: new Date().toISOString().split('T')[0],
      notes: `从智能选股添加 - ${row.ts_code}`
    })
    
    MessagePlugin.success(`已将 ${row.ts_code} 添加到自选股`)
  } catch (error) {
    console.error('Failed to add to watchlist:', error)
    MessagePlugin.error(`添加自选股失败: ${error.message || error}`)
  }
}

const handleDetailDialogClose = () => {
  showDetailDialog.value = false
  selectedStockCode.value = ''
}

// Format market value to billions
const formatMarketValue = (val: number | undefined) => {
  if (!val) return '-'
  return (val / 10000).toFixed(2) + '亿'
}

// Format volume to 10k
const formatVolume = (val: number | undefined) => {
  if (!val) return '-'
  return (val / 10000).toFixed(2) + '万手'
}

// Pagination config
const pagination = computed(() => ({
  current: screenerStore.page,
  pageSize: screenerStore.pageSize,
  total: screenerStore.total,
  showJumper: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50, 100],
}))

const columns = [
  { colKey: 'ts_code', title: '代码', width: 110, sortable: true },
  { colKey: 'trade_date', title: '日期', width: 100 },
  { colKey: 'close', title: '收盘价', width: 90, sortable: true },
  { colKey: 'pct_chg', title: '涨跌幅', width: 90, sortable: true },
  { colKey: 'pe_ttm', title: 'PE', width: 80, sortable: true },
  { colKey: 'pb', title: 'PB', width: 70, sortable: true },
  { colKey: 'total_mv', title: '总市值', width: 100, sortable: true },
  { colKey: 'turnover_rate', title: '换手率', width: 80, sortable: true },
  { colKey: 'vol', title: '成交量', width: 100 },
  { colKey: 'operation', title: '操作', width: 100, fixed: 'right' }
]

// Load data on mount
onMounted(() => {
  screenerStore.fetchStocks()
  screenerStore.fetchSummary()
})
</script>

<template>
  <div class="screener-view">
    <!-- Market Summary -->
    <t-card v-if="screenerStore.summary" class="summary-card" :bordered="false">
      <t-row :gutter="16">
        <t-col :span="2">
          <div class="summary-item">
            <div class="summary-label">交易日期</div>
            <div class="summary-value">{{ screenerStore.summary.trade_date }}</div>
          </div>
        </t-col>
        <t-col :span="2">
          <div class="summary-item">
            <div class="summary-label">股票总数</div>
            <div class="summary-value">{{ screenerStore.summary.total_stocks }}</div>
          </div>
        </t-col>
        <t-col :span="2">
          <div class="summary-item">
            <div class="summary-label up">上涨</div>
            <div class="summary-value up">{{ screenerStore.summary.up_count }}</div>
          </div>
        </t-col>
        <t-col :span="2">
          <div class="summary-item">
            <div class="summary-label down">下跌</div>
            <div class="summary-value down">{{ screenerStore.summary.down_count }}</div>
          </div>
        </t-col>
        <t-col :span="2">
          <div class="summary-item">
            <div class="summary-label up">涨停</div>
            <div class="summary-value up">{{ screenerStore.summary.limit_up }}</div>
          </div>
        </t-col>
        <t-col :span="2">
          <div class="summary-item">
            <div class="summary-label down">跌停</div>
            <div class="summary-value down">{{ screenerStore.summary.limit_down }}</div>
          </div>
        </t-col>
      </t-row>
    </t-card>

    <t-row :gutter="16" style="margin-top: 16px">
      <t-col :span="4">
        <t-card title="筛选条件">
          <t-tabs v-model="activeTab">
            <t-tab-panel value="condition" label="条件筛选">
              <div class="condition-list">
                <div
                  v-for="(cond, index) in conditions"
                  :key="index"
                  class="condition-item"
                >
                  <t-select v-model="cond.field" :options="fieldOptions" style="width: 120px" />
                  <t-select v-model="cond.operator" :options="operatorOptions" style="width: 70px" />
                  <t-input-number v-model="cond.value" style="width: 100px" />
                  <t-button
                    theme="danger"
                    variant="text"
                    shape="circle"
                    @click="removeCondition(index)"
                  >
                    <template #icon><t-icon name="delete" /></template>
                  </t-button>
                </div>
                
                <t-button variant="dashed" block @click="addCondition">
                  <template #icon><t-icon name="add" /></template>
                  添加条件
                </t-button>
                
                <t-space style="margin-top: 16px; width: 100%">
                  <t-button theme="primary" @click="handleFilter">
                    开始筛选
                  </t-button>
                  <t-button variant="outline" @click="handleClearFilters">
                    清除筛选
                  </t-button>
                </t-space>
              </div>
            </t-tab-panel>
            
            <t-tab-panel value="nl" label="自然语言">
              <t-textarea
                v-model="nlQuery"
                placeholder="例如：找出市盈率低于20，换手率超过5%的股票"
                :autosize="{ minRows: 3, maxRows: 6 }"
              />
              <t-button theme="primary" block style="margin-top: 16px" @click="handleNLScreener">
                智能选股
              </t-button>
            </t-tab-panel>
          </t-tabs>
          
          <t-divider>预设策略</t-divider>
          
          <div class="preset-list">
            <t-tag
              v-for="preset in presetStrategies"
              :key="preset.id"
              theme="primary"
              variant="light"
              class="preset-tag"
              @click="handlePreset(preset.id)"
            >
              {{ preset.name }}
            </t-tag>
          </div>
        </t-card>
      </t-col>
      
      <t-col :span="8">
        <t-card title="股票列表">
          <template #actions>
            <t-space>
              <t-input
                v-model="searchInput"
                placeholder="搜索股票代码"
                style="width: 200px"
                @enter="handleSearch"
              >
                <template #suffix-icon>
                  <t-icon name="search" @click="handleSearch" style="cursor: pointer" />
                </template>
              </t-input>
              <span class="result-count">共 {{ screenerStore.total }} 只股票</span>
            </t-space>
          </template>
          
          <t-table
            :data="screenerStore.stocks"
            :columns="columns"
            :loading="screenerStore.loading"
            row-key="ts_code"
            :pagination="pagination"
            max-height="calc(100vh - 350px)"
            @page-change="handlePageChange"
            @sort-change="handleSortChange"
          >
            <template #close="{ row }">
              {{ row.close?.toFixed(2) || '-' }}
            </template>
            <template #pct_chg="{ row }">
              <span :style="{ color: (row.pct_chg || 0) >= 0 ? '#e34d59' : '#00a870' }">
                {{ row.pct_chg?.toFixed(2) || '0.00' }}%
              </span>
            </template>
            <template #pe_ttm="{ row }">
              {{ row.pe_ttm?.toFixed(2) || '-' }}
            </template>
            <template #pb="{ row }">
              {{ row.pb?.toFixed(2) || '-' }}
            </template>
            <template #total_mv="{ row }">
              {{ formatMarketValue(row.total_mv) }}
            </template>
            <template #turnover_rate="{ row }">
              {{ row.turnover_rate?.toFixed(2) || '-' }}%
            </template>
            <template #vol="{ row }">
              {{ formatVolume(row.vol) }}
            </template>
            <template #operation="{ row }">
              <t-space>
                <t-link theme="primary" @click="handleViewDetail(row.ts_code)">详情</t-link>
                <t-link 
                  theme="primary" 
                  :loading="portfolioStore.loading"
                  @click="handleAddToWatchlist(row)"
                >
                  加自选
                </t-link>
              </t-space>
            </template>
          </t-table>
          
          <!-- Pagination -->
          <div class="pagination-wrapper">
            <t-pagination
              :current="screenerStore.page"
              :page-size="screenerStore.pageSize"
              :total="screenerStore.total"
              :page-size-options="[10, 20, 50, 100]"
              show-jumper
              @current-change="handlePageChange"
              @page-size-change="handlePageSizeChange"
            />
          </div>
        </t-card>
      </t-col>
    </t-row>
    
    <!-- Stock Detail Dialog -->
    <StockDetailDialog
      v-model:visible="showDetailDialog"
      :stock-code="selectedStockCode"
      @close="handleDetailDialogClose"
    />
  </div>
</template>

<style scoped>
.screener-view {
  height: 100%;
}

.summary-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.summary-item {
  text-align: center;
}

.summary-label {
  font-size: 12px;
  opacity: 0.8;
}

.summary-label.up {
  color: #ff6b6b;
}

.summary-label.down {
  color: #51cf66;
}

.summary-value {
  font-size: 20px;
  font-weight: bold;
  margin-top: 4px;
}

.summary-value.up {
  color: #ff6b6b;
}

.summary-value.down {
  color: #51cf66;
}

.condition-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.condition-item {
  display: flex;
  gap: 8px;
  align-items: center;
}

.preset-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.preset-tag {
  cursor: pointer;
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
