<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { InfoCircleFilledIcon, ErrorCircleFilledIcon } from 'tdesign-icons-vue-next'

interface Props {
  visible: boolean
  date: string
  pluginName?: string
  dataType?: 'ETF' | '指数'
}

const props = withDefaults(defineProps<Props>(), {
  pluginName: '',
  dataType: 'ETF'
})

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'confirm'): void
}>()

const router = useRouter()

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const formattedDate = computed(() => {
  if (!props.date) return ''
  // Format YYYYMMDD to YYYY-MM-DD
  if (props.date.length === 8) {
    return `${props.date.slice(0, 4)}-${props.date.slice(4, 6)}-${props.date.slice(6, 8)}`
  }
  return props.date
})

const handleCancel = () => {
  dialogVisible.value = false
}

const handleGoToDataManagement = () => {
  dialogVisible.value = false
  emit('confirm')
  // Navigate to data management with plugin filter
  const query: Record<string, string> = {}
  if (props.pluginName) {
    query.plugin = props.pluginName
  }
  router.push({ path: '/datamanage', query })
}
</script>

<template>
  <t-dialog
    v-model:visible="dialogVisible"
    header="数据提示"
    :footer="false"
    width="420px"
    placement="center"
  >
    <div class="dialog-content">
      <div class="warning-section">
        <ErrorCircleFilledIcon class="warning-icon" />
        <div class="warning-text">
          <p class="main-text">
            当前日期 <strong>{{ formattedDate }}</strong> 暂无{{ dataType }}数据
          </p>
        </div>
      </div>
      
      <div class="tip-section">
        <InfoCircleFilledIcon class="info-icon" />
        <p class="tip-text">
          您可以在「数据管理」中执行对应的插件来更新数据
        </p>
      </div>
    </div>
    
    <div class="dialog-footer">
      <t-button theme="default" @click="handleCancel">取消</t-button>
      <t-button theme="primary" @click="handleGoToDataManagement">
        前往数据管理
      </t-button>
    </div>
  </t-dialog>
</template>

<style scoped>
.dialog-content {
  padding: 8px 0;
}

.warning-section {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.warning-icon {
  font-size: 24px;
  color: #ed7b2f;
  flex-shrink: 0;
  margin-top: 2px;
}

.warning-text {
  flex: 1;
}

.main-text {
  margin: 0;
  font-size: 14px;
  color: #1d2129;
  line-height: 1.6;
}

.main-text strong {
  color: #0052d9;
}

.tip-section {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px;
  background: #f3f3f3;
  border-radius: 6px;
}

.info-icon {
  font-size: 16px;
  color: #0052d9;
  flex-shrink: 0;
  margin-top: 2px;
}

.tip-text {
  margin: 0;
  font-size: 13px;
  color: #4e5969;
  line-height: 1.5;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #e7e7e7;
}
</style>
