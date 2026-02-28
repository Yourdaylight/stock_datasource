<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { useQuantStore } from '@/stores/quant'

const store = useQuantStore()
const activeTab = ref('core')
const expandedRow = ref<string[]>([])

const poolColumns = [
  { colKey: 'rank', title: '排名', width: 60 },
  { colKey: 'ts_code', title: '代码', width: 120 },
  { colKey: 'stock_name', title: '名称', width: 120 },
  { colKey: 'quality_score', title: '质量', width: 80 },
  { colKey: 'growth_score', title: '成长', width: 80 },
  { colKey: 'value_score', title: '估值', width: 80 },
  { colKey: 'momentum_score', title: '动量', width: 80 },
  { colKey: 'total_score', title: '总分', width: 80 },
  { colKey: 'rps_250', title: 'RPS250', width: 80 },
]

const changeColumns = [
  { colKey: 'change_date', title: '日期', width: 120 },
  { colKey: 'change_type', title: '变动', width: 80 },
  { colKey: 'ts_code', title: '代码', width: 120 },
  { colKey: 'stock_name', title: '名称', width: 120 },
  { colKey: 'total_score', title: '总分', width: 80 },
  { colKey: 'reason', title: '原因' },
]

const factorDist = computed(() => {
  const dist = store.poolResult?.factor_distribution || {}
  return Object.entries(dist).map(([key, val]: [string, any]) => ({
    name: key.replace('_score', ''),
    ...val,
  }))
})

const handleRefreshPool = async () => {
  const result = await store.refreshPool()
  if (result) {
    MessagePlugin.success(`核心池已更新: ${result.core_stocks.length}核心 + ${result.supplement_stocks.length}补充`)
  }
}

onMounted(async () => {
  await Promise.all([
    store.fetchPool(),
    store.fetchPoolChanges(),
  ])
})
</script>

<template>
  <div class="pool-view">
    <t-card title="核心目标池" :bordered="false">
      <template #actions>
        <t-space>
          <t-button theme="primary" :loading="store.poolLoading" @click="handleRefreshPool">刷新核心池</t-button>
        </t-space>
      </template>

      <!-- Factor Distribution -->
      <div v-if="factorDist.length" class="factor-dist">
        <t-card v-for="f in factorDist" :key="f.name" :bordered="false" class="factor-card">
          <div class="factor-name">{{ f.name }}</div>
          <div class="factor-stats">
            <span>均值: {{ f.mean }}</span>
            <span>中位: {{ f.median }}</span>
            <span>范围: {{ f.min }}-{{ f.max }}</span>
          </div>
        </t-card>
      </div>

      <!-- Pool Changes -->
      <t-card v-if="store.poolChanges.length" title="入池/出池变动" :bordered="false" style="margin: 16px 0;">
        <t-table
          :data="store.poolChanges.slice(0, 20)"
          :columns="changeColumns"
          row-key="ts_code"
          size="small"
          :hover="true"
        >
          <template #change_type="{ row }">
            <t-tag :theme="row.change_type === 'new_entry' ? 'success' : row.change_type === 'exit' ? 'danger' : 'warning'" variant="light" size="small">
              {{ row.change_type === 'new_entry' ? '新入' : row.change_type === 'exit' ? '调出' : '排名变动' }}
            </t-tag>
          </template>
        </t-table>
      </t-card>

      <!-- Pool Tables -->
      <t-tabs v-model="activeTab">
        <t-tab-panel value="core" :label="`核心池 (${store.poolResult?.core_stocks?.length || 0})`">
          <t-table
            :data="store.poolResult?.core_stocks || []"
            :columns="poolColumns"
            row-key="ts_code"
            size="small"
            :hover="true"
            :loading="store.poolLoading"
            max-height="500"
          >
            <template #total_score="{ row }">
              <span style="font-weight: 700; color: var(--td-brand-color);">{{ row.total_score.toFixed(1) }}</span>
            </template>
          </t-table>
        </t-tab-panel>
        <t-tab-panel value="supplement" :label="`补充池 (${store.poolResult?.supplement_stocks?.length || 0})`">
          <t-table
            :data="store.poolResult?.supplement_stocks || []"
            :columns="poolColumns"
            row-key="ts_code"
            size="small"
            :hover="true"
            :loading="store.poolLoading"
            max-height="500"
          >
            <template #total_score="{ row }">
              <span style="font-weight: 700;">{{ row.total_score.toFixed(1) }}</span>
            </template>
          </t-table>
        </t-tab-panel>
      </t-tabs>
    </t-card>
  </div>
</template>

<style scoped>
.pool-view {
  padding: 16px;
}
.factor-dist {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.factor-card {
  flex: 1;
  min-width: 150px;
  text-align: center;
  background: var(--td-bg-color-secondarycontainer);
}
.factor-name {
  font-weight: 600;
  font-size: 14px;
  text-transform: capitalize;
}
.factor-stats {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 8px;
}
</style>
