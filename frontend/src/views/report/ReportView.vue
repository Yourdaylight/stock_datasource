<script setup lang="ts">
import { ref } from 'vue'
import { useReportStore } from '@/stores/report'
import StockSearch from '@/components/common/StockSearch.vue'

const reportStore = useReportStore()
const selectedStock = ref('')
const activeTab = ref('income')

const handleStockSelect = (code: string) => {
  selectedStock.value = code
  reportStore.fetchFinancial(code, activeTab.value as any)
}

const handleTabChange = (tab: string) => {
  activeTab.value = tab
  if (selectedStock.value) {
    reportStore.fetchFinancial(selectedStock.value, tab as any)
  }
}

const incomeColumns = [
  { colKey: 'period', title: '报告期', width: 120 },
  { colKey: 'revenue', title: '营业收入', width: 150 },
  { colKey: 'net_profit', title: '净利润', width: 150 },
  { colKey: 'gross_margin', title: '毛利率', width: 100 },
  { colKey: 'roe', title: 'ROE', width: 100 }
]

const formatNumber = (num?: number) => {
  if (!num) return '-'
  if (num >= 100000000) return (num / 100000000).toFixed(2) + '亿'
  if (num >= 10000) return (num / 10000).toFixed(2) + '万'
  return num.toFixed(2)
}
</script>

<template>
  <div class="report-view">
    <t-card title="财报研读">
      <template #actions>
        <StockSearch @select="handleStockSelect" />
      </template>

      <div v-if="!selectedStock" class="empty-state">
        <t-icon name="file-excel" size="64px" style="color: #ddd" />
        <p>请选择股票查看财报</p>
      </div>

      <div v-else>
        <t-tabs v-model="activeTab" @change="handleTabChange">
          <t-tab-panel value="income" label="利润表">
            <t-table
              :data="reportStore.financialData"
              :columns="incomeColumns"
              :loading="reportStore.loading"
              row-key="period"
            >
              <template #revenue="{ row }">
                {{ formatNumber(row.revenue) }}
              </template>
              <template #net_profit="{ row }">
                {{ formatNumber(row.net_profit) }}
              </template>
              <template #gross_margin="{ row }">
                {{ row.gross_margin ? (row.gross_margin * 100).toFixed(2) + '%' : '-' }}
              </template>
              <template #roe="{ row }">
                {{ row.roe ? (row.roe * 100).toFixed(2) + '%' : '-' }}
              </template>
            </t-table>
          </t-tab-panel>
          
          <t-tab-panel value="balance" label="资产负债表">
            <t-table
              :data="reportStore.financialData"
              :loading="reportStore.loading"
              row-key="period"
            />
          </t-tab-panel>
          
          <t-tab-panel value="cashflow" label="现金流量表">
            <t-table
              :data="reportStore.financialData"
              :loading="reportStore.loading"
              row-key="period"
            />
          </t-tab-panel>
        </t-tabs>

        <t-divider />

        <div class="analysis-section">
          <t-button theme="primary" @click="reportStore.analyzeReport(selectedStock)">
            <template #icon><t-icon name="root-list" /></template>
            AI 财报解读
          </t-button>
          
          <div v-if="reportStore.analysis" class="analysis-result">
            <t-alert theme="info" :message="reportStore.analysis" />
          </div>
        </div>
      </div>
    </t-card>
  </div>
</template>

<style scoped>
.report-view {
  height: 100%;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 400px;
  color: #999;
}

.analysis-section {
  margin-top: 16px;
}

.analysis-result {
  margin-top: 16px;
}
</style>
