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
  }
  return market ? map[market] || market : '-'
}

const getStatusLabel = (status?: string) => {
  const map: Record<string, string> = {
    'L': '上市',
    'D': '退市',
    'I': '发行',
  }
  return status ? map[status] || status : '-'
}
</script>

<template>
  <t-dialog
    :visible="visible"
    :header="etfInfo?.name || 'ETF详情'"
    width="700px"
    :footer="false"
    @close="handleClose"
  >
    <t-loading :loading="loading">
      <div v-if="etfInfo" class="etf-detail">
        <!-- Basic Info -->
        <t-descriptions title="基本信息" :column="2" bordered>
          <t-descriptions-item label="ETF代码">{{ etfInfo.ts_code }}</t-descriptions-item>
          <t-descriptions-item label="ETF名称">{{ etfInfo.name || '-' }}</t-descriptions-item>
          <t-descriptions-item label="交易所">{{ getMarketLabel(etfInfo.market) }}</t-descriptions-item>
          <t-descriptions-item label="状态">{{ getStatusLabel(etfInfo.status) }}</t-descriptions-item>
          <t-descriptions-item label="基金类型">{{ etfInfo.fund_type || '-' }}</t-descriptions-item>
          <t-descriptions-item label="投资类型">{{ etfInfo.invest_type || '-' }}</t-descriptions-item>
          <t-descriptions-item label="上市日期">{{ etfInfo.list_date || '-' }}</t-descriptions-item>
          <t-descriptions-item label="成立日期">{{ etfInfo.found_date || '-' }}</t-descriptions-item>
        </t-descriptions>

        <!-- Management Info -->
        <t-descriptions title="管理信息" :column="2" bordered style="margin-top: 16px">
          <t-descriptions-item label="管理人">{{ etfInfo.management || '-' }}</t-descriptions-item>
          <t-descriptions-item label="托管人">{{ etfInfo.custodian || '-' }}</t-descriptions-item>
          <t-descriptions-item label="管理费率">
            {{ etfInfo.m_fee ? (etfInfo.m_fee * 100).toFixed(2) + '%' : '-' }}
          </t-descriptions-item>
          <t-descriptions-item label="托管费率">
            {{ etfInfo.c_fee ? (etfInfo.c_fee * 100).toFixed(2) + '%' : '-' }}
          </t-descriptions-item>
        </t-descriptions>

        <!-- Tracking Info -->
        <t-descriptions title="跟踪信息" :column="1" bordered style="margin-top: 16px">
          <t-descriptions-item label="业绩基准">
            {{ etfInfo.benchmark || '-' }}
          </t-descriptions-item>
        </t-descriptions>

        <!-- Issue Info -->
        <t-descriptions title="发行信息" :column="2" bordered style="margin-top: 16px">
          <t-descriptions-item label="发行日期">{{ etfInfo.issue_date || '-' }}</t-descriptions-item>
          <t-descriptions-item label="发行规模">
            {{ etfInfo.issue_amount ? (etfInfo.issue_amount / 100000000).toFixed(2) + '亿' : '-' }}
          </t-descriptions-item>
          <t-descriptions-item label="面值">{{ etfInfo.p_value || '-' }}</t-descriptions-item>
          <t-descriptions-item label="最小申购">{{ etfInfo.min_amount || '-' }}</t-descriptions-item>
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
