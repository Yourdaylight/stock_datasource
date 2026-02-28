<script setup lang="ts">
import { onMounted } from 'vue'
import { useQuantStore } from '@/stores/quant'

const store = useQuantStore()

const columns = [
  { colKey: 'index', title: '#', width: 60, cell: (_h: any, { rowIndex }: any) => rowIndex + 1 },
  { colKey: 'ts_code', title: '代码', width: 120 },
  { colKey: 'stock_name', title: '名称', width: 120 },
  { colKey: 'rps_250', title: 'RPS250', width: 100 },
  { colKey: 'rps_120', title: 'RPS120', width: 100 },
  { colKey: 'rps_60', title: 'RPS60', width: 100 },
  { colKey: 'price_chg_250', title: '250日涨幅%', width: 120 },
  { colKey: 'price_chg_120', title: '120日涨幅%', width: 120 },
  { colKey: 'price_chg_60', title: '60日涨幅%', width: 120 },
]

onMounted(() => {
  store.fetchRps(200)
})
</script>

<template>
  <div class="rps-view">
    <t-card title="RPS 排名 (相对价格强度)" :bordered="false">
      <template #actions>
        <t-button variant="outline" @click="store.fetchRps(200)">刷新</t-button>
      </template>

      <t-table
        :data="store.rpsItems"
        :columns="columns"
        row-key="ts_code"
        size="small"
        :hover="true"
        :loading="store.rpsLoading"
        max-height="600"
      >
        <template #rps_250="{ row }">
          <t-tag :theme="row.rps_250 >= 80 ? 'success' : row.rps_250 >= 50 ? 'primary' : 'default'" variant="light" size="small">
            {{ row.rps_250?.toFixed(1) }}
          </t-tag>
        </template>
        <template #rps_120="{ row }">
          <span>{{ row.rps_120?.toFixed(1) }}</span>
        </template>
        <template #rps_60="{ row }">
          <span>{{ row.rps_60?.toFixed(1) }}</span>
        </template>
        <template #price_chg_250="{ row }">
          <span :style="{ color: row.price_chg_250 > 0 ? 'var(--td-error-color)' : 'var(--td-success-color)' }">
            {{ row.price_chg_250?.toFixed(2) }}%
          </span>
        </template>
        <template #price_chg_120="{ row }">
          <span :style="{ color: row.price_chg_120 > 0 ? 'var(--td-error-color)' : 'var(--td-success-color)' }">
            {{ row.price_chg_120?.toFixed(2) }}%
          </span>
        </template>
        <template #price_chg_60="{ row }">
          <span :style="{ color: row.price_chg_60 > 0 ? 'var(--td-error-color)' : 'var(--td-success-color)' }">
            {{ row.price_chg_60?.toFixed(2) }}%
          </span>
        </template>
      </t-table>
    </t-card>
  </div>
</template>

<style scoped>
.rps-view {
  padding: 16px;
}
</style>
