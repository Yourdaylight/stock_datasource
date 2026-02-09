<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { MessagePlugin, DialogPlugin } from 'tdesign-vue-next'
import { useDataManageStore } from '@/stores/datamanage'
import { useAuthStore } from '@/stores/auth'
import type { ScheduleExecutionRecord, BatchExecutionDetail, BatchTaskDetail } from '@/api/datamanage'
import TaskDetailDialog from './components/TaskDetailDialog.vue'
import type { SyncTask } from '@/api/datamanage'
import { datamanageApi } from '@/api/datamanage'

const dataStore = useDataManageStore()
const authStore = useAuthStore()

// Check admin permission
const isAdmin = computed(() => authStore.isAdmin)

// Task filter states
const taskStatusFilter = ref<string>('')
const triggerTypeFilter = ref<string>('')

const taskStatusOptions = [
  { label: '全部状态', value: '' },
  { label: '运行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '失败', value: 'failed' },
  { label: '已跳过', value: 'skipped' },
  { label: '已中断', value: 'interrupted' }
]

const triggerTypeOptions = [
  { label: '全部类型', value: '' },
  { label: '定时', value: 'scheduled' },
  { label: '手动', value: 'manual' },
  { label: '组合', value: 'group' },
  { label: '重试', value: 'retry' }
]

// Dialog states
const taskDetailDialogVisible = ref(false)
const batchDetailDialogVisible = ref(false)
const selectedTask = ref<SyncTask | null>(null)
const selectedBatchDetail = ref<BatchExecutionDetail | null>(null)
const batchDetailLoading = ref(false)

// Batch execution list states
const batchExecutions = ref<ScheduleExecutionRecord[]>([])
const batchExecutionsLoading = ref(false)
const expandedBatchIds = ref<string[]>([])
const batchTasksCache = ref<Record<string, BatchTaskDetail[]>>({})

// Selection for batch delete
const selectedRowKeys = ref<string[]>([])
const batchDeleteLoading = ref(false)

// Batch execution columns with selection
const batchColumns = [
  { colKey: 'row-select', type: 'multiple', width: 48 },
  { colKey: 'expand', type: 'expand', width: 48 },
  { colKey: 'group_name', title: '任务名称', width: 150 },
  { colKey: 'trigger_type', title: '触发方式', width: 90 },
  { colKey: 'date_range', title: '日期范围', width: 180 },
  { colKey: 'started_at', title: '开始时间', width: 160 },
  { colKey: 'status', title: '状态', width: 100 },
  { colKey: 'plugins_count', title: '插件数', width: 100 },
  { colKey: 'operation', title: '操作', width: 140 }
]

// Apply filters
const handleFilterChange = () => {
  fetchBatchExecutions()
}

const handleResetFilters = () => {
  taskStatusFilter.value = ''
  triggerTypeFilter.value = ''
  selectedRowKeys.value = []
  fetchBatchExecutions()
}

// Fetch batch executions with filters
const fetchBatchExecutions = async () => {
  batchExecutionsLoading.value = true
  try {
    const response = await dataStore.fetchScheduleHistory(
      30, 
      100, 
      taskStatusFilter.value || undefined,
      triggerTypeFilter.value || undefined
    )
    batchExecutions.value = response.items || []
    selectedRowKeys.value = []
    // Clear cache to ensure fresh data when expanding rows
    batchTasksCache.value = {}
    expandedBatchIds.value = []
  } finally {
    batchExecutionsLoading.value = false
  }
}

// Handle selection change
const handleSelectionChange = (value: string[]) => {
  selectedRowKeys.value = value
}

// Batch delete executions
const handleBatchDelete = async () => {
  if (selectedRowKeys.value.length === 0) {
    MessagePlugin.warning('请先选择要删除的任务')
    return
  }

  // Check if any running tasks
  const runningTasks = batchExecutions.value.filter(
    e => selectedRowKeys.value.includes(e.execution_id) && e.status === 'running'
  )
  if (runningTasks.length > 0) {
    MessagePlugin.warning('无法删除运行中的任务，请先停止')
    return
  }

  const confirmDialog = DialogPlugin.confirm({
    header: '确认删除',
    body: `确定删除选中的 ${selectedRowKeys.value.length} 个历史任务吗？此操作不可恢复。`,
    confirmBtn: '删除',
    cancelBtn: '取消',
    theme: 'danger',
    onConfirm: async () => {
      batchDeleteLoading.value = true
      confirmDialog.hide()
      try {
        let successCount = 0
        let failCount = 0
        for (const executionId of selectedRowKeys.value) {
          try {
            await datamanageApi.deleteScheduleExecution(executionId)
            successCount++
          } catch (e) {
            failCount++
          }
        }
        if (failCount > 0) {
          MessagePlugin.warning(`删除完成：${successCount} 成功，${failCount} 失败`)
        } else {
          MessagePlugin.success(`已删除 ${successCount} 个任务`)
        }
        selectedRowKeys.value = []
        await fetchBatchExecutions()
      } finally {
        batchDeleteLoading.value = false
      }
    }
  })
}

// Handle batch row expand
const handleBatchExpand = async (value: string[], context: { expandedRowData: ScheduleExecutionRecord[] }) => {
  expandedBatchIds.value = value || []
  
  // Fetch task details for newly expanded rows
  for (const row of context.expandedRowData || []) {
    const executionId = row.execution_id
    if (executionId && !batchTasksCache.value[executionId]) {
      const detail = await dataStore.fetchExecutionDetail(executionId)
      if (detail) {
        batchTasksCache.value[executionId] = detail.tasks
      }
    }
  }
}

// Get tasks for a batch execution
const getBatchTasks = (executionId: string): BatchTaskDetail[] => {
  return batchTasksCache.value[executionId] || []
}

// Handle view batch detail dialog
const handleViewBatchDetail = async (row: ScheduleExecutionRecord) => {
  batchDetailLoading.value = true
  batchDetailDialogVisible.value = true
  try {
    selectedBatchDetail.value = await dataStore.fetchExecutionDetail(row.execution_id)
  } finally {
    batchDetailLoading.value = false
  }
}

// Copy text to clipboard with fallback for non-HTTPS environments
const copyToClipboard = async (text: string): Promise<void> => {
  // Try modern Clipboard API first (requires HTTPS or localhost)
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  // Fallback: use textarea + execCommand for HTTP environments
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  textarea.style.top = '-9999px';
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  try {
    const success = document.execCommand('copy');
    if (!success) {
      throw new Error('execCommand copy failed');
    }
  } finally {
    document.body.removeChild(textarea);
  }
};

// Copy error summary to clipboard
const handleCopyErrorSummary = async () => {
  if (!selectedBatchDetail.value?.error_summary) return;
  try {
    await copyToClipboard(selectedBatchDetail.value.error_summary);
    MessagePlugin.success('错误信息已复制到剪贴板');
  } catch (e) {
    MessagePlugin.error('复制失败');
  }
};

// Stop batch execution
const handleStopExecution = async (executionId: string) => {
  try {
    await dataStore.stopExecution(executionId)
    MessagePlugin.success('已停止执行')
    await fetchBatchExecutions()
  } catch (e: any) {
    MessagePlugin.error(e?.message || '停止失败')
  }
}

// Retry batch execution (in-place, retries failed/cancelled tasks)
const handleRetryBatchExecution = async (executionId: string) => {
  try {
    await dataStore.retryScheduleExecution(executionId)
    MessagePlugin.success('正在重试失败任务')
    await fetchBatchExecutions()
    dataStore.startTaskPolling()
  } catch (e) {
    MessagePlugin.error('重试失败')
  }
}

// Partial retry (only failed tasks) - in-place retry
const handlePartialRetryExecution = async (executionId: string, taskIds?: string[]) => {
  try {
    await dataStore.partialRetryExecution(executionId, taskIds)
    MessagePlugin.success('正在重试失败任务')
    await fetchBatchExecutions()
    batchDetailDialogVisible.value = false
    dataStore.startTaskPolling()
  } catch (e: any) {
    MessagePlugin.error(e?.message || '部分重试失败')
  }
}

// Get brief error message for display in task list
const getErrorBrief = (errorMessage?: string) => {
  if (!errorMessage) return ''
  const stackSeparator = '\n\n--- 堆栈跟踪 ---\n'
  let brief = errorMessage.includes(stackSeparator) 
    ? errorMessage.substring(0, errorMessage.indexOf(stackSeparator))
    : errorMessage
  const maxLen = 40
  if (brief.length > maxLen) {
    brief = brief.substring(0, maxLen) + '...'
  }
  return brief
}

// Batch task status helpers
const getBatchStatusTheme = (status: string) => {
  switch (status) {
    case 'completed': return 'success'
    case 'failed': return 'danger'
    case 'running': return 'warning'
    case 'stopping': return 'warning'
    case 'stopped': return 'default'
    case 'interrupted': return 'danger'
    case 'skipped': return 'default'
    default: return 'default'
  }
}

const getBatchStatusText = (status: string) => {
  switch (status) {
    case 'completed': return '完成'
    case 'failed': return '失败'
    case 'running': return '执行中'
    case 'stopping': return '停止中'
    case 'stopped': return '已停止'
    case 'interrupted': return '中断'
    case 'skipped': return '跳过'
    default: return status
  }
}

const getTaskStatusText = (status: string) => {
  switch (status) {
    case 'completed': return '完成'
    case 'failed': return '失败'
    case 'running': return '执行中'
    case 'pending': return '等待'
    case 'cancelled': return '已取消'
    default: return status
  }
}

const getTriggerTypeTheme = (type: string) => {
  switch (type) {
    case 'scheduled': return 'primary'
    case 'manual': return 'warning'
    case 'group': return 'success'
    case 'retry': return 'default'
    default: return 'default'
  }
}

const getTriggerTypeText = (type: string) => {
  switch (type) {
    case 'scheduled': return '定时'
    case 'manual': return '手动'
    case 'group': return '组合'
    case 'retry': return '重试'
    default: return type
  }
}

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

const formatTime = (timeStr?: string) => {
  if (!timeStr) return '-'
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN')
}

// Get task name from group_name or trigger_type
// Used by both list view AND detail dialog for consistency
const getTaskName = (row: ScheduleExecutionRecord | BatchExecutionDetail) => {
  // 优先使用 group_name（组合名称或插件名称）
  if (row.group_name) {
    return row.group_name
  }
  // 没有 group_name 时，根据 trigger_type 和插件数生成通用名称
  const pluginCount = row.total_plugins || 0
  switch (row.trigger_type) {
    case 'scheduled': 
      return pluginCount > 1 ? `定时同步 (${pluginCount}个)` : '定时同步任务'
    case 'manual': 
      return pluginCount > 1 ? `手动同步 (${pluginCount}个)` : '手动同步任务'
    case 'group': 
      return pluginCount > 1 ? `组合同步 (${pluginCount}个)` : '组合同步任务'
    case 'retry': 
      return pluginCount > 1 ? `重试任务 (${pluginCount}个)` : '重试任务'
    default: 
      return '同步任务'
  }
}

onMounted(() => {
  fetchBatchExecutions()
})
</script>

<template>
  <div class="sync-tasks-view">
    <!-- Permission Check -->
    <template v-if="!isAdmin">
      <t-card class="no-permission-card">
        <div class="permission-denied">
          <t-icon name="error-circle" size="64px" style="color: var(--td-warning-color); margin-bottom: 16px" />
          <h3 style="margin: 0 0 8px 0; font-size: 20px">无访问权限</h3>
          <p style="margin: 0 0 24px 0; color: var(--td-text-color-secondary)">
            数据同步任务管理仅限管理员使用。如需访问，请联系系统管理员。
          </p>
          <t-button theme="primary" @click="$router.push('/')">返回首页</t-button>
        </div>
      </t-card>
    </template>

    <template v-else>
      <t-card title="数据同步任务" subtitle="查看和管理数据同步任务执行记录">
        <!-- Batch Task Header -->
        <div class="filter-bar">
          <t-select
            v-model="taskStatusFilter"
            :options="taskStatusOptions"
            placeholder="状态筛选"
            clearable
            style="width: 130px"
            @change="handleFilterChange"
          />
          <t-select
            v-model="triggerTypeFilter"
            :options="triggerTypeOptions"
            placeholder="类型筛选"
            clearable
            style="width: 130px"
            @change="handleFilterChange"
          />
          <t-button theme="default" variant="outline" @click="handleResetFilters">
            重置
          </t-button>
          <t-button theme="primary" @click="fetchBatchExecutions">
            <t-icon name="refresh" style="margin-right: 4px" />
            刷新
          </t-button>
          <t-divider layout="vertical" />
          <t-button 
            theme="danger" 
            variant="outline"
            :disabled="selectedRowKeys.length === 0"
            :loading="batchDeleteLoading"
            @click="handleBatchDelete"
          >
            <t-icon name="delete" style="margin-right: 4px" />
            批量删除 {{ selectedRowKeys.length > 0 ? `(${selectedRowKeys.length})` : '' }}
          </t-button>
          <div class="filter-result">
            共 <span class="count">{{ batchExecutions.length }}</span> 个任务
          </div>
        </div>

        <!-- Batch Executions Table with Expandable Rows -->
        <t-table
          :data="batchExecutions"
          :columns="batchColumns"
          :loading="batchExecutionsLoading"
          row-key="execution_id"
          :expanded-row-keys="expandedBatchIds"
          :selected-row-keys="selectedRowKeys"
          @expand-change="handleBatchExpand"
          @select-change="handleSelectionChange"
        >
          <!-- Expand Row - Sub Tasks -->
          <template #expandedRow="{ row }">
            <div class="sub-tasks-container">
              <t-table
                :data="getBatchTasks(row.execution_id)"
                :columns="[
                  { colKey: 'plugin_name', title: '插件', width: 180 },
                  { colKey: 'status', title: '状态', width: 100 },
                  { colKey: 'progress', title: '进度', width: 120 },
                  { colKey: 'records_processed', title: '处理记录', width: 120 },
                  { colKey: 'error_brief', title: '错误信息', minWidth: 200 }
                ]"
                size="small"
                row-key="task_id"
              >
                <template #status="{ row: task }">
                  <t-tag :theme="getStatusTheme(task.status)" size="small">
                    {{ getTaskStatusText(task.status) }}
                  </t-tag>
                </template>
                <template #progress="{ row: task }">
                  <t-progress 
                    :percentage="Number(task.progress.toFixed(1))" 
                    size="small"
                    :label="task.progress.toFixed(1) + '%'"
                    :status="task.status === 'completed' && task.records_processed === 0 ? 'warning' : undefined"
                  />
                </template>
                <template #records_processed="{ row: task }">
                  <span v-if="task.records_processed > 0">
                    {{ task.records_processed.toLocaleString() }}
                  </span>
                  <span v-else-if="task.status === 'completed'" class="no-data-warning">
                    <t-icon name="error-circle" size="14px" />
                    无数据
                  </span>
                  <span v-else>0</span>
                </template>
                <template #error_brief="{ row: task }">
                  <span v-if="task.error_message" class="error-brief">
                    {{ getErrorBrief(task.error_message) }}
                  </span>
                  <span v-else-if="task.status === 'completed' && task.records_processed === 0" class="no-data-hint">
                    数据源无该日期数据
                  </span>
                  <span v-else class="no-error">-</span>
                </template>
              </t-table>
            </div>
          </template>

          <!-- Columns -->
          <template #group_name="{ row }">
            <span class="task-name">{{ getTaskName(row) }}</span>
            <span v-if="row.execution_id" class="execution-id">{{ row.execution_id.substring(0, 8) }}</span>
          </template>
          <template #trigger_type="{ row }">
            <t-tag :theme="getTriggerTypeTheme(row.trigger_type)" variant="light" size="small">
              {{ getTriggerTypeText(row.trigger_type) }}
            </t-tag>
          </template>
          <template #date_range="{ row }">
            <span v-if="row.date_range" class="date-range-cell">{{ row.date_range }}</span>
            <span v-else class="no-date-range">-</span>
          </template>
          <template #started_at="{ row }">
            {{ formatTime(row.started_at) }}
          </template>
          <template #status="{ row }">
            <div class="status-cell">
              <t-tag :theme="getBatchStatusTheme(row.status)" size="small">
                {{ getBatchStatusText(row.status) }}
              </t-tag>
              <span v-if="row.failed_plugins > 0" class="failed-badge">
                {{ row.failed_plugins }} 失败
              </span>
            </div>
          </template>
          <template #plugins_count="{ row }">
            <span v-if="row.status === 'skipped'">-</span>
            <span v-else>
              <span class="completed-count">{{ row.completed_plugins }}</span>
              <span class="total-count">/{{ row.total_plugins }}</span>
            </span>
          </template>
          <template #completed_at="{ row }">
            {{ row.completed_at ? formatTime(row.completed_at) : '-' }}
          </template>
          <template #operation="{ row }">
            <t-space>
              <t-link theme="primary" @click="handleViewBatchDetail(row)">
                详情
              </t-link>
              <t-popconfirm 
                v-if="row.status === 'running'" 
                content="确定停止此任务？" 
                @confirm="handleStopExecution(row.execution_id)"
              >
                <t-link theme="danger">停止</t-link>
              </t-popconfirm>
              <t-link 
                v-if="row.failed_plugins > 0 && row.status !== 'running'" 
                theme="warning" 
                @click="handlePartialRetryExecution(row.execution_id)"
              >
                重试失败
              </t-link>
              <t-link 
                v-else-if="row.can_retry" 
                theme="primary" 
                @click="handleRetryBatchExecution(row.execution_id)"
              >
                重试
              </t-link>
            </t-space>
          </template>
        </t-table>
      </t-card>
    </template>

    <!-- Batch Execution Detail Dialog -->
    <t-dialog
      v-model:visible="batchDetailDialogVisible"
      header="任务详情"
      width="900px"
      :footer="false"
    >
      <t-loading :loading="batchDetailLoading">
        <div v-if="selectedBatchDetail" class="batch-detail">
          <!-- Summary -->
          <div class="batch-summary">
            <div class="summary-item">
              <span class="label">任务名称:</span>
              <span class="value">{{ getTaskName(selectedBatchDetail) }}</span>
            </div>
            <div class="summary-item">
              <span class="label">执行ID:</span>
              <span class="value execution-id-full">{{ selectedBatchDetail.execution_id }}</span>
            </div>
            <div class="summary-item">
              <span class="label">触发方式:</span>
              <t-tag :theme="getTriggerTypeTheme(selectedBatchDetail.trigger_type)" variant="light" size="small">
                {{ getTriggerTypeText(selectedBatchDetail.trigger_type) }}
              </t-tag>
            </div>
            <div class="summary-item">
              <span class="label">状态:</span>
              <t-tag :theme="getBatchStatusTheme(selectedBatchDetail.status)" size="small">
                {{ getBatchStatusText(selectedBatchDetail.status) }}
              </t-tag>
            </div>
            <div class="summary-item">
              <span class="label">插件数:</span>
              <span class="value">
                <span class="completed-count">{{ selectedBatchDetail.completed_plugins }}</span>
                <span class="total-count">/{{ selectedBatchDetail.total_plugins }}</span>
                <span v-if="selectedBatchDetail.failed_plugins > 0" class="failed-badge">
                  ({{ selectedBatchDetail.failed_plugins }} 失败)
                </span>
              </span>
            </div>
            <div v-if="selectedBatchDetail.date_range" class="summary-item full-width">
              <span class="label">日期范围:</span>
              <span class="value date-range-value">{{ selectedBatchDetail.date_range }}</span>
            </div>
            <div v-if="selectedBatchDetail.status === 'running'" class="summary-item">
              <t-popconfirm content="确定停止此任务？" @confirm="handleStopExecution(selectedBatchDetail.execution_id)">
                <t-button theme="danger" size="small">
                  <t-icon name="close" style="margin-right: 4px" />
                  停止任务
                </t-button>
              </t-popconfirm>
            </div>
            <div v-if="selectedBatchDetail.failed_plugins > 0 && selectedBatchDetail.status !== 'running'" class="summary-item">
              <t-button theme="warning" size="small" @click="handlePartialRetryExecution(selectedBatchDetail.execution_id)">
                <t-icon name="refresh" style="margin-right: 4px" />
                重试失败任务
              </t-button>
            </div>
          </div>
          
          <!-- Tasks Table -->
          <div class="batch-tasks">
            <h4>子任务列表</h4>
            <t-table
              :data="selectedBatchDetail.tasks"
              :columns="[
                { colKey: 'plugin_name', title: '插件', width: 180 },
                { colKey: 'status', title: '状态', width: 100 },
                { colKey: 'progress', title: '进度', width: 120 },
                { colKey: 'records_processed', title: '处理记录', width: 120 },
                { colKey: 'error_brief', title: '错误信息', minWidth: 200 }
              ]"
              size="small"
              row-key="task_id"
              max-height="300"
            >
              <template #status="{ row }">
                <t-tag :theme="getStatusTheme(row.status)" size="small">
                  {{ getTaskStatusText(row.status) }}
                </t-tag>
              </template>
              <template #progress="{ row }">
                <t-progress 
                  :percentage="Number(row.progress.toFixed(1))" 
                  size="small"
                  :label="row.progress.toFixed(1) + '%'"
                  :status="row.status === 'completed' && row.records_processed === 0 ? 'warning' : undefined"
                />
              </template>
              <template #records_processed="{ row }">
                <span v-if="row.records_processed > 0">
                  {{ row.records_processed.toLocaleString() }}
                </span>
                <span v-else-if="row.status === 'completed'" class="no-data-warning">
                  <t-icon name="error-circle" size="14px" />
                  无数据
                </span>
                <span v-else>0</span>
              </template>
              <template #error_brief="{ row }">
                <span v-if="row.error_message" class="error-brief">
                  {{ getErrorBrief(row.error_message) }}
                </span>
                <span v-else-if="row.status === 'completed' && row.records_processed === 0" class="no-data-hint">
                  数据源无该日期数据
                </span>
                <span v-else class="no-error">-</span>
              </template>
            </t-table>
          </div>
          
          <!-- Error Summary with Copy Button -->
          <div v-if="selectedBatchDetail.error_summary" class="error-summary-section">
            <div class="error-header">
              <h4>错误信息汇总</h4>
              <t-button theme="primary" variant="outline" size="small" @click="handleCopyErrorSummary">
                <t-icon name="file-copy" style="margin-right: 4px" />
                一键复制
              </t-button>
            </div>
            <pre class="error-content">{{ selectedBatchDetail.error_summary }}</pre>
          </div>
          
          <div v-else class="no-errors">
            <t-icon name="check-circle" size="20px" style="color: var(--td-success-color); margin-right: 8px" />
            所有任务执行成功，无错误信息
          </div>
        </div>
      </t-loading>
    </t-dialog>
    
    <TaskDetailDialog
      v-model:visible="taskDetailDialogVisible"
      :task="selectedTask"
    />
  </div>
</template>

<style scoped>
.sync-tasks-view {
  height: 100%;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding: 12px 16px;
  background: var(--td-bg-color-container-hover);
  border-radius: 6px;
}

.filter-result {
  margin-left: auto;
  font-size: 14px;
  color: var(--td-text-color-secondary);
}

.filter-result .count {
  font-weight: 600;
  color: var(--td-brand-color);
}

.no-permission-card {
  margin-top: 100px;
  max-width: 500px;
  margin-left: auto;
  margin-right: auto;
}

.permission-denied {
  text-align: center;
  padding: 40px 20px;
}

/* Task name styles */
.task-name {
  font-weight: 500;
  color: var(--td-text-color-primary);
}

.execution-id {
  display: block;
  font-family: monospace;
  font-size: 11px;
  color: var(--td-text-color-placeholder);
  margin-top: 2px;
}

.execution-id-full {
  font-family: monospace;
  font-size: 12px;
}

/* Batch task styles */
.sub-tasks-container {
  padding: 8px 16px;
  background: var(--td-bg-color-container);
}

.status-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.failed-badge {
  margin-left: 8px;
  font-size: 12px;
  color: var(--td-error-color);
}

.completed-count {
  color: var(--td-success-color);
  font-weight: 600;
}

.total-count {
  color: var(--td-text-color-secondary);
}

.error-brief {
  color: var(--td-error-color);
  font-size: 12px;
}

.no-error {
  color: var(--td-text-color-placeholder);
}

.no-data-warning {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--td-warning-color);
  font-size: 12px;
}

.no-data-hint {
  color: var(--td-warning-color-hover);
  font-size: 12px;
}

/* Batch detail dialog styles */
.batch-detail {
  padding: 8px 0;
}

.batch-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  padding: 16px;
  background: var(--td-bg-color-container-hover);
  border-radius: 6px;
  margin-bottom: 16px;
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.summary-item .label {
  color: var(--td-text-color-secondary);
  font-size: 13px;
}

.summary-item .value {
  font-weight: 500;
}

.batch-tasks {
  margin-bottom: 16px;
}

.batch-tasks h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: var(--td-text-color-primary);
}

.error-summary-section {
  border-top: 1px solid var(--td-border-level-1-color);
  padding-top: 16px;
}

.error-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.error-header h4 {
  margin: 0;
  font-size: 14px;
  color: var(--td-text-color-primary);
}

.error-content {
  background: var(--td-bg-color-container-hover);
  padding: 16px;
  border-radius: 6px;
  font-family: monospace;
  font-size: 12px;
  line-height: 1.6;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--td-error-color);
  margin: 0;
}

.no-errors {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: var(--td-success-color);
  font-size: 14px;
}
</style>
