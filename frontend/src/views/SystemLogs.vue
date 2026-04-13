<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import {
  systemLogsApi,
  type ErrorClusterItem,
  type LogAnalysisResponse,
  type LogEntry,
  type LogFilter,
  type LogStatsResponse,
  type LogStatsTrendPoint,
  type OperationTimelineItem
} from '@/api/systemLogs'
import AiDiagnosisDrawer from '@/components/system-logs/AiDiagnosisDrawer.vue'

interface PanelState {
  loading: boolean
  error: string
  ready: boolean
}

const windowHours = ref(2)
const autoRefresh = ref(true)
const autoRefreshInterval = ref(30)
let autoRefreshTimer: number | null = null

const pad = (value: number) => String(value).padStart(2, '0')
const formatDateTime = (date: Date) => {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

const buildTimeRange = (hours: number) => {
  const end = new Date()
  const start = new Date(end.getTime() - hours * 60 * 60 * 1000)
  return { start_time: formatDateTime(start), end_time: formatDateTime(end) }
}

const createDefaultFilter = (): LogFilter => ({
  level: undefined,
  keyword: undefined,
  request_id: undefined,
  page: 1,
  page_size: 100,
  ...buildTimeRange(windowHours.value)
})

const createPanelState = (): PanelState => ({ loading: false, error: '', ready: false })

const filter = ref<LogFilter>(createDefaultFilter())
const logs = ref<LogEntry[]>([])
const total = ref(0)
const logsLoading = ref(false)
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

const selectedLogIndex = ref<number | null>(null)
const selectedLog = computed(() => selectedLogIndex.value !== null ? logs.value[selectedLogIndex.value] : null)

const levelOptions = [
  { label: 'ALL', value: undefined },
  { label: 'ERROR', value: 'ERROR' },
  { label: 'WARN', value: 'WARNING' },
  { label: 'INFO', value: 'INFO' }
]

const windowOptions = [
  { label: '30m', value: 0.5 },
  { label: '2h', value: 2 },
  { label: '6h', value: 6 },
  { label: '24h', value: 24 }
]

const LEVEL_COLORS: Record<string, string> = {
  ERROR: '#e34d59',
  WARNING: '#e37318',
  WARN: '#e37318',
  INFO: '#0052d9',
  DEBUG: '#9ca3af'
}

const LEVEL_BG: Record<string, string> = {
  ERROR: 'rgba(227,77,89,0.10)',
  WARNING: 'rgba(227,115,24,0.10)',
  WARN: 'rgba(227,115,24,0.10)',
  INFO: 'rgba(0,82,217,0.08)',
  DEBUG: 'rgba(156,163,175,0.08)'
}

let logRequestSeq = 0
let insightRequestSeq = 0
let insightTimer: number | null = null

const isRequestFocused = computed(() => Boolean(filter.value.request_id && filter.value.request_id.trim()))
const insightLoading = computed(() => statsState.value.loading || clustersState.value.loading || timelineState.value.loading)

const activeWindowLabel = computed(() => {
  const h = windowHours.value
  if (h <= 1) return '最近1小时'
  if (h < 24) return `最近${h}小时`
  return `最近${Math.round(h / 24)}天`
})

const analysisEntries = computed(() => {
  if (isRequestFocused.value) return logs.value.slice(0, 20)
  const errorLogs = logs.value.filter((item) => item.level === 'ERROR')
  return (errorLogs.length ? errorLogs : logs.value).slice(0, 30)
})

// Trend mini chart
const trendPath = computed(() => {
  const trend = stats.value?.trend
  if (!trend || trend.length < 2) return ''
  const maxVal = Math.max(...trend.map(t => t.total), 1)
  const w = 240
  const h = 40
  const step = w / (trend.length - 1)
  const points = trend.map((t, i) => `${i * step},${h - (t.total / maxVal) * h}`)
  return `M${points.join(' L')}`
})

const trendErrorPath = computed(() => {
  const trend = stats.value?.trend
  if (!trend || trend.length < 2) return ''
  const maxVal = Math.max(...trend.map(t => t.total), 1)
  const w = 240
  const h = 40
  const step = w / (trend.length - 1)
  const points = trend.map((t, i) => `${i * step},${h - (t.error / maxVal) * h}`)
  return `M${points.join(' L')}`
})

const resetPanelState = (panel: typeof statsState) => { panel.value = createPanelState() }

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

const formatTime = (ts: string) => {
  if (!ts) return '-'
  return ts.replace('T', ' ').slice(11, 23)
}

const clearInsightTimer = () => {
  if (insightTimer !== null) { window.clearTimeout(insightTimer); insightTimer = null }
}

const getInsightParams = () => ({ ...filter.value, window_hours: windowHours.value })

const scheduleInsights = () => {
  clearInsightTimer()
  insightTimer = window.setTimeout(() => void loadInsights(), 120)
}

const fetchLogs = async () => {
  const seq = ++logRequestSeq
  logsLoading.value = true
  logsError.value = ''
  try {
    const response = await systemLogsApi.getLogs(filter.value)
    if (seq !== logRequestSeq) return
    logs.value = response.logs
    total.value = response.total
    hasMore.value = response.logs.length === (filter.value.page_size || 100) && logs.value.length < response.total
    scheduleInsights()
  } catch (error) {
    if (seq !== logRequestSeq) return
    logsError.value = getErrorMessage(error)
    logs.value = []
    total.value = 0
    hasMore.value = false
  } finally {
    if (seq === logRequestSeq) logsLoading.value = false
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
    stats.value = null; clusters.value = []
    resetPanelState(statsState); resetPanelState(clustersState)
    await fetchTimelinePanel(seq)
    return
  }
  await Promise.allSettled([fetchStatsPanel(seq), fetchClustersPanel(seq), fetchTimelinePanel(seq)])
}

const applyWindowPreset = (hours: number) => {
  windowHours.value = hours
  const range = buildTimeRange(hours)
  filter.value.start_time = range.start_time
  filter.value.end_time = range.end_time
}

const handleFilter = () => void fetchLogs()
const handleReset = () => {
  windowHours.value = 2
  filter.value = createDefaultFilter()
  stats.value = null; clusters.value = []; timeline.value = []
  resetPanelState(statsState); resetPanelState(clustersState); resetPanelState(timelineState)
  selectedLogIndex.value = null
  void fetchLogs()
}

const focusRequest = (requestId?: string) => {
  if (!requestId || requestId === '-') return
  filter.value.request_id = requestId
  selectedLogIndex.value = null
  void fetchLogs()
}

const clearRequestFocus = () => {
  if (!filter.value.request_id) return
  filter.value.request_id = undefined
  void fetchLogs()
}

const handleClusterSelect = (signature: string) => {
  filter.value.keyword = signature
  void fetchLogs()
}

const selectLog = (index: number) => {
  selectedLogIndex.value = selectedLogIndex.value === index ? null : index
}

const handleAnalyze = async () => {
  if (!analysisEntries.value.length) {
    MessagePlugin.warning('当前没有可分析的日志')
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
    MessagePlugin.error('AI 诊断失败')
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
    void fetchLogs()
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
    document.body.appendChild(link); link.click(); document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch { MessagePlugin.error('导出失败') }
}

const handleCopy = async (text: string) => {
  try { await navigator.clipboard.writeText(text); MessagePlugin.success('已复制') }
  catch { MessagePlugin.error('复制失败') }
}

// Auto refresh
const startAutoRefresh = () => {
  stopAutoRefresh()
  if (autoRefresh.value) {
    autoRefreshTimer = window.setInterval(() => void fetchLogs(), autoRefreshInterval.value * 1000)
  }
}
const stopAutoRefresh = () => {
  if (autoRefreshTimer !== null) { window.clearInterval(autoRefreshTimer); autoRefreshTimer = null }
}

const toggleAutoRefresh = () => {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) startAutoRefresh()
  else stopAutoRefresh()
}

// Pagination
const currentPage = ref(1)
const pageSize = ref(100)
const totalPages = computed(() => Math.ceil(total.value / pageSize.value))

const goToPage = (p: number) => {
  currentPage.value = Math.max(1, Math.min(p, totalPages.value))
  filter.value.page = currentPage.value
  void fetchLogs()
}

onMounted(() => {
  void fetchLogs()
  startAutoRefresh()
})

onUnmounted(() => { stopAutoRefresh(); clearInsightTimer() })
</script>

<template>
  <div class="obs-view">
    <!-- Top bar: filters + controls -->
    <div class="top-bar">
      <div class="top-left">
        <div class="brand">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
          <span>Observability</span>
        </div>
        <div class="separator" />
        <t-select v-model="filter.level" :options="levelOptions" style="width:96px" size="small" clearable @change="handleFilter" />
        <t-input v-model="filter.keyword" placeholder="filter keyword..." style="width:160px" size="small" clearable @enter="handleFilter" @clear="handleFilter" />
        <t-input v-model="filter.request_id" placeholder="request id..." style="width:140px" size="small" clearable @enter="handleFilter" @clear="handleFilter" />
        <t-button size="small" theme="primary" variant="base" :loading="logsLoading" @click="handleFilter">Search</t-button>
        <t-button size="small" variant="outline" @click="handleReset">Reset</t-button>
      </div>
      <div class="top-right">
        <div class="time-presets">
          <button v-for="item in windowOptions" :key="item.value" class="preset-btn" :class="{ active: windowHours === item.value }" @click="applyWindowPreset(item.value); handleFilter()">{{ item.label }}</button>
        </div>
        <div class="separator" />
        <button class="icon-btn" :class="{ active: autoRefresh }" @click="toggleAutoRefresh" :title="autoRefresh ? '关闭自动刷新' : '开启自动刷新'">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
        </button>
        <t-button size="small" variant="outline" @click="handleExport('csv')">CSV</t-button>
        <t-button size="small" variant="outline" @click="handleExport('json')">JSON</t-button>
        <t-button size="small" theme="warning" :loading="analyzing" @click="handleAnalyze">AI Diagnosis</t-button>
      </div>
    </div>

    <!-- Focus strip -->
    <div v-if="filter.request_id" class="focus-bar">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--blue)" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <span class="focus-text">Tracing <code>{{ filter.request_id }}</code></span>
      <button class="focus-close" @click="clearRequestFocus">&times;</button>
    </div>

    <!-- Stats row -->
    <div class="stats-row" v-if="stats || statsState.loading">
      <div class="stat-chip">
        <span class="stat-label">TOTAL</span>
        <span class="stat-value">{{ stats?.total ?? '—' }}</span>
      </div>
      <div class="stat-chip stat-error">
        <span class="stat-label">ERROR</span>
        <span class="stat-value">{{ stats?.error ?? '—' }}</span>
      </div>
      <div class="stat-chip stat-warn">
        <span class="stat-label">WARN</span>
        <span class="stat-value">{{ stats?.warning ?? '—' }}</span>
      </div>
      <div class="stat-chip stat-info">
        <span class="stat-label">INFO</span>
        <span class="stat-value">{{ stats?.info ?? '—' }}</span>
      </div>
      <div class="stat-trend" v-if="trendPath">
        <svg :width="240" :height="40" class="trend-svg">
          <path :d="trendPath" fill="none" stroke="var(--bg-3)" stroke-width="1.5" />
          <path :d="trendErrorPath" fill="none" stroke="var(--red)" stroke-width="1" opacity="0.7" />
        </svg>
      </div>
      <div class="stat-window">{{ activeWindowLabel }}</div>
    </div>

    <!-- Main: log stream + detail -->
    <div class="main-area">
      <!-- Log stream -->
      <div class="log-stream" :class="{ 'with-detail': selectedLog !== null }">
        <div class="stream-header">
          <span class="stream-count">{{ total }} logs</span>
          <span v-if="logsLoading" class="stream-loading">loading...</span>
          <span v-if="autoRefresh" class="stream-auto">auto {{ autoRefreshInterval }}s</span>
        </div>

        <div v-if="logsError" class="stream-error">
          <span>{{ logsError }}</span>
          <t-button size="small" @click="handleFilter">Retry</t-button>
        </div>

        <div v-else-if="!logs.length && !logsLoading" class="stream-empty">No logs in this time window</div>

        <div v-else class="stream-body">
          <div
            v-for="(log, i) in logs"
            :key="i"
            class="log-row"
            :class="{ 'log-selected': selectedLogIndex === i, [`log-${log.level.toLowerCase()}`]: true }"
            @click="selectLog(i)"
          >
            <span class="log-time">{{ formatTime(log.timestamp) }}</span>
            <span class="log-level" :style="{ color: LEVEL_COLORS[log.level] || '#6b7280', background: LEVEL_BG[log.level] || 'transparent' }">{{ log.level }}</span>
            <span class="log-module">{{ log.module.split('.').slice(-2).join('.') }}</span>
            <span class="log-msg">{{ log.message }}</span>
            <span v-if="log.request_id && log.request_id !== '-'" class="log-rid" @click.stop="focusRequest(log.request_id)">{{ log.request_id.slice(0, 8) }}</span>
          </div>
        </div>

        <!-- Pagination -->
        <div class="stream-footer" v-if="total > pageSize">
          <button class="page-btn" :disabled="currentPage <= 1" @click="goToPage(currentPage - 1)">&larr;</button>
          <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
          <button class="page-btn" :disabled="currentPage >= totalPages" @click="goToPage(currentPage + 1)">&rarr;</button>
        </div>
      </div>

      <!-- Detail panel -->
      <div v-if="selectedLog" class="detail-panel">
        <div class="detail-header">
          <span class="detail-title">Log Detail</span>
          <button class="detail-close" @click="selectedLogIndex = null">&times;</button>
        </div>
        <div class="detail-body">
          <div class="detail-field">
            <span class="detail-key">Timestamp</span>
            <span class="detail-val mono">{{ selectedLog.timestamp?.replace('T', ' ') }}</span>
          </div>
          <div class="detail-field">
            <span class="detail-key">Level</span>
            <span class="detail-val"><span class="log-level" :style="{ color: LEVEL_COLORS[selectedLog.level] || '#6b7280', background: LEVEL_BG[selectedLog.level] || 'transparent' }">{{ selectedLog.level }}</span></span>
          </div>
          <div class="detail-field">
            <span class="detail-key">Module</span>
            <span class="detail-val mono">{{ selectedLog.module }}</span>
          </div>
          <div class="detail-field">
            <span class="detail-key">Request ID</span>
            <span class="detail-val mono">
              <span v-if="selectedLog.request_id && selectedLog.request_id !== '-'">
                <t-link theme="primary" @click="focusRequest(selectedLog.request_id)">{{ selectedLog.request_id }}</t-link>
              </span>
              <span v-else style="color:#475569">—</span>
            </span>
          </div>
          <div class="detail-field">
            <span class="detail-key">User</span>
            <span class="detail-val mono">{{ selectedLog.user_id || '—' }}</span>
          </div>
          <div class="detail-section">
            <span class="detail-key">Message</span>
            <pre class="detail-pre">{{ selectedLog.message }}</pre>
          </div>
          <div v-if="selectedLog.raw_line" class="detail-section">
            <span class="detail-key">Raw</span>
            <pre class="detail-pre raw">{{ selectedLog.raw_line }}</pre>
          </div>
        </div>
        <div class="detail-actions">
          <t-button size="small" variant="outline" @click="handleCopy(formatLogText(selectedLog))">Copy Log</t-button>
          <t-button size="small" variant="outline" @click="handleCopy(selectedLog.request_id || '')">Copy Req ID</t-button>
        </div>
      </div>
    </div>

    <!-- Bottom panels: timeline + clusters -->
    <div class="bottom-panels" v-if="!isRequestFocused">
      <div class="panel-timeline">
        <div class="panel-head">
          <span>Timeline</span>
          <span v-if="timelineState.loading" class="panel-loading">...</span>
        </div>
        <div v-if="timelineState.error" class="panel-error">{{ timelineState.error }}</div>
        <div v-else-if="!timeline.length" class="panel-empty">No events</div>
        <div v-else class="timeline-list">
          <div v-for="(item, i) in timeline.slice(0, 15)" :key="i" class="tl-item" @click="item.request_id && focusRequest(item.request_id)">
            <span class="tl-dot" :style="{ background: LEVEL_COLORS[item.level] || '#6b7280' }" />
            <span class="tl-time">{{ formatTime(item.timestamp) }}</span>
            <span class="tl-level" :style="{ color: LEVEL_COLORS[item.level] }">{{ item.level }}</span>
            <span class="tl-summary">{{ item.summary }}</span>
            <span class="tl-module">{{ item.module.split('.').slice(-1)[0] }}</span>
          </div>
        </div>
      </div>
      <div class="panel-clusters">
        <div class="panel-head">
          <span>Error Clusters</span>
          <span v-if="clustersState.loading" class="panel-loading">...</span>
        </div>
        <div v-if="clustersState.error" class="panel-error">{{ clustersState.error }}</div>
        <div v-else-if="!clusters.length" class="panel-empty">No error clusters</div>
        <div v-else class="cluster-list">
          <div v-for="(item, i) in clusters.slice(0, 8)" :key="i" class="cl-item" @click="handleClusterSelect(item.signature)">
            <span class="cl-count">{{ item.count }}x</span>
            <span class="cl-level" :style="{ color: LEVEL_COLORS[item.level] }">{{ item.level }}</span>
            <span class="cl-sig">{{ item.signature }}</span>
            <span class="cl-module">{{ item.module.split('.').slice(-1)[0] }}</span>
          </div>
        </div>
      </div>
    </div>

    <AiDiagnosisDrawer v-model:visible="showAnalysisDrawer" :loading="analyzing" :result="analysisResult" />

    <t-dialog v-model:visible="showArchiveDialog" header="归档日志" @confirm="handleArchive" :confirm-btn="{ loading: archiving }">
      <t-form layout="vertical">
        <t-form-item label="保留天数">
          <t-input-number v-model="archiveRetentionDays" :min="1" :max="365" style="width:200px" />
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<style scoped>
.obs-view {
  --bg-0: #ffffff;
  --bg-1: #f3f4f6;
  --bg-2: #e5e7eb;
  --bg-3: #d1d5db;
  --border: #e5e7eb;
  --text-1: #1f2937;
  --text-2: #4b5563;
  --text-3: #9ca3af;
  --accent: #0052d9;
  --accent-dim: rgba(0, 82, 217, 0.08);
  --red: #e34d59;
  --amber: #e37318;
  --blue: #0052d9;
  --green: #00a870;
  --mono: 'Menlo', 'Consolas', 'Monaco', monospace;

  background: var(--bg-0);
  color: var(--text-1);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  gap: 0;
  font-size: 13px;
}

/* ── Top Bar ── */
.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: var(--bg-1);
  border-bottom: 1px solid var(--border);
  gap: 12px;
  flex-wrap: wrap;
}
.top-left, .top-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.brand {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 700;
  font-size: 14px;
  color: var(--accent);
  letter-spacing: 0.02em;
}
.separator {
  width: 1px;
  height: 18px;
  background: var(--border);
}

/* Override TDesign inputs for light consistency */
.top-bar :deep(.t-button) {
  font-size: 12px;
}

.time-presets {
  display: flex;
  gap: 2px;
  background: var(--bg-2);
  border-radius: 6px;
  padding: 2px;
}
.preset-btn {
  padding: 3px 10px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--text-2);
  font-size: 11px;
  font-family: var(--mono);
  cursor: pointer;
  transition: all 0.15s;
}
.preset-btn:hover { color: var(--text-1); background: var(--bg-3); }
.preset-btn.active { color: var(--accent); background: var(--accent-dim); font-weight: 600; }

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-2);
  color: var(--text-3);
  cursor: pointer;
  transition: all 0.15s;
}
.icon-btn:hover { color: var(--text-1); border-color: var(--text-3); }
.icon-btn.active { color: var(--accent); border-color: var(--accent); background: var(--accent-dim); }

/* ── Focus Bar ── */
.focus-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  background: rgba(0, 82, 217, 0.05);
  border-bottom: 1px solid rgba(0, 82, 217, 0.15);
  font-size: 12px;
}
.focus-text { color: var(--text-2); }
.focus-text code { color: var(--blue); font-family: var(--mono); font-size: 12px; }
.focus-close {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--text-3);
  font-size: 16px;
  cursor: pointer;
  line-height: 1;
}
.focus-close:hover { color: var(--text-1); }

/* ── Stats Row ── */
.stats-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: var(--bg-1);
  border-bottom: 1px solid var(--border);
}
.stat-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4px 12px;
  border-radius: 6px;
  background: var(--bg-2);
  min-width: 56px;
}
.stat-label {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--text-3);
}
.stat-value {
  font-family: var(--mono);
  font-size: 16px;
  font-weight: 600;
  color: var(--text-1);
  line-height: 1.4;
}
.stat-error .stat-value { color: var(--red); }
.stat-warn .stat-value { color: var(--amber); }
.stat-info .stat-value { color: var(--blue); }

.stat-trend {
  margin-left: auto;
  opacity: 0.8;
}
.trend-svg {
  display: block;
}

.stat-window {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--text-3);
}

/* ── Main Area ── */
.main-area {
  flex: 1;
  display: flex;
  min-height: 0;
  border-bottom: 1px solid var(--border);
}

/* ── Log Stream ── */
.log-stream {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  transition: flex 0.2s;
}
.log-stream.with-detail {
  flex: 3;
}

.stream-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 16px;
  background: var(--bg-1);
  border-bottom: 1px solid var(--border);
}
.stream-count {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 600;
  color: var(--text-2);
}
.stream-loading, .stream-auto {
  font-size: 10px;
  color: var(--text-3);
  font-family: var(--mono);
}
.stream-auto { color: var(--accent); }

.stream-error {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  color: var(--red);
  font-size: 12px;
}
.stream-empty {
  padding: 40px;
  text-align: center;
  color: var(--text-3);
  font-size: 13px;
}

.stream-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  font-family: var(--mono);
  font-size: 12px;
}

.log-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 3px 16px;
  cursor: pointer;
  border-left: 2px solid transparent;
  transition: background 0.1s, border-color 0.1s;
}
.log-row:hover { background: var(--bg-2); }
.log-row.log-selected { background: var(--bg-2); border-left-color: var(--accent); }
.log-row.log-error { background: rgba(227, 77, 89, 0.06); }
.log-row.log-error:hover, .log-row.log-error.log-selected { background: rgba(227, 77, 89, 0.12); }
.log-row.log-warning { background: rgba(227, 115, 24, 0.05); }

.log-time {
  color: var(--text-3);
  font-size: 11px;
  white-space: nowrap;
  min-width: 88px;
}
.log-level {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 3px;
  white-space: nowrap;
  letter-spacing: 0.04em;
}
.log-module {
  color: var(--text-2);
  font-size: 11px;
  white-space: nowrap;
  min-width: 100px;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.log-msg {
  flex: 1;
  color: var(--text-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.6;
}
.log-rid {
  color: var(--blue);
  font-size: 10px;
  cursor: pointer;
  opacity: 0.7;
  transition: opacity 0.15s;
  flex-shrink: 0;
}
.log-rid:hover { opacity: 1; text-decoration: underline; }

/* Pagination */
.stream-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 6px;
  background: var(--bg-1);
  border-top: 1px solid var(--border);
}
.page-btn {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-2);
  padding: 2px 8px;
  cursor: pointer;
  font-size: 12px;
}
.page-btn:hover:not(:disabled) { color: var(--text-1); border-color: var(--text-3); }
.page-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.page-info { font-family: var(--mono); font-size: 11px; color: var(--text-3); }

/* ── Detail Panel ── */
.detail-panel {
  width: 340px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-1);
  border-left: 1px solid var(--border);
  animation: slideIn 0.15s ease;
}
@keyframes slideIn {
  from { opacity: 0; transform: translateX(8px); }
  to { opacity: 1; transform: translateX(0); }
}
.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}
.detail-title {
  font-weight: 600;
  font-size: 12px;
  color: var(--text-2);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.detail-close {
  background: none;
  border: none;
  color: var(--text-3);
  font-size: 18px;
  cursor: pointer;
  line-height: 1;
}
.detail-close:hover { color: var(--text-1); }

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.detail-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.detail-key {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-3);
}
.detail-val {
  font-size: 12px;
  color: var(--text-1);
}
.detail-val.mono {
  font-family: var(--mono);
  font-size: 11px;
  word-break: break-all;
}
.detail-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.detail-pre {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 8px;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--text-1);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  line-height: 1.6;
  max-height: 200px;
  overflow-y: auto;
}
.detail-pre.raw {
  color: var(--text-3);
  max-height: 120px;
}
.detail-actions {
  display: flex;
  gap: 6px;
  padding: 8px 12px;
  border-top: 1px solid var(--border);
}

/* ── Bottom Panels ── */
.bottom-panels {
  display: flex;
  gap: 0;
  min-height: 200px;
  max-height: 280px;
}
.panel-timeline, .panel-clusters {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.panel-timeline {
  border-right: 1px solid var(--border);
}
.panel-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--bg-1);
  border-bottom: 1px solid var(--border);
  font-weight: 600;
  font-size: 11px;
  color: var(--text-2);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.panel-loading { color: var(--accent); font-family: var(--mono); }
.panel-error, .panel-empty {
  padding: 16px;
  color: var(--text-3);
  font-size: 12px;
  text-align: center;
}
.panel-error { color: var(--red); }

/* Timeline */
.timeline-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
  font-family: var(--mono);
  font-size: 11px;
}
.tl-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 12px;
  cursor: pointer;
  transition: background 0.1s;
}
.tl-item:hover { background: var(--bg-2); }
.tl-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.tl-time { color: var(--text-3); min-width: 72px; }
.tl-level { font-weight: 700; min-width: 40px; font-size: 10px; }
.tl-summary { flex: 1; color: var(--text-1); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tl-module { color: var(--text-3); font-size: 10px; }

/* Clusters */
.cluster-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
  font-family: var(--mono);
  font-size: 11px;
}
.cl-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  cursor: pointer;
  transition: background 0.1s;
  border-left: 2px solid transparent;
}
.cl-item:hover { background: var(--bg-2); border-left-color: var(--red); }
.cl-count { color: var(--red); font-weight: 700; min-width: 32px; }
.cl-level { font-weight: 700; min-width: 40px; font-size: 10px; }
.cl-sig { flex: 1; color: var(--text-1); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cl-module { color: var(--text-3); font-size: 10px; }

/* ── Scrollbar ── */
.stream-body::-webkit-scrollbar,
.timeline-list::-webkit-scrollbar,
.cluster-list::-webkit-scrollbar,
.detail-body::-webkit-scrollbar,
.detail-pre::-webkit-scrollbar {
  width: 5px;
}
.stream-body::-webkit-scrollbar-track,
.timeline-list::-webkit-scrollbar-track,
.cluster-list::-webkit-scrollbar-track,
.detail-body::-webkit-scrollbar-track {
  background: var(--bg-0);
}
.stream-body::-webkit-scrollbar-thumb,
.timeline-list::-webkit-scrollbar-thumb,
.cluster-list::-webkit-scrollbar-thumb,
.detail-body::-webkit-scrollbar-thumb {
  background: var(--bg-3);
  border-radius: 3px;
}

/* ── Responsive ── */
@media (max-width: 1024px) {
  .top-bar { flex-direction: column; align-items: flex-start; }
  .main-area { flex-direction: column; }
  .detail-panel { width: 100%; border-left: none; border-top: 1px solid var(--border); max-height: 300px; }
  .bottom-panels { flex-direction: column; max-height: none; }
  .panel-timeline { border-right: none; border-bottom: 1px solid var(--border); }
}
</style>
