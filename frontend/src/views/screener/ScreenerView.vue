<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { useScreenerStore } from '@/stores/screener'
import { usePortfolioStore } from '@/stores/portfolio'
import StockDetailDialog from '@/components/StockDetailDialog.vue'
import ProfileCard from './components/ProfileCard.vue'
import RecommendationPanel from './components/RecommendationPanel.vue'
import SectorFilter from './components/SectorFilter.vue'
import type { ScreenerCondition } from '@/api/screener'

const screenerStore = useScreenerStore()
const portfolioStore = usePortfolioStore()
const nlQuery = ref('')
const activeTab = ref('condition')
const searchInput = ref('')
const selectedDate = ref<string | null>(null)

// 市场类型筛选
const marketType = ref<'a_share' | 'hk_stock' | 'all'>('a_share')

// Stock detail dialog
const showDetailDialog = ref(false)
const selectedStockCode = ref('')

// Profile drawer
const showProfileDrawer = ref(false)
const profileStockCode = ref('')

const presetStrategies = [
  { id: 'low_pe', name: '低估值策略', description: 'PE < 15, PB < 2' },
  { id: 'value_dividend', name: '高股息策略', description: '股息率 > 3%' },
  { id: 'high_turnover', name: '活跃股策略', description: '换手率 > 5%' },
  { id: 'large_cap', name: '大盘股策略', description: '总市值 > 1000亿' },
  { id: 'strong_momentum', name: '强势股策略', description: '涨幅 > 5%' },
  { id: 'momentum_volume', name: '放量上涨策略', description: '涨幅 > 3%, 换手率 > 3%' },
]

const conditions = ref<ScreenerCondition[]>([
  { field: 'pct_chg', operator: 'gt', value: 3 }
])

// A股支持的全部字段
const aShareFieldOptions = [
  { value: 'pe', label: 'PE (市盈率)', defaultValue: 30 },
  { value: 'pb', label: 'PB (市净率)', defaultValue: 3 },
  { value: 'ps', label: 'PS (市销率)', defaultValue: 5 },
  { value: 'dv_ratio', label: '股息率 (%)', defaultValue: 2 },
  { value: 'turnover_rate', label: '换手率 (%)', defaultValue: 5 },
  { value: 'volume_ratio', label: '量比', defaultValue: 1.5 },
  { value: 'pct_chg', label: '涨跌幅 (%)', defaultValue: 3 },
  { value: 'close', label: '收盘价', defaultValue: 50 },
  { value: 'total_mv', label: '总市值 (万元)', defaultValue: 1000000 },
  { value: 'circ_mv', label: '流通市值 (万元)', defaultValue: 500000 },
  { value: 'vol', label: '成交量 (手)', defaultValue: 100000 },
  { value: 'amount', label: '成交额 (千元)', defaultValue: 50000 },
]

// 港股支持的字段（基于 ods_hk_daily 表结构）
const hkFieldOptions = [
  { value: 'pct_chg', label: '涨跌幅 (%)', defaultValue: 3 },
  { value: 'close', label: '收盘价', defaultValue: 50 },
  { value: 'open', label: '开盘价', defaultValue: 50 },
  { value: 'high', label: '最高价', defaultValue: 50 },
  { value: 'low', label: '最低价', defaultValue: 50 },
  { value: 'vol', label: '成交量 (股)', defaultValue: 1000000 },
  { value: 'amount', label: '成交额 (元)', defaultValue: 10000000 },
]

// 根据市场类型返回可用字段
const fieldOptions = computed(() => {
  if (marketType.value === 'hk_stock') {
    return hkFieldOptions
  }
  return aShareFieldOptions
})

// 获取字段默认值
const getFieldDefaultValue = (field: string): number => {
  const options = marketType.value === 'hk_stock' ? hkFieldOptions : aShareFieldOptions
  const option = options.find(opt => opt.value === field)
  return option?.defaultValue ?? 0
}

// 监听市场类型变化，重置筛选条件
watch(marketType, (newType) => {
  // 重置为该市场支持的默认条件
  const defaultField = newType === 'hk_stock' ? 'pct_chg' : 'pct_chg'
  const defaultValue = getFieldDefaultValue(defaultField)
  conditions.value = [{ field: defaultField, operator: 'gt', value: defaultValue }]
})

const operatorOptions = [
  { value: 'gt', label: '>' },
  { value: 'gte', label: '>=' },
  { value: 'lt', label: '<' },
  { value: 'lte', label: '<=' },
  { value: 'eq', label: '=' }
]

const addCondition = () => {
  // 根据市场类型选择默认字段
  const defaultField = marketType.value === 'hk_stock' ? 'pct_chg' : 'pe'
  conditions.value.push({ 
    field: defaultField, 
    operator: 'lt', 
    value: getFieldDefaultValue(defaultField) 
  })
}

// 当字段变更时更新默认值
const handleFieldChange = (index: number, field: string) => {
  conditions.value[index].field = field
  conditions.value[index].value = getFieldDefaultValue(field)
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

const handleDateChange = (date: string | null) => {
  selectedDate.value = date
  screenerStore.changeTradeDate(date)
}

const handleMarketTypeChange = (value: 'a_share' | 'hk_stock' | 'all') => {
  marketType.value = value
  screenerStore.changeMarketType(value)
}

const handleClearFilters = () => {
  // 重置为当前市场的默认条件
  const defaultField = marketType.value === 'hk_stock' ? 'pct_chg' : 'pct_chg'
  conditions.value = [{ field: defaultField, operator: 'gt', value: getFieldDefaultValue(defaultField) }]
  searchInput.value = ''
  selectedDate.value = null
  nlQuery.value = ''
  screenerStore.clearFilters()
}

const handlePageChange = (current: number) => {
  if (current !== screenerStore.page) {
    screenerStore.changePage(current)
  }
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

const handleViewProfile = (stockCode: string) => {
  profileStockCode.value = stockCode
  showProfileDrawer.value = true
}

const handleAddToWatchlist = async (row: any) => {
  try {
    const costPrice = row.close || row.current_price || 10.0
    
    await portfolioStore.addPosition({
      ts_code: row.ts_code,
      quantity: 100,
      cost_price: costPrice,
      buy_date: new Date().toISOString().split('T')[0],
      notes: `从智能选股添加 - ${row.stock_name || row.ts_code}`
    })
    
    MessagePlugin.success(`已将 ${row.stock_name || row.ts_code} 添加到自选股`)
  } catch (error: any) {
    console.error('Failed to add to watchlist:', error)
    MessagePlugin.error(`添加自选股失败: ${error.message || error}`)
  }
}

const handleDetailDialogClose = () => {
  showDetailDialog.value = false
  selectedStockCode.value = ''
}

const handleProfileDrawerClose = () => {
  showProfileDrawer.value = false
  profileStockCode.value = ''
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

const columns = [
  { colKey: 'ts_code', title: '代码', width: 100, sortable: true },
  { colKey: 'stock_name', title: '名称', width: 90 },
  { colKey: 'trade_date', title: '日期', width: 100 },
  { colKey: 'close', title: '收盘价', width: 80, sortable: true },
  { colKey: 'pct_chg', title: '涨跌幅', width: 90, sortable: true },
  { colKey: 'pe_ttm', title: 'PE', width: 70, sortable: true },
  { colKey: 'pb', title: 'PB', width: 60, sortable: true },
  { colKey: 'total_mv', title: '总市值', width: 90, sortable: true },
  { colKey: 'turnover_rate', title: '换手率', width: 80, sortable: true },
  { colKey: 'industry', title: '行业', width: 80 },
  { colKey: 'operation', title: '操作', width: 140, fixed: 'right' }
]

// Load data on mount
onMounted(() => {
  screenerStore.fetchStocks()
  screenerStore.fetchSummary()
})
</script>

<template>
  <div class="screener-view">
    <!-- Market Type TAB -->
    <div class="market-tab-bar">
      <div 
        class="market-tab-item" 
        :class="{ active: marketType === 'a_share' }" 
        @click="handleMarketTypeChange('a_share')"
      >
        <span class="market-tab-icon">🇨🇳</span>
        <span class="market-tab-label">A 股</span>
      </div>
      <div 
        class="market-tab-item" 
        :class="{ active: marketType === 'hk_stock' }" 
        @click="handleMarketTypeChange('hk_stock')"
      >
        <span class="market-tab-icon">🇭🇰</span>
        <span class="market-tab-label">港股</span>
      </div>
      <div 
        class="market-tab-item" 
        :class="{ active: marketType === 'all' }" 
        @click="handleMarketTypeChange('all')"
      >
        <span class="market-tab-icon">🌐</span>
        <span class="market-tab-label">全部</span>
      </div>
    </div>

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
            <div class="summary-label up">{{ marketType === 'hk_stock' ? '大涨(≥10%)' : '涨停' }}</div>
            <div class="summary-value up">{{ screenerStore.summary.limit_up }}</div>
          </div>
        </t-col>
        <t-col :span="2">
          <div class="summary-item">
            <div class="summary-label down">{{ marketType === 'hk_stock' ? '大跌(≤-10%)' : '跌停' }}</div>
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
                  <t-select 
                    v-model="cond.field" 
                    :options="fieldOptions" 
                    style="width: 120px" 
                    @change="(val: string) => handleFieldChange(index, val)"
                  />
                  <t-select v-model="cond.operator" :options="operatorOptions" style="width: 70px" />
                  <t-input-number 
                    v-model="cond.value" 
                    style="width: 120px"
                    :decimal-places="2"
                    :allow-input-over-limit="false"
                    theme="normal"
                  />
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
            
            <t-tab-panel value="nl" label="智能选股">
              <t-textarea
                v-model="nlQuery"
                placeholder="例如：找出市盈率低于20，换手率超过5%的科技股"
                :autosize="{ minRows: 3, maxRows: 6 }"
              />
              <t-button theme="primary" block style="margin-top: 16px" @click="handleNLScreener">
                <template #icon><t-icon name="lightbulb" /></template>
                智能选股
              </t-button>
              
              <!-- NL解析结果提示 -->
              <t-alert 
                v-if="screenerStore.nlExplanation" 
                theme="info" 
                :message="screenerStore.nlExplanation"
                style="margin-top: 12px"
              />
            </t-tab-panel>
            
            <t-tab-panel value="sector" label="行业筛选">
              <SectorFilter />
            </t-tab-panel>
            
            <t-tab-panel value="recommend" label="AI推荐">
              <RecommendationPanel 
                @view-detail="handleViewDetail" 
                @add-watchlist="handleAddToWatchlist"
              />
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
              <t-date-picker
                v-model="selectedDate"
                placeholder="选择日期"
                style="width: 130px"
                :clearable="true"
                format="YYYY-MM-DD"
                value-type="YYYY-MM-DD"
                @change="handleDateChange"
              />
              <t-input
                v-model="searchInput"
                placeholder="搜索代码/名称"
                style="width: 140px"
                @enter="handleSearch"
              >
                <template #suffix-icon>
                  <t-icon name="search" @click="handleSearch" style="cursor: pointer" />
                </template>
              </t-input>
              <span class="result-count">共 {{ screenerStore.total }} 只{{ marketType === 'hk_stock' ? '港股' : (marketType === 'all' ? '股票' : 'A股') }}</span>
            </t-space>
          </template>
          
          <t-table
            :data="screenerStore.stocks"
            :columns="columns"
            :loading="screenerStore.loading"
            row-key="ts_code"
            max-height="calc(100vh - 350px)"
            @sort-change="handleSortChange"
          >
            <template #stock_name="{ row }">
              {{ row.stock_name || '-' }}
            </template>
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
            <template #industry="{ row }">
              {{ row.industry || '-' }}
            </template>
            <template #operation="{ row }">
              <t-space>
                <t-link theme="primary" @click="handleViewDetail(row.ts_code)">详情</t-link>
                <t-link theme="primary" @click="handleViewProfile(row.ts_code)">画像</t-link>
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
    
    <!-- Profile Drawer -->
    <ProfileCard
      :ts-code="profileStockCode"
      :visible="showProfileDrawer"
      @update:visible="showProfileDrawer = $event"
      @close="handleProfileDrawerClose"
    />
  </div>
</template>

<style scoped>
.screener-view {
  height: 100%;
}

.market-tab-bar {
  display: flex;
  gap: 0;
  margin-bottom: 16px;
  background: var(--td-bg-color-container);
  border-radius: 8px;
  padding: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.market-tab-item {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 24px;
  cursor: pointer;
  border-radius: 6px;
  font-size: 15px;
  font-weight: 500;
  color: var(--td-text-color-secondary);
  transition: all 0.25s ease;
  user-select: none;
}

.market-tab-item:hover {
  color: var(--td-brand-color);
  background: var(--td-brand-color-light);
}

.market-tab-item.active {
  color: #fff;
  background: linear-gradient(135deg, var(--td-brand-color) 0%, var(--td-brand-color-hover) 100%);
  box-shadow: 0 2px 8px rgba(0, 82, 217, 0.3);
}

.market-tab-icon {
  font-size: 18px;
}

.market-tab-label {
  font-size: 15px;
  letter-spacing: 1px;
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
  flex-wrap: wrap;
}

.condition-item :deep(.t-input-number) {
  min-width: 100px;
}

.condition-item :deep(.t-input-number__decrease),
.condition-item :deep(.t-input-number__increase) {
  display: none;
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
