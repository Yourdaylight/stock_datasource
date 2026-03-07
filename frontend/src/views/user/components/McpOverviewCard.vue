<script setup lang="ts">
import { computed } from 'vue'
import type { McpUsageStatsResponse } from '@/api/mcpUsage'

const props = defineProps<{
  stats: McpUsageStatsResponse | null
  loading: boolean
}>()

const totalCalls = computed(() => props.stats?.total_calls || 0)
const totalRecords = computed(() => props.stats?.total_records || 0)
const avgDailyCalls = computed(() => Math.round(props.stats?.avg_daily_calls || 0))
const topToolCount = computed(() => props.stats?.top_tools?.length || 0)

const formatNumber = (n: number | undefined) => {
  if (n === undefined || n === null) return '0'
  if (n >= 1000000) return (n / 1000000).toFixed(2) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n.toLocaleString()
}
</script>

<template>
  <div class="overview-card">
    <t-loading :loading="loading" class="overview-loading">
      <div class="overview-content">
        <div class="stat-item">
          <span class="stat-label">总调用次数</span>
          <span class="stat-value primary">{{ formatNumber(totalCalls) }}</span>
          <span class="stat-unit">次 (近30天)</span>
        </div>
        <div class="stat-divider" />
        <div class="stat-item">
          <span class="stat-label">总查询记录数</span>
          <span class="stat-value warning">{{ formatNumber(totalRecords) }}</span>
          <span class="stat-unit">条</span>
        </div>
        <div class="stat-divider" />
        <div class="stat-item">
          <span class="stat-label">日均调用</span>
          <span class="stat-value success">{{ formatNumber(avgDailyCalls) }}</span>
          <span class="stat-unit">次/天</span>
        </div>
        <div class="stat-divider" />
        <div class="stat-item">
          <span class="stat-label">使用工具数</span>
          <span class="stat-value default">{{ topToolCount }}</span>
          <span class="stat-unit">个</span>
        </div>
      </div>

      <!-- Top Tools -->
      <div v-if="stats?.top_tools?.length" class="top-tools">
        <div class="top-tools-title">热门工具 Top 5</div>
        <div class="top-tools-list">
          <div v-for="(tool, idx) in stats.top_tools.slice(0, 5)" :key="tool.tool_name" class="tool-item">
            <span class="tool-rank">#{{ idx + 1 }}</span>
            <span class="tool-name">{{ tool.tool_name }}</span>
            <t-tag v-if="tool.table_name" size="small" variant="light" theme="primary">{{ tool.table_name }}</t-tag>
            <span class="tool-stats">{{ formatNumber(tool.call_count) }} 次 / {{ formatNumber(tool.total_records) }} 条</span>
          </div>
        </div>
      </div>
    </t-loading>
  </div>
</template>

<style scoped>
.overview-card {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  margin-bottom: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}

.overview-loading {
  width: 100%;
}

.overview-content {
  display: flex;
  align-items: center;
  justify-content: space-around;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stat-label {
  font-size: 13px;
  color: #86909c;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.5px;
}

.stat-value.primary { color: #0052d9; }
.stat-value.warning { color: #ed7b2f; }
.stat-value.success { color: #2ba471; }
.stat-value.default { color: #595959; }

.stat-unit {
  font-size: 12px;
  color: #a0a0b8;
}

.stat-divider {
  width: 1px;
  height: 48px;
  background: #e7e7e7;
}

.top-tools {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.top-tools-title {
  font-size: 14px;
  font-weight: 600;
  color: #262626;
  margin-bottom: 12px;
}

.top-tools-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tool-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.tool-rank {
  color: #86909c;
  font-weight: 600;
  width: 24px;
}

.tool-name {
  color: #262626;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'SF Mono', 'Menlo', monospace;
  font-size: 12px;
}

.tool-stats {
  color: #86909c;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
</style>
