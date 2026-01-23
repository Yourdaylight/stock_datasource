<template>
  <t-card title="定时任务配置" class="schedule-config-panel">
    <template #actions>
      <t-tag v-if="status.is_running" theme="success">运行中</t-tag>
      <t-tag v-else-if="status.enabled" theme="warning">已启用 (未运行)</t-tag>
      <t-tag v-else theme="default">未启用</t-tag>
    </template>

    <t-loading :loading="loading">
      <t-alert
        theme="info"
        message="定时任务会在指定时间自动执行数据同步和分析任务。仅在交易日执行。"
        style="margin-bottom: 16px"
      />

      <t-form
        ref="formRef"
        :data="config"
        label-width="140px"
        @submit="handleSave"
      >
        <t-form-item label="启用定时任务">
          <t-switch v-model="config.enabled" />
          <span class="form-help">启用后，系统将在指定时间自动执行任务</span>
        </t-form-item>

        <t-form-item label="数据同步时间">
          <t-time-picker
            v-model="config.data_sync_time"
            format="HH:mm"
            :disabled="!config.enabled"
            style="width: 150px"
          />
          <span class="form-help">每日自动同步所有启用的日频插件数据</span>
        </t-form-item>

        <t-form-item label="分析任务时间">
          <t-time-picker
            v-model="config.analysis_time"
            format="HH:mm"
            :disabled="!config.enabled"
            style="width: 150px"
          />
          <span class="form-help">每日自动运行投资组合分析</span>
        </t-form-item>

        <t-form-item>
          <t-space>
            <t-button theme="primary" type="submit" :loading="saving">
              保存配置
            </t-button>
            <t-button
              v-if="!status.is_running && status.enabled"
              theme="success"
              :loading="starting"
              @click="handleStart"
            >
              启动调度器
            </t-button>
            <t-button
              v-if="status.is_running"
              theme="warning"
              :loading="stopping"
              @click="handleStop"
            >
              停止调度器
            </t-button>
          </t-space>
        </t-form-item>
      </t-form>

      <!-- Status Info -->
      <t-divider>任务状态</t-divider>

      <t-descriptions :column="2" layout="horizontal" size="small">
        <t-descriptions-item label="调度器状态">
          <t-tag :theme="status.is_running ? 'success' : 'default'" size="small">
            {{ status.is_running ? '运行中' : '已停止' }}
          </t-tag>
        </t-descriptions-item>
        <t-descriptions-item label="当前任务">
          <t-tag v-if="status.current_task" theme="primary" size="small">
            {{ status.current_task === 'data_sync' ? '数据同步' : '分析任务' }}
          </t-tag>
          <span v-else class="text-placeholder">无</span>
        </t-descriptions-item>
        <t-descriptions-item label="下次数据同步">
          {{ formatNextRun(status.next_data_sync) }}
        </t-descriptions-item>
        <t-descriptions-item label="下次分析任务">
          {{ formatNextRun(status.next_analysis) }}
        </t-descriptions-item>
        <t-descriptions-item label="上次数据同步">
          {{ formatLastRun(status.last_data_sync) }}
        </t-descriptions-item>
        <t-descriptions-item label="上次分析任务">
          {{ formatLastRun(status.last_analysis) }}
        </t-descriptions-item>
      </t-descriptions>

      <!-- Manual Trigger -->
      <t-divider>手动执行</t-divider>

      <t-space>
        <t-button
          variant="outline"
          :loading="runningDataSync"
          @click="handleRunNow('data_sync')"
        >
          <template #icon><t-icon name="refresh" /></template>
          立即同步数据
        </t-button>
        <t-button
          variant="outline"
          :loading="runningAnalysis"
          @click="handleRunNow('analysis')"
        >
          <template #icon><t-icon name="chart-line" /></template>
          立即运行分析
        </t-button>
        <t-button variant="text" @click="loadStatus">
          刷新状态
        </t-button>
      </t-space>
    </t-loading>
  </t-card>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { datamanageApi, type SchedulerStatus, type SchedulerConfigUpdate } from '@/api/datamanage'

const formRef = ref()
const loading = ref(false)
const saving = ref(false)
const starting = ref(false)
const stopping = ref(false)
const runningDataSync = ref(false)
const runningAnalysis = ref(false)

const config = reactive<SchedulerConfigUpdate>({
  enabled: false,
  data_sync_time: '18:00',
  analysis_time: '18:30'
})

const status = reactive<SchedulerStatus & { current_task?: string }>({
  enabled: false,
  is_running: false,
  data_sync_time: '18:00',
  analysis_time: '18:30',
  next_data_sync: undefined,
  next_analysis: undefined,
  last_data_sync: undefined,
  last_analysis: undefined,
  current_task: undefined
})

let refreshInterval: ReturnType<typeof setInterval> | null = null

const loadStatus = async () => {
  loading.value = true
  try {
    const data = await datamanageApi.getSchedulerStatus()
    Object.assign(status, data)
    config.enabled = data.enabled
    config.data_sync_time = data.data_sync_time
    config.analysis_time = data.analysis_time
  } catch (error) {
    console.error('Failed to load scheduler status:', error)
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  saving.value = true
  try {
    await datamanageApi.updateSchedulerConfig({
      enabled: config.enabled,
      data_sync_time: config.data_sync_time,
      analysis_time: config.analysis_time
    })
    MessagePlugin.success('配置已保存')
    await loadStatus()
  } catch (error) {
    MessagePlugin.error('保存配置失败')
  } finally {
    saving.value = false
  }
}

const handleStart = async () => {
  starting.value = true
  try {
    await datamanageApi.startScheduler()
    MessagePlugin.success('调度器已启动')
    await loadStatus()
  } catch (error) {
    MessagePlugin.error('启动调度器失败')
  } finally {
    starting.value = false
  }
}

const handleStop = async () => {
  stopping.value = true
  try {
    await datamanageApi.stopScheduler()
    MessagePlugin.success('调度器已停止')
    await loadStatus()
  } catch (error) {
    MessagePlugin.error('停止调度器失败')
  } finally {
    stopping.value = false
  }
}

const handleRunNow = async (taskType: 'data_sync' | 'analysis') => {
  if (taskType === 'data_sync') {
    runningDataSync.value = true
  } else {
    runningAnalysis.value = true
  }
  
  try {
    const result = await datamanageApi.runSchedulerNow(taskType)
    MessagePlugin.success(result.message)
    // Refresh status after a short delay
    setTimeout(loadStatus, 1000)
  } catch (error) {
    MessagePlugin.error('执行任务失败')
  } finally {
    if (taskType === 'data_sync') {
      runningDataSync.value = false
    } else {
      runningAnalysis.value = false
    }
  }
}

const formatNextRun = (dateStr?: string): string => {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateStr
  }
}

const formatLastRun = (dateStr?: string): string => {
  if (!dateStr) return '从未执行'
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateStr
  }
}

onMounted(() => {
  loadStatus()
  // Refresh status every 30 seconds
  refreshInterval = setInterval(loadStatus, 30000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
.schedule-config-panel {
  margin-bottom: 16px;
}

.form-help {
  margin-left: 12px;
  color: #909399;
  font-size: 12px;
}

.text-placeholder {
  color: #909399;
}
</style>
