import { defineStore } from 'pinia'
import { ref } from 'vue'
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
  type PluginFilterParams
} from '@/api/datamanage'

export const useDataManageStore = defineStore('datamanage', () => {
  // State
  const dataSources = ref<DataSource[]>([])
  const syncTasks = ref<SyncTask[]>([])
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
  const fetchSyncTasks = async () => {
    try {
      syncTasks.value = await datamanageApi.getSyncTasks()
    } catch (e) {
      console.error('Failed to fetch sync tasks:', e)
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
  const fetchMissingData = async (days: number = 30, forceRefresh: boolean = false) => {
    loading.value = true
    try {
      missingData.value = await datamanageApi.getMissingData(days, forceRefresh)
    } catch (e) {
      console.error('Failed to fetch missing data:', e)
    } finally {
      loading.value = false
    }
  }

  const triggerMissingDataDetection = async (days: number = 30) => {
    loading.value = true
    try {
      missingData.value = await datamanageApi.triggerMissingDataDetection(days)
    } catch (e) {
      console.error('Failed to trigger detection:', e)
    } finally {
      loading.value = false
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
    stopTaskPolling
  }
})
