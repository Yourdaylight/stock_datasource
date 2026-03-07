<script setup lang="ts">
import { computed } from 'vue'
import type { TokenBalance, UsageStatsResponse } from '@/api/token'

const props = defineProps<{
  balance: TokenBalance | null
  stats: UsageStatsResponse | null
  loading: boolean
}>()

const usedPercent = computed(() => {
  if (!props.balance) return 0
  const total = props.balance.total_quota || 1000000
  return Math.round((props.balance.used_tokens / total) * 100)
})

const progressColor = computed(() => {
  if (usedPercent.value >= 90) return '#e34d59'
  if (usedPercent.value >= 75) return '#ed7b2f'
  return '#0052d9'
})

const formatNumber = (n: number | undefined) => {
  if (n === undefined || n === null) return '0'
  if (n >= 1000000) return (n / 1000000).toFixed(2) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n.toLocaleString()
}

const avgDaily = computed(() => {
  if (!props.stats) return 0
  return Math.round(props.stats.avg_daily_tokens)
})
</script>

<template>
  <div class="overview-card">
    <t-loading :loading="loading" class="overview-loading">
      <div class="overview-content">
        <!-- Left: Ring Progress -->
        <div class="ring-section">
          <t-progress
            theme="circle"
            :percentage="usedPercent"
            :color="progressColor"
            :stroke-width="8"
            :size="140"
          >
            <div class="ring-inner">
              <span class="ring-percent">{{ usedPercent }}%</span>
              <span class="ring-label">已使用</span>
            </div>
          </t-progress>
        </div>

        <!-- Right: Stats Columns -->
        <div class="stats-section">
          <div class="stat-item">
            <span class="stat-label">总额度</span>
            <span class="stat-value primary">{{ formatNumber(balance?.total_quota) }}</span>
            <span class="stat-unit">Tokens</span>
          </div>
          <div class="stat-divider" />
          <div class="stat-item">
            <span class="stat-label">已使用</span>
            <span class="stat-value warning">{{ formatNumber(balance?.used_tokens) }}</span>
            <span class="stat-unit">Tokens</span>
          </div>
          <div class="stat-divider" />
          <div class="stat-item">
            <span class="stat-label">剩余额度</span>
            <span class="stat-value success">{{ formatNumber(balance?.remaining_tokens) }}</span>
            <span class="stat-unit">Tokens</span>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="overview-footer">
        <span class="daily-avg">日均消耗 <strong>{{ formatNumber(avgDaily) }}</strong> Tokens</span>
        <span v-if="balance && balance.remaining_tokens > 0 && avgDaily > 0" class="days-remaining">
          预计可用 <strong>{{ Math.floor(balance.remaining_tokens / avgDaily) }}</strong> 天
        </span>
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
  gap: 48px;
}

.ring-section {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ring-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.ring-percent {
  font-size: 28px;
  font-weight: 700;
  color: #262626;
}

.ring-label {
  font-size: 12px;
  color: #86909c;
}

.stats-section {
  flex: 1;
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

.stat-value.primary {
  color: #0052d9;
}

.stat-value.warning {
  color: #ed7b2f;
}

.stat-value.success {
  color: #2ba471;
}

.stat-unit {
  font-size: 12px;
  color: #a0a0b8;
}

.stat-divider {
  width: 1px;
  height: 48px;
  background: #e7e7e7;
}

.overview-footer {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #86909c;
}

.overview-footer strong {
  color: #262626;
  font-weight: 600;
}

.days-remaining {
  color: #86909c;
}
</style>
