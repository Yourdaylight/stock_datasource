<script setup lang="ts">
import type { OperationTimelineItem } from '@/api/systemLogs'

defineProps<{
  items: OperationTimelineItem[]
  loading?: boolean
}>()

const getColor = (level: string) => {
  if (level === 'ERROR') return 'danger'
  if (level === 'WARNING') return 'warning'
  return 'primary'
}
</script>

<template>
  <t-card title="最近操作时间线" :bordered="false">
    <t-loading :loading="loading">
      <t-empty v-if="!items.length" description="当前筛选下无时间线事件" />
      <t-timeline v-else>
        <t-timeline-item v-for="item in items" :key="`${item.event_type}-${item.timestamp}-${item.summary}`">
          <template #dot>
            <t-tag size="small" :theme="getColor(item.level)" variant="light">{{ item.level }}</t-tag>
          </template>
          <div class="time-line-item">
            <div class="time-line-head">
              <span class="event-title">{{ item.summary }}</span>
              <span class="event-time">{{ item.timestamp }}</span>
            </div>
            <div class="event-meta">{{ item.event_type }} · {{ item.module }}</div>
            <div v-if="item.detail" class="event-detail">{{ item.detail }}</div>
          </div>
        </t-timeline-item>
      </t-timeline>
    </t-loading>
  </t-card>
</template>

<style scoped>
.time-line-item {
  width: 100%;
}
.time-line-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.event-title {
  color: #111827;
  font-weight: 600;
}
.event-time {
  color: #6b7280;
  font-size: 12px;
  white-space: nowrap;
}
.event-meta {
  margin-top: 4px;
  color: #6b7280;
  font-size: 12px;
}
.event-detail {
  margin-top: 6px;
  color: #374151;
  font-size: 12px;
  line-height: 1.5;
}
</style>
