<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { datamanageApi, type DataExistsCheckResult } from '@/api/datamanage'

const props = defineProps<{
  visible: boolean
  pluginName: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'confirm', pluginName: string, taskType: 'incremental' | 'full' | 'backfill', dates: string[], forceOverwrite: boolean): void
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

// Form state
const taskType = ref<'incremental' | 'full' | 'backfill'>('incremental')
const dateRange = ref<string[]>([])
const checking = ref(false)
const checkResult = ref<DataExistsCheckResult | null>(null)
const showOverwriteConfirm = ref(false)

// Reset state when dialog opens
watch(() => props.visible, (val) => {
  if (val) {
    taskType.value = 'incremental'
    dateRange.value = []
    checkResult.value = null
    showOverwriteConfirm.value = false
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

// Check if selected dates have existing data
const checkDataExists = async () => {
  if (dateRange.value.length !== 2) {
    return
  }
  
  checking.value = true
  try {
    const dateList = generateDateList(dateRange.value[0], dateRange.value[1])
    checkResult.value = await datamanageApi.checkDataExists(props.pluginName, dateList)
  } catch (e) {
    console.error('Failed to check data exists:', e)
    MessagePlugin.error('检查数据存在性失败')
  } finally {
    checking.value = false
  }
}

// Watch date selection changes
watch(dateRange, () => {
  checkResult.value = null
  showOverwriteConfirm.value = false
})

const handleConfirm = async () => {
  if (taskType.value === 'backfill' && dateRange.value.length !== 2) {
    MessagePlugin.warning('请选择要补录的日期范围')
    return
  }
  
  // For backfill, check if data exists
  if (taskType.value === 'backfill' && dateRange.value.length === 2) {
    await checkDataExists()
    
    if (checkResult.value && checkResult.value.existing_dates.length > 0) {
      // Show confirmation dialog
      showOverwriteConfirm.value = true
      return
    }
  }
  
  // Proceed with sync
  submitSync(false)
}

const handleOverwriteConfirm = (overwrite: boolean) => {
  if (overwrite) {
    submitSync(true)
  } else {
    // Only sync non-existing dates
    if (checkResult.value && checkResult.value.non_existing_dates.length > 0) {
      const dates = checkResult.value.non_existing_dates
      emit('confirm', props.pluginName, taskType.value, dates, false)
      dialogVisible.value = false
    } else {
      MessagePlugin.info('所有选择的日期都已有数据，无需同步')
      showOverwriteConfirm.value = false
    }
  }
}

const submitSync = (forceOverwrite: boolean) => {
  let dates: string[] = []
  
  if (taskType.value === 'backfill' && dateRange.value.length === 2) {
    dates = generateDateList(dateRange.value[0], dateRange.value[1])
  }
  
  emit('confirm', props.pluginName, taskType.value, dates, forceOverwrite)
  dialogVisible.value = false
}

const formatRecordCount = (count: number) => {
  return count.toLocaleString()
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
    header="数据同步"
    :width="560"
    :confirm-btn="null"
    :cancel-btn="null"
  >
    <div class="sync-dialog">
      <t-form label-align="left" :label-width="80">
        <t-form-item label="插件名称">
          <t-input :value="pluginName" disabled />
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
            <span>已选择 {{ selectedDateCount }} 天</span>
          </div>
        </t-form-item>
        
        <!-- Data exists check result -->
        <t-form-item v-if="checkResult && checkResult.existing_dates.length > 0" label="检测结果">
          <t-alert theme="warning" :close="false">
            <template #message>
              <div class="check-result">
                <p>以下 {{ checkResult.existing_dates.length }} 个日期已存在数据：</p>
                <div class="existing-dates">
                  <t-tag 
                    v-for="date in checkResult.existing_dates.slice(0, 10)" 
                    :key="date"
                    theme="warning"
                    variant="light"
                    class="date-tag"
                  >
                    {{ date }} ({{ formatRecordCount(checkResult.record_counts[date] || 0) }}条)
                  </t-tag>
                  <t-tag 
                    v-if="checkResult.existing_dates.length > 10"
                    theme="default"
                    variant="light"
                    class="date-tag"
                  >
                    ...还有 {{ checkResult.existing_dates.length - 10 }} 个日期
                  </t-tag>
                </div>
                <p v-if="checkResult.non_existing_dates.length > 0" class="non-existing-hint">
                  另有 {{ checkResult.non_existing_dates.length }} 个日期无数据
                </p>
              </div>
            </template>
          </t-alert>
        </t-form-item>
        
        <!-- Overwrite confirmation -->
        <t-form-item v-if="showOverwriteConfirm" label="">
          <t-alert theme="error" :close="false">
            <template #message>
              <div class="overwrite-confirm">
                <p><strong>请选择操作方式：</strong></p>
                <t-space direction="vertical" size="small" style="width: 100%">
                  <t-button 
                    theme="danger" 
                    variant="outline" 
                    block
                    @click="handleOverwriteConfirm(true)"
                  >
                    覆盖更新所有 {{ selectedDateCount }} 天数据
                  </t-button>
                  <t-button 
                    v-if="checkResult && checkResult.non_existing_dates.length > 0"
                    theme="primary" 
                    variant="outline" 
                    block
                    @click="handleOverwriteConfirm(false)"
                  >
                    仅同步 {{ checkResult.non_existing_dates.length }} 天缺失数据
                  </t-button>
                  <t-button 
                    theme="default" 
                    variant="outline" 
                    block
                    @click="showOverwriteConfirm = false"
                  >
                    返回重新选择日期
                  </t-button>
                </t-space>
              </div>
            </template>
          </t-alert>
        </t-form-item>
        
        <!-- Task type hints -->
        <t-form-item v-if="!showOverwriteConfirm" label="">
          <t-alert 
            v-if="taskType === 'incremental'" 
            theme="info" 
            :close="false"
          >
            <template #message>
              增量同步将获取最新一个交易日的数据
            </template>
          </t-alert>
          <t-alert 
            v-else-if="taskType === 'full'" 
            theme="warning" 
            :close="false"
          >
            <template #message>
              全量同步将重新获取所有数据，耗时较长
            </template>
          </t-alert>
          <t-alert 
            v-else-if="taskType === 'backfill' && selectedDateCount > 30" 
            theme="warning" 
            :close="false"
          >
            <template #message>
              选择了 {{ selectedDateCount }} 天数据，同步可能需要较长时间
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
          :loading="checking"
          :disabled="showOverwriteConfirm"
          @click="handleConfirm"
        >
          {{ checking ? '检查中...' : '开始同步' }}
        </t-button>
      </t-space>
    </template>
  </t-dialog>
</template>

<style scoped>
.sync-dialog {
  padding: 8px 0;
}

.date-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.check-result {
  width: 100%;
}

.check-result p {
  margin: 0 0 8px 0;
}

.existing-dates {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.date-tag {
  margin: 0;
}

.non-existing-hint {
  margin-top: 8px !important;
  color: var(--td-text-color-secondary);
  font-size: 12px;
}

.overwrite-confirm {
  width: 100%;
}

.overwrite-confirm p {
  margin: 0 0 12px 0;
}
</style>
