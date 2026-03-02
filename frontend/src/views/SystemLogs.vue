<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  systemLogsApi,
  type ErrorClusterItem,
  type LogAnalysisResponse,
  type LogEntry,
  type LogFilter,
  type LogStatsResponse,
  type OperationTimelineItem
} from '@/api/systemLogs'
import { MessagePlugin } from 'tdesign-vue-next'
import OverviewCards from '@/components/system-logs/OverviewCards.vue'
import ErrorClusterPanel from '@/components/system-logs/ErrorClusterPanel.vue'
import OperationTimeline from '@/components/system-logs/OperationTimeline.vue'
import AiDiagnosisDrawer from '@/components/system-logs/AiDiagnosisDrawer.vue'

const filter = ref<LogFilter>({
  level: undefined,
  start_time: undefined,
  end_time: undefined,
  keyword: undefined,
  page: 1,
  page_size: 100
})
const windowHours = ref(2)

const logs = ref<LogEntry[]>([])
const total = ref(0)
const loading = ref(false)
const loadingMore = ref(false)
const hasMore = ref(true)

const stats = ref<LogStatsResponse | null>(null)
const clusters = ref<ErrorClusterItem[]>([])
const timeline = ref<OperationTimelineItem[]>([])
const insightLoading = ref(false)

const showAnalysisDrawer = ref(false)
const analysisResult = ref<LogAnalysisResponse | null>(null)
const analyzing = ref(false)

const showArchiveDialog = ref(false)
const archiving = ref(false)
const archiveRetentionDays = ref(30)

const levelOptions = [
  { label: '全部', value: undefined },
  { label: 'INFO', value: 'INFO' },
  { label: 'WARNING', value: 'WARNING' },
  { label: 'ERROR', value: 'ERROR' }
]

const windowOptions = [
  { label: '最近30分钟', value: 1 },
  { label: '最近2小时', value: 2 },
  { label: '最近6小时', value: 6 },
  { label: '最近24小时', value: 24 }
]

const sortedLogs = computed(() => [...logs.value].sort((a, b) => +new Date(b.timestamp) - +new Date(a.timestamp)))
const formatLogText = (log: LogEntry) => log.raw_line || `${log.timestamp} [${log.level}] [${log.module}] ${log.message}`

const getInsightParams = () => ({ ...filter.value, window_hours: windowHours.value })

const fetchLogs = async () => {
  loading.value = true
  try {
    filter.value.page = 1
    const response = await systemLogsApi.getLogs(filter.value)
    logs.value = response.logs
    total.value = response.total
    hasMore.value = response.logs.length === filter.value.page_size
  } finally {
    loading.value = false
  }
}

const loadMore = async () => {
  if (loadingMore.value || !hasMore.value) return
  loadingMore.value = true
  try {
    filter.value.page = (filter.value.page || 1) + 1
    const response = await systemLogsApi.getLogs(filter.value)
    logs.value = [...logs.value, ...response.logs]
    hasMore.value = response.logs.length === filter.value.page_size
  } finally {
    loadingMore.value = false
  }
}

const fetchInsights = async () => {
  insightLoading.value = true
  try {
    const params = getInsightParams()
    const [statsRes, clusterRes, timelineRes] = await Promise.all([
      systemLogsApi.getStats(params),
      systemLogsApi.getClusters({ ...params, limit: 10 }),
      systemLogsApi.getTimeline({ ...params, limit: 30 })
    ])
    stats.value = statsRes
    clusters.value = clusterRes.clusters
    timeline.value = timelineRes.items
  } finally {
    insightLoading.value = false
  }
}

const fetchAll = async () => {
  await Promise.all([fetchLogs(), fetchInsights()])
}

const handleFilter = () => {
  fetchAll()
}

const handleReset = () => {
  filter.value = {
    level: undefined,
    start_time: undefined,
    end_time: undefined,
    keyword: undefined,
    page: 1,
    page_size: 100
  }
  windowHours.value = 2
  fetchAll()
}

const handleClusterSelect = (signature: string) => {
  filter.value.keyword = signature
  fetchAll()
}

const handleAnalyze = async () => {
  showAnalysisDrawer.value = true
  analyzing.value = true
  analysisResult.value = null
  try {
    const selected = logs.value.filter((item) => item.level === 'ERROR').slice(0, 50)
    analysisResult.value = await systemLogsApi.analyzeLogs({
      log_entries: selected,
      user_query: '请结合最近日志与操作，定位根因并给出修复建议与影响范围',
      default_window_hours: windowHours.value,
      include_code_context: true,
      max_entries: 50
    })
  } catch {
    MessagePlugin.error('AI 诊断失败，已切换规则分析')
  } finally {
    analyzing.value = false
  }
}

const handleArchive = async () => {
  archiving.value = true
  try {
    const response = await systemLogsApi.archiveLogs(archiveRetentionDays.value)
    MessagePlugin.success(`已归档 ${response.archived_count} 个文件`)
    showArchiveDialog.value = false
    fetchAll()
  } finally {
    archiving.value = false
  }
}

const handleExport = async (format: 'csv' | 'json') => {
  try {
    const blob = await systemLogsApi.exportLogs({ ...filter.value, format })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `logs_export_${new Date().toISOString().slice(0, 19).replace(/[-T:]/g, '')}.${format}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    MessagePlugin.success('导出成功')
  } catch {
    MessagePlugin.error('导出失败')
  }
}

const handleCopy = (log: LogEntry) => {
  navigator.clipboard.writeText(formatLogText(log))
  MessagePlugin.success('已复制到剪贴板')
}

onMounted(() => {
  fetchAll()
})
</script>

<template>
  <div class="system-logs-view">
    <t-card title="系统日志可观测工作台" :bordered="false" class="mb-4">
      <t-form layout="inline">
        <t-form-item label="级别">
          <t-select v-model="filter.level" :options="levelOptions" style="width: 120px" clearable />
        </t-form-item>
        <t-form-item label="开始时间">
          <t-date-picker v-model="filter.start_time" enable-time-picker format="YYYY-MM-DD HH:mm:ss" style="width: 220px" />
        </t-form-item>
        <t-form-item label="结束时间">
          <t-date-picker v-model="filter.end_time" enable-time-picker format="YYYY-MM-DD HH:mm:ss" style="width: 220px" />
        </t-form-item>
        <t-form-item label="关键词">
          <t-input v-model="filter.keyword" placeholder="模块/错误签名/关键字" style="width: 220px" clearable />
        </t-form-item>
        <t-form-item label="分析窗口">
          <t-select v-model="windowHours" :options="windowOptions" style="width: 140px" />
        </t-form-item>
        <t-form-item>
          <t-space>
            <t-button theme="primary" @click="handleFilter">查询</t-button>
            <t-button variant="outline" @click="handleReset">重置</t-button>
            <t-button theme="warning" variant="outline" :loading="analyzing" @click="handleAnalyze">一键AI诊断</t-button>
          </t-space>
        </t-form-item>
      </t-form>
      <t-space class="mt-3">
        <t-button size="small" variant="outline" @click="handleExport('csv')">导出 CSV</t-button>
        <t-button size="small" variant="outline" @click="handleExport('json')">导出 JSON</t-button>
        <t-button size="small" variant="outline" @click="showArchiveDialog = true">归档日志</t-button>
      </t-space>
    </t-card>

    <OverviewCards :stats="stats" :loading="insightLoading" />

    <t-row :gutter="16" class="mt-4">
      <t-col :span="4">
        <ErrorClusterPanel :clusters="clusters" :loading="insightLoading" @select="handleClusterSelect" />
      </t-col>
      <t-col :span="8">
        <OperationTimeline :items="timeline" :loading="insightLoading" />
      </t-col>
    </t-row>

    <t-card title="系统日志明细" :bordered="false" class="mt-4">
      <div v-if="loading && !logs.length" class="center">
        <t-loading text="加载中..." />
      </div>
      <div v-else>
        <div class="logs-text-container">
          <div v-for="log in sortedLogs" :key="`${log.timestamp}-${log.message}`" class="log-line-wrapper">
            <span class="log-line">{{ formatLogText(log) }}</span>
            <t-button size="small" variant="text" @click="handleCopy(log)" class="copy-button">复制</t-button>
          </div>
        </div>
        <div class="center mt-4" v-if="hasMore && logs.length > 0">
          <t-button :loading="loadingMore" @click="loadMore">加载更多</t-button>
        </div>
        <div class="center mt-4 text-gray-400 text-xs" v-else-if="logs.length > 0">共 {{ total }} 条，已加载完毕</div>
      </div>
    </t-card>

    <AiDiagnosisDrawer v-model:visible="showAnalysisDrawer" :loading="analyzing" :result="analysisResult" />

    <t-dialog v-model:visible="showArchiveDialog" header="归档日志" @confirm="handleArchive" :confirm-btn="{ loading: archiving }">
      <t-form layout="vertical">
        <t-form-item label="保留天数">
          <t-input-number v-model="archiveRetentionDays" :min="1" :max="365" style="width: 200px" />
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<style scoped>
.system-logs-view { padding: 16px; }
.logs-text-container {
  background: linear-gradient(180deg, #0b1220 0%, #111827 100%);
  color: #e5e7eb;
  padding: 14px;
  border-radius: 10px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
  max-height: 520px;
  overflow-y: auto;
}
.log-line-wrapper { display: flex; align-items: flex-start; padding: 2px 0; }
.log-line { flex: 1; white-space: pre-wrap; word-wrap: break-word; }
.copy-button { margin-left: 8px; opacity: 0; }
.log-line-wrapper:hover .copy-button { opacity: 1; }
.center { text-align: center; padding: 22px; }
.mt-3 { margin-top: 12px; }
.mt-4 { margin-top: 16px; }
.mb-4 { margin-bottom: 16px; }
.text-gray-400 { color: #9ca3af; }
.text-xs { font-size: 12px; }
</style>
