import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { 
  datamanageApi, 
  type DataSource, 
  type SyncTask, 
  type QualityMetrics, 
  type PluginInfo,
  type PluginDetail,
  type PluginDataPreview,
  type MissingDataSummary,
  type TriggerSyncRequest,
  type DataExistsCheckResult,
  type DependencyCheckResult,
  type DependencyGraphResult,
  type BatchSyncRequest,
  type BatchSyncResponse,
  type PluginFilterParams,
  type SyncTaskListResponse,
  type SyncTaskQueryParams,
  type ScheduleConfig,
  type ScheduleConfigRequest,
  type PluginScheduleConfig,
  type PluginScheduleConfigRequest,
  type ScheduleExecutionRecord,
  type ScheduleHistoryResponse,
  type PluginCategory,
  type BatchExecutionDetail,
  type PluginGroup,
  type PluginGroupCreateRequest,
  type PluginGroupUpdateRequest,
  type PluginGroupListResponse,
  type PluginGroupTriggerRequest,
  type GroupCategory,
  type GroupCategoryInfo,
  type PluginGroupDetail
} from '@/api/datamanage'

export const useDataManageStore = defineStore('datamanage', () => {
  // State
  const dataSources = ref<DataSource[]>([])
  const syncTasks = ref<SyncTask[]>([])
  const syncTasksTotal = ref(0)
  const syncTasksPage = ref(1)
  const syncTasksPageSize = ref(20)
  const syncTasksTotalPages = ref(1)
  const qualityMetrics = ref<QualityMetrics[]>([])
  const plugins = ref<PluginInfo[]>([])
  const missingData = ref<MissingDataSummary | null>(null)
  const currentPluginDetail = ref<PluginDetail | null>(null)
  const currentPluginData = ref<PluginDataPreview | null>(null)
  const currentDependencies = ref<DependencyCheckResult | null>(null)
  const dependencyGraph = ref<DependencyGraphResult | null>(null)
  const loading = ref(false)
  const detailLoading = ref(false)
  const dataLoading = ref(false)
  const dependencyLoading = ref(false)
  const tasksLoading = ref(false)
  const missingDataLoading = ref(false)
  
  // Schedule state
  const scheduleConfig = ref<ScheduleConfig | null>(null)
  const pluginScheduleConfigs = ref<PluginScheduleConfig[]>([])
  const scheduleHistory = ref<ScheduleExecutionRecord[]>([])
  const scheduleLoading = ref(false)

  // Data Sources
  const fetchDataSources = async () => {
    loading.value = true
    try {
      dataSources.value = await datamanageApi.getDataSources()
    } catch (e) {
      console.error('Failed to fetch data sources:', e)
    } finally {
      loading.value = false
    }
  }

  // Sync Tasks
  const fetchSyncTasks = async (params?: SyncTaskQueryParams) => {
    tasksLoading.value = true
    try {
      const response = await datamanageApi.getSyncTasks({
        page: params?.page || syncTasksPage.value,
        page_size: params?.page_size || syncTasksPageSize.value,
        status: params?.status,
        plugin_name: params?.plugin_name,
        sort_by: params?.sort_by || 'created_at',
        sort_order: params?.sort_order || 'desc'
      })
      syncTasks.value = response.items
      syncTasksTotal.value = response.total
      syncTasksPage.value = response.page
      syncTasksPageSize.value = response.page_size
      syncTasksTotalPages.value = response.total_pages
    } catch (e) {
      console.error('Failed to fetch sync tasks:', e)
    } finally {
      tasksLoading.value = false
    }
  }

  const triggerSync = async (req: TriggerSyncRequest) => {
    try {
      const task = await datamanageApi.triggerSync(req)
      syncTasks.value.unshift(task)
      return task
    } catch (e) {
      console.error('Failed to trigger sync:', e)
      throw e
    }
  }

  const cancelTask = async (taskId: string) => {
    try {
      await datamanageApi.cancelSyncTask(taskId)
      await fetchSyncTasks()
    } catch (e) {
      console.error('Failed to cancel task:', e)
      throw e
    }
  }

  const deleteTask = async (taskId: string) => {
    try {
      await datamanageApi.deleteSyncTask(taskId)
      await fetchSyncTasks()
    } catch (e) {
      console.error('Failed to delete task:', e)
      throw e
    }
  }

  const retryTask = async (taskId: string) => {
    try {
      const task = await datamanageApi.retrySyncTask(taskId)
      syncTasks.value.unshift(task)
      return task
    } catch (e) {
      console.error('Failed to retry task:', e)
      throw e
    }
  }

  const fetchSyncHistory = async (limit: number = 20, pluginName?: string) => {
    try {
      return await datamanageApi.getSyncHistory(limit, pluginName)
    } catch (e) {
      console.error('Failed to fetch sync history:', e)
      return []
    }
  }

  // Missing Data
  const fetchMissingData = async (days: number = 365, forceRefresh: boolean = false) => {
    missingDataLoading.value = true
    try {
      missingData.value = await datamanageApi.getMissingData(days, forceRefresh)
    } catch (e) {
      console.error('Failed to fetch missing data:', e)
    } finally {
      missingDataLoading.value = false
    }
  }

  const triggerMissingDataDetection = async (days: number = 365) => {
    missingDataLoading.value = true
    try {
      missingData.value = await datamanageApi.triggerMissingDataDetection(days)
    } catch (e) {
      console.error('Failed to trigger detection:', e)
    } finally {
      missingDataLoading.value = false
    }
  }

  // Plugins
  const fetchPlugins = async (params?: PluginFilterParams) => {
    try {
      plugins.value = await datamanageApi.getPlugins(params)
    } catch (e) {
      console.error('Failed to fetch plugins:', e)
    }
  }

  const fetchPluginDetail = async (name: string) => {
    detailLoading.value = true
    try {
      currentPluginDetail.value = await datamanageApi.getPluginDetail(name)
    } catch (e) {
      console.error('Failed to fetch plugin detail:', e)
      currentPluginDetail.value = null
    } finally {
      detailLoading.value = false
    }
  }

  const fetchPluginData = async (name: string, tradeDate?: string, page: number = 1, pageSize: number = 100) => {
    dataLoading.value = true
    try {
      currentPluginData.value = await datamanageApi.getPluginData(name, tradeDate, page, pageSize)
    } catch (e) {
      console.error('Failed to fetch plugin data:', e)
      currentPluginData.value = null
    } finally {
      dataLoading.value = false
    }
  }

  const enablePlugin = async (name: string) => {
    try {
      await datamanageApi.enablePlugin(name)
      await fetchPlugins()
    } catch (e) {
      console.error('Failed to enable plugin:', e)
    }
  }

  const disablePlugin = async (name: string) => {
    try {
      await datamanageApi.disablePlugin(name)
      await fetchPlugins()
    } catch (e) {
      console.error('Failed to disable plugin:', e)
    }
  }

  // Plugin Dependencies
  const fetchPluginDependencies = async (name: string) => {
    dependencyLoading.value = true
    try {
      currentDependencies.value = await datamanageApi.getPluginDependencies(name)
      return currentDependencies.value
    } catch (e) {
      console.error('Failed to fetch plugin dependencies:', e)
      currentDependencies.value = null
      return null
    } finally {
      dependencyLoading.value = false
    }
  }

  const checkPluginDependencies = async (name: string): Promise<DependencyCheckResult | null> => {
    try {
      return await datamanageApi.checkPluginDependencies(name)
    } catch (e) {
      console.error('Failed to check plugin dependencies:', e)
      return null
    }
  }

  const fetchDependencyGraph = async () => {
    try {
      dependencyGraph.value = await datamanageApi.getDependencyGraph()
      return dependencyGraph.value
    } catch (e) {
      console.error('Failed to fetch dependency graph:', e)
      dependencyGraph.value = null
      return null
    }
  }

  // Batch Sync
  const batchTriggerSync = async (req: BatchSyncRequest): Promise<BatchSyncResponse | null> => {
    try {
      const response = await datamanageApi.batchTriggerSync(req)
      // Refresh tasks after batch sync
      await fetchSyncTasks()
      return response
    } catch (e) {
      console.error('Failed to batch trigger sync:', e)
      throw e
    }
  }

  // ============ Schedule Management ============
  
  const fetchScheduleConfig = async () => {
    scheduleLoading.value = true
    try {
      scheduleConfig.value = await datamanageApi.getScheduleConfig()
      return scheduleConfig.value
    } catch (e) {
      console.error('Failed to fetch schedule config:', e)
      return null
    } finally {
      scheduleLoading.value = false
    }
  }

  const updateScheduleConfig = async (config: ScheduleConfigRequest) => {
    try {
      scheduleConfig.value = await datamanageApi.updateScheduleConfig(config)
      return scheduleConfig.value
    } catch (e) {
      console.error('Failed to update schedule config:', e)
      throw e
    }
  }

  const fetchPluginScheduleConfigs = async (category?: PluginCategory) => {
    scheduleLoading.value = true
    try {
      pluginScheduleConfigs.value = await datamanageApi.getPluginScheduleConfigs(category)
      return pluginScheduleConfigs.value
    } catch (e) {
      console.error('Failed to fetch plugin schedule configs:', e)
      return []
    } finally {
      scheduleLoading.value = false
    }
  }

  const updatePluginScheduleConfig = async (name: string, config: PluginScheduleConfigRequest) => {
    try {
      const updated = await datamanageApi.updatePluginScheduleConfig(name, config)
      // Update in local state
      const index = pluginScheduleConfigs.value.findIndex(p => p.plugin_name === name)
      if (index >= 0) {
        pluginScheduleConfigs.value[index] = updated
      }
      return updated
    } catch (e) {
      console.error('Failed to update plugin schedule config:', e)
      throw e
    }
  }

  const triggerScheduleNow = async () => {
    try {
      const record = await datamanageApi.triggerScheduleNow()
      // Refresh history and tasks
      await fetchScheduleHistory()
      await fetchSyncTasks()
      return record
    } catch (e) {
      console.error('Failed to trigger schedule:', e)
      throw e
    }
  }

  const retryScheduleExecution = async (executionId: string) => {
    try {
      const record = await datamanageApi.retryScheduleExecution(executionId)
      // Refresh history and tasks
      await fetchScheduleHistory()
      await fetchSyncTasks()
      return record
    } catch (e) {
      console.error('Failed to retry schedule execution:', e)
      throw e
    }
  }

  const fetchScheduleHistory = async (
    days: number = 7, 
    limit: number = 50,
    status?: string,
    triggerType?: string
  ) => {
    try {
      const response = await datamanageApi.getScheduleHistory(days, limit, status, triggerType)
      scheduleHistory.value = response.items
      return response
    } catch (e) {
      console.error('Failed to fetch schedule history:', e)
      return { items: [], total: 0 }
    }
  }

  const fetchExecutionDetail = async (executionId: string): Promise<BatchExecutionDetail | null> => {
    try {
      return await datamanageApi.getExecutionDetail(executionId)
    } catch (e) {
      console.error('Failed to fetch execution detail:', e)
      return null
    }
  }

  const partialRetryExecution = async (executionId: string, taskIds?: string[]) => {
    try {
      const record = await datamanageApi.partialRetryExecution(executionId, taskIds)
      // Refresh history and tasks
      await fetchScheduleHistory()
      await fetchSyncTasks()
      return record
    } catch (e) {
      console.error('Failed to partial retry execution:', e)
      throw e
    }
  }

  const stopExecution = async (executionId: string) => {
    try {
      const record = await datamanageApi.stopExecution(executionId)
      // Refresh history and tasks
      await fetchScheduleHistory()
      await fetchSyncTasks()
      return record
    } catch (e) {
      console.error('Failed to stop execution:', e)
      throw e
    }
  }

  // ============ Plugin Groups ============
  
  const pluginGroups = ref<PluginGroup[]>([])
  const pluginGroupsLoading = ref(false)
  const groupCategories = ref<GroupCategoryInfo[]>([])
  const selectedGroupCategory = ref<GroupCategory | ''>('')
  
  // 计算属性：预定义组合和自定义组合分开
  const predefinedGroups = computed(() => 
    pluginGroups.value.filter(g => g.is_predefined)
  )
  const customGroups = computed(() => 
    pluginGroups.value.filter(g => !g.is_predefined)
  )
  
  // 按分类筛选后的组合
  const filteredPredefinedGroups = computed(() => {
    if (!selectedGroupCategory.value) return predefinedGroups.value
    return predefinedGroups.value.filter(g => g.category === selectedGroupCategory.value)
  })
  const filteredCustomGroups = computed(() => {
    if (!selectedGroupCategory.value) return customGroups.value
    return customGroups.value.filter(g => g.category === selectedGroupCategory.value)
  })

  const fetchPluginGroups = async (category?: GroupCategory) => {
    pluginGroupsLoading.value = true
    try {
      const response = await datamanageApi.getPluginGroups(category)
      pluginGroups.value = response.items
      return response
    } catch (e) {
      console.error('Failed to fetch plugin groups:', e)
      return { items: [], total: 0, predefined_count: 0, custom_count: 0 }
    } finally {
      pluginGroupsLoading.value = false
    }
  }

  const fetchPredefinedGroups = async () => {
    try {
      const response = await datamanageApi.getPredefinedGroups()
      groupCategories.value = response.categories
      return response
    } catch (e) {
      console.error('Failed to fetch predefined groups:', e)
      return { groups: [], categories: [] }
    }
  }

  const fetchGroupDetail = async (groupId: string): Promise<PluginGroupDetail | null> => {
    try {
      return await datamanageApi.getPluginGroup(groupId)
    } catch (e) {
      console.error('Failed to fetch group detail:', e)
      return null
    }
  }

  const createPluginGroup = async (data: PluginGroupCreateRequest) => {
    try {
      const group = await datamanageApi.createPluginGroup(data)
      pluginGroups.value.push(group)
      return group
    } catch (e) {
      console.error('Failed to create plugin group:', e)
      throw e
    }
  }

  const updatePluginGroup = async (groupId: string, data: PluginGroupUpdateRequest) => {
    try {
      const updated = await datamanageApi.updatePluginGroup(groupId, data)
      const index = pluginGroups.value.findIndex(g => g.group_id === groupId)
      if (index >= 0) {
        pluginGroups.value[index] = updated
      }
      return updated
    } catch (e) {
      console.error('Failed to update plugin group:', e)
      throw e
    }
  }

  const deletePluginGroup = async (groupId: string) => {
    try {
      await datamanageApi.deletePluginGroup(groupId)
      pluginGroups.value = pluginGroups.value.filter(g => g.group_id !== groupId)
    } catch (e) {
      console.error('Failed to delete plugin group:', e)
      throw e
    }
  }

  const triggerPluginGroup = async (groupId: string, request?: PluginGroupTriggerRequest) => {
    try {
      const record = await datamanageApi.triggerPluginGroup(groupId, request)
      // Refresh history and tasks
      await fetchScheduleHistory()
      await fetchSyncTasks()
      return record
    } catch (e) {
      console.error('Failed to trigger plugin group:', e)
      throw e
    }
  }

  // Quality
  const fetchQualityMetrics = async () => {
    try {
      qualityMetrics.value = await datamanageApi.getQualityMetrics()
    } catch (e) {
      console.error('Failed to fetch quality metrics:', e)
    }
  }

  // Polling for task updates
  let pollInterval: ReturnType<typeof setInterval> | null = null

  const startTaskPolling = (intervalMs: number = 3000) => {
    if (pollInterval) return
    pollInterval = setInterval(() => {
      const hasRunning = syncTasks.value.some(t => t.status === 'running' || t.status === 'pending')
      if (hasRunning) {
        fetchSyncTasks()
      }
    }, intervalMs)
  }

  const stopTaskPolling = () => {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }

  return {
    // State
    dataSources,
    syncTasks,
    syncTasksTotal,
    syncTasksPage,
    syncTasksPageSize,
    syncTasksTotalPages,
    tasksLoading,
    qualityMetrics,
    plugins,
    missingData,
    currentPluginDetail,
    currentPluginData,
    currentDependencies,
    dependencyGraph,
    loading,
    detailLoading,
    dataLoading,
    dependencyLoading,
    missingDataLoading,
    
    // Schedule state
    scheduleConfig,
    pluginScheduleConfigs,
    scheduleHistory,
    scheduleLoading,
    
    // Plugin groups state
    pluginGroups,
    pluginGroupsLoading,
    groupCategories,
    selectedGroupCategory,
    predefinedGroups,
    customGroups,
    filteredPredefinedGroups,
    filteredCustomGroups,
    
    // Actions
    fetchDataSources,
    fetchSyncTasks,
    triggerSync,
    cancelTask,
    deleteTask,
    retryTask,
    fetchSyncHistory,
    fetchMissingData,
    triggerMissingDataDetection,
    fetchPlugins,
    fetchPluginDetail,
    fetchPluginData,
    enablePlugin,
    disablePlugin,
    fetchPluginDependencies,
    checkPluginDependencies,
    fetchDependencyGraph,
    batchTriggerSync,
    fetchQualityMetrics,
    startTaskPolling,
    stopTaskPolling,
    
    // Schedule actions
    fetchScheduleConfig,
    updateScheduleConfig,
    fetchPluginScheduleConfigs,
    updatePluginScheduleConfig,
    triggerScheduleNow,
    retryScheduleExecution,
    fetchScheduleHistory,
    fetchExecutionDetail,
    partialRetryExecution,
    stopExecution,
    
    // Plugin groups actions
    fetchPluginGroups,
    fetchPredefinedGroups,
    fetchGroupDetail,
    createPluginGroup,
    updatePluginGroup,
    deletePluginGroup,
    triggerPluginGroup
  }
})
