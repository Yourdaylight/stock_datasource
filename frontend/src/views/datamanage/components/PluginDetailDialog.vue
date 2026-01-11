<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useDataManageStore } from '@/stores/datamanage'

const props = defineProps<{
  visible: boolean
  pluginName: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const dataStore = useDataManageStore()
const activeTab = ref('info')

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

watch(() => props.visible, (val) => {
  if (val && props.pluginName) {
    dataStore.fetchPluginDetail(props.pluginName)
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
</style>
