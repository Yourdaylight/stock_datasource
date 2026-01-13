<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { useDataManageStore } from '@/stores/datamanage'
import type { PluginCategory, PluginRole } from '@/api/datamanage'
import MissingDataPanel from './components/MissingDataPanel.vue'
import SyncTaskPanel from './components/SyncTaskPanel.vue'
import PluginDetailDialog from './components/PluginDetailDialog.vue'
import PluginDataDialog from './components/PluginDataDialog.vue'
import DiagnosisPanel from './components/DiagnosisPanel.vue'
import SyncDialog from './components/SyncDialog.vue'
import ProxyConfigPanel from './components/ProxyConfigPanel.vue'

const dataStore = useDataManageStore()
const activeTab = ref('plugins')

// Plugin filter states
const searchKeyword = ref('')
const selectedCategory = ref<PluginCategory | ''>('')
const selectedRole = ref<PluginRole | ''>('')

const categoryOptions = [
  { label: '全部类别', value: '' },
  { label: '股票', value: 'stock' },
  { label: '指数', value: 'index' },
  { label: 'ETF基金', value: 'etf_fund' },
  { label: '系统', value: 'system' }
]

const roleOptions = [
  { label: '全部角色', value: '' },
  { label: '主数据', value: 'primary' },
  { label: '基础数据', value: 'basic' },
  { label: '衍生数据', value: 'derived' },
  { label: '辅助数据', value: 'auxiliary' }
]

// Filtered plugins based on search and filters
const filteredPlugins = computed(() => {
  let result = dataStore.plugins
  
  // Filter by keyword
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    result = result.filter(p => 
      p.name.toLowerCase().includes(keyword) || 
      p.description.toLowerCase().includes(keyword)
    )
  }
  
  // Filter by category
  if (selectedCategory.value) {
    result = result.filter(p => p.category === selectedCategory.value)
  }
  
  // Filter by role
  if (selectedRole.value) {
    result = result.filter(p => p.role === selectedRole.value)
  }
  
  return result
})

const handleResetFilters = () => {
  searchKeyword.value = ''
  selectedCategory.value = ''
  selectedRole.value = ''
}

// Dialog states
const detailDialogVisible = ref(false)
const dataDialogVisible = ref(false)
const syncDialogVisible = ref(false)
const selectedPluginName = ref('')

const pluginColumns = [
  { colKey: 'name', title: '插件名称', width: 180 },
  { colKey: 'description', title: '描述', minWidth: 200, ellipsis: true },
  { colKey: 'category', title: '类别', width: 100 },
  { colKey: 'role', title: '角色', width: 100 },
  { colKey: 'schedule_frequency', title: '调度频率', width: 100 },
  { colKey: 'latest_date', title: '最新数据', width: 120 },
  { colKey: 'missing_count', title: '缺失天数', width: 100 },
  { colKey: 'is_enabled', title: '状态', width: 80 },
  { colKey: 'operation', title: '操作', width: 200, fixed: 'right' }
]

const getCategoryText = (category?: string) => {
  const map: Record<string, string> = {
    stock: '股票',
    index: '指数',
    etf_fund: 'ETF基金',
    system: '系统'
  }
  return category ? map[category] || category : '-'
}

const getRoleText = (role?: string) => {
  const map: Record<string, string> = {
    primary: '主数据',
    basic: '基础数据',
    derived: '衍生数据',
    auxiliary: '辅助数据'
  }
  return role ? map[role] || role : '-'
}

const getCategoryTheme = (category?: string) => {
  const map: Record<string, string> = {
    stock: 'primary',
    index: 'success',
    etf_fund: 'warning',
    system: 'default'
  }
  return category ? map[category] || 'default' : 'default'
}

const getRoleTheme = (role?: string) => {
  const map: Record<string, string> = {
    primary: 'primary',
    basic: 'success',
    derived: 'warning',
    auxiliary: 'default'
  }
  return role ? map[role] || 'default' : 'default'
}

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


    <!-- Main Content -->
    <t-card>
      <t-tabs v-model="activeTab">
        <!-- Plugins Tab -->
        <t-tab-panel value="plugins" label="插件管理">
          <!-- Filter Bar -->
          <div class="filter-bar">
            <t-input
              v-model="searchKeyword"
              placeholder="搜索插件名称或描述"
              clearable
              style="width: 240px"
            >
              <template #prefix-icon>
                <t-icon name="search" />
              </template>
            </t-input>
            <t-select
              v-model="selectedCategory"
              :options="categoryOptions"
              placeholder="选择类别"
              clearable
              style="width: 140px"
            />
            <t-select
              v-model="selectedRole"
              :options="roleOptions"
              placeholder="选择角色"
              clearable
              style="width: 140px"
            />
            <t-button theme="default" variant="outline" @click="handleResetFilters">
              <t-icon name="refresh" style="margin-right: 4px" />
              重置
            </t-button>
            <div class="filter-result">
              共 <span class="count">{{ filteredPlugins.length }}</span> 个插件
            </div>
          </div>
          
          <t-table
            :data="filteredPlugins"
            :columns="pluginColumns"
            :loading="dataStore.loading"
            row-key="name"
            hover
          >
            <template #category="{ row }">
              <t-tag :theme="getCategoryTheme(row.category)" variant="light" size="small">
                {{ getCategoryText(row.category) }}
              </t-tag>
            </template>
            <template #role="{ row }">
              <t-tag :theme="getRoleTheme(row.role)" variant="outline" size="small">
                {{ getRoleText(row.role) }}
              </t-tag>
            </template>
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

        <!-- Settings Tab -->
        <t-tab-panel value="settings" label="配置">
          <ProxyConfigPanel />
        </t-tab-panel>
      </t-tabs>
    </t-card>
    <!-- Missing Data Panel -->
    <MissingDataPanel @sync="handleBackfill" />

    <!-- AI Diagnosis Panel -->
    <DiagnosisPanel />
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
</style>
