import { defineStore } from 'pinia'
import { ref } from 'vue'
import { datamanageApi, type DataSource, type SyncTask, type QualityMetrics, type PluginInfo } from '@/api/datamanage'

export const useDataManageStore = defineStore('datamanage', () => {
  const dataSources = ref<DataSource[]>([])
  const syncTasks = ref<SyncTask[]>([])
  const qualityMetrics = ref<QualityMetrics[]>([])
  const plugins = ref<PluginInfo[]>([])
  const loading = ref(false)

  const fetchDataSources = async () => {
    loading.value = true
    try {
      dataSources.value = await datamanageApi.getDataSources()
    } catch (e) {
      // Error handled by interceptor
    } finally {
      loading.value = false
    }
  }

  const fetchSyncTasks = async () => {
    try {
      syncTasks.value = await datamanageApi.getSyncTasks()
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const triggerSync = async (sourceId: string, syncType: 'full' | 'incremental') => {
    try {
      await datamanageApi.triggerSync(sourceId, syncType)
      await fetchSyncTasks()
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const fetchQualityMetrics = async () => {
    try {
      qualityMetrics.value = await datamanageApi.getQualityMetrics()
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const fetchPlugins = async () => {
    try {
      plugins.value = await datamanageApi.getPlugins()
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const enablePlugin = async (name: string) => {
    try {
      await datamanageApi.enablePlugin(name)
      await fetchPlugins()
    } catch (e) {
      // Error handled by interceptor
    }
  }

  const disablePlugin = async (name: string) => {
    try {
      await datamanageApi.disablePlugin(name)
      await fetchPlugins()
    } catch (e) {
      // Error handled by interceptor
    }
  }

  return {
    dataSources,
    syncTasks,
    qualityMetrics,
    plugins,
    loading,
    fetchDataSources,
    fetchSyncTasks,
    triggerSync,
    fetchQualityMetrics,
    fetchPlugins,
    enablePlugin,
    disablePlugin
  }
})
