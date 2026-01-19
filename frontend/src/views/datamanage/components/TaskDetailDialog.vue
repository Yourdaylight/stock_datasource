<script setup lang="ts">
import { computed } from 'vue'
import type { SyncTask } from '@/api/datamanage'

const props = defineProps<{
  visible: boolean
  task: SyncTask | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const getStatusTheme = (status: string) => {
  const themes: Record<string, string> = {
    pending: 'warning',
    running: 'primary',
    completed: 'success',
    failed: 'danger',
    cancelled: 'default'
  }
  return themes[status] || 'default'
}

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  }
  return texts[status] || status
}

const getTaskTypeText = (type: string) => {
  const texts: Record<string, string> = {
    incremental: '增量同步',
    full: '全量同步',
    backfill: '补录同步'
  }
  return texts[type] || type
}

const formatTime = (timeStr?: string) => {
  if (!timeStr) return '-'
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN')
}

const getDuration = (task: SyncTask | null) => {
  if (!task) return '-'
  if (!task.started_at) return '-'
  
  const start = new Date(task.started_at)
  const end = task.completed_at ? new Date(task.completed_at) : new Date()
  const duration = Math.floor((end.getTime() - start.getTime()) / 1000)
  
  if (duration < 60) return `${duration}秒`
  if (duration < 3600) return `${Math.floor(duration / 60)}分${duration % 60}秒`
  return `${Math.floor(duration / 3600)}小时${Math.floor((duration % 3600) / 60)}分`
}

// Error stack trace parsing
const STACK_SEPARATOR = '\n\n--- 堆栈跟踪 ---\n'

const hasStackTrace = computed(() => {
  if (!props.task?.error_message) return false
  return props.task.error_message.includes(STACK_SEPARATOR)
})

const getErrorSummary = (errorMessage: string) => {
  const idx = errorMessage.indexOf(STACK_SEPARATOR)
  return idx > 0 ? errorMessage.substring(0, idx) : errorMessage
}

const getStackTrace = (errorMessage: string) => {
  const idx = errorMessage.indexOf(STACK_SEPARATOR)
  return idx > 0 ? errorMessage.substring(idx + STACK_SEPARATOR.length) : ''
}
</script>

<template>
  <t-dialog
    v-model:visible="dialogVisible"
    header="任务详情"
    :footer="false"
    width="600px"
  >
    <div v-if="task" class="task-detail">
      <!-- 基本信息 -->
      <t-descriptions :column="2" bordered>
        <t-descriptions-item label="任务ID">
          <code>{{ task.task_id }}</code>
        </t-descriptions-item>
        <t-descriptions-item label="插件名称">
          {{ task.plugin_name }}
        </t-descriptions-item>
        <t-descriptions-item label="任务类型">
          <t-tag variant="outline">{{ getTaskTypeText(task.task_type) }}</t-tag>
        </t-descriptions-item>
        <t-descriptions-item label="状态">
          <t-tag :theme="getStatusTheme(task.status)">
            {{ getStatusText(task.status) }}
          </t-tag>
        </t-descriptions-item>
        <t-descriptions-item label="进度">
          <t-progress 
            :percentage="Number(task.progress.toFixed(1))" 
            :status="task.status === 'running' ? 'active' : 'default'"
            size="small"
            style="width: 150px"
          />
          <span style="margin-left: 8px">{{ task.progress.toFixed(1) }}%</span>
        </t-descriptions-item>
        <t-descriptions-item label="耗时">
          {{ getDuration(task) }}
        </t-descriptions-item>
        <t-descriptions-item label="创建时间">
          {{ formatTime(task.created_at) }}
        </t-descriptions-item>
        <t-descriptions-item label="开始时间">
          {{ formatTime(task.started_at) }}
        </t-descriptions-item>
        <t-descriptions-item label="完成时间">
          {{ formatTime(task.completed_at) }}
        </t-descriptions-item>
      </t-descriptions>

      <!-- 数据获取结果 - 突出显示 -->
      <div class="data-result-section">
        <h4>数据获取结果</h4>
        <div class="result-card" :class="{ success: task.records_processed > 0, warning: task.records_processed === 0 && task.status === 'completed' }">
          <div class="result-main">
            <span class="result-label">获取数据量</span>
            <span class="result-value">{{ task.records_processed.toLocaleString() }}</span>
            <span class="result-unit">条记录</span>
          </div>
          <div v-if="task.total_records > 0" class="result-sub">
            计划处理: {{ task.total_records.toLocaleString() }} 条
          </div>
          <div v-if="task.records_processed === 0 && task.status === 'completed'" class="result-warning">
            <t-icon name="error-circle" /> 任务完成但未获取到数据，请检查数据源或日期范围
          </div>
          <div v-else-if="task.records_processed > 0 && task.status === 'completed'" class="result-success">
            <t-icon name="check-circle" /> 数据获取成功
          </div>
        </div>
      </div>

      <!-- 交易日期列表 -->
      <div v-if="task.trade_dates && task.trade_dates.length > 0" class="trade-dates-section">
        <h4>处理日期 ({{ task.trade_dates.length }}天)</h4>
        <div class="date-tags">
          <t-tag 
            v-for="date in task.trade_dates.slice(0, 20)" 
            :key="date"
            theme="default"
            variant="light"
            size="small"
          >
            {{ date }}
          </t-tag>
          <span v-if="task.trade_dates.length > 20" class="more-dates">
            +{{ task.trade_dates.length - 20 }} 更多
          </span>
        </div>
      </div>

      <!-- 错误信息 -->
      <div v-if="task.error_message" class="error-section">
        <h4>
          <t-icon name="error-circle" style="margin-right: 4px" />
          错误信息
        </h4>
        <div class="error-content">
          <div v-if="hasStackTrace" class="error-summary">
            {{ getErrorSummary(task.error_message) }}
          </div>
          <t-collapse v-if="hasStackTrace" :default-expand-all="false">
            <t-collapse-panel header="查看完整堆栈" value="stack">
              <pre class="stack-trace">{{ getStackTrace(task.error_message) }}</pre>
            </t-collapse-panel>
          </t-collapse>
          <pre v-else class="error-message">{{ task.error_message }}</pre>
        </div>
      </div>
    </div>
    <t-empty v-else description="无任务信息" />
  </t-dialog>
</template>

<style scoped>
.task-detail {
  padding: 8px 0;
}

.trade-dates-section {
  margin-top: 16px;
}

.trade-dates-section h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: var(--td-text-color-primary);
}

.date-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 150px;
  overflow-y: auto;
  padding: 8px;
  background: var(--td-bg-color-secondarycontainer);
  border-radius: 4px;
}

.more-dates {
  color: var(--td-text-color-secondary);
  font-size: 12px;
  align-self: center;
}

.error-section {
  margin-top: 16px;
}

.error-section h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: var(--td-error-color);
  display: flex;
  align-items: center;
}

.error-content {
  background: var(--td-error-color-1);
  border: 1px solid var(--td-error-color-3);
  border-radius: 6px;
  padding: 12px;
}

.error-summary {
  font-size: 14px;
  color: var(--td-error-color);
  margin-bottom: 12px;
  font-weight: 500;
}

.error-message {
  margin: 0;
  font-family: monospace;
  font-size: 12px;
  color: var(--td-text-color-primary);
  white-space: pre-wrap;
  word-break: break-all;
}

.stack-trace {
  margin: 0;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 11px;
  color: var(--td-text-color-secondary);
  background: var(--td-bg-color-container);
  padding: 12px;
  border-radius: 4px;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.5;
}

code {
  font-family: monospace;
  font-size: 12px;
  background: var(--td-bg-color-secondarycontainer);
  padding: 2px 6px;
  border-radius: 3px;
}

.data-result-section {
  margin-top: 16px;
}

.data-result-section h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: var(--td-text-color-primary);
}

.result-card {
  padding: 16px;
  background: var(--td-bg-color-secondarycontainer);
  border-radius: 6px;
  border-left: 4px solid var(--td-gray-color-5);
}

.result-card.success {
  border-left-color: var(--td-success-color);
  background: var(--td-success-color-1);
}

.result-card.warning {
  border-left-color: var(--td-warning-color);
  background: var(--td-warning-color-1);
}

.result-main {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.result-label {
  font-size: 14px;
  color: var(--td-text-color-secondary);
}

.result-value {
  font-size: 28px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.result-unit {
  font-size: 14px;
  color: var(--td-text-color-secondary);
}

.result-sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}

.result-warning {
  margin-top: 8px;
  font-size: 13px;
  color: var(--td-warning-color);
  display: flex;
  align-items: center;
  gap: 4px;
}

.result-success {
  margin-top: 8px;
  font-size: 13px;
  color: var(--td-success-color);
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
