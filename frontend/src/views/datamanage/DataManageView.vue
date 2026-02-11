<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { useDataManageStore } from '@/stores/datamanage'
import { useAuthStore } from '@/stores/auth'
import type { PluginCategory, PluginRole, PluginGroup, GroupCategory } from '@/api/datamanage'
import MissingDataPanel from './components/MissingDataPanel.vue'
import PluginDetailDialog from './components/PluginDetailDialog.vue'
import PluginDataDialog from './components/PluginDataDialog.vue'
import DiagnosisPanel from './components/DiagnosisPanel.vue'
import SyncDialog from './components/SyncDialog.vue'
import GroupSyncDialog from './components/GroupSyncDialog.vue'
import GroupDetailDialog from './components/GroupDetailDialog.vue'

const dataStore = useDataManageStore()
const authStore = useAuthStore()
const activeTab = ref('plugins')

// Check admin permission
const isAdmin = computed(() => authStore.isAdmin)

// Plugin filter states
const searchKeyword = ref('')
const selectedCategory = ref<PluginCategory | ''>('')
const selectedRole = ref<PluginRole | ''>('')

const categoryOptions = [
  { label: '全部类别', value: '' },
  { label: 'A股', value: 'cn_stock' },
  { label: '港股', value: 'hk_stock' },
  { label: '指数', value: 'index' },
  { label: 'ETF基金', value: 'etf_fund' },
  { label: '市场统计', value: 'market' },
  { label: '参考数据', value: 'reference' },
  { label: '基本面', value: 'fundamental' },
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

// ============ Plugin Groups ============

const groupDialogVisible = ref(false)
const groupDialogMode = ref<'create' | 'edit'>('create')
const selectedGroup = ref<PluginGroup | null>(null)
const groupForm = ref({
  name: '',
  description: '',
  plugin_names: [] as string[],
  default_task_type: 'incremental' as 'incremental' | 'full' | 'backfill'
})
const groupFormLoading = ref(false)

// Group sync dialog state
const groupSyncDialogVisible = ref(false)
const selectedGroupForSync = ref<PluginGroup | null>(null)

// Group detail dialog state
const groupDetailDialogVisible = ref(false)
const selectedGroupForDetail = ref<PluginGroup | null>(null)

// Group category filter
const selectedGroupCategory = ref<GroupCategory | ''>('')
const groupCategoryOptions = [
  { label: '全部', value: '' },
  { label: 'A股', value: 'cn_stock' },
  { label: '指数', value: 'index' },
  { label: 'ETF基金', value: 'etf_fund' },
  { label: '每日更新', value: 'daily' },
  { label: '自定义', value: 'custom' }
]

// Computed: filtered groups by category
const filteredPredefinedGroups = computed(() => {
  const groups = dataStore.predefinedGroups
  if (!selectedGroupCategory.value) return groups
  return groups.filter(g => g.category === selectedGroupCategory.value)
})

const filteredCustomGroups = computed(() => {
  const groups = dataStore.customGroups
  if (!selectedGroupCategory.value || selectedGroupCategory.value === 'custom') {
    return selectedGroupCategory.value === 'custom' ? groups : groups
  }
  return groups.filter(g => g.category === selectedGroupCategory.value)
})

// Task type options for group form
const taskTypeOptions = [
  { label: '增量同步', value: 'incremental' },
  { label: '全量同步', value: 'full' },
  { label: '按日期补录', value: 'backfill' }
]

// Open create group dialog
const handleCreateGroup = () => {
  groupDialogMode.value = 'create'
  groupForm.value = { name: '', description: '', plugin_names: [], default_task_type: 'incremental' }
  selectedGroup.value = null
  groupDialogVisible.value = true
}

// Open edit group dialog
const handleEditGroup = (group: PluginGroup) => {
  groupDialogMode.value = 'edit'
  selectedGroup.value = group
  groupForm.value = {
    name: group.name,
    description: group.description || '',
    plugin_names: [...group.plugin_names],
    default_task_type: group.default_task_type || 'incremental'
  }
  groupDialogVisible.value = true
}

// Save group (create or update)
const handleSaveGroup = async () => {
  if (!groupForm.value.name) {
    MessagePlugin.warning('请输入组合名称')
    return
  }
  if (groupForm.value.plugin_names.length === 0) {
    MessagePlugin.warning('请选择至少一个插件')
    return
  }

  groupFormLoading.value = true
  try {
    if (groupDialogMode.value === 'create') {
      await dataStore.createPluginGroup({
        name: groupForm.value.name,
        description: groupForm.value.description,
        plugin_names: groupForm.value.plugin_names,
        default_task_type: groupForm.value.default_task_type
      })
      MessagePlugin.success('组合创建成功')
    } else {
      await dataStore.updatePluginGroup(selectedGroup.value!.group_id, {
        name: groupForm.value.name,
        description: groupForm.value.description,
        plugin_names: groupForm.value.plugin_names,
        default_task_type: groupForm.value.default_task_type
      })
      MessagePlugin.success('组合更新成功')
    }
    groupDialogVisible.value = false
  } catch (e: any) {
    MessagePlugin.error(e?.message || '保存失败')
  } finally {
    groupFormLoading.value = false
  }
}

// Delete group
const handleDeleteGroup = async (group: PluginGroup) => {
  try {
    await dataStore.deletePluginGroup(group.group_id)
    MessagePlugin.success('组合已删除')
  } catch (e) {
    MessagePlugin.error('删除失败')
  }
}

// Show group detail dialog
const handleShowGroupDetail = (group: PluginGroup) => {
  selectedGroupForDetail.value = group
  groupDetailDialogVisible.value = true
}

// Handle edit group (check if readonly)
const handleEditGroupSafe = (group: PluginGroup) => {
  if (group.is_predefined || group.is_readonly) {
    MessagePlugin.warning('预定义组合不可编辑')
    return
  }
  handleEditGroup(group)
}

// Handle delete group (check if readonly)
const handleDeleteGroupSafe = async (group: PluginGroup) => {
  if (group.is_predefined || group.is_readonly) {
    MessagePlugin.warning('预定义组合不可删除')
    return
  }
  await handleDeleteGroup(group)
}

// Handle execute from group detail dialog
const handleGroupDetailExecute = async () => {
  dataStore.startTaskPolling()
}

// Trigger group sync - open dialog
const handleTriggerGroup = (group: PluginGroup) => {
  selectedGroupForSync.value = group
  groupSyncDialogVisible.value = true
}

// Confirm group sync with selected options
const handleGroupSyncConfirm = async (
  groupId: string, 
  taskType: 'incremental' | 'full' | 'backfill', 
  dates: string[]
) => {
  try {
    await dataStore.triggerPluginGroup(groupId, {
      task_type: taskType,
      trade_dates: dates.length > 0 ? dates : undefined
    })
    MessagePlugin.success(`已触发组合同步`)
    dataStore.startTaskPolling()
  } catch (e) {
    MessagePlugin.error('触发失败')
  }
}

// Get available plugins for group selection
const availablePlugins = computed(() => {
  return dataStore.plugins.map(p => ({
    label: `${p.name} - ${p.description || ''}`,
    value: p.name
  }))
})

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
    market: '市场统计',
    reference: '参考数据',
    fundamental: '基本面',
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
    market: 'primary',
    reference: 'warning',
    fundamental: 'success',
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

// Format time for display
const formatTime = (timeStr?: string) => {
  if (!timeStr) return '-'
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN')
}

// Get category label for display
const getCategoryLabel = (category: GroupCategory | string): string => {
  const labelMap: Record<string, string> = {
    system: '系统维护',
    cn_stock: 'A股',
    index: '指数',
    etf_fund: 'ETF基金',
    daily: '每日更新',
    custom: '自定义'
  }
  return labelMap[category] || category
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
  dataStore.fetchPlugins()
  dataStore.fetchQualityMetrics()
  dataStore.fetchPluginGroups()
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

        <!-- Plugin Groups Tab -->
        <t-tab-panel value="groups" label="自定义组合">
          <div class="filter-bar">
            <t-radio-group v-model="selectedGroupCategory" variant="default-filled" size="small">
              <t-radio-button 
                v-for="option in groupCategoryOptions" 
                :key="option.value" 
                :value="option.value"
              >
                {{ option.label }}
              </t-radio-button>
            </t-radio-group>
            <div class="filter-bar-right">
              <t-button theme="primary" @click="handleCreateGroup">
                <t-icon name="add" style="margin-right: 4px" />
                创建组合
              </t-button>
              <t-button theme="default" variant="outline" @click="() => dataStore.fetchPluginGroups()">
                <t-icon name="refresh" style="margin-right: 4px" />
                刷新
              </t-button>
            </div>
          </div>

          <!-- 预定义组合 -->
          <div v-if="filteredPredefinedGroups.length > 0" class="group-section">
            <h4 class="section-title">
              <t-icon name="lock-on" />
              预定义组合 ({{ filteredPredefinedGroups.length }})
            </h4>
            <t-table
              :data="filteredPredefinedGroups"
              :columns="[
                { colKey: 'name', title: '组合名称', width: 180 },
                { colKey: 'description', title: '描述', minWidth: 150 },
                { colKey: 'category', title: '分类', width: 100 },
                { colKey: 'default_task_type', title: '默认同步', width: 100 },
                { colKey: 'plugin_count', title: '插件数', width: 80 },
                { colKey: 'operation', title: '操作', width: 150, fixed: 'right' }
              ]"
              :loading="dataStore.pluginGroupsLoading"
              row-key="group_id"
              size="small"
            >
              <template #name="{ row }">
                <span>{{ row.name }}</span>
              </template>
              <template #category="{ row }">
                <t-tag size="small" variant="outline">
                  {{ getCategoryLabel(row.category) }}
                </t-tag>
              </template>
              <template #default_task_type="{ row }">
                <t-tag 
                  :theme="row.default_task_type === 'full' ? 'warning' : row.default_task_type === 'backfill' ? 'default' : 'primary'" 
                  variant="light" 
                  size="small"
                >
                  {{ row.default_task_type === 'full' ? '全量' : row.default_task_type === 'backfill' ? '补录' : '增量' }}
                </t-tag>
              </template>
              <template #plugin_count="{ row }">
                {{ row.plugin_names?.length || 0 }}
              </template>
              <template #operation="{ row }">
                <t-space size="small">
                  <t-link theme="primary" @click="handleTriggerGroup(row)">执行</t-link>
                  <t-link theme="default" @click="handleShowGroupDetail(row)">详情</t-link>
                </t-space>
              </template>
            </t-table>
          </div>

          <!-- 用户自定义组合 -->
          <div class="group-section">
            <h4 class="section-title">
              <t-icon name="folder" />
              我的组合 ({{ filteredCustomGroups.length }})
            </h4>
            <t-table
              v-if="filteredCustomGroups.length > 0"
              :data="filteredCustomGroups"
              :columns="[
                { colKey: 'name', title: '组合名称', width: 180 },
                { colKey: 'description', title: '描述', minWidth: 150 },
                { colKey: 'default_task_type', title: '默认同步', width: 100 },
                { colKey: 'plugin_count', title: '插件数', width: 80 },
                { colKey: 'created_at', title: '创建时间', width: 160 },
                { colKey: 'operation', title: '操作', width: 200, fixed: 'right' }
              ]"
              :loading="dataStore.pluginGroupsLoading"
              row-key="group_id"
              size="small"
            >
              <template #default_task_type="{ row }">
                <t-tag 
                  :theme="row.default_task_type === 'full' ? 'warning' : row.default_task_type === 'backfill' ? 'default' : 'primary'" 
                  variant="light" 
                  size="small"
                >
                  {{ row.default_task_type === 'full' ? '全量' : row.default_task_type === 'backfill' ? '补录' : '增量' }}
                </t-tag>
              </template>
              <template #plugin_count="{ row }">
                {{ row.plugin_names?.length || 0 }}
              </template>
              <template #created_at="{ row }">
                {{ formatTime(row.created_at) }}
              </template>
              <template #operation="{ row }">
                <t-space size="small">
                  <t-link theme="primary" @click="handleTriggerGroup(row)">执行</t-link>
                  <t-link theme="default" @click="handleShowGroupDetail(row)">详情</t-link>
                  <t-link theme="default" @click="handleEditGroupSafe(row)">编辑</t-link>
                  <t-popconfirm content="确定删除该组合？" @confirm="handleDeleteGroupSafe(row)">
                    <t-link theme="danger">删除</t-link>
                  </t-popconfirm>
                </t-space>
              </template>
            </t-table>
            <t-result 
              v-else 
              theme="default" 
              title="暂无自定义组合" 
              description="点击「创建组合」添加您的第一个组合"
              style="padding: 40px 0"
            >
              <template #extra>
                <t-button theme="primary" @click="handleCreateGroup">
                  <t-icon name="add" style="margin-right: 4px" />
                  创建组合
                </t-button>
              </template>
            </t-result>
          </div>
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
    
    <!-- Plugin Group Dialog -->
    <t-dialog
      v-model:visible="groupDialogVisible"
      :header="groupDialogMode === 'create' ? '创建插件组合' : '编辑插件组合'"
      width="600px"
      :confirm-btn="{ content: '保存', loading: groupFormLoading }"
      @confirm="handleSaveGroup"
    >
      <t-form label-width="100px">
        <t-form-item label="组合名称" required>
          <t-input v-model="groupForm.name" placeholder="请输入组合名称" clearable />
        </t-form-item>
        <t-form-item label="描述">
          <t-textarea v-model="groupForm.description" placeholder="请输入组合描述（可选）" :maxlength="200" />
        </t-form-item>
        <t-form-item label="默认同步类型">
          <t-select
            v-model="groupForm.default_task_type"
            :options="taskTypeOptions"
            placeholder="选择默认同步类型"
            style="width: 200px"
          />
        </t-form-item>
        <t-form-item label="选择插件" required>
          <t-select
            v-model="groupForm.plugin_names"
            :options="availablePlugins"
            multiple
            filterable
            placeholder="请选择插件"
            style="width: 100%"
          />
        </t-form-item>
        <t-form-item v-if="groupForm.plugin_names.length > 0">
          <div class="selected-plugins">
            <span class="label">已选 {{ groupForm.plugin_names.length }} 个插件:</span>
            <t-tag v-for="name in groupForm.plugin_names" :key="name" size="small" style="margin: 2px">
              {{ name }}
            </t-tag>
          </div>
        </t-form-item>
      </t-form>
    </t-dialog>
    
    <!-- Group Sync Dialog -->
    <GroupSyncDialog
      v-model:visible="groupSyncDialogVisible"
      :group="selectedGroupForSync"
      @confirm="handleGroupSyncConfirm"
    />
    
    <!-- Group Detail Dialog -->
    <GroupDetailDialog
      v-model:visible="groupDetailDialogVisible"
      :group="selectedGroupForDetail"
      @execute="handleGroupDetailExecute"
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

.status-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.error-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--td-error-color);
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
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

/* Batch task styles */
.sub-tasks-container {
  padding: 8px 16px;
  background: var(--td-bg-color-container);
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

/* Group name display */
.group-name {
  margin-left: 8px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

/* Selected plugins in group dialog */
.selected-plugins {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.selected-plugins .label {
  color: var(--td-text-color-secondary);
  font-size: 13px;
  margin-right: 8px;
}

/* Group section styles */
.group-section {
  margin-bottom: 24px;
  
  .section-title {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0 0 12px 0;
    font-size: 14px;
    font-weight: 500;
    color: var(--td-text-color-primary);
  }
}

.filter-bar-right {
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
