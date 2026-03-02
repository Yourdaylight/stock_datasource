<script setup lang="ts">
import { computed } from 'vue'
import type { LogStatsResponse } from '@/api/systemLogs'

const props = defineProps<{
  stats: LogStatsResponse | null
  loading?: boolean
}>()

const riskLevel = computed(() => {
  const error = props.stats?.error ?? 0
  const warning = props.stats?.warning ?? 0
  if (error >= 20) return { text: '高风险', theme: 'danger' as const }
  if (error > 0 || warning >= 20) return { text: '中风险', theme: 'warning' as const }
  return { text: '低风险', theme: 'success' as const }
})

const cards = computed(() => {
  const stats = props.stats
  return [
    { title: '总日志', value: stats?.total ?? 0, color: '#3B82F6' },
    { title: '错误', value: stats?.error ?? 0, color: '#EF4444' },
    { title: '告警', value: stats?.warning ?? 0, color: '#F59E0B' },
    { title: '信息', value: stats?.info ?? 0, color: '#10B981' }
  ]
})
</script>

<template>
  <t-row :gutter="16">
    <t-col v-for="item in cards" :key="item.title" :span="3">
      <t-card :bordered="false" class="overview-card">
        <div class="title">{{ item.title }}</div>
        <div class="value" :style="{ color: item.color }">{{ item.value }}</div>
      </t-card>
    </t-col>
    <t-col :span="3">
      <t-card :bordered="false" class="overview-card">
        <div class="title">风险等级</div>
        <t-tag :theme="riskLevel.theme" variant="light">{{ riskLevel.text }}</t-tag>
        <div class="tip">基于最近窗口错误/告警数量</div>
      </t-card>
    </t-col>
    <t-col :span="3">
      <t-card :bordered="false" class="overview-card">
        <div class="title">分析窗口</div>
        <div class="value text-[#7C3AED]">最近2小时</div>
        <div v-if="loading" class="tip">统计刷新中...</div>
        <div v-else class="tip">支持筛选联动</div>
      </t-card>
    </t-col>
  </t-row>
</template>

<style scoped>
.overview-card {
  min-height: 116px;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.08), rgba(124, 58, 237, 0.08));
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
}
.title {
  color: #6b7280;
  font-size: 12px;
}
.value {
  margin-top: 8px;
  font-size: 26px;
  font-weight: 700;
  line-height: 1;
}
.tip {
  margin-top: 8px;
  color: #9ca3af;
  font-size: 12px;
}
</style>
