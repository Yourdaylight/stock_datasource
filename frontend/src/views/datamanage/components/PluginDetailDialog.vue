<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useDataManageStore } from '@/stores/datamanage'
import type { DependencyCheckResult } from '@/api/datamanage'

const props = defineProps<{
  visible: boolean
  pluginName: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const dataStore = useDataManageStore()
const activeTab = ref('info')
const dependencies = ref<DependencyCheckResult | null>(null)

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

watch(() => props.visible, async (val) => {
  if (val && props.pluginName) {
    dataStore.fetchPluginDetail(props.pluginName)
    // Fetch dependencies
    dependencies.value = await dataStore.fetchPluginDependencies(props.pluginName)
  }
})

const detail = computed(() => dataStore.currentPluginDetail)

const frequencyText = computed(() => {
  if (!detail.value?.config.schedule) return '-'
  const schedule = detail.value.config.schedule
  if (schedule.frequency === 'daily') {
    return `每日 ${schedule.time}`
  } else if (schedule.frequency === 'weekly') {
    const dayMap: Record<string, string> = {
      monday: '周一', tuesday: '周二', wednesday: '周三',
      thursday: '周四', friday: '周五', saturday: '周六', sunday: '周日'
    }
    return `每${dayMap[schedule.day_of_week || 'monday'] || '周一'} ${schedule.time}`
  }
  return '-'
})

const schemaColumns = [
  { colKey: 'name', title: '字段名', width: 150 },
  { colKey: 'data_type', title: '数据类型', width: 200 },
  { colKey: 'nullable', title: '可空', width: 80 },
  { colKey: 'comment', title: '说明', minWidth: 200 }
]
</script>

<template>
  <t-dialog
    v-model:visible="dialogVisible"
    :header="`插件详情 - ${pluginName}`"
    width="800px"
    :footer="false"
  >
    <t-loading :loading="dataStore.detailLoading">
      <div v-if="detail" class="plugin-detail">
        <t-tabs v-model="activeTab">
          <t-tab-panel value="info" label="基本信息">
            <t-descriptions :column="2" bordered>
              <t-descriptions-item label="插件名称">{{ detail.plugin_name }}</t-descriptions-item>
              <t-descriptions-item label="版本">{{ detail.version }}</t-descriptions-item>
              <t-descriptions-item label="描述" :span="2">{{ detail.description || '-' }}</t-descriptions-item>
              <t-descriptions-item label="调度频率">{{ frequencyText }}</t-descriptions-item>
              <t-descriptions-item label="状态">
                <t-tag :theme="detail.config.enabled ? 'success' : 'default'">
                  {{ detail.config.enabled ? '已启用' : '已禁用' }}
                </t-tag>
              </t-descriptions-item>
              <t-descriptions-item label="速率限制">{{ detail.config.rate_limit }} 次/分钟</t-descriptions-item>
              <t-descriptions-item label="超时时间">{{ detail.config.timeout }} 秒</t-descriptions-item>
              <t-descriptions-item label="重试次数">{{ detail.config.retry_attempts }} 次</t-descriptions-item>
            </t-descriptions>
          </t-tab-panel>

          <t-tab-panel value="schema" label="数据结构">
            <t-descriptions :column="2" bordered style="margin-bottom: 16px">
              <t-descriptions-item label="表名">{{ detail.table_schema.table_name }}</t-descriptions-item>
              <t-descriptions-item label="表类型">{{ detail.table_schema.table_type }}</t-descriptions-item>
              <t-descriptions-item label="分区键">{{ detail.table_schema.partition_by || '-' }}</t-descriptions-item>
              <t-descriptions-item label="排序键">{{ detail.table_schema.order_by.join(', ') || '-' }}</t-descriptions-item>
              <t-descriptions-item label="存储引擎">{{ detail.table_schema.engine }}</t-descriptions-item>
              <t-descriptions-item label="引擎参数">{{ detail.table_schema.engine_params.join(', ') || '-' }}</t-descriptions-item>
              <t-descriptions-item label="表说明" :span="2">{{ detail.table_schema.comment || '-' }}</t-descriptions-item>
            </t-descriptions>
            
            <h4 style="margin-bottom: 12px">字段定义</h4>
            <t-table
              :data="detail.table_schema.columns"
              :columns="schemaColumns"
              row-key="name"
              size="small"
              bordered
              max-height="300"
            >
              <template #nullable="{ row }">
                <t-tag :theme="row.nullable ? 'default' : 'warning'" size="small">
                  {{ row.nullable ? '是' : '否' }}
                </t-tag>
              </template>
            </t-table>
          </t-tab-panel>

          <t-tab-panel value="status" label="运行状态">
            <t-descriptions :column="2" bordered>
              <t-descriptions-item label="最新数据日期">
                {{ detail.status.latest_date || '-' }}
              </t-descriptions-item>
              <t-descriptions-item label="总记录数">
                {{ detail.status.total_records.toLocaleString() }}
              </t-descriptions-item>
              <t-descriptions-item label="缺失天数">
                <t-tag :theme="detail.status.missing_count > 0 ? 'danger' : 'success'">
                  {{ detail.status.missing_count }}
                </t-tag>
              </t-descriptions-item>
              <t-descriptions-item label="缺失日期" :span="2">
                <div v-if="detail.status.missing_dates.length > 0">
                  <t-tag 
                    v-for="date in detail.status.missing_dates" 
                    :key="date" 
                    theme="warning"
                    style="margin-right: 8px; margin-bottom: 4px"
                  >
                    {{ date }}
                  </t-tag>
                </div>
                <span v-else>无</span>
              </t-descriptions-item>
            </t-descriptions>
          </t-tab-panel>

          <t-tab-panel value="params" label="参数配置">
            <div v-if="Object.keys(detail.config.parameters_schema).length > 0">
              <t-table
                :data="Object.entries(detail.config.parameters_schema).map(([key, val]) => ({ key, ...val as object }))"
                :columns="[
                  { colKey: 'key', title: '参数名', width: 150 },
                  { colKey: 'type', title: '类型', width: 100 },
                  { colKey: 'default', title: '默认值', width: 100 },
                  { colKey: 'description', title: '说明', minWidth: 200 }
                ]"
                row-key="key"
                size="small"
                bordered
              >
                <template #enum="{ row }">
                  <span v-if="row.enum">{{ row.enum.join(', ') }}</span>
                </template>
              </t-table>
            </div>
            <t-empty v-else description="暂无参数配置" />
          </t-tab-panel>

          <t-tab-panel value="dependencies" label="依赖关系">
            <t-loading :loading="dataStore.dependencyLoading">
              <div v-if="dependencies">
                <!-- Dependency Status Summary -->
                <t-alert 
                  :theme="dependencies.satisfied ? 'success' : 'warning'" 
                  :close="false"
                  style="margin-bottom: 16px"
                >
                  <template #message>
                    <div class="dep-status">
                      <t-icon :name="dependencies.satisfied ? 'check-circle' : 'error-circle'" />
                      <span v-if="dependencies.satisfied">所有依赖已满足，可以正常同步</span>
                      <span v-else>依赖未满足，请先运行依赖插件</span>
                    </div>
                  </template>
                </t-alert>

                <!-- Dependencies List -->
                <div v-if="dependencies.dependencies.length > 0">
                  <h4 style="margin-bottom: 12px">依赖插件</h4>
                  <t-table
                    :data="dependencies.dependency_details"
                    :columns="[
                      { colKey: 'plugin_name', title: '插件名称', width: 200 },
                      { colKey: 'table_name', title: '数据表', width: 200 },
                      { colKey: 'has_data', title: '数据状态', width: 120 }
                    ]"
                    row-key="plugin_name"
                    size="small"
                    bordered
                  >
                    <template #has_data="{ row }">
                      <t-tag :theme="row.has_data ? 'success' : 'danger'" variant="light">
                        <t-icon :name="row.has_data ? 'check' : 'close'" style="margin-right: 4px" />
                        {{ row.has_data ? '有数据' : '无数据' }}
                      </t-tag>
                    </template>
                  </t-table>

                  <!-- Missing Data Warning -->
                  <div v-if="Object.keys(dependencies.missing_data).length > 0" style="margin-top: 16px">
                    <t-alert theme="error" :close="false">
                      <template #message>
                        <div>
                          <p style="margin: 0 0 8px 0"><strong>缺失数据的依赖：</strong></p>
                          <ul style="margin: 0; padding-left: 20px">
                            <li v-for="(reason, name) in dependencies.missing_data" :key="name">
                              {{ name }}: {{ reason }}
                            </li>
                          </ul>
                        </div>
                      </template>
                    </t-alert>
                  </div>
                </div>
                <t-empty v-else description="此插件没有依赖其他插件" />

                <!-- Optional Dependencies -->
                <div v-if="dependencies.optional_dependencies && dependencies.optional_dependencies.length > 0" style="margin-top: 20px">
                  <h4 style="margin-bottom: 12px">可选依赖（同步时自动触发）</h4>
                  <t-space wrap>
                    <t-tag 
                      v-for="dep in dependencies.optional_dependencies" 
                      :key="dep"
                      theme="primary"
                      variant="light"
                    >
                      {{ dep }}
                    </t-tag>
                  </t-space>
                  <p style="margin-top: 8px; font-size: 12px; color: var(--td-text-color-secondary)">
                    当同步此插件时，可选依赖会自动被触发同步
                  </p>
                </div>
              </div>
              <t-empty v-else-if="!dataStore.dependencyLoading" description="无法加载依赖信息" />
            </t-loading>
          </t-tab-panel>
        </t-tabs>
      </div>
      <t-empty v-else-if="!dataStore.detailLoading" description="无法加载插件详情" />
    </t-loading>
  </t-dialog>
</template>

<style scoped>
.plugin-detail {
  min-height: 300px;
}

.dep-status {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
