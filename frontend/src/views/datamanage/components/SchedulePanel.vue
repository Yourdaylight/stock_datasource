<template>
  <t-card class="schedule-panel">
    <template #header>
      <div class="schedule-header">
        <span class="title">定时调度配置</span>
        <t-switch 
          v-model="config.enabled" 
          @change="handleEnabledChange"
          :loading="saving"
        />
      </div>
    </template>
    
    <!-- 配置项 -->
    <t-form label-width="140px" :disabled="!config.enabled">
      <t-form-item label="执行时间">
        <div class="form-row">
          <t-time-picker 
            v-model="executeTime" 
            format="HH:mm"
            :clearable="false"
            @change="handleConfigChange"
            style="width: 120px"
          />
          <t-select v-model="config.frequency" style="width: 120px; margin-left: 8px" @change="handleConfigChange">
            <t-option label="每天" value="daily" />
            <t-option label="仅工作日" value="weekday" />
          </t-select>
        </div>
      </t-form-item>
      
      <t-form-item label="包含可选依赖">
        <div class="form-row">
          <t-switch 
            v-model="config.include_optional_deps"
            @change="handleConfigChange"
          />
          <t-tooltip content="如复权因子等衍生数据，在同步主数据时一并同步">
            <t-icon name="help-circle" class="help-icon" />
          </t-tooltip>
        </div>
      </t-form-item>
      
      <t-form-item label="跳过非交易日">
        <div class="form-row">
          <t-switch 
            v-model="config.skip_non_trading_days"
            @change="handleConfigChange"
          />
          <t-tooltip content="非交易日不执行同步任务，避免无效请求">
            <t-icon name="help-circle" class="help-icon" />
          </t-tooltip>
        </div>
      </t-form-item>
      
      <t-form-item label="下次执行时间" v-if="config.enabled && config.next_run_at">
        <span class="next-run-time">{{ formatDateTime(config.next_run_at) }}</span>
      </t-form-item>
      
      <t-form-item label="上次执行时间" v-if="config.last_run_at">
        <span class="last-run-time">{{ formatDateTime(config.last_run_at) }}</span>
      </t-form-item>
    </t-form>
    
    <!-- 操作按钮 -->
    <div class="action-buttons">
      <t-button theme="primary" @click="handleTriggerNow" :loading="triggering">
        立即执行一次
      </t-button>
      <t-button theme="default" @click="showHistoryDialog = true">
        查看执行历史
      </t-button>
    </div>
    
    <!-- 操作说明 -->
    <t-alert theme="info" :close="false" class="info-alert">
      <template #message>
        <div class="alert-title">操作说明</div>
        <ul class="alert-list">
          <li>定时调度会在每个交易日自动执行增量同步</li>
          <li>插件按依赖顺序执行：基础数据 → 主数据 → 衍生数据</li>
          <li>开启"全量扫描"会重新获取全部历史数据（耗时较长）</li>
          <li>建议仅在数据异常时开启全量扫描</li>
        </ul>
      </template>
    </t-alert>
    
    <!-- 执行历史对话框 -->
    <t-dialog 
      v-model:visible="showHistoryDialog" 
      header="调度执行历史" 
      width="800px"
      :footer="false"
    >
      <t-table :data="history" :loading="historyLoading" row-key="execution_id">
        <t-table-column label="执行时间" prop="started_at" width="180">
          <template #cell="{ row }">
            {{ formatDateTime(row.started_at) }}
          </template>
        </t-table-column>
        <t-table-column label="触发方式" prop="trigger_type" width="100">
          <template #cell="{ row }">
            <t-tag :theme="row.trigger_type === 'manual' ? 'warning' : 'primary'" variant="light" size="small">
              {{ row.trigger_type === 'manual' ? '手动' : '定时' }}
            </t-tag>
          </template>
        </t-table-column>
        <t-table-column label="状态" prop="status" width="100">
          <template #cell="{ row }">
            <t-tag :theme="getStatusTheme(row.status)" variant="light" size="small">
              {{ getStatusLabel(row.status) }}
            </t-tag>
          </template>
        </t-table-column>
        <t-table-column label="插件数" width="120">
          <template #cell="{ row }">
            <span v-if="row.status === 'skipped'">-</span>
            <span v-else>
              {{ row.completed_plugins }}/{{ row.total_plugins }}
              <span v-if="row.failed_plugins > 0" class="failed-count">
                ({{ row.failed_plugins }}失败)
              </span>
            </span>
          </template>
        </t-table-column>
        <t-table-column label="完成时间" prop="completed_at" width="180">
          <template #cell="{ row }">
            {{ row.completed_at ? formatDateTime(row.completed_at) : '-' }}
          </template>
        </t-table-column>
        <t-table-column label="备注">
          <template #cell="{ row }">
            <span v-if="row.skip_reason" class="skip-reason">{{ row.skip_reason }}</span>
            <span v-else-if="row.task_ids?.length" class="task-count">
              {{ row.task_ids.length }} 个任务
            </span>
          </template>
        </t-table-column>
      </t-table>
    </t-dialog>
  </t-card>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { useDataManageStore } from '@/stores/datamanage'
import type { ScheduleConfig, ScheduleExecutionRecord } from '@/api/datamanage'

const store = useDataManageStore()

const config = reactive<ScheduleConfig>({
  enabled: false,
  cron_expression: '0 18 * * 1-5',
  execute_time: '18:00',
  frequency: 'weekday',
  include_optional_deps: true,
  skip_non_trading_days: true,
  last_run_at: undefined,
  next_run_at: undefined
})

const executeTime = ref('18:00')
const saving = ref(false)
const triggering = ref(false)
const showHistoryDialog = ref(false)
const historyLoading = ref(false)
const history = ref<ScheduleExecutionRecord[]>([])

onMounted(async () => {
  await loadConfig()
})

const loadConfig = async () => {
  const data = await store.fetchScheduleConfig()
  if (data) {
    Object.assign(config, data)
    executeTime.value = data.execute_time || '18:00'
  }
}

watch(showHistoryDialog, async (visible) => {
  if (visible) {
    historyLoading.value = true
    const response = await store.fetchScheduleHistory(7, 50)
    history.value = response.items || []
    historyLoading.value = false
  }
})

const handleEnabledChange = async (enabled: boolean) => {
  saving.value = true
  try {
    await store.updateScheduleConfig({ enabled })
    MessagePlugin.success(enabled ? '定时调度已启用' : '定时调度已禁用')
    await loadConfig()
  } catch (e) {
    MessagePlugin.error('更新失败')
    config.enabled = !enabled
  } finally {
    saving.value = false
  }
}

const handleConfigChange = async () => {
  saving.value = true
  try {
    await store.updateScheduleConfig({
      execute_time: executeTime.value,
      frequency: config.frequency,
      include_optional_deps: config.include_optional_deps,
      skip_non_trading_days: config.skip_non_trading_days
    })
    await loadConfig()
  } catch (e) {
    MessagePlugin.error('更新失败')
  } finally {
    saving.value = false
  }
}

const handleTriggerNow = async () => {
  triggering.value = true
  try {
    const record = await store.triggerScheduleNow()
    if (record.status === 'skipped') {
      MessagePlugin.warning(`调度已跳过：${record.skip_reason}`)
    } else {
      MessagePlugin.success(`已创建 ${record.task_ids?.length || 0} 个同步任务`)
    }
    await loadConfig()
  } catch (e) {
    MessagePlugin.error('触发失败')
  } finally {
    triggering.value = false
  }
}

const formatDateTime = (dateStr?: string) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const getStatusTheme = (status: string) => {
  switch (status) {
    case 'completed': return 'success'
    case 'failed': return 'danger'
    case 'running': return 'warning'
    case 'skipped': return 'default'
    default: return 'default'
  }
}

const getStatusLabel = (status: string) => {
  switch (status) {
    case 'completed': return '完成'
    case 'failed': return '失败'
    case 'running': return '执行中'
    case 'skipped': return '跳过'
    default: return status
  }
}
</script>

<style scoped>
.schedule-panel {
  margin-bottom: 20px;
}

.schedule-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.schedule-header .title {
  font-size: 16px;
  font-weight: 600;
}

.form-row {
  display: flex;
  align-items: center;
}

.help-icon {
  margin-left: 8px;
  color: var(--td-text-color-placeholder);
  cursor: help;
}

.next-run-time {
  color: var(--td-brand-color);
  font-weight: 500;
}

.last-run-time {
  color: var(--td-text-color-secondary);
}

.action-buttons {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}

.info-alert {
  margin-top: 16px;
}

.alert-title {
  font-weight: 600;
  margin-bottom: 8px;
}

.alert-list {
  list-style-type: disc;
  margin-left: 20px;
  font-size: 13px;
  color: var(--td-text-color-secondary);
  line-height: 1.8;
}

.failed-count {
  color: var(--td-error-color);
}

.skip-reason {
  color: var(--td-text-color-placeholder);
}

.task-count {
  color: var(--td-brand-color);
}
</style>
