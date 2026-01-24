<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { etfApi, type EtfInfo, type EtfKLineData } from '@/api/etf'
import KLineChart from '@/components/charts/KLineChart.vue'
import type { KLineData } from '@/types/common'

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
const chartLoading = ref(false)
const etfInfo = ref<EtfInfo | null>(null)
const klineData = ref<KLineData[]>([])
const activeTab = ref('info')

// Chart controls
const adjustType = ref<'qfq' | 'hfq' | 'none'>('qfq')
const adjustOptions = [
  { label: '前复权', value: 'qfq' },
  { label: '后复权', value: 'hfq' },
  { label: '不复权', value: 'none' }
]

// Date range picker
const getDefaultDateRange = (): [string, string] => {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - 90)
  const formatDate = (d: Date) => d.toISOString().split('T')[0].replace(/-/g, '')
  return [formatDate(start), formatDate(end)]
}
const dateRange = ref<[string, string]>(getDefaultDateRange())

// Fetch ETF info
const fetchEtfInfo = async (code: string) => {
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

// Fetch K-line data
const fetchKlineData = async () => {
  if (!props.etfCode) return
  
  chartLoading.value = true
  try {
    const response = await etfApi.getKLine(props.etfCode, {
      start_date: dateRange.value[0],
      end_date: dateRange.value[1],
      adjust: adjustType.value
    })
    
    // Convert to KLineData format
    klineData.value = response.data.map((d: EtfKLineData) => ({
      date: formatDateDisplay(d.trade_date),
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
      volume: d.vol || 0,
      amount: d.amount || 0
    }))
  } catch (e) {
    console.error('Failed to fetch K-line data:', e)
    klineData.value = []
  } finally {
    chartLoading.value = false
  }
}

const formatDateDisplay = (date: string) => {
  if (!date) return date
  // If already in YYYY-MM-DD format
  if (date.includes('-')) return date
  // Convert YYYYMMDD to YYYY-MM-DD
  if (date.length === 8) {
    return `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`
  }
  return date
}

// Watch for changes
watch(() => props.etfCode, async (code) => {
  if (code && props.visible) {
    await fetchEtfInfo(code)
  }
}, { immediate: true })

watch(() => props.visible, async (visible) => {
  if (visible && props.etfCode) {
    await fetchEtfInfo(props.etfCode)
    activeTab.value = 'info'
  }
})

// Lazy load chart data when tab changes
watch(() => activeTab.value, (tab) => {
  if (tab === 'chart' && klineData.value.length === 0 && !chartLoading.value) {
    fetchKlineData()
  }
})

const handleDateRangeChange = () => {
  fetchKlineData()
}

const handleAdjustChange = () => {
  fetchKlineData()
}

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
    width="900px"
    :footer="false"
    @close="handleClose"
  >
    <t-loading :loading="loading">
      <div v-if="etfInfo" class="etf-detail">
        <t-tabs v-model="activeTab">
          <!-- Basic Info Tab -->
          <t-tab-panel value="info" label="基本信息">
            <t-descriptions :column="2" bordered>
              <t-descriptions-item label="ETF代码">{{ etfInfo.ts_code }}</t-descriptions-item>
              <t-descriptions-item label="ETF简称">{{ etfInfo.csname || '-' }}</t-descriptions-item>
              <t-descriptions-item label="ETF全称">{{ etfInfo.cname || '-' }}</t-descriptions-item>
              <t-descriptions-item label="交易所">{{ getMarketLabel(etfInfo.exchange) }}</t-descriptions-item>
              <t-descriptions-item label="状态">{{ getStatusLabel(etfInfo.list_status) }}</t-descriptions-item>
              <t-descriptions-item label="基金类型">{{ etfInfo.etf_type || '-' }}</t-descriptions-item>
              <t-descriptions-item label="上市日期">{{ etfInfo.list_date || '-' }}</t-descriptions-item>
              <t-descriptions-item label="设立日期">{{ etfInfo.setup_date || '-' }}</t-descriptions-item>
              <t-descriptions-item label="管理人">{{ etfInfo.mgr_name || '-' }}</t-descriptions-item>
              <t-descriptions-item label="托管人">{{ etfInfo.custod_name || '-' }}</t-descriptions-item>
              <t-descriptions-item label="管理费率">
                {{ etfInfo.mgt_fee ? etfInfo.mgt_fee.toFixed(2) + '%' : '-' }}
              </t-descriptions-item>
              <t-descriptions-item label="指数代码">{{ etfInfo.index_code || '-' }}</t-descriptions-item>
              <t-descriptions-item label="跟踪指数" :span="2">{{ etfInfo.index_name || '-' }}</t-descriptions-item>
            </t-descriptions>
          </t-tab-panel>
          
          <!-- K-line Chart Tab -->
          <t-tab-panel value="chart" label="K线走势">
            <div class="chart-controls">
              <t-space>
                <t-date-range-picker
                  v-model="dateRange"
                  style="width: 260px"
                  enable-time-picker="false"
                  format="YYYYMMDD"
                  value-type="YYYYMMDD"
                  @change="handleDateRangeChange"
                />
                <t-select
                  v-model="adjustType"
                  :options="adjustOptions"
                  style="width: 100px"
                  @change="handleAdjustChange"
                />
              </t-space>
            </div>
            
            <div class="chart-container">
              <KLineChart
                :data="klineData"
                :loading="chartLoading"
                :height="400"
              />
            </div>
          </t-tab-panel>
        </t-tabs>

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

.chart-controls {
  margin-bottom: 16px;
}

.chart-container {
  min-height: 400px;
}

.detail-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--td-component-border);
}
</style>
