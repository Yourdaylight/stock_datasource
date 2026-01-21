<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { researchApi, type ReportRcItem, type HotCoveredStock, type RatingDistribution, type ConsensusForecast } from '@/api/research'

// State
const loading = ref(false)
const reportData = ref<ReportRcItem[]>([])
const hotStocks = ref<HotCoveredStock[]>([])
const ratingStats = ref<RatingDistribution[]>([])
const consensusData = ref<ConsensusForecast | null>(null)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchStock = ref('')
const selectedDate = ref('')
const activeView = ref<'hot' | 'date' | 'stock'>('hot')
const selectedStockCode = ref('')

// Columns for report table
const reportColumns = computed(() => [
  { colKey: 'ts_code', title: '股票代码', width: 100 },
  { colKey: 'name', title: '股票名称', width: 100 },
  { colKey: 'report_date', title: '发布日期', width: 110 },
  { colKey: 'org_name', title: '研究机构', width: 120, ellipsis: true },
  { colKey: 'author', title: '分析师', width: 80 },
  { colKey: 'rating', title: '评级', width: 80 },
  { colKey: 'target_price', title: '目标价', width: 90 },
  { colKey: 'eps_curr', title: '当年EPS', width: 90 },
  { colKey: 'eps_next', title: '次年EPS', width: 90 },
  { colKey: 'report_title', title: '报告标题', ellipsis: true }
])

// Columns for hot stocks table
const hotStocksColumns = computed(() => [
  { colKey: 'index', title: '排名', width: 60 },
  { colKey: 'ts_code', title: '股票代码', width: 100 },
  { colKey: 'name', title: '股票名称', width: 100 },
  { colKey: 'report_count', title: '报告数', width: 80 },
  { colKey: 'unique_org_count', title: '机构数', width: 80 },
  { colKey: 'avg_target_price', title: '平均目标价', width: 100 },
  { colKey: 'latest_report_date', title: '最新报告', width: 110 },
  { colKey: 'ratings', title: '评级分布' }
])

// Format date
const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-'
  if (dateStr.length === 8) {
    return dateStr.replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3')
  }
  return dateStr
}

// Format number
const formatNumber = (val?: number, decimals = 2) => {
  if (val === undefined || val === null) return '-'
  return val.toFixed(decimals)
}

// Get rating theme
const getRatingTheme = (rating?: string) => {
  if (!rating) return 'default'
  if (rating.includes('买') || rating.includes('增')) return 'success'
  if (rating.includes('持') || rating.includes('中')) return 'warning'
  if (rating.includes('减') || rating.includes('卖')) return 'danger'
  return 'default'
}

// Load hot covered stocks
const loadHotStocks = async () => {
  loading.value = true
  try {
    const [hotRes, ratingRes] = await Promise.all([
      researchApi.getHotCoveredStocks(30, 30),
      researchApi.getRatingDistribution(undefined, 30)
    ])
    hotStocks.value = hotRes.data || []
    ratingStats.value = ratingRes.data || []
  } catch (error) {
    console.error('Failed to load hot covered stocks:', error)
    hotStocks.value = []
  } finally {
    loading.value = false
  }
}

// Load reports by date
const loadReportsByDate = async () => {
  if (!selectedDate.value) return
  loading.value = true
  try {
    const dateStr = selectedDate.value.replace(/-/g, '')
    const res = await researchApi.getReportsByDate(dateStr, page.value, pageSize.value)
    reportData.value = res.data || []
    total.value = res.total || 0
  } catch (error) {
    console.error('Failed to load reports by date:', error)
    reportData.value = []
  } finally {
    loading.value = false
  }
}

// Handle date change
const handleDateChange = (val: string) => {
  selectedDate.value = val
  activeView.value = 'date'
  page.value = 1
  loadReportsByDate()
}

// Handle page change
const handlePageChange = (pageInfo: { current: number; pageSize: number }) => {
  page.value = pageInfo.current
  pageSize.value = pageInfo.pageSize
  if (activeView.value === 'date') {
    loadReportsByDate()
  } else if (activeView.value === 'stock') {
    loadStockReports(selectedStockCode.value)
  }
}

// View stock reports
const loadStockReports = async (tsCode: string) => {
  loading.value = true
  selectedStockCode.value = tsCode
  activeView.value = 'stock'
  try {
    const [reportRes, consensusRes] = await Promise.all([
      researchApi.getReportsByStock(tsCode, 180, page.value, pageSize.value),
      researchApi.getConsensusForecast(tsCode, 90)
    ])
    reportData.value = reportRes.data || []
    total.value = reportRes.total || 0
    consensusData.value = consensusRes.data || null
  } catch (error) {
    console.error('Failed to load stock reports:', error)
    reportData.value = []
  } finally {
    loading.value = false
  }
}

// Handle search
const handleSearch = () => {
  if (!searchStock.value.trim()) return
  loadStockReports(searchStock.value.trim().toUpperCase())
}

// Switch to hot view
const switchToHot = () => {
  activeView.value = 'hot'
  searchStock.value = ''
  selectedDate.value = ''
  consensusData.value = null
}

onMounted(() => {
  loadHotStocks()
})
</script>

<template>
  <div class="report-panel">
    <!-- Filter bar -->
    <div class="filter-bar">
      <t-space>
        <t-button 
          :theme="activeView === 'hot' ? 'primary' : 'default'"
          @click="switchToHot"
        >
          热门覆盖
        </t-button>
        <t-date-picker
          v-model="selectedDate"
          placeholder="选择日期"
          clearable
          @change="handleDateChange"
        />
        <t-input
          v-model="searchStock"
          placeholder="输入股票代码"
          style="width: 180px"
          clearable
          @enter="handleSearch"
        >
          <template #suffix-icon>
            <t-icon name="search" @click="handleSearch" style="cursor: pointer" />
          </template>
        </t-input>
      </t-space>
    </div>

    <!-- Hot stocks view -->
    <div v-if="activeView === 'hot'" class="content-section">
      <t-row :gutter="16">
        <!-- Hot stocks table -->
        <t-col :span="8">
          <t-card title="热门覆盖股票" size="small" :bordered="false">
            <template #subtitle>
              <span class="card-subtitle">近30天研报覆盖排行</span>
            </template>
            <t-table
              :data="hotStocks"
              :columns="hotStocksColumns"
              :loading="loading"
              row-key="ts_code"
              size="small"
              :max-height="500"
              hover
            >
              <template #index="{ rowIndex }">
                <t-tag 
                  :theme="rowIndex < 3 ? 'primary' : 'default'" 
                  size="small"
                  :variant="rowIndex < 3 ? 'dark' : 'light'"
                >
                  {{ rowIndex + 1 }}
                </t-tag>
              </template>
              <template #ts_code="{ row }">
                <t-link theme="primary" @click="loadStockReports(row.ts_code)">
                  {{ row.ts_code }}
                </t-link>
              </template>
              <template #avg_target_price="{ row }">
                {{ formatNumber(row.avg_target_price) }}
              </template>
              <template #latest_report_date="{ row }">
                {{ formatDate(row.latest_report_date) }}
              </template>
              <template #ratings="{ row }">
                <t-space size="small" v-if="row.ratings">
                  <t-tag 
                    v-for="(count, rating) in row.ratings" 
                    :key="rating as string" 
                    size="small" 
                    :theme="getRatingTheme(rating as string)"
                    variant="light"
                  >
                    {{ rating }}: {{ count }}
                  </t-tag>
                </t-space>
                <span v-else>-</span>
              </template>
            </t-table>
          </t-card>
        </t-col>

        <!-- Rating distribution -->
        <t-col :span="4">
          <t-card title="评级分布" size="small" :bordered="false">
            <template #subtitle>
              <span class="card-subtitle">近30天统计</span>
            </template>
            <div class="rating-stats">
              <div 
                v-for="stat in ratingStats" 
                :key="stat.rating" 
                class="stat-item"
              >
                <div class="stat-label">
                  <t-tag :theme="getRatingTheme(stat.rating)" size="small" variant="light">
                    {{ stat.rating || '其他' }}
                  </t-tag>
                </div>
                <t-progress 
                  :percentage="stat.percentage" 
                  :theme="getRatingTheme(stat.rating) === 'success' ? 'success' : 
                         getRatingTheme(stat.rating) === 'danger' ? 'error' : 'warning'"
                  size="small"
                />
                <div class="stat-count">{{ stat.count }}份</div>
              </div>
              <div v-if="ratingStats.length === 0 && !loading" class="empty-stats">
                暂无数据
              </div>
            </div>
          </t-card>
        </t-col>
      </t-row>
    </div>

    <!-- Report list view (date/stock) -->
    <div v-else class="content-section">
      <!-- Consensus forecast card (only for stock view) -->
      <t-card v-if="activeView === 'stock' && consensusData" size="small" :bordered="false" class="consensus-card">
        <template #title>
          <span>{{ consensusData.name || selectedStockCode }} 一致预期</span>
        </template>
        <t-row :gutter="24">
          <t-col :span="2">
            <div class="consensus-item">
              <div class="consensus-label">平均EPS</div>
              <div class="consensus-value">{{ formatNumber(consensusData.eps_avg) }}</div>
              <div class="consensus-range">
                {{ formatNumber(consensusData.eps_low) }} - {{ formatNumber(consensusData.eps_high) }}
              </div>
            </div>
          </t-col>
          <t-col :span="3">
            <div class="consensus-item">
              <div class="consensus-label">平均目标价</div>
              <div class="consensus-value highlight">{{ formatNumber(consensusData.target_price_avg) }}</div>
              <div class="consensus-range">
                {{ formatNumber(consensusData.target_price_low) }} - {{ formatNumber(consensusData.target_price_high) }}
              </div>
            </div>
          </t-col>
          <t-col :span="2">
            <div class="consensus-item">
              <div class="consensus-label">报告数量</div>
              <div class="consensus-value">{{ consensusData.report_count }}</div>
            </div>
          </t-col>
          <t-col :span="5">
            <div class="consensus-item">
              <div class="consensus-label">评级分布</div>
              <t-space size="small" v-if="consensusData.rating_distribution">
                <t-tag 
                  v-for="(count, rating) in consensusData.rating_distribution" 
                  :key="rating as string" 
                  :theme="getRatingTheme(rating as string)"
                  variant="light"
                >
                  {{ rating }}: {{ count }}
                </t-tag>
              </t-space>
            </div>
          </t-col>
        </t-row>
      </t-card>

      <!-- Report list -->
      <t-card size="small" :bordered="false">
        <template #title>
          <span v-if="activeView === 'date'">
            {{ formatDate(selectedDate) }} 研报列表
          </span>
          <span v-else>
            {{ selectedStockCode }} 研报列表
          </span>
        </template>
        <template #actions>
          <t-button variant="text" @click="switchToHot">
            <t-icon name="chevron-left" /> 返回热门
          </t-button>
        </template>
        <t-table
          :data="reportData"
          :columns="reportColumns"
          :loading="loading"
          row-key="ts_code"
          size="small"
          :max-height="400"
          hover
          :pagination="{
            current: page,
            pageSize: pageSize,
            total: total,
            showJumper: true,
            showPageSize: true,
            pageSizeOptions: [10, 20, 50]
          }"
          @page-change="handlePageChange"
        >
          <template #report_date="{ row }">
            {{ formatDate(row.report_date) }}
          </template>
          <template #rating="{ row }">
            <t-tag v-if="row.rating" :theme="getRatingTheme(row.rating)" size="small">
              {{ row.rating }}
            </t-tag>
            <span v-else>-</span>
          </template>
          <template #target_price="{ row }">
            <span :class="{ 'text-primary': row.target_price }">
              {{ formatNumber(row.target_price) }}
            </span>
          </template>
          <template #eps_curr="{ row }">
            {{ formatNumber(row.eps_curr) }}
          </template>
          <template #eps_next="{ row }">
            {{ formatNumber(row.eps_next) }}
          </template>
          <template #report_title="{ row }">
            <t-tooltip v-if="row.report_title" :content="row.report_title" placement="top-left">
              <span class="title-cell">{{ row.report_title }}</span>
            </t-tooltip>
            <span v-else>-</span>
          </template>
        </t-table>
      </t-card>
    </div>
  </div>
</template>

<style scoped>
.report-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.content-section {
  min-height: 400px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-subtitle {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.rating-stats {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-label {
  min-width: 70px;
}

.stat-count {
  min-width: 50px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
  text-align: right;
}

.empty-stats {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--td-text-color-placeholder);
}

.consensus-card {
  margin-bottom: 0;
}

.consensus-item {
  text-align: center;
}

.consensus-label {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  margin-bottom: 8px;
}

.consensus-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.consensus-value.highlight {
  color: var(--td-brand-color);
}

.consensus-range {
  font-size: 12px;
  color: var(--td-text-color-placeholder);
  margin-top: 4px;
}

.title-cell {
  display: block;
  max-width: 250px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.text-primary {
  color: var(--td-brand-color);
  font-weight: 500;
}

:deep(.t-progress__inner) {
  border-radius: 4px;
}
</style>
