<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { etfApi, type BenchmarkIndexInfo, type PublisherOption } from '@/api/etf'

const loading = ref(false)
const indices = ref<BenchmarkIndexInfo[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

// Filters
const searchInput = ref('')
const selectedPublisher = ref('')
const publishers = ref<PublisherOption[]>([])

// Statistics
const statistics = ref<{
  total_count: number
  publisher_count: number
  earliest_pub_date?: string
  latest_pub_date?: string
  avg_base_point?: number
}>({
  total_count: 0,
  publisher_count: 0
})

// Table columns
const columns = [
  { colKey: 'ts_code', title: '指数代码', width: 120 },
  { colKey: 'indx_csname', title: '指数简称', width: 150 },
  { colKey: 'indx_name', title: '指数全称', width: 250, ellipsis: true },
  { colKey: 'pub_party_name', title: '发布机构', width: 180 },
  { colKey: 'pub_date', title: '发布日期', width: 120 },
  { colKey: 'base_date', title: '基日', width: 120 },
  { colKey: 'bp', title: '基点', width: 100 },
  { colKey: 'adj_circle', title: '调整周期', width: 120 },
]

// Publisher options for select
const publisherOptions = computed(() => [
  { value: '', label: '全部发布机构' },
  ...publishers.value.map(p => ({ value: p.value, label: `${p.label} (${p.count})` }))
])

// Fetch data
const fetchIndices = async () => {
  loading.value = true
  try {
    const params: any = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (searchInput.value) params.keyword = searchInput.value
    if (selectedPublisher.value) params.publisher = selectedPublisher.value
    
    const response = await etfApi.getBenchmarkIndices(params)
    indices.value = response.items
    total.value = response.total
  } catch (error: any) {
    MessagePlugin.error('获取基准指数列表失败: ' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

const fetchPublishers = async () => {
  try {
    publishers.value = await etfApi.getBenchmarkPublishers()
  } catch (error) {
    console.error('Failed to fetch publishers:', error)
  }
}

const fetchStatistics = async () => {
  try {
    statistics.value = await etfApi.getBenchmarkStatistics()
  } catch (error) {
    console.error('Failed to fetch statistics:', error)
  }
}

// Handlers
const handleSearch = () => {
  page.value = 1
  fetchIndices()
}

const handlePublisherChange = (value: string) => {
  selectedPublisher.value = value
  page.value = 1
  fetchIndices()
}

const handlePageChange = (current: number) => {
  page.value = current
  fetchIndices()
}

const handlePageSizeChange = (size: number) => {
  pageSize.value = size
  page.value = 1
  fetchIndices()
}

const handleClearFilters = () => {
  searchInput.value = ''
  selectedPublisher.value = ''
  page.value = 1
  fetchIndices()
}

// Initialize
onMounted(() => {
  fetchIndices()
  fetchPublishers()
  fetchStatistics()
})
</script>

<template>
  <div class="benchmark-index-panel">
    <!-- Statistics Cards -->
    <t-row :gutter="16" style="margin-bottom: 16px">
      <t-col :span="3">
        <t-card :bordered="false" class="stat-card">
          <div class="stat-value">{{ statistics.total_count }}</div>
          <div class="stat-label">基准指数总数</div>
        </t-card>
      </t-col>
      <t-col :span="3">
        <t-card :bordered="false" class="stat-card">
          <div class="stat-value">{{ statistics.publisher_count }}</div>
          <div class="stat-label">发布机构数</div>
        </t-card>
      </t-col>
      <t-col :span="3">
        <t-card :bordered="false" class="stat-card">
          <div class="stat-value">{{ statistics.avg_base_point?.toFixed(0) || '-' }}</div>
          <div class="stat-label">平均基点</div>
        </t-card>
      </t-col>
      <t-col :span="3">
        <t-card :bordered="false" class="stat-card">
          <div class="stat-value">{{ statistics.latest_pub_date || '-' }}</div>
          <div class="stat-label">最新发布日期</div>
        </t-card>
      </t-col>
    </t-row>

    <!-- Filters -->
    <t-card :bordered="false" style="margin-bottom: 16px">
      <div class="filter-row">
        <t-input
          v-model="searchInput"
          placeholder="搜索指数名称"
          clearable
          style="width: 200px"
          @enter="handleSearch"
        >
          <template #suffix-icon>
            <t-icon name="search" @click="handleSearch" style="cursor: pointer" />
          </template>
        </t-input>
        
        <t-select
          :value="selectedPublisher"
          :options="publisherOptions"
          placeholder="选择发布机构"
          clearable
          filterable
          style="width: 200px; margin-left: 16px"
          @change="handlePublisherChange"
        />
        
        <t-button variant="outline" style="margin-left: 16px" @click="handleClearFilters">
          清除筛选
        </t-button>
        
        <span class="result-count" style="margin-left: auto">
          共 {{ total }} 个基准指数
        </span>
      </div>
    </t-card>

    <!-- Data Table -->
    <t-card :bordered="false">
      <t-table
        :data="indices"
        :columns="columns"
        :loading="loading"
        row-key="ts_code"
        max-height="calc(100vh - 400px)"
        hover
      >
        <template #ts_code="{ row }">
          <t-link theme="primary">{{ row.ts_code }}</t-link>
        </template>
        <template #bp="{ row }">
          {{ row.bp?.toFixed(2) || '-' }}
        </template>
      </t-table>
      
      <!-- Pagination -->
      <div class="pagination-wrapper">
        <t-pagination
          :current="page"
          :page-size="pageSize"
          :total="total"
          :page-size-options="[10, 20, 50, 100]"
          show-jumper
          @current-change="handlePageChange"
          @page-size-change="handlePageSizeChange"
        />
      </div>
    </t-card>
  </div>
</template>

<style scoped>
.benchmark-index-panel {
  height: 100%;
}

.stat-card {
  text-align: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 14px;
  opacity: 0.9;
}

.filter-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
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
