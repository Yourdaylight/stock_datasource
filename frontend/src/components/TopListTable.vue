<template>
  <div class="top-list-table">
    <!-- 筛选器 -->
    <div class="filters">
      <div class="filter-row">
        <div class="filter-item">
          <label>日期:</label>
          <input 
            type="date" 
            v-model="selectedDate" 
            @change="handleDateChange"
            class="date-input"
          />
        </div>
        <div class="filter-item">
          <label>股票代码:</label>
          <input 
            type="text" 
            v-model="stockFilter" 
            placeholder="输入股票代码或名称"
            @input="handleStockFilter"
            class="stock-input"
          />
        </div>
        <div class="filter-item">
          <label>涨跌幅:</label>
          <select v-model="pctChgFilter" @change="handlePctChgFilter" class="select-input">
            <option value="">全部</option>
            <option value="positive">上涨</option>
            <option value="negative">下跌</option>
            <option value="limit_up">涨停</option>
            <option value="limit_down">跌停</option>
          </select>
        </div>
        <div class="filter-item">
          <button @click="refreshData" :disabled="loading" class="refresh-btn">
            {{ loading ? '加载中...' : '刷新' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 统计信息 -->
    <div class="stats-bar" v-if="marketStats">
      <div class="stat-item">
        <span class="label">上榜股票:</span>
        <span class="value">{{ marketStats.total_stocks }}</span>
      </div>
      <div class="stat-item">
        <span class="label">总成交额:</span>
        <span class="value">{{ formatAmount(marketStats.total_amount) }}</span>
      </div>
      <div class="stat-item">
        <span class="label">平均涨跌幅:</span>
        <span class="value" :class="{ 'positive': marketStats.avg_pct_chg > 0, 'negative': marketStats.avg_pct_chg < 0 }">
          {{ marketStats.avg_pct_chg?.toFixed(2) }}%
        </span>
      </div>
    </div>

    <!-- 数据表格 -->
    <div class="table-container">
      <table class="top-list-table-content">
        <thead>
          <tr>
            <th>股票代码</th>
            <th>股票名称</th>
            <th>收盘价</th>
            <th>涨跌幅(%)</th>
            <th>换手率(%)</th>
            <th>成交额(万)</th>
            <th>龙虎榜净买额(万)</th>
            <th>净买额占比(%)</th>
            <th>上榜原因</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="10" class="loading-row">
              <div class="loading-spinner">加载中...</div>
            </td>
          </tr>
          <tr v-else-if="!hasData">
            <td colspan="10" class="no-data">暂无数据</td>
          </tr>
          <tr v-else v-for="item in topListData" :key="`${item.ts_code}-${item.trade_date}`" class="data-row">
            <td class="ts-code">{{ item.ts_code }}</td>
            <td class="stock-name">{{ item.name || '-' }}</td>
            <td class="close-price">{{ item.close?.toFixed(2) || '-' }}</td>
            <td class="pct-chg" :class="{ 'positive': (item.pct_chg || 0) > 0, 'negative': (item.pct_chg || 0) < 0 }">
              {{ item.pct_chg?.toFixed(2) || '-' }}
            </td>
            <td class="turnover-rate">{{ item.turnover_rate?.toFixed(2) || '-' }}</td>
            <td class="amount">{{ formatAmount(item.amount) }}</td>
            <td class="net-amount" :class="{ 'positive': (item.net_amount || 0) > 0, 'negative': (item.net_amount || 0) < 0 }">
              {{ formatAmount(item.net_amount) }}
            </td>
            <td class="net-rate" :class="{ 'positive': (item.net_rate || 0) > 0, 'negative': (item.net_rate || 0) < 0 }">
              {{ item.net_rate?.toFixed(2) || '-' }}
            </td>
            <td class="reason">
              <span class="reason-text" :title="item.reason">{{ item.reason || '-' }}</span>
            </td>
            <td class="actions">
              <button @click="viewDetail(item)" class="detail-btn">详情</button>
              <button @click="viewAnalysis(item)" class="analysis-btn">分析</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <div class="pagination" v-if="totalPages > 1">
      <button 
        @click="setPage(currentPage - 1)" 
        :disabled="currentPage <= 1"
        class="page-btn"
      >
        上一页
      </button>
      
      <span class="page-info">
        第 {{ currentPage }} 页 / 共 {{ totalPages }} 页 ({{ total }} 条记录)
      </span>
      
      <button 
        @click="setPage(currentPage + 1)" 
        :disabled="currentPage >= totalPages"
        class="page-btn"
      >
        下一页
      </button>
      
      <select v-model="pageSize" @change="handlePageSizeChange" class="page-size-select">
        <option value="20">20条/页</option>
        <option value="50">50条/页</option>
        <option value="100">100条/页</option>
      </select>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-message">
      {{ error }}
      <button @click="clearError" class="close-btn">×</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useTopListStore } from '@/stores/toplist'
import type { TopListItem } from '@/api/toplist'

// Store
const topListStore = useTopListStore()

// Computed properties from store
const topListData = computed(() => topListStore.topListData)
const loading = computed(() => topListStore.loading)
const error = computed(() => topListStore.error)
const hasData = computed(() => topListStore.hasData)
const currentPage = computed(() => topListStore.currentPage)
const totalPages = computed(() => topListStore.totalPages)
const total = computed(() => topListStore.total)
const marketStats = computed(() => topListStore.marketStats)

// Local reactive data
const selectedDate = ref(topListStore.selectedDate)
const stockFilter = ref('')
const pctChgFilter = ref('')
const pageSize = ref(topListStore.pageSize)

// Emits
const emit = defineEmits<{
  viewDetail: [item: TopListItem]
  viewAnalysis: [item: TopListItem]
}>()

// Methods
const handleDateChange = () => {
  topListStore.setSelectedDate(selectedDate.value)
  refreshData()
}

const handleStockFilter = () => {
  // Debounce search
  setTimeout(() => {
    if (stockFilter.value.trim()) {
      searchByStock()
    } else {
      refreshData()
    }
  }, 500)
}

const handlePctChgFilter = () => {
  searchByPctChg()
}

const handlePageSizeChange = () => {
  topListStore.setPageSize(pageSize.value)
  refreshData()
}

const refreshData = async () => {
  await Promise.all([
    topListStore.fetchTopListByDate(selectedDate.value),
    topListStore.fetchMarketStats(selectedDate.value)
  ])
}

const searchByStock = async () => {
  if (stockFilter.value.trim()) {
    await topListStore.searchTopList({
      keyword: stockFilter.value.trim(),
      start_date: selectedDate.value,
      end_date: selectedDate.value
    })
  }
}

const searchByPctChg = async () => {
  const params: any = {
    start_date: selectedDate.value,
    end_date: selectedDate.value
  }
  
  switch (pctChgFilter.value) {
    case 'positive':
      params.min_pct_chg = 0.01
      break
    case 'negative':
      params.max_pct_chg = -0.01
      break
    case 'limit_up':
      params.min_pct_chg = 9.5
      break
    case 'limit_down':
      params.max_pct_chg = -9.5
      break
  }
  
  if (stockFilter.value.trim()) {
    params.keyword = stockFilter.value.trim()
  }
  
  await topListStore.searchTopList(params)
}

const setPage = (page: number) => {
  topListStore.setPage(page)
  refreshData()
}

const viewDetail = (item: TopListItem) => {
  emit('viewDetail', item)
}

const viewAnalysis = (item: TopListItem) => {
  emit('viewAnalysis', item)
}

const clearError = () => {
  topListStore.clearError()
}

const formatAmount = (amount?: number): string => {
  if (!amount) return '-'
  if (Math.abs(amount) >= 100000000) {
    return (amount / 100000000).toFixed(2) + '亿'
  } else if (Math.abs(amount) >= 10000) {
    return (amount / 10000).toFixed(2) + '万'
  }
  return amount.toFixed(2)
}

// Watch for store changes
watch(() => topListStore.selectedDate, (newDate) => {
  selectedDate.value = newDate
})

watch(() => topListStore.pageSize, (newSize) => {
  pageSize.value = newSize
})

// Initialize
onMounted(() => {
  refreshData()
})
</script>

<style scoped>
.top-list-table {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.filters {
  margin-bottom: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 6px;
}

.filter-row {
  display: flex;
  gap: 20px;
  align-items: center;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-item label {
  font-weight: 500;
  color: #333;
  white-space: nowrap;
}

.date-input, .stock-input, .select-input {
  padding: 6px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.stock-input {
  width: 200px;
}

.refresh-btn {
  padding: 6px 16px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.refresh-btn:hover:not(:disabled) {
  background: #0056b3;
}

.refresh-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.stats-bar {
  display: flex;
  gap: 30px;
  margin-bottom: 20px;
  padding: 12px;
  background: #f1f3f4;
  border-radius: 6px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stat-item .label {
  color: #666;
  font-size: 14px;
}

.stat-item .value {
  font-weight: 600;
  font-size: 16px;
}

.table-container {
  overflow-x: auto;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
}

.top-list-table-content {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.top-list-table-content th {
  background: #f5f5f5;
  padding: 12px 8px;
  text-align: left;
  font-weight: 600;
  border-bottom: 2px solid #e0e0e0;
  white-space: nowrap;
}

.top-list-table-content td {
  padding: 10px 8px;
  border-bottom: 1px solid #f0f0f0;
  white-space: nowrap;
}

.data-row:hover {
  background: #f8f9fa;
}

.ts-code {
  font-family: monospace;
  font-weight: 600;
  color: #007bff;
}

.stock-name {
  font-weight: 500;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.positive {
  color: #dc3545;
}

.negative {
  color: #28a745;
}

.reason-text {
  max-width: 150px;
  display: inline-block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.actions {
  display: flex;
  gap: 8px;
}

.detail-btn, .analysis-btn {
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 3px;
  background: white;
  cursor: pointer;
  font-size: 12px;
}

.detail-btn:hover {
  background: #e9ecef;
}

.analysis-btn {
  background: #007bff;
  color: white;
  border-color: #007bff;
}

.analysis-btn:hover {
  background: #0056b3;
}

.loading-row, .no-data {
  text-align: center;
  padding: 40px;
  color: #666;
}

.loading-spinner {
  display: inline-block;
}

.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
  padding: 15px 0;
}

.page-btn {
  padding: 8px 16px;
  border: 1px solid #ddd;
  background: white;
  border-radius: 4px;
  cursor: pointer;
}

.page-btn:hover:not(:disabled) {
  background: #f8f9fa;
}

.page-btn:disabled {
  color: #ccc;
  cursor: not-allowed;
}

.page-info {
  color: #666;
  font-size: 14px;
}

.page-size-select {
  padding: 6px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.error-message {
  position: fixed;
  top: 20px;
  right: 20px;
  background: #f8d7da;
  color: #721c24;
  padding: 12px 16px;
  border-radius: 6px;
  border: 1px solid #f5c6cb;
  display: flex;
  align-items: center;
  gap: 12px;
  z-index: 1000;
}

.close-btn {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: #721c24;
}
</style>