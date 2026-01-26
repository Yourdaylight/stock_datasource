<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { systemLogsApi, type LogEntry, type LogFilter } from '@/api/systemLogs'
import { MessagePlugin } from 'tdesign-vue-next'

// Filter state
const filter = ref<LogFilter>({
  level: undefined,
  start_time: undefined,
  end_time: undefined,
  keyword: undefined,
  page: 1,
  page_size: 100
})

// Table data
const logs = ref<LogEntry[]>([])
const total = ref(0)
const loading = ref(false)
const loadingMore = ref(false)
const hasMore = ref(true)

// Dialog state
const showAnalysisDialog = ref(false)
const analysisResult = ref<any>(null)
const analyzing = ref(false)

// Archive dialog state
const showArchiveDialog = ref(false)
const archiving = ref(false)
const archiveRetentionDays = ref(30)

// Level options
const levelOptions = [
  { label: '全部', value: undefined },
  { label: 'INFO', value: 'INFO' },
  { label: 'WARNING', value: 'WARNING' },
  { label: 'ERROR', value: 'ERROR' }
]

// Format log as plain text
const formatLogText = (log: LogEntry) => {
  return log.raw_line || `${log.timestamp} [${log.level}] [${log.module}] ${log.message}`
}

// Sort logs by timestamp descending (newest first)
const sortedLogs = computed(() => {
  return [...logs.value].sort((a, b) => {
    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  })
})

// Fetch logs
const fetchLogs = async () => {
  loading.value = true
  try {
    filter.value.page = 1
    const response = await systemLogsApi.getLogs(filter.value)
    logs.value = response.logs
    total.value = response.total
    hasMore.value = response.logs.length === filter.value.page_size
  } catch (error) {
    // Error handled by request interceptor
  } finally {
    loading.value = false
  }
}

// Load more logs
const loadMore = async () => {
  if (loadingMore.value || !hasMore.value) return

  loadingMore.value = true
  try {
    filter.value.page += 1
    const response = await systemLogsApi.getLogs(filter.value)
    logs.value = [...logs.value, ...response.logs]
    hasMore.value = response.logs.length === filter.value.page_size
  } catch (error) {
    // Error handled by request interceptor
  } finally {
    loadingMore.value = false
  }
}

// Apply filters
const handleFilter = () => {
  filter.value.page = 1
  fetchLogs()
}

// Reset filters
const handleReset = () => {
  filter.value = {
    level: undefined,
    start_time: undefined,
    end_time: undefined,
    keyword: undefined,
    page: 1,
    page_size: 50
  }
  fetchLogs()
}



// Analyze selected logs
const handleAnalyze = async (log: LogEntry) => {
  showAnalysisDialog.value = true
  analysisResult.value = null
  analyzing.value = true

  try {
    const errorLogs = logs.value.filter(l => l.level === 'ERROR')
    const response = await systemLogsApi.analyzeLogs({
      log_entries: errorLogs.length > 0 ? errorLogs : [log],
      user_query: '请分析错误日志并提供修复建议'
    })
    analysisResult.value = response
  } catch (error) {
    MessagePlugin.error('分析失败')
  } finally {
    analyzing.value = false
  }
}

// Archive logs
const handleArchive = async () => {
  archiving.value = true
  try {
    const response = await systemLogsApi.archiveLogs(archiveRetentionDays.value)
    MessagePlugin.success(`已归档 ${response.archived_count} 个文件`)
    showArchiveDialog.value = false
    fetchLogs()
  } catch (error) {
    // Error handled by request interceptor
  } finally {
    archiving.value = false
  }
}

// Export logs
const handleExport = async (format: 'csv' | 'json') => {
  try {
    const blob = await systemLogsApi.exportLogs({ ...filter.value, format })

    // Create download link
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `logs_export_${new Date().toISOString().slice(0, 19).replace(/[-T:]/g, '')}.${format}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    MessagePlugin.success('导出成功')
  } catch (error) {
    MessagePlugin.error('导出失败')
  }
}

// Copy log line
const handleCopy = (log: LogEntry) => {
  navigator.clipboard.writeText(formatLogText(log))
  MessagePlugin.success('已复制到剪贴板')
}

onMounted(() => {
  fetchLogs()
})
</script>

<template>
  <div class="system-logs-view">
    <!-- Filters -->
    <t-card title="日志查询" :bordered="false" style="margin-bottom: 16px">
      <t-form layout="inline" @submit="handleFilter">
        <t-form-item label="级别">
          <t-select v-model="filter.level" :options="levelOptions" style="width: 120px" clearable />
        </t-form-item>

        <t-form-item label="开始时间">
          <t-date-picker
            v-model="filter.start_time"
            enable-time-picker
            format="YYYY-MM-DD HH:mm:ss"
            placeholder="选择开始时间"
            style="width: 220px"
          />
        </t-form-item>

        <t-form-item label="结束时间">
          <t-date-picker
            v-model="filter.end_time"
            enable-time-picker
            format="YYYY-MM-DD HH:mm:ss"
            placeholder="选择结束时间"
            style="width: 220px"
          />
        </t-form-item>

        <t-form-item label="关键词">
          <t-input
            v-model="filter.keyword"
            placeholder="搜索消息内容"
            style="width: 200px"
            clearable
          />
        </t-form-item>

        <t-form-item>
          <t-button theme="primary" @click="handleFilter">
            <template #icon><t-icon name="search" /></template>
            查询
          </t-button>
          <t-button theme="default" @click="handleReset" style="margin-left: 8px">
            <template #icon><t-icon name="refresh" /></template>
            重置
          </t-button>
        </t-form-item>
      </t-form>

      <div style="margin-top: 12px">
        <t-button size="small" variant="outline" @click="handleExport('csv')">
          <template #icon><t-icon name="download" /></template>
          导出 CSV
        </t-button>
        <t-button size="small" variant="outline" @click="handleExport('json')" style="margin-left: 8px">
          <template #icon><t-icon name="download" /></template>
          导出 JSON
        </t-button>
        <t-button size="small" variant="outline" @click="showArchiveDialog = true" style="margin-left: 8px">
          <template #icon><t-icon name="archive" /></template>
          归档日志
        </t-button>
      </div>
    </t-card>

    <!-- Logs Text Display -->
    <t-card title="系统日志" :bordered="false">
      <div v-if="loading && logs.length === 0" style="text-align: center; padding: 40px;">
        <t-loading text="加载中..." />
      </div>
      <div v-else>
        <div class="logs-text-container">
          <div v-for="log in sortedLogs" :key="log.timestamp" class="log-line-wrapper">
            <span class="log-line">{{ formatLogText(log) }}</span>
            <t-button
              size="small"
              variant="text"
              theme="default"
              @click="handleCopy(log)"
              class="copy-button"
            >
              复制
            </t-button>
          </div>
        </div>

        <div v-if="hasMore && logs.length > 0" style="text-align: center; padding-top: 16px;">
          <t-button
            :loading="loadingMore"
            @click="loadMore"
          >
            加载更多
          </t-button>
        </div>

        <div v-else-if="logs.length > 0" style="text-align: center; padding-top: 16px; color: #999; font-size: 12px;">
          已加载全部日志
        </div>
      </div>
    </t-card>

    <!-- Analysis Dialog -->
    <t-dialog v-model:visible="showAnalysisDialog" header="AI日志分析" width="800" :footer="false">
      <div v-if="analyzing" style="text-align: center; padding: 40px;">
        <t-loading text="分析中..." />
      </div>

      <div v-else-if="analysisResult" class="analysis-result">
        <t-descriptions :column="1" bordered>
          <t-descriptions-item label="错误类型">
            {{ analysisResult.error_type }}
          </t-descriptions-item>
          <t-descriptions-item label="置信度">
            {{ (analysisResult.confidence * 100).toFixed(1) }}%
          </t-descriptions-item>
        </t-descriptions>

        <div style="margin-top: 16px">
          <div style="font-weight: bold; margin-bottom: 8px;">可能的原因：</div>
          <ul>
            <li v-for="(cause, index) in analysisResult.possible_causes" :key="index">
              {{ cause }}
            </li>
          </ul>
        </div>

        <div style="margin-top: 16px">
          <div style="font-weight: bold; margin-bottom: 8px;">建议的修复方案：</div>
          <ul>
            <li v-for="(fix, index) in analysisResult.suggested_fixes" :key="index">
              {{ fix }}
            </li>
          </ul>
        </div>

        <div v-if="analysisResult.related_logs.length > 0" style="margin-top: 16px">
          <div style="font-weight: bold; margin-bottom: 8px;">相关日志：</div>
          <div
            v-for="(log, index) in analysisResult.related_logs"
            :key="index"
            style="padding: 8px; background: #f5f5f5; border-radius: 4px; margin-bottom: 8px; font-size: 12px;"
          >
            {{ log }}
          </div>
        </div>
      </div>

      <div v-else style="text-align: center; padding: 40px;">
        <t-result theme="error" title="分析失败" />
      </div>
    </t-dialog>

    <!-- Archive Dialog -->
    <t-dialog
      v-model:visible="showArchiveDialog"
      header="归档日志"
      @confirm="handleArchive"
      :confirm-btn="{ loading: archiving }"
    >
      <t-form layout="vertical">
        <t-form-item label="保留天数">
          <t-input-number
            v-model="archiveRetentionDays"
            :min="1"
            :max="365"
            style="width: 200px"
          />
          <div style="color: #999; font-size: 12px; margin-top: 4px;">
            将归档超过指定天数的日志文件
          </div>
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<style scoped>
.system-logs-view {
  padding: 16px;
}

.logs-text-container {
  background: #1a1a1a;
  color: #f5f5f5;
  padding: 16px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  max-height: 600px;
  overflow-y: auto;
}

.log-line-wrapper {
  display: flex;
  align-items: flex-start;
  padding: 2px 0;
}

.log-line {
  flex: 1;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.copy-button {
  flex-shrink: 0;
  margin-left: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}

.log-line-wrapper:hover .copy-button {
  opacity: 1;
}

.analysis-result {
  max-height: 500px;
  overflow-y: auto;
}

.analysis-result ul {
  margin: 0;
  padding-left: 20px;
}

.analysis-result li {
  margin: 4px 0;
  line-height: 1.6;
}
</style>
