<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { newsAPI } from '@/api/news'
import type { NewsItem } from '@/types/news'

interface HotCoveredStock {
  ts_code: string
  report_count: number
  unique_org_count: number
  latest_report_date: string
}

interface TypeDistribution {
  report_type: string
  count: number
  percentage: number
}

const loading = ref(false)
const allReports = ref<NewsItem[]>([])
const partial = ref(false)
const failedSources = ref<string[]>([])

const page = ref(1)
const pageSize = ref(20)
const searchStock = ref('')
const selectedDate = ref('')
const selectedReportType = ref('')
const selectedInstitution = ref('')
const activeView = ref<'hot' | 'list'>('hot')
const selectedStockCode = ref('')

const FILTER_STORAGE_KEY = 'news-research-filters-v1'

const normalizeStockCode = (code: string) => {
  const normalized = code.trim().toUpperCase()
  if (/^\d{6}$/.test(normalized)) {
    if (normalized.startsWith('6') || normalized.startsWith('9')) return `${normalized}.SH`
    return `${normalized}.SZ`
  }
  if (/^\d{5}$/.test(normalized)) return `${normalized}.HK`
  return normalized
}

const formatDate = (value?: string) => {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('zh-CN', { hour12: false })
}

const getPrimaryCode = (item: NewsItem) => item.stock_codes?.[0] || '-'

const getInstitution = (item: NewsItem) => {
  const match = item.content?.match(/机构:\s*([^\n]+)/)
  return match?.[1]?.trim() || '-'
}

const getReportType = (item: NewsItem) => {
  const typeVal = (item as any)?.sentiment_reasoning
  return typeof typeVal === 'string' && typeVal.trim() ? typeVal.trim() : '未分类'
}

const filteredReports = computed(() => {
  return allReports.value.filter((item) => {
    if (selectedReportType.value && getReportType(item) !== selectedReportType.value) return false
    if (selectedInstitution.value && getInstitution(item) !== selectedInstitution.value) return false
    return true
  })
})

const total = computed(() => filteredReports.value.length)

const pagedReports = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredReports.value.slice(start, start + pageSize.value)
})

const reportTypeOptions = computed(() => {
  const set = new Set<string>()
  allReports.value.forEach((item) => set.add(getReportType(item)))
  return Array.from(set).map((v) => ({ label: v, value: v }))
})

const institutionOptions = computed(() => {
  const set = new Set<string>()
  allReports.value.forEach((item) => {
    const org = getInstitution(item)
    if (org && org !== '-') set.add(org)
  })
  return Array.from(set).map((v) => ({ label: v, value: v }))
})

const hotStocks = computed<HotCoveredStock[]>(() => {
  const map = new Map<string, { count: number; orgSet: Set<string>; latest: string }>()
  allReports.value.forEach((item) => {
    const code = getPrimaryCode(item)
    if (!code || code === '-') return
    const current = map.get(code) || { count: 0, orgSet: new Set<string>(), latest: '' }
    current.count += 1
    const org = getInstitution(item)
    if (org && org !== '-') current.orgSet.add(org)
    if (!current.latest || new Date(item.publish_time).getTime() > new Date(current.latest).getTime()) {
      current.latest = item.publish_time
    }
    map.set(code, current)
  })

  return Array.from(map.entries())
    .map(([ts_code, val]) => ({
      ts_code,
      report_count: val.count,
      unique_org_count: val.orgSet.size,
      latest_report_date: val.latest
    }))
    .sort((a, b) => b.report_count - a.report_count)
    .slice(0, 30)
})

const typeDistribution = computed<TypeDistribution[]>(() => {
  const map = new Map<string, number>()
  allReports.value.forEach((item) => {
    const key = getReportType(item)
    map.set(key, (map.get(key) || 0) + 1)
  })
  const countTotal = allReports.value.length || 1
  return Array.from(map.entries())
    .map(([report_type, count]) => ({ report_type, count, percentage: Math.round((count * 10000) / countTotal) / 100 }))
    .sort((a, b) => b.count - a.count)
})

const reportColumns = [
  { colKey: 'publish_time', title: '发布时间', width: 170 },
  { colKey: 'stock_code', title: '股票代码', width: 110 },
  { colKey: 'report_type', title: '研报类型', width: 110 },
  { colKey: 'author', title: '作者', width: 120 },
  { colKey: 'institution', title: '机构', width: 160, ellipsis: true },
  { colKey: 'title', title: '标题', ellipsis: true, minWidth: 260 },
  { colKey: 'abstract', title: '摘要', ellipsis: true, minWidth: 260 },
  { colKey: 'url', title: '链接', width: 90 }
]

const hotColumns = [
  { colKey: 'index', title: '排名', width: 70 },
  { colKey: 'ts_code', title: '股票代码', width: 110 },
  { colKey: 'report_count', title: '研报数', width: 100 },
  { colKey: 'unique_org_count', title: '机构数', width: 100 },
  { colKey: 'latest_report_date', title: '最新发布时间' }
]

const loadReports = async (params?: {
  ts_code?: string
  trade_date?: string
  report_type?: string
  inst_csname?: string
}) => {
  loading.value = true
  try {
    const resp = await newsAPI.getResearchReports({
      ts_code: params?.ts_code,
      trade_date: params?.trade_date,
      report_type: params?.report_type,
      inst_csname: params?.inst_csname,
      limit: 500
    })
    allReports.value = resp.data || []
    partial.value = !!resp.partial
    failedSources.value = resp.failed_sources || []
    page.value = 1
  } catch (error) {
    console.error('Failed to load research reports:', error)
    allReports.value = []
    partial.value = true
    failedSources.value = ['tushare_research']
  } finally {
    loading.value = false
  }
}

const handleDateChange = async (val: string) => {
  selectedDate.value = val
  selectedStockCode.value = ''
  searchStock.value = ''
  activeView.value = 'list'
  const tradeDate = val ? val.replace(/-/g, '') : undefined
  await loadReports({
    trade_date: tradeDate,
    report_type: selectedReportType.value || undefined,
    inst_csname: selectedInstitution.value || undefined
  })
}

const handleSearch = async () => {
  if (!searchStock.value.trim()) return
  const normalized = normalizeStockCode(searchStock.value)
  selectedStockCode.value = normalized
  selectedDate.value = ''
  activeView.value = 'list'
  await loadReports({
    ts_code: normalized,
    report_type: selectedReportType.value || undefined,
    inst_csname: selectedInstitution.value || undefined
  })
}

const loadStockFromHot = async (tsCode: string) => {
  searchStock.value = tsCode
  await handleSearch()
}

const reloadWithCurrentContext = async () => {
  const baseParams = {
    report_type: selectedReportType.value || undefined,
    inst_csname: selectedInstitution.value || undefined
  }
  if (selectedStockCode.value) {
    await loadReports({ ts_code: selectedStockCode.value, ...baseParams })
    return
  }
  if (selectedDate.value) {
    await loadReports({ trade_date: selectedDate.value.replace(/-/g, ''), ...baseParams })
    return
  }
  await loadReports(baseParams)
}

const switchToHot = async () => {
  activeView.value = 'hot'
  selectedStockCode.value = ''
  selectedDate.value = ''
  searchStock.value = ''
  await loadReports({
    report_type: selectedReportType.value || undefined,
    inst_csname: selectedInstitution.value || undefined
  })
}

const handlePageChange = (info: { current: number; pageSize: number }) => {
  page.value = info.current
  pageSize.value = info.pageSize
}

const saveFilterMemory = () => {
  try {
    localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify({
      reportType: selectedReportType.value,
      institution: selectedInstitution.value
    }))
  } catch (e) {
    console.warn('save research filter memory failed', e)
  }
}

const restoreFilterMemory = () => {
  try {
    const raw = localStorage.getItem(FILTER_STORAGE_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw) as { reportType?: string; institution?: string }
    selectedReportType.value = parsed.reportType || ''
    selectedInstitution.value = parsed.institution || ''
  } catch (e) {
    console.warn('restore research filter memory failed', e)
  }
}

watch([selectedReportType, selectedInstitution], () => {
  page.value = 1
  saveFilterMemory()
})

onMounted(async () => {
  restoreFilterMemory()
  await loadReports({
    report_type: selectedReportType.value || undefined,
    inst_csname: selectedInstitution.value || undefined
  })
})
</script>

<template>
  <div class="report-panel">
    <t-alert
      v-if="partial"
      theme="warning"
      :message="`研报数据部分拉取失败：${failedSources.join('、')}`"
      class="partial-alert"
      close
    />

    <div class="filter-bar">
      <t-space>
        <t-button :theme="activeView === 'hot' ? 'primary' : 'default'" @click="switchToHot">
          热门覆盖
        </t-button>
        <t-date-picker
          v-model="selectedDate"
          placeholder="按日期筛选"
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
        <t-select
          v-model="selectedReportType"
          clearable
          placeholder="研报类型"
          style="width: 180px"
          :options="reportTypeOptions"
          @change="reloadWithCurrentContext"
        />
        <t-select
          v-model="selectedInstitution"
          clearable
          filterable
          placeholder="机构"
          style="width: 220px"
          :options="institutionOptions"
          @change="reloadWithCurrentContext"
        />
      </t-space>
    </div>

    <div v-if="activeView === 'hot'" class="content-section">
      <t-row :gutter="16">
        <t-col :span="8">
          <t-card title="热门覆盖股票" size="small" :bordered="false">
            <t-table
              :data="hotStocks"
              :columns="hotColumns"
              :loading="loading"
              row-key="ts_code"
              size="small"
              :max-height="500"
            >
              <template #index="{ rowIndex }">
                <t-tag size="small" :theme="rowIndex < 3 ? 'primary' : 'default'">{{ rowIndex + 1 }}</t-tag>
              </template>
              <template #ts_code="{ row }">
                <t-link theme="primary" @click="loadStockFromHot(row.ts_code)">{{ row.ts_code }}</t-link>
              </template>
              <template #latest_report_date="{ row }">{{ formatDate(row.latest_report_date) }}</template>
            </t-table>
          </t-card>
        </t-col>

        <t-col :span="4">
          <t-card title="研报类型分布" size="small" :bordered="false">
            <div class="type-stats">
              <div v-for="item in typeDistribution" :key="item.report_type" class="type-item">
                <div class="type-label">{{ item.report_type }}</div>
                <t-progress :percentage="item.percentage" size="small" theme="success" />
                <div class="type-count">{{ item.count }} 份</div>
              </div>
              <div v-if="typeDistribution.length === 0 && !loading" class="empty-stats">暂无数据</div>
            </div>
          </t-card>
        </t-col>
      </t-row>
    </div>

    <div v-else class="content-section">
      <t-card size="small" :bordered="false">
        <template #title>
          <span v-if="selectedDate">{{ selectedDate }} 研报列表</span>
          <span v-else>{{ selectedStockCode }} 研报列表</span>
        </template>
        <template #actions>
          <t-button variant="text" @click="switchToHot">
            <t-icon name="chevron-left" /> 返回热门
          </t-button>
        </template>

        <t-table
          :data="pagedReports"
          :columns="reportColumns"
          :loading="loading"
          row-key="id"
          size="small"
          :max-height="460"
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
          <template #publish_time="{ row }">{{ formatDate(row.publish_time) }}</template>
          <template #stock_code="{ row }">{{ getPrimaryCode(row) }}</template>
          <template #report_type="{ row }">{{ getReportType(row) }}</template>
          <template #author="{ row }">{{ row.author || '-' }}</template>
          <template #institution="{ row }">{{ getInstitution(row) }}</template>
          <template #title="{ row }">
            <t-tooltip :content="row.title" placement="top-left">
              <span class="title-cell">{{ row.title }}</span>
            </t-tooltip>
          </template>
          <template #abstract="{ row }">
            <t-tooltip :content="row.abstract || row.content" placement="top-left">
              <span class="title-cell">{{ row.abstract || row.content || '-' }}</span>
            </t-tooltip>
          </template>
          <template #url="{ row }">
            <t-link v-if="row.url" :href="row.url" target="_blank">查看</t-link>
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

.partial-alert {
  margin-bottom: 4px;
}

.filter-bar {
  display: flex;
  align-items: center;
}

.content-section {
  min-height: 400px;
}

.type-stats {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.type-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.type-label {
  min-width: 72px;
  font-size: 12px;
}

.type-count {
  min-width: 54px;
  text-align: right;
  color: var(--td-text-color-secondary);
  font-size: 12px;
}

.empty-stats {
  color: var(--td-text-color-placeholder);
  text-align: center;
  padding: 24px 0;
}

.title-cell {
  display: block;
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
