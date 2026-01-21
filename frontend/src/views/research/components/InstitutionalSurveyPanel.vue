<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { researchApi, type SurveyItem, type HotSurveyedStock, type OrgTypeStats } from '@/api/research'

// State
const loading = ref(false)
const surveyData = ref<SurveyItem[]>([])
const hotStocks = ref<HotSurveyedStock[]>([])
const orgStats = ref<OrgTypeStats[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchKeyword = ref('')
const selectedDate = ref('')
const activeView = ref<'date' | 'hot' | 'search'>('hot')

// Columns for survey table
const surveyColumns = computed(() => [
  { colKey: 'ts_code', title: '股票代码', width: 100 },
  { colKey: 'name', title: '股票名称', width: 100 },
  { colKey: 'surv_date', title: '调研日期', width: 110 },
  { colKey: 'org_type', title: '机构类型', width: 100 },
  { colKey: 'total_visitors', title: '参与人数', width: 90 },
  { colKey: 'rece_mode', title: '接待方式', width: 100 },
  { colKey: 'rece_place', title: '接待地点', width: 120, ellipsis: true },
  { colKey: 'rece_org', title: '接待机构', width: 150, ellipsis: true },
  { colKey: 'content', title: '调研内容', ellipsis: true }
])

// Columns for hot stocks table
const hotStocksColumns = computed(() => [
  { colKey: 'index', title: '排名', width: 60 },
  { colKey: 'ts_code', title: '股票代码', width: 100 },
  { colKey: 'name', title: '股票名称', width: 100 },
  { colKey: 'survey_count', title: '调研次数', width: 90 },
  { colKey: 'unique_org_count', title: '机构数', width: 80 },
  { colKey: 'latest_survey_date', title: '最新调研', width: 110 },
  { colKey: 'org_types', title: '机构类型', ellipsis: true }
])

// Format date for display
const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-'
  if (dateStr.length === 8) {
    return dateStr.replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3')
  }
  return dateStr
}

// Load hot surveyed stocks
const loadHotStocks = async () => {
  loading.value = true
  try {
    const res = await researchApi.getHotSurveyedStocks(30, 30)
    hotStocks.value = res.data || []
    // Load org type stats as well
    const statsRes = await researchApi.getOrgTypeStats(undefined, 30)
    orgStats.value = statsRes.data || []
  } catch (error) {
    console.error('Failed to load hot surveyed stocks:', error)
    hotStocks.value = []
  } finally {
    loading.value = false
  }
}

// Load surveys by date
const loadSurveysByDate = async () => {
  if (!selectedDate.value) return
  loading.value = true
  try {
    const dateStr = selectedDate.value.replace(/-/g, '')
    const res = await researchApi.getSurveysByDate(dateStr, page.value, pageSize.value)
    surveyData.value = res.data || []
    total.value = res.total || 0
  } catch (error) {
    console.error('Failed to load surveys by date:', error)
    surveyData.value = []
  } finally {
    loading.value = false
  }
}

// Search surveys
const handleSearch = async () => {
  if (!searchKeyword.value.trim()) return
  loading.value = true
  activeView.value = 'search'
  try {
    const res = await researchApi.searchSurveyContent(searchKeyword.value.trim(), 90, page.value, pageSize.value)
    surveyData.value = res.data || []
    total.value = res.total || 0
  } catch (error) {
    console.error('Failed to search surveys:', error)
    surveyData.value = []
  } finally {
    loading.value = false
  }
}

// Handle date change
const handleDateChange = (val: string) => {
  selectedDate.value = val
  activeView.value = 'date'
  page.value = 1
  loadSurveysByDate()
}

// Handle page change
const handlePageChange = (pageInfo: { current: number; pageSize: number }) => {
  page.value = pageInfo.current
  pageSize.value = pageInfo.pageSize
  if (activeView.value === 'date') {
    loadSurveysByDate()
  } else if (activeView.value === 'search') {
    handleSearch()
  }
}

// View stock surveys
const viewStockSurveys = async (tsCode: string) => {
  loading.value = true
  activeView.value = 'search'
  try {
    const res = await researchApi.getSurveysByStock(tsCode, 180, 1, 50)
    surveyData.value = res.data || []
    total.value = res.total || 0
    searchKeyword.value = tsCode
  } catch (error) {
    console.error('Failed to load stock surveys:', error)
  } finally {
    loading.value = false
  }
}

// Switch to hot view
const switchToHot = () => {
  activeView.value = 'hot'
  searchKeyword.value = ''
  selectedDate.value = ''
}

onMounted(() => {
  loadHotStocks()
})
</script>

<template>
  <div class="survey-panel">
    <!-- Filter bar -->
    <div class="filter-bar">
      <t-space>
        <t-button 
          :theme="activeView === 'hot' ? 'primary' : 'default'"
          @click="switchToHot"
        >
          热门调研
        </t-button>
        <t-date-picker
          v-model="selectedDate"
          placeholder="选择日期"
          clearable
          @change="handleDateChange"
        />
        <t-input
          v-model="searchKeyword"
          placeholder="搜索股票/内容"
          style="width: 200px"
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
          <t-card title="热门调研股票" size="small" :bordered="false">
            <template #subtitle>
              <span class="card-subtitle">近30天调研热度排行</span>
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
                <t-link theme="primary" @click="viewStockSurveys(row.ts_code)">
                  {{ row.ts_code }}
                </t-link>
              </template>
              <template #latest_survey_date="{ row }">
                {{ formatDate(row.latest_survey_date) }}
              </template>
              <template #org_types="{ row }">
                <t-space size="small" v-if="row.org_types?.length">
                  <t-tag v-for="org in row.org_types.slice(0, 3)" :key="org" size="small" variant="light">
                    {{ org }}
                  </t-tag>
                  <span v-if="row.org_types.length > 3" class="more-tag">+{{ row.org_types.length - 3 }}</span>
                </t-space>
                <span v-else>-</span>
              </template>
            </t-table>
          </t-card>
        </t-col>

        <!-- Org type stats -->
        <t-col :span="4">
          <t-card title="机构类型分布" size="small" :bordered="false">
            <template #subtitle>
              <span class="card-subtitle">近30天统计</span>
            </template>
            <div class="org-stats">
              <div 
                v-for="stat in orgStats" 
                :key="stat.org_type" 
                class="stat-item"
              >
                <div class="stat-label">{{ stat.org_type || '其他' }}</div>
                <t-progress 
                  :percentage="stat.percentage" 
                  theme="plump"
                  size="small"
                />
                <div class="stat-count">{{ stat.count }}次</div>
              </div>
              <div v-if="orgStats.length === 0 && !loading" class="empty-stats">
                暂无数据
              </div>
            </div>
          </t-card>
        </t-col>
      </t-row>
    </div>

    <!-- Survey list view (date/search) -->
    <div v-else class="content-section">
      <t-card size="small" :bordered="false">
        <template #title>
          <span v-if="activeView === 'date'">
            {{ formatDate(selectedDate) }} 调研记录
          </span>
          <span v-else>
            搜索结果: {{ searchKeyword }}
          </span>
        </template>
        <template #actions>
          <t-button variant="text" @click="switchToHot">
            <t-icon name="chevron-left" /> 返回热门
          </t-button>
        </template>
        <t-table
          :data="surveyData"
          :columns="surveyColumns"
          :loading="loading"
          row-key="ts_code"
          size="small"
          :max-height="500"
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
          <template #surv_date="{ row }">
            {{ formatDate(row.surv_date) }}
          </template>
          <template #content="{ row }">
            <t-tooltip v-if="row.content" :content="row.content" placement="top-left">
              <span class="content-cell">{{ row.content }}</span>
            </t-tooltip>
            <span v-else>-</span>
          </template>
        </t-table>
      </t-card>
    </div>
  </div>
</template>

<style scoped>
.survey-panel {
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
}

.card-subtitle {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.org-stats {
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
  min-width: 60px;
  font-size: 13px;
  color: var(--td-text-color-primary);
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

.more-tag {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.content-cell {
  display: block;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.t-progress__inner) {
  border-radius: 4px;
}
</style>
