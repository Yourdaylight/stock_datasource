<script setup lang="ts">
import { computed } from 'vue'
import type { McpUsageHistoryResponse } from '@/api/mcpUsage'

const props = defineProps<{
  history: McpUsageHistoryResponse | null
  loading: boolean
  page: number
  pageSize: number
}>()

const emit = defineEmits<{
  (e: 'page-change', page: number): void
}>()

const columns = computed(() => [
  { colKey: 'created_at', title: '时间', width: 170 },
  { colKey: 'tool_name', title: '工具名称', ellipsis: true },
  { colKey: 'table_name', title: '查询表', width: 150 },
  { colKey: 'record_count', title: '记录条数', width: 110, align: 'right' as const },
  { colKey: 'duration_ms', title: '耗时', width: 100, align: 'right' as const },
  { colKey: 'is_error', title: '状态', width: 80 }
])

const records = computed(() => props.history?.records || [])
const total = computed(() => props.history?.total || 0)

const formatTime = (dt: string) => {
  if (!dt) return '--'
  const d = new Date(dt)
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const formatDuration = (ms: number) => {
  if (!ms) return '--'
  if (ms < 1000) return ms + 'ms'
  return (ms / 1000).toFixed(1) + 's'
}
</script>

<template>
  <div class="usage-table">
    <t-table
      :data="records"
      :columns="columns"
      :loading="loading"
      row-key="id"
      :hover="true"
      :stripe="true"
      size="small"
      :bordered="false"
    >
      <template #created_at="{ row }">
        <span class="time-cell">{{ formatTime(row.created_at) }}</span>
      </template>

      <template #tool_name="{ row }">
        <span class="tool-name-cell">{{ row.tool_name || '--' }}</span>
      </template>

      <template #table_name="{ row }">
        <t-tag v-if="row.table_name" size="small" variant="light" theme="primary">
          {{ row.table_name }}
        </t-tag>
        <span v-else class="dim">--</span>
      </template>

      <template #record_count="{ row }">
        <span class="num-cell">{{ row.record_count?.toLocaleString() || '0' }}</span>
      </template>

      <template #duration_ms="{ row }">
        <span class="num-cell">{{ formatDuration(row.duration_ms) }}</span>
      </template>

      <template #is_error="{ row }">
        <t-tag v-if="row.is_error" size="small" theme="danger" variant="light">失败</t-tag>
        <t-tag v-else size="small" theme="success" variant="light">成功</t-tag>
      </template>
    </t-table>

    <div v-if="total > pageSize" class="pagination-wrapper">
      <t-pagination
        :total="total"
        :current="page"
        :page-size="pageSize"
        :show-jumper="true"
        :show-page-size="false"
        @current-change="emit('page-change', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.usage-table {
  width: 100%;
}

.time-cell {
  font-size: 13px;
  color: #595959;
  font-variant-numeric: tabular-nums;
}

.tool-name-cell {
  font-size: 12px;
  color: #262626;
  font-family: 'SF Mono', 'Menlo', monospace;
}

.num-cell {
  font-size: 13px;
  color: #595959;
  font-variant-numeric: tabular-nums;
}

.dim {
  color: #c0c4cc;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
