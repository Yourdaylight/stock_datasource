<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { MessagePlugin } from 'tdesign-vue-next'
import { useFinancialAnalysisStore } from '@/stores/financial-analysis'

const router = useRouter()
const store = useFinancialAnalysisStore()

const activeMarket = ref('A')
const keyword = ref('')
const selectedIndustry = ref('')
const currentPage = ref(1)
const pageSize = ref(20)

// Load data
const loadCompanies = async () => {
  try {
    await store.fetchCompanies({
      market: activeMarket.value,
      keyword: keyword.value,
      industry: selectedIndustry.value,
      page: currentPage.value,
      page_size: pageSize.value,
    })
  } catch {
    MessagePlugin.error('加载公司列表失败')
  }
}

const loadIndustries = async () => {
  try {
    await store.fetchIndustries(activeMarket.value)
  } catch {
    // silent
  }
}

// Search handler with debounce
let searchTimer: ReturnType<typeof setTimeout> | null = null
const onSearchInput = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    currentPage.value = 1
    loadCompanies()
  }, 400)
}

const onSearch = () => {
  currentPage.value = 1
  loadCompanies()
}

const onIndustryChange = () => {
  currentPage.value = 1
  loadCompanies()
}

const onMarketChange = () => {
  keyword.value = ''
  selectedIndustry.value = ''
  currentPage.value = 1
  loadIndustries()
  loadCompanies()
}

const onPageChange = (pageInfo: { current: number; pageSize: number }) => {
  currentPage.value = pageInfo.current
  pageSize.value = pageInfo.pageSize
  loadCompanies()
}

// Navigate to company reports
const goToReports = (code: string) => {
  // Use raw code (without .SZ/.SH/.HK) for cleaner URLs
  const rawCode = code.split('.')[0]
  const market = activeMarket.value
  router.push({ name: 'ReportList', params: { code: rawCode }, query: { market } })
}

// Table columns
const columns = [
  { colKey: 'ts_code', title: '代码', width: 120 },
  { colKey: 'name', title: '名称', width: 140 },
  { colKey: 'industry', title: '行业', width: 120 },
  { colKey: 'area', title: '地域', width: 100 },
  { colKey: 'market', title: '市场', width: 80 },
  { colKey: 'list_date', title: '上市日期', width: 120 },
  { colKey: 'action', title: '操作', width: 100, fixed: 'right' as const },
]

// Format amount helper
const formatAmount = (val: number | null): string => {
  if (val === null || val === undefined) return '-'
  const abs = Math.abs(val)
  if (abs >= 1e8) return (val / 1e8).toFixed(2) + '亿'
  if (abs >= 1e4) return (val / 1e4).toFixed(2) + '万'
  return val.toFixed(2)
}

// Hot stocks for quick access
const hotStocks = [
  { code: '600519', name: '贵州茅台', market: 'A' },
  { code: '000001', name: '平安银行', market: 'A' },
  { code: '002594', name: '比亚迪', market: 'A' },
  { code: '600036', name: '招商银行', market: 'A' },
  { code: '000858', name: '五粮液', market: 'A' },
  { code: '00700', name: '腾讯控股', market: 'HK' },
]

onMounted(() => {
  loadIndustries()
  loadCompanies()
})

watch(activeMarket, onMarketChange)
</script>

<template>
  <div class="company-list-view">
    <!-- Header -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-title-area">
          <h1 class="page-title">财报分析</h1>
          <p class="page-desc">浏览上市公司，深入分析财务报表，获取AI专业洞察</p>
        </div>
      </div>
    </div>

    <!-- Market Tabs + Search -->
    <div class="filter-bar">
      <div class="filter-left">
        <t-tabs v-model="activeMarket" size="medium" theme="card">
          <t-tab-panel value="A" label="A股" />
          <t-tab-panel value="HK" label="港股" />
        </t-tabs>
      </div>

      <div class="filter-right">
        <t-select
          v-if="activeMarket === 'A' && store.industries.length > 0"
          v-model="selectedIndustry"
          placeholder="筛选行业"
          clearable
          style="width: 160px"
          @change="onIndustryChange"
        >
          <t-option
            v-for="ind in store.industries"
            :key="ind"
            :value="ind"
            :label="ind"
          />
        </t-select>

        <t-input
          v-model="keyword"
          placeholder="搜索代码或名称..."
          clearable
          style="width: 240px"
          @enter="onSearch"
          @input="onSearchInput"
          @clear="onSearch"
        >
          <template #prefix-icon>
            <t-icon name="search" />
          </template>
        </t-input>
      </div>
    </div>

    <!-- Hot stocks quick access -->
    <div class="hot-stocks">
      <span class="hot-label">热门：</span>
      <t-tag
        v-for="stock in hotStocks.filter(s => s.market === activeMarket)"
        :key="stock.code"
        theme="primary"
        variant="light"
        class="hot-tag"
        @click="goToReports(stock.code)"
      >
        {{ stock.name }}
      </t-tag>
    </div>

    <!-- Company Table -->
    <div class="table-container">
      <t-table
        :data="store.companies"
        :columns="columns"
        :loading="store.companyLoading"
        row-key="ts_code"
        hover
        stripe
        :pagination="{
          current: currentPage,
          pageSize: pageSize,
          total: store.companyTotal,
          showJumper: true,
          showPageSize: true,
          pageSizeOptions: [20, 50, 100],
        }"
        @page-change="onPageChange"
      >
        <template #ts_code="{ row }">
          <span class="stock-code" @click="goToReports(row.ts_code)">
            {{ row.ts_code }}
          </span>
        </template>

        <template #name="{ row }">
          <span class="stock-name" @click="goToReports(row.ts_code)">
            {{ row.name }}
          </span>
        </template>

        <template #industry="{ row }">
          <t-tag v-if="row.industry" theme="default" variant="light" size="small">
            {{ row.industry }}
          </t-tag>
          <span v-else class="text-placeholder">-</span>
        </template>

        <template #action="{ row }">
          <t-button
            theme="primary"
            variant="text"
            size="small"
            @click="goToReports(row.ts_code)"
          >
            查看财报
          </t-button>
        </template>
      </t-table>
    </div>
  </div>
</template>

<style scoped>
.company-list-view {
  padding: 16px 24px;
  min-height: 100%;
}

.page-header {
  margin-bottom: 20px;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--td-text-color-primary);
  margin: 0 0 4px;
}

.page-desc {
  font-size: 14px;
  color: var(--td-text-color-secondary);
  margin: 0;
}

.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 16px;
  flex-wrap: wrap;
}

.filter-left {
  flex-shrink: 0;
}

.filter-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.hot-stocks {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.hot-label {
  font-size: 13px;
  color: var(--td-text-color-placeholder);
}

.hot-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.hot-tag:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 82, 217, 0.15);
}

.table-container {
  background: var(--td-bg-color-container);
  border-radius: 8px;
  padding: 0;
  box-shadow: var(--td-shadow-1);
}

.stock-code {
  color: var(--td-brand-color);
  cursor: pointer;
  font-weight: 500;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
}

.stock-code:hover {
  text-decoration: underline;
}

.stock-name {
  cursor: pointer;
  font-weight: 500;
  color: var(--td-text-color-primary);
}

.stock-name:hover {
  color: var(--td-brand-color);
}

.text-placeholder {
  color: var(--td-text-color-placeholder);
}

:deep(.t-table__pagination) {
  padding: 12px 16px;
}
</style>
