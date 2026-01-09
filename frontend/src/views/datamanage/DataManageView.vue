<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useDataManageStore } from '@/stores/datamanage'

const dataStore = useDataManageStore()
const activeTab = ref('datasource')

const datasourceColumns = [
  { colKey: 'source_name', title: '数据源名称', width: 150 },
  { colKey: 'provider', title: '提供商', width: 100 },
  { colKey: 'source_type', title: '类型', width: 100 },
  { colKey: 'is_enabled', title: '状态', width: 80 },
  { colKey: 'last_sync_at', title: '最后同步', width: 150 },
  { colKey: 'operation', title: '操作', width: 150 }
]

const taskColumns = [
  { colKey: 'plugin_name', title: '插件', width: 150 },
  { colKey: 'task_type', title: '类型', width: 100 },
  { colKey: 'status', title: '状态', width: 100 },
  { colKey: 'progress', title: '进度', width: 150 },
  { colKey: 'records_processed', title: '处理记录', width: 100 },
  { colKey: 'started_at', title: '开始时间', width: 150 }
]

const pluginColumns = [
  { colKey: 'name', title: '插件名称', width: 150 },
  { colKey: 'type', title: '类型', width: 100 },
  { colKey: 'is_enabled', title: '状态', width: 80 },
  { colKey: 'last_run_at', title: '最后运行', width: 150 },
  { colKey: 'last_run_status', title: '运行状态', width: 100 },
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

const handleTriggerSync = (sourceId: string, syncType: 'full' | 'incremental') => {
  dataStore.triggerSync(sourceId, syncType)
}

const handleTogglePlugin = (name: string, enabled: boolean) => {
  if (enabled) {
    dataStore.disablePlugin(name)
  } else {
    dataStore.enablePlugin(name)
  }
}

const overallQuality = computed(() => {
  if (!dataStore.qualityMetrics.length) return 0
  const sum = dataStore.qualityMetrics.reduce((acc, m) => acc + m.overall_score, 0)
  return (sum / dataStore.qualityMetrics.length).toFixed(1)
})

onMounted(() => {
  dataStore.fetchDataSources()
  dataStore.fetchSyncTasks()
  dataStore.fetchPlugins()
  dataStore.fetchQualityMetrics()
})
</script>

<template>
  <div class="datamanage-view">
    <t-row :gutter="16" style="margin-bottom: 16px">
      <t-col :span="3">
        <t-card title="数据源" :bordered="false">
          <div class="stat-value">{{ dataStore.dataSources.length }}</div>
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
        <t-card title="已启用插件" :bordered="false">
          <div class="stat-value">
            {{ dataStore.plugins.filter(p => p.is_enabled).length }}
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

    <t-card>
      <t-tabs v-model="activeTab">
        <t-tab-panel value="datasource" label="数据源">
          <t-table
            :data="dataStore.dataSources"
            :columns="datasourceColumns"
            :loading="dataStore.loading"
            row-key="id"
          >
            <template #is_enabled="{ row }">
              <t-tag :theme="row.is_enabled ? 'success' : 'default'">
                {{ row.is_enabled ? '已启用' : '已禁用' }}
              </t-tag>
            </template>
            <template #operation="{ row }">
              <t-space>
                <t-link theme="primary" @click="handleTriggerSync(row.id, 'incremental')">
                  增量同步
                </t-link>
                <t-link theme="primary" @click="handleTriggerSync(row.id, 'full')">
                  全量同步
                </t-link>
              </t-space>
            </template>
          </t-table>
        </t-tab-panel>

        <t-tab-panel value="tasks" label="同步任务">
          <t-table
            :data="dataStore.syncTasks"
            :columns="taskColumns"
            :loading="dataStore.loading"
            row-key="task_id"
          >
            <template #status="{ row }">
              <t-tag
                :theme="(({
                  pending: 'warning',
                  running: 'primary',
                  completed: 'success',
                  failed: 'danger'
                } as Record<string, string>)[row.status as string]) || 'default'"
              >
                {{ row.status }}
              </t-tag>
            </template>
            <template #progress="{ row }">
              <t-progress :percentage="row.progress" size="small" />
            </template>
          </t-table>
        </t-tab-panel>

        <t-tab-panel value="plugins" label="插件管理">
          <t-table
            :data="dataStore.plugins"
            :columns="pluginColumns"
            :loading="dataStore.loading"
            row-key="name"
          >
            <template #is_enabled="{ row }">
              <t-switch
                :value="row.is_enabled"
                @change="handleTogglePlugin(row.name, row.is_enabled)"
              />
            </template>
            <template #last_run_status="{ row }">
              <t-tag
                v-if="row.last_run_status"
                :theme="row.last_run_status === 'success' ? 'success' : 'danger'"
              >
                {{ row.last_run_status }}
              </t-tag>
            </template>
          </t-table>
        </t-tab-panel>

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
          </t-table>
        </t-tab-panel>
      </t-tabs>
    </t-card>
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
