<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { useDataManageStore } from '@/stores/datamanage'
import MissingDataPanel from './components/MissingDataPanel.vue'
import SyncTaskPanel from './components/SyncTaskPanel.vue'
import PluginDetailDialog from './components/PluginDetailDialog.vue'
import PluginDataDialog from './components/PluginDataDialog.vue'
import DiagnosisPanel from './components/DiagnosisPanel.vue'
import SyncDialog from './components/SyncDialog.vue'

const dataStore = useDataManageStore()
const activeTab = ref('plugins')

// Dialog states
const detailDialogVisible = ref(false)
const dataDialogVisible = ref(false)
const syncDialogVisible = ref(false)
const selectedPluginName = ref('')

const pluginColumns = [
  { colKey: 'name', title: '插件名称', width: 180 },
  { colKey: 'description', title: '描述', minWidth: 200, ellipsis: true },
  { colKey: 'schedule_frequency', title: '调度频率', width: 100 },
  { colKey: 'latest_date', title: '最新数据', width: 120 },
  { colKey: 'missing_count', title: '缺失天数', width: 100 },
  { colKey: 'is_enabled', title: '状态', width: 80 },
  { colKey: 'operation', title: '操作', width: 200, fixed: 'right' }
]

const taskColumns = [
  { colKey: 'plugin_name', title: '插件', width: 150 },
  { colKey: 'task_type', title: '类型', width: 100 },
  { colKey: 'status', title: '状态', width: 100 },
  { colKey: 'progress', title: '进度', width: 150 },
  { colKey: 'records_processed', title: '处理记录', width: 100 },
  { colKey: 'started_at', title: '开始时间', width: 150 },
  { colKey: 'operation', title: '操作', width: 100 }
]

const qualityColumns = [
  { colKey: 'table_name', title: '表名', width: 150 },
  { colKey: 'overall_score', title: '综合得分', width: 100 },
  { colKey: 'completeness_score', title: '完整性', width: 100 },
  { colKey: 'timeliness_score', title: '时效性', width: 100 },
  { colKey: 'record_count', title: '记录数', width: 100 },
  { colKey: 'latest_update', title: '最后更新', width: 150 }
]

const handleViewDetail = (name: string) => {
  selectedPluginName.value = name
  detailDialogVisible.value = true
}

const handleViewData = (name: string) => {
  selectedPluginName.value = name
  dataDialogVisible.value = true
}

const handleOpenSyncDialog = (name: string) => {
  selectedPluginName.value = name
  syncDialogVisible.value = true
}

const handleSyncConfirm = async (
  pluginName: string, 
  taskType: 'incremental' | 'full' | 'backfill', 
  dates: string[],
  forceOverwrite: boolean
) => {
  try {
    await dataStore.triggerSync({
      plugin_name: pluginName,
      task_type: taskType,
      trade_dates: dates.length > 0 ? dates : undefined,
      force_overwrite: forceOverwrite
    })
    MessagePlugin.success('同步任务已创建')
    // Start polling for task updates
    dataStore.startTaskPolling()
  } catch (e) {
    MessagePlugin.error('创建同步任务失败')
  }
}

const handleTriggerSync = (pluginName: string) => {
  // Open sync dialog instead of directly triggering
  handleOpenSyncDialog(pluginName)
}

const handleBackfill = (pluginName: string, _dates: string[]) => {
  // Open sync dialog with backfill mode (dates are passed but we let user select in dialog)
  selectedPluginName.value = pluginName
  syncDialogVisible.value = true
}

const handleTogglePlugin = (name: string, enabled: boolean) => {
  if (enabled) {
    dataStore.disablePlugin(name)
  } else {
    dataStore.enablePlugin(name)
  }
}

const handleCancelTask = async (taskId: string) => {
  try {
    await dataStore.cancelTask(taskId)
    MessagePlugin.success('任务已取消')
  } catch (e) {
    MessagePlugin.error('取消任务失败')
  }
}

const getFrequencyText = (freq?: string) => {
  if (!freq) return '-'
  return freq === 'daily' ? '每日' : freq === 'weekly' ? '每周' : freq
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

const overallQuality = computed(() => {
  if (!dataStore.qualityMetrics.length) return 0
  const sum = dataStore.qualityMetrics.reduce((acc, m) => acc + m.overall_score, 0)
  return (sum / dataStore.qualityMetrics.length).toFixed(1)
})

const pluginsWithMissing = computed(() => {
  return dataStore.plugins.filter(p => p.missing_count > 0).length
})

const formatTime = (timeStr?: string) => {
  if (!timeStr) return '-'
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN')
}

onMounted(() => {
  dataStore.fetchDataSources()
  dataStore.fetchSyncTasks()
  dataStore.fetchPlugins()
  dataStore.fetchQualityMetrics()
  dataStore.fetchMissingData()
})
</script>

<template>
  <div class="datamanage-view">
    <!-- Stats Cards -->
    <t-row :gutter="16" style="margin-bottom: 16px">
      <t-col :span="3">
        <t-card title="已注册插件" :bordered="false">
          <div class="stat-value">{{ dataStore.plugins.length }}</div>
        </t-card>
      </t-col>
      <t-col :span="3">
        <t-card title="数据缺失" :bordered="false">
          <div class="stat-value" :style="{ color: pluginsWithMissing > 0 ? '#e34d59' : '#00a870' }">
            {{ pluginsWithMissing }}
          </div>
        </t-card>
      </t-col>
      <t-col :span="3">
        <t-card title="运行中任务" :bordered="false">
          <div class="stat-value">
            {{ dataStore.syncTasks.filter(t => t.status === 'running').length }}
          </div>
        </t-card>
      </t-col>
      <t-col :span="3">
        <t-card title="数据质量" :bordered="false">
          <div class="stat-value" :style="{ color: Number(overallQuality) >= 80 ? '#00a870' : '#e34d59' }">
            {{ overallQuality }}%
          </div>
        </t-card>
      </t-col>
    </t-row>

    <!-- Missing Data Panel -->
    <MissingDataPanel @sync="handleBackfill" />

    <!-- AI Diagnosis Panel -->
    <DiagnosisPanel />

    <!-- Main Content -->
    <t-card>
      <t-tabs v-model="activeTab">
        <!-- Plugins Tab -->
        <t-tab-panel value="plugins" label="插件管理">
          <t-table
            :data="dataStore.plugins"
            :columns="pluginColumns"
            :loading="dataStore.loading"
            row-key="name"
            hover
          >
            <template #schedule_frequency="{ row }">
              <t-tag :theme="row.schedule_frequency === 'daily' ? 'primary' : 'default'" variant="light">
                {{ getFrequencyText(row.schedule_frequency) }}
              </t-tag>
            </template>
            <template #latest_date="{ row }">
              {{ row.latest_date || '-' }}
            </template>
            <template #missing_count="{ row }">
              <t-tag :theme="row.missing_count > 0 ? 'danger' : 'success'">
                {{ row.missing_count }}
              </t-tag>
            </template>
            <template #is_enabled="{ row }">
              <t-switch
                :value="row.is_enabled"
                @change="handleTogglePlugin(row.name, row.is_enabled)"
              />
            </template>
            <template #operation="{ row }">
              <t-space>
                <t-link theme="primary" @click="handleViewDetail(row.name)">详情</t-link>
                <t-link theme="primary" @click="handleViewData(row.name)">数据</t-link>
                <t-link theme="primary" @click="handleTriggerSync(row.name)">同步</t-link>
              </t-space>
            </template>
          </t-table>
        </t-tab-panel>

        <!-- Tasks Tab -->
        <t-tab-panel value="tasks" label="同步任务">
          <t-table
            :data="dataStore.syncTasks"
            :columns="taskColumns"
            :loading="dataStore.loading"
            row-key="task_id"
          >
            <template #task_type="{ row }">
              {{ row.task_type === 'incremental' ? '增量' : row.task_type === 'full' ? '全量' : '补录' }}
            </template>
            <template #status="{ row }">
              <t-tag :theme="getStatusTheme(row.status)">
                {{ row.status }}
              </t-tag>
            </template>
            <template #progress="{ row }">
              <t-progress 
                :percentage="row.progress" 
                :status="row.status === 'running' ? 'active' : 'default'"
                size="small" 
              />
            </template>
            <template #records_processed="{ row }">
              {{ row.records_processed.toLocaleString() }}
            </template>
            <template #started_at="{ row }">
              {{ formatTime(row.started_at) }}
            </template>
            <template #operation="{ row }">
              <t-link 
                v-if="row.status === 'pending'" 
                theme="danger" 
                @click="handleCancelTask(row.task_id)"
              >
                取消
              </t-link>
            </template>
          </t-table>
        </t-tab-panel>

        <!-- Quality Tab -->
        <t-tab-panel value="quality" label="数据质量">
          <t-table
            :data="dataStore.qualityMetrics"
            :columns="qualityColumns"
            :loading="dataStore.loading"
            row-key="table_name"
          >
            <template #overall_score="{ row }">
              <t-tag :theme="row.overall_score >= 80 ? 'success' : row.overall_score >= 60 ? 'warning' : 'danger'">
                {{ row.overall_score.toFixed(1) }}%
              </t-tag>
            </template>
            <template #completeness_score="{ row }">
              {{ row.completeness_score.toFixed(1) }}%
            </template>
            <template #timeliness_score="{ row }">
              {{ row.timeliness_score.toFixed(1) }}%
            </template>
            <template #record_count="{ row }">
              {{ row.record_count.toLocaleString() }}
            </template>
          </t-table>
        </t-tab-panel>
      </t-tabs>
    </t-card>

    <!-- Dialogs -->
    <PluginDetailDialog 
      v-model:visible="detailDialogVisible" 
      :plugin-name="selectedPluginName" 
    />
    <PluginDataDialog 
      v-model:visible="dataDialogVisible" 
      :plugin-name="selectedPluginName" 
    />
    <SyncDialog
      v-model:visible="syncDialogVisible"
      :plugin-name="selectedPluginName"
      @confirm="handleSyncConfirm"
    />
  </div>
</template>

<style scoped>
.datamanage-view {
  height: 100%;
}

.stat-value {
  font-size: 32px;
  font-weight: 600;
  color: #0052d9;
}
</style>
