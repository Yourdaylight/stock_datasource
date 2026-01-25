<template>
  <t-dialog
    :visible="visible"
    :header="group?.name || '组合详情'"
    width="700px"
    :footer="false"
    @close="handleClose"
  >
    <div v-if="loading" class="loading-container">
      <t-loading size="medium" text="加载中..." />
    </div>
    
    <div v-else-if="detail" class="group-detail">
      <!-- 基本信息 -->
      <t-descriptions :column="2" bordered>
        <t-descriptions-item label="组合名称">
          <span>{{ detail.name }}</span>
          <t-tag v-if="detail.is_predefined" theme="warning" size="small" style="margin-left: 8px;">
            <t-icon name="lock-on" size="12px" />
            预定义
          </t-tag>
        </t-descriptions-item>
        <t-descriptions-item label="分类">
          <t-tag>{{ getCategoryLabel(detail.category) }}</t-tag>
        </t-descriptions-item>
        <t-descriptions-item label="描述" :span="2">
          {{ detail.description || '暂无描述' }}
        </t-descriptions-item>
        <t-descriptions-item label="插件数量">
          {{ detail.plugin_names?.length || 0 }} 个
        </t-descriptions-item>
        <t-descriptions-item label="默认同步类型">
          <t-tag :theme="getTaskTypeTheme(detail.default_task_type)">
            {{ getTaskTypeLabel(detail.default_task_type) }}
          </t-tag>
        </t-descriptions-item>
      </t-descriptions>

      <!-- 插件列表 -->
      <div class="plugin-list-section">
        <h4 class="section-title">包含的插件</h4>
        <t-table
          :data="detail.plugin_status"
          :columns="pluginColumns"
          size="small"
          row-key="name"
          :hover="true"
        >
          <template #exists="{ row }">
            <t-tag :theme="row.exists ? 'success' : 'danger'" size="small">
              {{ row.exists ? '已安装' : '未安装' }}
            </t-tag>
          </template>
          <template #has_data="{ row }">
            <t-tag :theme="row.has_data ? 'success' : 'warning'" size="small">
              {{ row.has_data ? '有数据' : '无数据' }}
            </t-tag>
          </template>
        </t-table>
      </div>

      <!-- 执行顺序 -->
      <div class="execution-order-section">
        <h4 class="section-title">执行顺序</h4>
        <div class="execution-steps">
          <t-steps :current="-1" readonly layout="horizontal">
            <t-step-item 
              v-for="(name, index) in detail.execution_order" 
              :key="name"
              :title="name"
              :content="`第 ${index + 1} 步`"
            />
          </t-steps>
        </div>
        <div class="execution-note">
          <t-icon name="info-circle" />
          <span>系统将按依赖关系自动确定执行顺序，无依赖的插件可并行执行</span>
        </div>
      </div>

      <!-- 数据重复校验结果 -->
      <div v-if="checkResult && checkResult.plugins_with_existing_data.length > 0" class="check-result-section">
        <h4 class="section-title">数据检测结果</h4>
        <t-alert theme="warning" :close="false">
          <template #message>
            <div class="check-result-content">
              <p><strong>以下 {{ checkResult.plugins_with_existing_data.length }} 个插件已有数据：</strong></p>
              <div class="plugin-tags">
                <t-tag 
                  v-for="name in checkResult.plugins_with_existing_data" 
                  :key="name"
                  theme="warning"
                  variant="light"
                >
                  {{ name }}
                </t-tag>
              </div>
              <p v-if="checkResult.plugins_missing_data.length > 0" class="missing-hint">
                另有 {{ checkResult.plugins_missing_data.length }} 个插件无数据
              </p>
            </div>
          </template>
        </t-alert>
      </div>

      <!-- 覆盖确认 -->
      <div v-if="showOverwriteConfirm" class="overwrite-section">
        <t-alert theme="error" :close="false">
          <template #message>
            <div class="overwrite-content">
              <p><strong>请选择操作方式：</strong></p>
              <t-space direction="vertical" size="small" style="width: 100%">
                <t-button 
                  theme="danger" 
                  variant="outline" 
                  block
                  @click="handleOverwriteConfirm(true)"
                >
                  覆盖更新所有插件数据
                </t-button>
                <t-button 
                  v-if="checkResult && checkResult.plugins_missing_data.length > 0"
                  theme="primary" 
                  variant="outline" 
                  block
                  @click="handleOverwriteConfirm(false)"
                >
                  仅同步 {{ checkResult.plugins_missing_data.length }} 个缺失数据的插件
                </t-button>
                <t-button 
                  theme="default" 
                  variant="outline" 
                  block
                  @click="showOverwriteConfirm = false"
                >
                  取消
                </t-button>
              </t-space>
            </div>
          </template>
        </t-alert>
      </div>

      <!-- 操作按钮 -->
      <div class="dialog-footer">
        <t-button theme="default" @click="handleClose">关闭</t-button>
        <t-button 
          theme="primary" 
          @click="handleExecute" 
          :loading="executing || checking"
          :disabled="showOverwriteConfirm"
        >
          <t-icon name="play-circle" />
          {{ checking ? '检查中...' : '执行同步' }}
        </t-button>
      </div>
    </div>
    
    <div v-else class="empty-container">
      <t-result theme="warning" title="加载失败" description="无法获取组合详情" />
    </div>
  </t-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import type { PluginGroup, PluginGroupDetail, GroupCategory, TaskType, GroupDataExistsCheckResult } from '@/api/datamanage'
import { datamanageApi } from '@/api/datamanage'
import { useDataManageStore } from '@/stores/datamanage'

interface Props {
  visible: boolean
  group: PluginGroup | null
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:visible': [value: boolean]
  'execute': [group: PluginGroup]
}>()

const dataStore = useDataManageStore()

const loading = ref(false)
const executing = ref(false)
const checking = ref(false)
const detail = ref<PluginGroupDetail | null>(null)
const checkResult = ref<GroupDataExistsCheckResult | null>(null)
const showOverwriteConfirm = ref(false)

const pluginColumns = [
  { colKey: 'name', title: '插件名称', width: 200 },
  { colKey: 'exists', title: '插件状态', width: 100 },
  { colKey: 'has_data', title: '数据状态', width: 100 }
]

const categoryLabelMap: Record<GroupCategory, string> = {
  system: '系统维护',
  cn_stock: 'A股',
  index: '指数',
  etf_fund: 'ETF基金',
  daily: '每日更新',
  custom: '自定义'
}

const getCategoryLabel = (category: GroupCategory): string => {
  return categoryLabelMap[category] || category
}

const getTaskTypeLabel = (type: TaskType): string => {
  const map: Record<TaskType, string> = {
    incremental: '增量同步',
    full: '全量同步',
    backfill: '回补数据'
  }
  return map[type] || type
}

const getTaskTypeTheme = (type: TaskType): string => {
  const map: Record<TaskType, string> = {
    incremental: 'primary',
    full: 'warning',
    backfill: 'success'
  }
  return map[type] || 'default'
}

// Get today's date in YYYY-MM-DD format
const getTodayDate = (): string => {
  const today = new Date()
  return today.toISOString().split('T')[0]
}

// 监听 visible 变化，加载详情
watch(() => props.visible, async (newVal) => {
  if (newVal && props.group) {
    loading.value = true
    checkResult.value = null
    showOverwriteConfirm.value = false
    try {
      detail.value = await dataStore.fetchGroupDetail(props.group.group_id)
    } catch (e) {
      console.error('Failed to load group detail:', e)
    } finally {
      loading.value = false
    }
  } else {
    detail.value = null
    checkResult.value = null
    showOverwriteConfirm.value = false
  }
})

const handleClose = () => {
  emit('update:visible', false)
}

// Check if data exists for the group
const checkDataExists = async (): Promise<boolean> => {
  if (!props.group) return false
  
  checking.value = true
  try {
    // Check today's date for incremental sync
    const dates = [getTodayDate()]
    checkResult.value = await datamanageApi.checkGroupDataExists(props.group.group_id, dates)
    
    // Return true if any plugin has existing data
    return checkResult.value.plugins_with_existing_data.length > 0
  } catch (e) {
    console.error('Failed to check data exists:', e)
    // If check fails, proceed without warning
    return false
  } finally {
    checking.value = false
  }
}

const handleExecute = async () => {
  if (!props.group) return
  
  // First check if data exists
  const hasExistingData = await checkDataExists()
  
  if (hasExistingData) {
    // Show confirmation dialog
    showOverwriteConfirm.value = true
    return
  }
  
  // No existing data, proceed directly
  await doExecute(false)
}

const handleOverwriteConfirm = async (overwrite: boolean) => {
  if (overwrite) {
    // Overwrite all
    await doExecute(true)
  } else {
    // Only sync plugins with missing data
    // For now, just trigger with force_overwrite=false
    // The backend will handle incremental sync
    await doExecute(false)
  }
}

const doExecute = async (forceOverwrite: boolean) => {
  if (!props.group) return
  
  executing.value = true
  try {
    await dataStore.triggerPluginGroup(props.group.group_id, {
      task_type: detail.value?.default_task_type || 'incremental',
      force_overwrite: forceOverwrite
    })
    MessagePlugin.success(`已触发组合 "${props.group.name}" 同步`)
    emit('execute', props.group)
    handleClose()
  } catch (e: any) {
    MessagePlugin.error(e.message || '触发同步失败')
  } finally {
    executing.value = false
    showOverwriteConfirm.value = false
  }
}
</script>

<style scoped>
.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px;
}

.empty-container {
  padding: 40px 0;
}

.group-detail .section-title {
  margin: 24px 0 12px;
  font-size: 14px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}

.group-detail .section-title:first-child {
  margin-top: 16px;
}

.group-detail .plugin-list-section {
  margin-top: 16px;
}

.group-detail .execution-order-section {
  margin-top: 16px;
}

.group-detail .execution-steps {
  padding: 16px;
  background: var(--td-bg-color-container);
  border-radius: var(--td-radius-medium);
  overflow-x: auto;
}

.group-detail .execution-note {
  margin-top: 8px;
  padding: 8px 12px;
  background: var(--td-bg-color-container-hover);
  border-radius: var(--td-radius-small);
  font-size: 12px;
  color: var(--td-text-color-secondary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.group-detail .check-result-section {
  margin-top: 16px;
}

.group-detail .check-result-content {
  width: 100%;
}

.group-detail .check-result-content p {
  margin: 0 0 8px 0;
}

.group-detail .plugin-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.group-detail .missing-hint {
  margin-top: 8px !important;
  color: var(--td-text-color-secondary);
  font-size: 12px;
}

.group-detail .overwrite-section {
  margin-top: 16px;
}

.group-detail .overwrite-content {
  width: 100%;
}

.group-detail .overwrite-content p {
  margin: 0 0 12px 0;
}

.group-detail .dialog-footer {
  margin-top: 24px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid var(--td-component-border);
}
</style>
