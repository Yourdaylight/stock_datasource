<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import {
  systemLogsApi,
  type ErrorClusterItem,
  type LogAnalysisResponse,
  type LogEntry,
  type LogFilter,
  type LogStatsResponse,
  type OperationTimelineItem
} from '@/api/systemLogs'
import DataEmptyGuide from '@/components/DataEmptyGuide.vue'
import OverviewCards from '@/components/system-logs/OverviewCards.vue'
import ErrorClusterPanel from '@/components/system-logs/ErrorClusterPanel.vue'
import OperationTimeline from '@/components/system-logs/OperationTimeline.vue'
import AiDiagnosisDrawer from '@/components/system-logs/AiDiagnosisDrawer.vue'

interface PanelState {
  loading: boolean
  error: string
  ready: boolean
}

const windowHours = ref(2)

const pad = (value: number) => String(value).padStart(2, '0')
const formatDateTime = (date: Date) => {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

const buildTimeRange = (hours: number) => {
  const end = new Date()
  const start = new Date(end.getTime() - hours * 60 * 60 * 1000)
  return {
    start_time: formatDateTime(start),
    end_time: formatDateTime(end)
  }
}

const createDefaultFilter = (): LogFilter => ({
  level: undefined,
  keyword: undefined,
  request_id: undefined,
  page: 1,
  page_size: 50,
  ...buildTimeRange(windowHours.value)
})

const createPanelState = (): PanelState => ({
  loading: false,
  error: '',
  ready: false
})

const filter = ref<LogFilter>(createDefaultFilter())

const logs = ref<LogEntry[]>([])
const total = ref(0)
const logsLoading = ref(false)
const logsLoadingMore = ref(false)
const logsError = ref('')
const hasMore = ref(true)

const stats = ref<LogStatsResponse | null>(null)
const clusters = ref<ErrorClusterItem[]>([])
const timeline = ref<OperationTimelineItem[]>([])

const statsState = ref<PanelState>(createPanelState())
const clustersState = ref<PanelState>(createPanelState())
const timelineState = ref<PanelState>(createPanelState())

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

const levelThemeMap: Record<string, 'danger' | 'warning' | 'primary'> = {
  ERROR: 'danger',
  WARNING: 'warning',
  INFO: 'primary'
}

let logRequestSeq = 0
let insightRequestSeq = 0
let insightTimer: number | null = null

const isRequestFocused = computed(() => Boolean(filter.value.request_id && filter.value.request_id.trim()))
const hasInsightErrors = computed(() => Boolean(statsState.value.error || clustersState.value.error || timelineState.value.error))
const insightLoading = computed(() => statsState.value.loading || clustersState.value.loading || timelineState.value.loading)

const activeWindowLabel = computed(() => {
  const matched = windowOptions.find((item) => item.value === windowHours.value)
  return matched?.label || `最近${windowHours.value}小时`
})

const statusTheme = computed(() => {
  if (logsError.value) return 'error'
  if (hasInsightErrors.value) return 'warning'
  if (insightLoading.value) return 'info'
  return 'success'
})

const statusMessage = computed(() => {
  if (logsError.value) return `日志加载失败：${logsError.value}`
  if (isRequestFocused.value && timelineState.value.loading) {
    return '已切换到 Request ID 模式，正在补全请求链路。'
  }
  if (insightLoading.value) {
    return `日志流已就绪，分析面板正在后台加载。当前窗口：${activeWindowLabel.value}。`
  }
  if (hasInsightErrors.value) {
    return '日志明细仍可继续使用，但部分分析面板暂时不可用。你可以稍后重试分析面板。'
  }
  if (isRequestFocused.value) {
    return '当前正在按 Request ID 聚焦查看，请求链路会优先显示。'
  }
  return '系统日志工作台已就绪。你可以先排障，再按需查看聚类、时间线和 AI 诊断。'
})

const analysisEntries = computed(() => {
  if (isRequestFocused.value) {
    return logs.value.slice(0, 20)
  }

  const errorLogs = logs.value.filter((item) => item.level === 'ERROR')
  return (errorLogs.length ? errorLogs : logs.value).slice(0, 30)
})

const resetPanelState = (panel: typeof statsState) => {
  panel.value = createPanelState()
}

const getLevelTheme = (level: string) => levelThemeMap[level] || 'primary'

const getErrorMessage = (error: unknown) => {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  const message = (error as { message?: string })?.message
  return detail || message || '请求失败'
}

const formatLogText = (log: LogEntry) => {
  if (log.raw_line) return log.raw_line
  const reqId = log.request_id && log.request_id !== '-' ? ` [${log.request_id}]` : ''
  return `${log.timestamp} [${log.level}]${reqId} [${log.module}] ${log.message}`
}

const clearInsightTimer = () => {
  if (insightTimer !== null) {
    window.clearTimeout(insightTimer)
    insightTimer = null
  }
}

const getInsightParams = () => ({ ...filter.value, window_hours: windowHours.value })

const scheduleInsights = () => {
  clearInsightTimer()
  insightTimer = window.setTimeout(() => {
    void loadInsights()
  }, 120)
}

const fetchLogs = async (append = false) => {
  const seq = ++logRequestSeq
  const nextPage = append ? (filter.value.page || 1) + 1 : 1
  const params = { ...filter.value, page: nextPage }

  if (append) {
    logsLoadingMore.value = true
  } else {
    logsLoading.value = true
    logsError.value = ''
  }

  try {
    const response = await systemLogsApi.getLogs(params)
    if (seq !== logRequestSeq) return

    filter.value.page = nextPage
    logs.value = append ? [...logs.value, ...response.logs] : response.logs
    total.value = response.total
    hasMore.value = response.logs.length === (filter.value.page_size || 50) && logs.value.length < response.total

    if (!append) {
      scheduleInsights()
    }
  } catch (error) {
    if (seq !== logRequestSeq) return
    logsError.value = getErrorMessage(error)
    if (!append) {
      logs.value = []
      total.value = 0
      hasMore.value = false
    }
  } finally {
    if (seq === logRequestSeq) {
      logsLoading.value = false
      logsLoadingMore.value = false
    }
  }
}

const fetchStatsPanel = async (seq: number) => {
  statsState.value = { loading: true, error: '', ready: false }
  try {
    const result = await systemLogsApi.getStats(getInsightParams())
    if (seq !== insightRequestSeq) return
    stats.value = result
    statsState.value = { loading: false, error: '', ready: true }
  } catch (error) {
    if (seq !== insightRequestSeq) return
    stats.value = null
    statsState.value = { loading: false, error: getErrorMessage(error), ready: false }
  }
}

const fetchClustersPanel = async (seq: number) => {
  clustersState.value = { loading: true, error: '', ready: false }
  try {
    const result = await systemLogsApi.getClusters({ ...getInsightParams(), limit: 10 })
    if (seq !== insightRequestSeq) return
    clusters.value = result.clusters
    clustersState.value = { loading: false, error: '', ready: true }
  } catch (error) {
    if (seq !== insightRequestSeq) return
    clusters.value = []
    clustersState.value = { loading: false, error: getErrorMessage(error), ready: false }
  }
}

const fetchTimelinePanel = async (seq: number) => {
  timelineState.value = { loading: true, error: '', ready: false }
  try {
    const result = await systemLogsApi.getTimeline({ ...getInsightParams(), limit: isRequestFocused.value ? 40 : 30 })
    if (seq !== insightRequestSeq) return
    timeline.value = result.items
    timelineState.value = { loading: false, error: '', ready: true }
  } catch (error) {
    if (seq !== insightRequestSeq) return
    timeline.value = []
    timelineState.value = { loading: false, error: getErrorMessage(error), ready: false }
  }
}

const loadInsights = async () => {
  const seq = ++insightRequestSeq
  clearInsightTimer()

  if (isRequestFocused.value) {
    stats.value = null
    clusters.value = []
    resetPanelState(statsState)
    resetPanelState(clustersState)
    await fetchTimelinePanel(seq)
    return
  }

  await Promise.allSettled([
    fetchStatsPanel(seq),
    fetchClustersPanel(seq),
    fetchTimelinePanel(seq)
  ])
}

const applyWindowPreset = (hours: number) => {
  windowHours.value = hours
  const range = buildTimeRange(hours)
  filter.value.start_time = range.start_time
  filter.value.end_time = range.end_time
}

const handleFilter = async () => {
  await fetchLogs(false)
}

const handleReset = async () => {
  windowHours.value = 2
  filter.value = createDefaultFilter()
  stats.value = null
  clusters.value = []
  timeline.value = []
  resetPanelState(statsState)
  resetPanelState(clustersState)
  resetPanelState(timelineState)
  await fetchLogs(false)
}

const loadMore = async () => {
  if (logsLoadingMore.value || !hasMore.value) return
  await fetchLogs(true)
}

const handleClusterSelect = async (signature: string) => {
  filter.value.keyword = signature
  await fetchLogs(false)
}

const focusRequest = async (requestId?: string) => {
  if (!requestId || requestId === '-') return
  filter.value.request_id = requestId
  await fetchLogs(false)
}

const clearRequestFocus = async () => {
  if (!filter.value.request_id) return
  filter.value.request_id = undefined
  await fetchLogs(false)
}

const handleAnalyze = async () => {
  if (!analysisEntries.value.length) {
    MessagePlugin.warning('当前上下文没有可分析的日志，请先筛选出需要排查的日志。')
    return
  }

  showAnalysisDrawer.value = true
  analyzing.value = true
  analysisResult.value = null
  try {
    analysisResult.value = await systemLogsApi.analyzeLogs({
      log_entries: analysisEntries.value,
      user_query: isRequestFocused.value
        ? '请围绕当前 Request ID 的链路定位根因、影响范围与修复建议'
        : '请优先分析当前筛选窗口中的异常日志，给出根因、影响范围和修复建议',
      default_window_hours: windowHours.value,
      include_code_context: true,
      max_entries: Math.min(analysisEntries.value.length, 30)
    })
  } catch {
    MessagePlugin.error('AI 诊断失败，请先根据时间线与日志明细继续排查。')
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
    await fetchLogs(false)
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

const handleCopy = async (text: string, successMessage: string) => {
  try {
    await navigator.clipboard.writeText(text)
    MessagePlugin.success(successMessage)
  } catch {
    MessagePlugin.error('复制失败')
  }
}

onMounted(() => {
  void fetchLogs(false)
})
</script>

<template>
  <div class="system-logs-view">
    <t-card :bordered="false" class="hero-card">
      <div class="hero-layout">
        <div>
          <div class="hero-eyebrow">System Observability</div>
          <h1 class="hero-title">系统日志工作台</h1>
          <p class="hero-copy">
            先看最新日志流，再按需拉取时间线、聚类和 AI 诊断，避免首屏因为重分析而整体超时。
          </p>
        </div>
        <div class="hero-actions">
          <t-button size="small" variant="outline" @click="handleExport('csv')">导出 CSV</t-button>
          <t-button size="small" variant="outline" @click="handleExport('json')">导出 JSON</t-button>
          <t-button size="small" variant="outline" @click="showArchiveDialog = true">归档日志</t-button>
          <t-button size="small" theme="warning" :loading="analyzing" @click="handleAnalyze">AI 诊断</t-button>
        </div>
      </div>
    </t-card>

    <t-card :bordered="false" class="filters-card mt-4">
      <div class="filters-header">
        <div>
          <div class="section-title">筛选与聚焦</div>
          <div class="section-copy">默认只查看最近窗口，先把排障范围收紧，再决定是否展开分析面板。</div>
        </div>
        <div class="preset-group">
          <t-button
            v-for="item in windowOptions"
            :key="item.value"
            size="small"
            :theme="windowHours === item.value ? 'primary' : 'default'"
            variant="outline"
            @click="applyWindowPreset(item.value)"
          >
            {{ item.label }}
          </t-button>
        </div>
      </div>

      <t-form layout="inline" class="filters-form mt-3">
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
          <t-input v-model="filter.keyword" placeholder="模块、错误签名、关键字" style="width: 220px" clearable />
        </t-form-item>
        <t-form-item label="Request ID">
          <t-input v-model="filter.request_id" placeholder="按请求链路聚焦" style="width: 220px" clearable />
        </t-form-item>
        <t-form-item>
          <t-space>
            <t-button theme="primary" :loading="logsLoading" @click="handleFilter">查询日志</t-button>
            <t-button variant="outline" @click="handleReset">重置</t-button>
            <t-button variant="outline" :loading="insightLoading" @click="loadInsights">重试分析面板</t-button>
          </t-space>
        </t-form-item>
      </t-form>
    </t-card>

    <t-alert class="mt-4" :theme="statusTheme" :message="statusMessage" closeable />

    <div v-if="filter.request_id" class="focus-strip mt-3">
      <div>
        <div class="focus-label">当前聚焦 Request ID</div>
        <div class="focus-value">{{ filter.request_id }}</div>
      </div>
      <t-button size="small" variant="outline" @click="clearRequestFocus">退出链路聚焦</t-button>
    </div>

    <OverviewCards v-if="stats || statsState.loading" class="mt-4" :stats="stats" :window-hours="windowHours" :loading="statsState.loading" />

    <t-row :gutter="16" class="mt-4 workspace-grid">
      <t-col :xs="12" :xl="8">
        <t-card :bordered="false" class="log-stream-card">
          <template #title>
            <div class="card-title-row">
              <div>
                <div class="section-title">日志流</div>
                <div class="section-copy">优先展示最新匹配日志。点击 Request ID 可切到单次请求链路排障。</div>
              </div>
              <div class="log-meta">
                <span>{{ activeWindowLabel }}</span>
                <span v-if="hasMore">已加载 {{ logs.length }} 条，仍可继续加载</span>
                <span v-else>当前共 {{ total }} 条</span>
              </div>
            </div>
          </template>

          <div v-if="logsLoading && !logs.length" class="center"><t-loading text="正在加载日志流..." /></div>
          <div v-else-if="logsError" class="panel-error">
            <t-alert theme="error" :message="logsError" />
            <t-button class="mt-3" theme="primary" @click="handleFilter">重试日志加载</t-button>
          </div>
          <DataEmptyGuide v-else-if="!logs.length" description="当前筛选窗口内没有日志。可以扩大时间范围，或改用关键词 / Request ID 聚焦。" :show-guide="false" />
          <div v-else class="log-stream-list">
            <div v-for="log in logs" :key="`${log.timestamp}-${log.message}-${log.request_id}`" class="log-entry" :class="`log-entry--${log.level.toLowerCase()}`">
              <div class="log-entry-head">
                <div class="log-entry-tags">
                  <t-tag size="small" :theme="getLevelTheme(log.level)" variant="light">{{ log.level }}</t-tag>
                  <span class="log-module">{{ log.module }}</span>
                </div>
                <span class="log-time">{{ log.timestamp }}</span>
              </div>

              <div class="log-message">{{ log.message }}</div>

              <div class="log-entry-foot">
                <button
                  v-if="log.request_id && log.request_id !== '-'"
                  class="request-chip"
                  type="button"
                  @click="focusRequest(log.request_id)"
                >
                  {{ log.request_id }}
                </button>
                <div class="entry-actions">
                  <t-button size="small" variant="text" @click="handleCopy(formatLogText(log), '日志已复制')">复制日志</t-button>
                  <t-button
                    v-if="log.request_id && log.request_id !== '-'"
                    size="small"
                    variant="text"
                    @click="handleCopy(log.request_id, 'Request ID 已复制')"
                  >
                    复制 Request ID
                  </t-button>
                </div>
              </div>
            </div>

            <div class="center mt-4" v-if="hasMore">
              <t-button :loading="logsLoadingMore" @click="loadMore">加载更多日志</t-button>
            </div>
          </div>
        </t-card>
      </t-col>

      <t-col :xs="12" :xl="4">
        <div class="side-panel-stack">
          <div v-if="timelineState.error" class="panel-error-card">
            <t-alert theme="warning" :message="`时间线加载失败：${timelineState.error}`" />
          </div>
          <OperationTimeline :items="timeline" :loading="timelineState.loading" />

          <div v-if="!isRequestFocused">
            <div v-if="clustersState.error" class="panel-error-card mt-4">
              <t-alert theme="warning" :message="`错误聚类加载失败：${clustersState.error}`" />
            </div>
            <ErrorClusterPanel class="mt-4" :clusters="clusters" :loading="clustersState.loading" @select="handleClusterSelect" />
          </div>

          <t-card v-else :bordered="false" class="mt-4 helper-card">
            <div class="section-title">请求链路模式</div>
            <div class="section-copy mt-2">
              当前已切到单次请求排障视角。为了避免无效重查询，聚类和总体统计会暂时让位给时间线和日志流。
            </div>
          </t-card>
        </div>
      </t-col>
    </t-row>

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
.system-logs-view {
  padding: 16px;
}

.hero-card,
.filters-card,
.log-stream-card,
.helper-card {
  border-radius: 20px;
}

.hero-layout,
.filters-header,
.card-title-row,
.focus-strip,
.log-entry-head,
.log-entry-foot {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.hero-layout,
.filters-header,
.card-title-row,
.focus-strip {
  align-items: flex-start;
}

.hero-eyebrow,
.focus-label {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #64748b;
}

.hero-title {
  margin: 6px 0 0;
  font-size: 30px;
  line-height: 1.1;
  color: #0f172a;
}

.hero-copy,
.section-copy,
.log-meta {
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.hero-copy {
  margin-top: 10px;
  max-width: 720px;
}

.hero-actions,
.preset-group,
.log-entry-tags,
.entry-actions,
.log-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
}

.focus-strip {
  align-items: center;
  padding: 14px 16px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.08), rgba(59, 130, 246, 0.12));
  border: 1px solid rgba(59, 130, 246, 0.15);
}

.focus-value {
  margin-top: 4px;
  font-size: 14px;
  font-family: 'Consolas', 'Monaco', monospace;
  color: #0f172a;
}

.side-panel-stack {
  display: flex;
  flex-direction: column;
}

.panel-error,
.center {
  text-align: center;
  padding: 24px;
}

.panel-error-card {
  margin-bottom: 12px;
}

.log-stream-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.log-entry {
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.95), rgba(241, 245, 249, 0.9));
}

.log-entry--error {
  border-color: rgba(239, 68, 68, 0.22);
  background: linear-gradient(180deg, rgba(254, 242, 242, 0.92), rgba(255, 255, 255, 0.98));
}

.log-entry--warning {
  border-color: rgba(245, 158, 11, 0.22);
  background: linear-gradient(180deg, rgba(255, 251, 235, 0.94), rgba(255, 255, 255, 0.98));
}

.log-module,
.log-time {
  font-size: 12px;
  color: #64748b;
}

.log-time {
  white-space: nowrap;
}

.log-message {
  margin-top: 10px;
  color: #1f2937;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.log-entry-foot {
  margin-top: 12px;
  align-items: center;
}

.request-chip {
  border: none;
  border-radius: 999px;
  padding: 6px 10px;
  background: rgba(14, 165, 233, 0.12);
  color: #0369a1;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  cursor: pointer;
}

.mt-2 {
  margin-top: 8px;
}

.mt-3 {
  margin-top: 12px;
}

.mt-4 {
  margin-top: 16px;
}

@media (max-width: 1024px) {
  .hero-layout,
  .filters-header,
  .card-title-row,
  .focus-strip,
  .log-entry-head,
  .log-entry-foot {
    flex-direction: column;
  }

  .log-time {
    white-space: normal;
  }
}
</style>
