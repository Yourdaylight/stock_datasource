<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { useDataManageStore } from '@/stores/datamanage'
import { useAuthStore } from '@/stores/auth'
import type { PluginCategory, PluginRole, SyncTaskQueryParams } from '@/api/datamanage'
import MissingDataPanel from './components/MissingDataPanel.vue'
import SyncTaskPanel from './components/SyncTaskPanel.vue'
import PluginDetailDialog from './components/PluginDetailDialog.vue'
import PluginDataDialog from './components/PluginDataDialog.vue'
import DiagnosisPanel from './components/DiagnosisPanel.vue'
import SyncDialog from './components/SyncDialog.vue'
import ProxyConfigPanel from './components/ProxyConfigPanel.vue'
import TaskDetailDialog from './components/TaskDetailDialog.vue'
import SchedulePanel from './components/SchedulePanel.vue'
import type { SyncTask } from '@/api/datamanage'

const dataStore = useDataManageStore()
const authStore = useAuthStore()
const activeTab = ref('plugins')

// Check admin permission
const isAdmin = computed(() => authStore.isAdmin)

// Plugin filter states
const searchKeyword = ref('')
const selectedCategory = ref<PluginCategory | ''>('')
const selectedRole = ref<PluginRole | ''>('')

// Task filter states
const taskSearchKeyword = ref('')
const taskStatusFilter = ref<string>('')
const taskSortBy = ref<'created_at' | 'started_at' | 'completed_at'>('created_at')
const taskSortOrder = ref<'asc' | 'desc'>('desc')

const taskStatusOptions = [
  { label: '全部状态', value: '' },
  { label: '等待中', value: 'pending' },
  { label: '运行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '失败', value: 'failed' },
  { label: '已取消', value: 'cancelled' }
]

const taskSortOptions = [
  { label: '创建时间', value: 'created_at' },
  { label: '开始时间', value: 'started_at' },
  { label: '完成时间', value: 'completed_at' }
]

const categoryOptions = [
  { label: '全部类别', value: '' },
  { label: 'A股', value: 'cn_stock' },
  { label: '港股', value: 'hk_stock' },
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

// Task filtering and pagination handlers
const handleTaskSearch = () => {
  dataStore.fetchSyncTasks({
    page: 1,
    plugin_name: taskSearchKeyword.value || undefined,
    status: taskStatusFilter.value as any || undefined,
    sort_by: taskSortBy.value,
    sort_order: taskSortOrder.value
  })
}

const handleTaskPageChange = (pageInfo: { current: number; pageSize: number }) => {
  dataStore.fetchSyncTasks({
    page: pageInfo.current,
    page_size: pageInfo.pageSize,
    plugin_name: taskSearchKeyword.value || undefined,
    status: taskStatusFilter.value as any || undefined,
    sort_by: taskSortBy.value,
    sort_order: taskSortOrder.value
  })
}

const handleResetTaskFilters = () => {
  taskSearchKeyword.value = ''
  taskStatusFilter.value = ''
  taskSortBy.value = 'created_at'
  taskSortOrder.value = 'desc'
  dataStore.fetchSyncTasks({ page: 1 })
}

// Dialog states
const detailDialogVisible = ref(false)
const dataDialogVisible = ref(false)
const syncDialogVisible = ref(false)
const taskDetailDialogVisible = ref(false)
const selectedPluginName = ref('')
const selectedTask = ref<SyncTask | null>(null)

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
    cn_stock: 'A股',
    hk_stock: '港股',
    stock: 'A股',  // backward compatibility
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
    cn_stock: 'primary',
    hk_stock: 'danger',
    stock: 'primary',  // backward compatibility
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
  { colKey: 'created_at', title: '创建时间', width: 150 },
  { colKey: 'operation', title: '操作', width: 120 }
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

const handleRetryTask = async (taskId: string) => {
  try {
    await dataStore.retryTask(taskId)
    MessagePlugin.success('已创建重试任务')
    dataStore.startTaskPolling()
  } catch (e) {
    MessagePlugin.error('重试任务失败')
  }
}

const handleViewTaskDetail = (task: SyncTask) => {
  selectedTask.value = task
  taskDetailDialogVisible.value = true
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

// Handle tab change - lazy load missing data only when quality tab is selected
const handleTabChange = (value: string) => {
  if (value === 'quality') {
    // Check if we need to refresh missing data (once per day)
    const lastCheckTime = dataStore.missingData?.check_time
    if (lastCheckTime) {
      const lastCheck = new Date(lastCheckTime)
      const now = new Date()
      const hoursSinceLastCheck = (now.getTime() - lastCheck.getTime()) / (1000 * 60 * 60)
      // Only auto-refresh if last check was more than 24 hours ago
      if (hoursSinceLastCheck < 24) {
        return
      }
    }
    // Lazy load missing data with default 5 years (1825 days)
    dataStore.fetchMissingData(1825, false)
  }
}

onMounted(() => {
  dataStore.fetchDataSources()
  dataStore.fetchSyncTasks()
  dataStore.fetchPlugins()
  dataStore.fetchQualityMetrics()
  // Don't fetch missing data on mount - it will be fetched when quality tab is selected
})
</script>

<template>
  <div class="datamanage-view">
    <!-- Permission Check -->
    <template v-if="!isAdmin">
      <t-card class="no-permission-card">
        <div class="permission-denied">
          <t-icon name="error-circle" size="64px" style="color: var(--td-warning-color); margin-bottom: 16px" />
          <h3 style="margin: 0 0 8px 0; font-size: 20px">无访问权限</h3>
          <p style="margin: 0 0 24px 0; color: var(--td-text-color-secondary)">
            数据管理功能仅限管理员使用。如需访问，请联系系统管理员。
          </p>
          <t-button theme="primary" @click="$router.push('/')">返回首页</t-button>
        </div>
      </t-card>
    </template>

    <template v-else>
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
      <t-tabs v-model="activeTab" @change="handleTabChange">
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
          <!-- Task Filter Bar -->
          <div class="filter-bar">
            <t-input
              v-model="taskSearchKeyword"
              placeholder="搜索插件名称"
              clearable
              style="width: 200px"
              @enter="handleTaskSearch"
              @clear="handleTaskSearch"
            >
              <template #prefix-icon>
                <t-icon name="search" />
              </template>
            </t-input>
            <t-select
              v-model="taskStatusFilter"
              :options="taskStatusOptions"
              placeholder="状态筛选"
              clearable
              style="width: 120px"
              @change="handleTaskSearch"
            />
            <t-select
              v-model="taskSortBy"
              :options="taskSortOptions"
              placeholder="排序字段"
              style="width: 120px"
              @change="handleTaskSearch"
            />
            <t-radio-group v-model="taskSortOrder" variant="default-filled" size="small" @change="handleTaskSearch">
              <t-radio-button value="desc">
                <t-icon name="arrow-down" />
              </t-radio-button>
              <t-radio-button value="asc">
                <t-icon name="arrow-up" />
              </t-radio-button>
            </t-radio-group>
            <t-button theme="default" variant="outline" @click="handleResetTaskFilters">
              <t-icon name="refresh" style="margin-right: 4px" />
              重置
            </t-button>
            <div class="filter-result">
              共 <span class="count">{{ dataStore.syncTasksTotal }}</span> 个任务
            </div>
          </div>

          <t-table
            :data="dataStore.syncTasks"
            :columns="taskColumns"
            :loading="dataStore.tasksLoading"
            row-key="task_id"
            :pagination="{
              current: dataStore.syncTasksPage,
              pageSize: dataStore.syncTasksPageSize,
              total: dataStore.syncTasksTotal,
              showPageSize: true,
              pageSizeOptions: [10, 20, 50],
              showJumper: true
            }"
            @page-change="handleTaskPageChange"
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
                :percentage="Number(row.progress.toFixed(1))" 
                :status="row.status === 'running' ? 'active' : 'default'"
                size="small"
                :label="row.progress.toFixed(1) + '%'"
              />
            </template>
            <template #records_processed="{ row }">
              {{ row.records_processed.toLocaleString() }}
            </template>
            <template #created_at="{ row }">
              {{ formatTime(row.created_at) }}
            </template>
            <template #operation="{ row }">
              <t-space>
                <t-link 
                  theme="primary" 
                  @click="handleViewTaskDetail(row)"
                >
                  详情
                </t-link>
                <t-link 
                  v-if="row.status === 'pending'" 
                  theme="danger" 
                  @click="handleCancelTask(row.task_id)"
                >
                  取消
                </t-link>
                <t-link 
                  v-if="row.status === 'failed' || row.status === 'cancelled'" 
                  theme="primary" 
                  @click="handleRetryTask(row.task_id)"
                >
                  重试
                </t-link>
              </t-space>
            </template>
          </t-table>
        </t-tab-panel>

        <!-- Quality Tab -->
        <t-tab-panel value="quality" label="数据质量">
          <!-- Missing Data Panel - 数据缺失检测 -->
          <MissingDataPanel @sync="handleBackfill" style="margin-bottom: 16px" />
          
          <!-- Quality Metrics Table -->
          <t-card title="质量指标" :bordered="false">
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
          </t-card>
        </t-tab-panel>

        <!-- Settings Tab -->
        <t-tab-panel value="settings" label="配置">
          <SchedulePanel />
          <ProxyConfigPanel />
        </t-tab-panel>
      </t-tabs>
    </t-card>

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
    <TaskDetailDialog
      v-model:visible="taskDetailDialogVisible"
      :task="selectedTask"
    />
    </template>
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
</style>
