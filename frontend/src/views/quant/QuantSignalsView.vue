<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useQuantStore } from '@/stores/quant'

const store = useQuantStore()

const signalColumns = [
  { colKey: 'signal_date', title: '日期', width: 120 },
  { colKey: 'ts_code', title: '代码', width: 120 },
  { colKey: 'stock_name', title: '名称', width: 120 },
  { colKey: 'signal_type', title: '信号', width: 80 },
  { colKey: 'signal_source', title: '来源', width: 120 },
  { colKey: 'price', title: '价格', width: 80 },
  { colKey: 'confidence', title: '置信度', width: 80 },
  { colKey: 'reason', title: '触发原因' },
  { colKey: 'context', title: '详情', width: 80 },
]

const expandedRows = computed(() => {
  return (store.signals || []).filter(s => s.signal_context && Object.keys(s.signal_context).length > 0)
})

onMounted(async () => {
  await Promise.all([
    store.fetchSignals(),
    store.fetchMarketRisk(),
  ])
})
</script>

<template>
  <div class="signals-view">
    <!-- Market Risk Panel -->
    <t-card v-if="store.marketRisk" :bordered="false" style="margin-bottom: 16px">
      <t-row :gutter="16">
        <t-col :span="8">
          <div class="risk-header">
            <span>市场风控状态</span>
            <t-tag
              :theme="store.marketRisk.risk_level === 'normal' ? 'success' : store.marketRisk.risk_level === 'warning' ? 'warning' : 'danger'"
              size="medium"
            >
              {{ store.marketRisk.risk_level === 'normal' ? '正常' : store.marketRisk.risk_level === 'warning' ? '警告' : '危险' }}
            </t-tag>
          </div>
          <div class="risk-desc">{{ store.marketRisk.description }}</div>
          <div class="risk-detail">
            <span>沪深300: {{ store.marketRisk.index_close?.toFixed(0) }}</span>
            <span>MA250: {{ store.marketRisk.index_ma250?.toFixed(0) }}</span>
            <span>建议仓位: {{ (store.marketRisk.suggested_position * 100).toFixed(0) }}%</span>
          </div>
        </t-col>
      </t-row>
    </t-card>

    <!-- Signals -->
    <t-card title="交易信号" :bordered="false">
      <template #actions>
        <t-button variant="outline" @click="store.fetchSignals()">刷新</t-button>
      </template>

      <t-empty v-if="!store.signals?.length && !store.signalsLoading" description="暂无交易信号" />

      <t-table
        v-else
        :data="store.signals || []"
        :columns="signalColumns"
        row-key="ts_code"
        size="small"
        :hover="true"
        :loading="store.signalsLoading"
      >
        <template #signal_type="{ row }">
          <t-tag
            :theme="row.signal_type === 'buy' || row.signal_type === 'add' ? 'success' : 'danger'"
            size="small"
          >
            {{ row.signal_type === 'buy' ? '买入' : row.signal_type === 'sell' ? '卖出' : row.signal_type === 'add' ? '加仓' : '减仓' }}
          </t-tag>
        </template>
        <template #signal_source="{ row }">
          <t-tag variant="outline" size="small">
            {{ row.signal_source === 'ma_crossover' ? '均线突破' : row.signal_source === 'stop_loss' ? '止损' : row.signal_source === 'stop_profit' ? '止盈' : row.signal_source }}
          </t-tag>
        </template>
        <template #confidence="{ row }">
          <t-tag
            :theme="row.confidence >= 0.7 ? 'success' : row.confidence >= 0.5 ? 'warning' : 'default'"
            variant="light" size="small"
          >
            {{ (row.confidence * 100).toFixed(0) }}%
          </t-tag>
        </template>
        <template #context="{ row }">
          <t-popup v-if="row.signal_context && Object.keys(row.signal_context).length" trigger="hover" placement="left">
            <t-link theme="primary" size="small">查看</t-link>
            <template #content>
              <div style="max-width: 300px; padding: 8px;">
                <div v-for="(val, key) in row.signal_context" :key="key" style="margin-bottom: 4px; font-size: 12px;">
                  <span style="color: var(--td-text-color-secondary);">{{ key }}:</span>
                  <span style="margin-left: 4px;">{{ val }}</span>
                </div>
              </div>
            </template>
          </t-popup>
        </template>
      </t-table>
    </t-card>
  </div>
</template>

<style scoped>
.signals-view {
  padding: 16px;
}
.risk-header {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 8px;
}
.risk-desc {
  color: var(--td-text-color-secondary);
  margin-bottom: 8px;
}
.risk-detail {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--td-text-color-placeholder);
}
</style>
