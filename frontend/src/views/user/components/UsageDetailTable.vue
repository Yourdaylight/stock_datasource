<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { UsageHistoryResponse } from '@/api/token'

const props = defineProps<{
  history: UsageHistoryResponse | null
  loading: boolean
  page: number
  pageSize: number
}>()

const emit = defineEmits<{
  (e: 'page-change', page: number): void
}>()

const router = useRouter()

const AGENT_COLORS: Record<string, string> = {
  MarketAgent: 'primary',
  ScreenerAgent: 'success',
  ReportAgent: 'warning',
  PortfolioAgent: 'danger',
  BacktestAgent: 'default',
  ChatAgent: 'primary',
  OrchestratorAgent: 'default',
  StockDeepAgent: 'warning',
  IndexAgent: 'primary',
  EtfAgent: 'success',
  NewsAnalystAgent: 'warning'
}

const AGENT_NAMES: Record<string, string> = {
  MarketAgent: '行情分析',
  ScreenerAgent: '智能选股',
  ReportAgent: '财报解读',
  PortfolioAgent: '持仓管理',
  BacktestAgent: '策略回测',
  ChatAgent: '智能对话',
  OrchestratorAgent: '调度器',
  StockDeepAgent: 'DeepAgent',
  IndexAgent: '指数分析',
  EtfAgent: 'ETF分析',
  OverviewAgent: '市场概览',
  NewsAnalystAgent: '新闻分析',
  MemoryAgent: '记忆管理',
  DataManageAgent: '数据管理'
}

const columns = computed(() => [
  { colKey: 'created_at', title: '时间', width: 170 },
  { colKey: 'session_title', title: '会话标题', ellipsis: true },
  { colKey: 'agent_name', title: 'Agent 类型', width: 130 },
  { colKey: 'prompt_tokens', title: '输入 Token', width: 120, align: 'right' as const },
  { colKey: 'completion_tokens', title: '输出 Token', width: 120, align: 'right' as const },
  { colKey: 'total_tokens', title: '总消耗', width: 120, align: 'right' as const }
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
    minute: '2-digit'
  })
}

const goToSession = (sessionId: string) => {
  if (sessionId) {
    router.push('/chat')
  }
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

      <template #session_title="{ row }">
        <span
          class="session-link"
          :class="{ clickable: !!row.session_id }"
          @click="goToSession(row.session_id)"
        >
          {{ row.session_title || '未命名会话' }}
        </span>
      </template>

      <template #agent_name="{ row }">
        <t-tag
          :theme="AGENT_COLORS[row.agent_name] || 'default'"
          variant="light"
          size="small"
        >
          {{ AGENT_NAMES[row.agent_name] || row.agent_name || '--' }}
        </t-tag>
      </template>

      <template #prompt_tokens="{ row }">
        <span class="num-cell">{{ row.prompt_tokens?.toLocaleString() || '0' }}</span>
      </template>

      <template #completion_tokens="{ row }">
        <span class="num-cell">{{ row.completion_tokens?.toLocaleString() || '0' }}</span>
      </template>

      <template #total_tokens="{ row }">
        <span class="num-cell total">{{ row.total_tokens?.toLocaleString() || '0' }}</span>
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

.session-link {
  font-size: 13px;
  color: #262626;
}

.session-link.clickable {
  color: #0052d9;
  cursor: pointer;
}

.session-link.clickable:hover {
  text-decoration: underline;
}

.num-cell {
  font-size: 13px;
  color: #595959;
  font-variant-numeric: tabular-nums;
}

.num-cell.total {
  font-weight: 600;
  color: #262626;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
