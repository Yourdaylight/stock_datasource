<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useThsIndexStore } from '@/stores/thsIndex'
import { INDEX_TYPE_LABELS } from '@/api/thsIndex'

const emit = defineEmits<{
  (e: 'select', tsCode: string, name: string): void
}>()

const thsStore = useThsIndexStore()

const sortBy = ref<'pct_change' | 'vol' | 'turnover_rate'>('pct_change')
const order = ref<'desc' | 'asc'>('desc')
const selectedType = ref('')

const sortOptions = [
  { value: 'pct_change', label: '涨跌幅' },
  { value: 'vol', label: '成交量' },
  { value: 'turnover_rate', label: '换手率' },
]

const typeOptions = [
  { value: '', label: '全部' },
  { value: 'I', label: '行业' },
  { value: 'N', label: '概念' },
  { value: 'R', label: '地域' },
  { value: 'S', label: '特色' },
]

const columns = computed(() => [
  { colKey: 'index', title: '排名', width: 60 },
  { colKey: 'name', title: '板块名称', ellipsis: true },
  { colKey: 'type', title: '类型', width: 80 },
  { colKey: 'count', title: '成分股', width: 80, align: 'right' },
  { colKey: 'close', title: '收盘', width: 90, align: 'right' },
  { colKey: 'pct_change', title: '涨跌幅', width: 90, align: 'right' },
  { colKey: 'turnover_rate', title: '换手率', width: 80, align: 'right' },
])

const tableData = computed(() => {
  return thsStore.rankingList.map((item, index) => ({
    ...item,
    index: index + 1,
  }))
})

const formatNumber = (val?: number, decimals = 2) => {
  if (val === undefined || val === null) return '-'
  return val.toFixed(decimals)
}

const getPctClass = (val?: number) => {
  if (val === undefined || val === null) return ''
  return val > 0 ? 'text-up' : val < 0 ? 'text-down' : ''
}

const fetchData = async () => {
  await thsStore.fetchRanking({
    type: selectedType.value || undefined,
    sort_by: sortBy.value,
    order: order.value,
    limit: 50
  })
}

const handleSortChange = (value: 'pct_change' | 'vol' | 'turnover_rate') => {
  sortBy.value = value
  fetchData()
}

const handleOrderToggle = () => {
  order.value = order.value === 'desc' ? 'asc' : 'desc'
  fetchData()
}

const handleTypeChange = () => {
  fetchData()
}

const handleRowClick = (context: { row: any }) => {
  emit('select', context.row.ts_code, context.row.name)
}

onMounted(() => {
  fetchData()
})
</script>

<template>
  <div class="sector-ranking">
    <div class="ranking-header">
      <t-space>
        <t-select
          v-model="selectedType"
          :options="typeOptions"
          size="small"
          style="width: 100px"
          @change="handleTypeChange"
        />
        <t-radio-group 
          v-model="sortBy" 
          variant="default-filled" 
          size="small"
          @change="handleSortChange"
        >
          <t-radio-button 
            v-for="opt in sortOptions" 
            :key="opt.value" 
            :value="opt.value"
          >
            {{ opt.label }}
          </t-radio-button>
        </t-radio-group>
        <t-button 
          size="small" 
          variant="outline"
          @click="handleOrderToggle"
        >
          <template #icon>
            <t-icon :name="order === 'desc' ? 'order-descending' : 'order-ascending'" />
          </template>
          {{ order === 'desc' ? '降序' : '升序' }}
        </t-button>
      </t-space>
      <span class="trade-date" v-if="thsStore.tradeDate">
        {{ thsStore.tradeDate }}
      </span>
    </div>

    <t-table
      :data="tableData"
      :columns="columns"
      :loading="thsStore.rankingLoading"
      row-key="ts_code"
      size="small"
      height="100%"
      hover
      stripe
      @row-click="handleRowClick"
    >
      <template #name="{ row }">
        <span class="sector-name">{{ row.name }}</span>
      </template>
      <template #type="{ row }">
        <t-tag size="small" variant="light">
          {{ INDEX_TYPE_LABELS[row.type] || row.type || '-' }}
        </t-tag>
      </template>
      <template #count="{ row }">
        {{ row.count || '-' }}
      </template>
      <template #close="{ row }">
        {{ formatNumber(row.close) }}
      </template>
      <template #pct_change="{ row }">
        <span :class="getPctClass(row.pct_change)">
          {{ row.pct_change !== undefined ? 
             (row.pct_change > 0 ? '+' : '') + formatNumber(row.pct_change) + '%' : '-' }}
        </span>
      </template>
      <template #turnover_rate="{ row }">
        {{ formatNumber(row.turnover_rate) }}%
      </template>
    </t-table>
  </div>
</template>

<style scoped>
.sector-ranking {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.ranking-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.trade-date {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.sector-name {
  cursor: pointer;
}

.sector-name:hover {
  color: var(--td-brand-color);
}

.text-up {
  color: var(--td-error-color);
}

.text-down {
  color: var(--td-success-color);
}

:deep(.t-table) {
  flex: 1;
}

:deep(.t-table__row) {
  cursor: pointer;
}
</style>
