<script setup lang="ts">
import { ref, watch } from 'vue'
import { etfApi, type EtfInfo } from '@/api/etf'

const props = defineProps<{
  visible: boolean
  etfCode: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
  (e: 'analyze', row: EtfInfo): void
}>()

const loading = ref(false)
const etfInfo = ref<EtfInfo | null>(null)

watch(() => props.etfCode, async (code) => {
  if (code && props.visible) {
    loading.value = true
    try {
      etfInfo.value = await etfApi.getEtfDetail(code)
    } catch (e) {
      console.error('Failed to fetch ETF detail:', e)
      etfInfo.value = null
    } finally {
      loading.value = false
    }
  }
}, { immediate: true })

watch(() => props.visible, (visible) => {
  if (visible && props.etfCode) {
    // Reload when dialog opens
    etfApi.getEtfDetail(props.etfCode).then(data => {
      etfInfo.value = data
    })
  }
})

const handleClose = () => {
  emit('update:visible', false)
  emit('close')
}

const handleAnalyze = () => {
  if (etfInfo.value) {
    emit('analyze', etfInfo.value)
    handleClose()
  }
}

const getMarketLabel = (market?: string) => {
  const map: Record<string, string> = {
    'E': '上交所',
    'Z': '深交所',
    'SH': '上交所',
    'SZ': '深交所',
  }
  return market ? map[market] || market : '-'
}

const getStatusLabel = (status?: string) => {
  const map: Record<string, string> = {
    'L': '上市',
    'D': '退市',
    'P': '待上市',
    'I': '发行',
  }
  return status ? map[status] || status : '-'
}
</script>

<template>
  <t-dialog
    :visible="visible"
    :header="etfInfo?.csname || 'ETF详情'"
    width="700px"
    :footer="false"
    @close="handleClose"
  >
    <t-loading :loading="loading">
      <div v-if="etfInfo" class="etf-detail">
        <!-- Basic Info -->
        <t-descriptions title="基本信息" :column="2" bordered>
          <t-descriptions-item label="ETF代码">{{ etfInfo.ts_code }}</t-descriptions-item>
          <t-descriptions-item label="ETF简称">{{ etfInfo.csname || '-' }}</t-descriptions-item>
          <t-descriptions-item label="ETF全称">{{ etfInfo.cname || '-' }}</t-descriptions-item>
          <t-descriptions-item label="交易所">{{ getMarketLabel(etfInfo.exchange) }}</t-descriptions-item>
          <t-descriptions-item label="状态">{{ getStatusLabel(etfInfo.list_status) }}</t-descriptions-item>
          <t-descriptions-item label="基金类型">{{ etfInfo.etf_type || '-' }}</t-descriptions-item>
          <t-descriptions-item label="上市日期">{{ etfInfo.list_date || '-' }}</t-descriptions-item>
          <t-descriptions-item label="设立日期">{{ etfInfo.setup_date || '-' }}</t-descriptions-item>
        </t-descriptions>

        <!-- Management Info -->
        <t-descriptions title="管理信息" :column="2" bordered style="margin-top: 16px">
          <t-descriptions-item label="管理人">{{ etfInfo.mgr_name || '-' }}</t-descriptions-item>
          <t-descriptions-item label="托管人">{{ etfInfo.custod_name || '-' }}</t-descriptions-item>
          <t-descriptions-item label="管理费率">
            {{ etfInfo.mgt_fee ? (etfInfo.mgt_fee * 100).toFixed(2) + '%' : '-' }}
          </t-descriptions-item>
        </t-descriptions>

        <!-- Tracking Info -->
        <t-descriptions title="跟踪信息" :column="2" bordered style="margin-top: 16px">
          <t-descriptions-item label="指数代码">{{ etfInfo.index_code || '-' }}</t-descriptions-item>
          <t-descriptions-item label="指数名称">{{ etfInfo.index_name || '-' }}</t-descriptions-item>
        </t-descriptions>

        <!-- Actions -->
        <div class="detail-actions">
          <t-button theme="primary" @click="handleAnalyze">
            <t-icon name="chart-analytics" style="margin-right: 4px" />
            AI分析
          </t-button>
        </div>
      </div>
      <t-empty v-else description="未找到ETF信息" />
    </t-loading>
  </t-dialog>
</template>

<style scoped>
.etf-detail {
  padding: 8px 0;
}

.detail-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--td-component-border);
}
</style>
