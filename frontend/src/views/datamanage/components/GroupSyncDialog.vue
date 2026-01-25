<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import type { PluginGroup } from '@/api/datamanage'

const props = defineProps<{
  visible: boolean
  group: PluginGroup | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'confirm', groupId: string, taskType: 'incremental' | 'full' | 'backfill', dates: string[]): void
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

// Form state
const taskType = ref<'incremental' | 'full' | 'backfill'>('incremental')
const dateRange = ref<string[]>([])

// Reset state when dialog opens, use group's default task type
watch(() => props.visible, (val) => {
  if (val && props.group) {
    taskType.value = props.group.default_task_type || 'incremental'
    dateRange.value = []
  }
})

// Generate date list from range
const generateDateList = (start: string, end: string): string[] => {
  const dates: string[] = []
  const startDate = new Date(start)
  const endDate = new Date(end)
  
  const current = new Date(startDate)
  while (current <= endDate) {
    dates.push(current.toISOString().split('T')[0])
    current.setDate(current.getDate() + 1)
  }
  
  return dates
}

const handleConfirm = () => {
  if (!props.group) return
  
  if (taskType.value === 'backfill' && dateRange.value.length !== 2) {
    MessagePlugin.warning('请选择要补录的日期范围')
    return
  }
  
  let dates: string[] = []
  if (taskType.value === 'backfill' && dateRange.value.length === 2) {
    dates = generateDateList(dateRange.value[0], dateRange.value[1])
  }
  
  emit('confirm', props.group.group_id, taskType.value, dates)
  dialogVisible.value = false
}

// Disable future dates
const disableFutureDates = (date: Date) => {
  return date > new Date()
}

// Computed: selected date count
const selectedDateCount = computed(() => {
  if (dateRange.value.length !== 2) return 0
  return generateDateList(dateRange.value[0], dateRange.value[1]).length
})
</script>

<template>
  <t-dialog
    v-model:visible="dialogVisible"
    header="组合数据同步"
    :width="560"
    :confirm-btn="null"
    :cancel-btn="null"
  >
    <div class="sync-dialog">
      <t-form label-align="left" :label-width="80">
        <t-form-item label="组合名称">
          <t-input :value="group?.name || ''" disabled />
        </t-form-item>
        
        <t-form-item label="包含插件">
          <div class="plugin-list">
            <t-tag 
              v-for="name in (group?.plugin_names || [])" 
              :key="name" 
              theme="primary" 
              variant="light" 
              size="small"
              style="margin: 2px"
            >
              {{ name }}
            </t-tag>
            <span v-if="!group?.plugin_names?.length" class="no-plugins">无插件</span>
          </div>
        </t-form-item>
        
        <t-form-item label="同步类型">
          <t-radio-group v-model="taskType">
            <t-radio value="incremental">增量同步</t-radio>
            <t-radio value="full">全量同步</t-radio>
            <t-radio value="backfill">按日期补录</t-radio>
          </t-radio-group>
        </t-form-item>
        
        <t-form-item v-if="taskType === 'backfill'" label="日期范围">
          <t-date-range-picker
            v-model="dateRange"
            :disable-date="disableFutureDates"
            allow-input
            clearable
            placeholder="选择日期范围"
            style="width: 100%"
          />
          <div v-if="selectedDateCount > 0" class="date-hint">
            <t-icon name="info-circle" />
            <span>已选择 {{ selectedDateCount }} 天（系统会自动过滤非交易日）</span>
          </div>
        </t-form-item>
        
        <!-- Task type hints -->
        <t-form-item label="">
          <t-alert 
            v-if="taskType === 'incremental'" 
            theme="info" 
            :close="false"
          >
            <template #message>
              增量同步将获取最新一个交易日的数据（针对组合内所有插件）
            </template>
          </t-alert>
          <t-alert 
            v-else-if="taskType === 'full'" 
            theme="warning" 
            :close="false"
          >
            <template #message>
              全量同步将重新获取所有数据，耗时较长（针对组合内所有插件）
            </template>
          </t-alert>
          <t-alert 
            v-else-if="taskType === 'backfill' && selectedDateCount > 30" 
            theme="warning" 
            :close="false"
          >
            <template #message>
              选择了 {{ selectedDateCount }} 天数据，针对 {{ group?.plugin_names?.length || 0 }} 个插件同步可能需要较长时间
            </template>
          </t-alert>
        </t-form-item>
      </t-form>
    </div>
    
    <template #footer>
      <t-space>
        <t-button theme="default" @click="dialogVisible = false">取消</t-button>
        <t-button 
          theme="primary" 
          @click="handleConfirm"
        >
          开始同步
        </t-button>
      </t-space>
    </template>
  </t-dialog>
</template>

<style scoped>
.sync-dialog {
  padding: 8px 0;
}

.plugin-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  max-height: 120px;
  overflow-y: auto;
}

.no-plugins {
  color: var(--td-text-color-placeholder);
  font-size: 13px;
}

.date-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}
</style>
