<script setup lang="ts">
import type { ErrorClusterItem } from '@/api/systemLogs'

defineProps<{
  clusters: ErrorClusterItem[]
  loading?: boolean
}>()

const emit = defineEmits<{
  select: [signature: string]
}>()

const handlePick = (signature: string) => {
  emit('select', signature)
}
</script>

<template>
  <t-card title="错误聚类" :bordered="false" class="h-full">
    <t-loading :loading="loading">
      <t-empty v-if="!clusters.length" description="最近窗口无错误聚类" />
      <div v-else class="cluster-list">
        <div v-for="item in clusters" :key="`${item.signature}-${item.module}`" class="cluster-item">
          <div class="cluster-head">
            <t-tag :theme="item.level === 'ERROR' ? 'danger' : 'warning'" variant="light">{{ item.level }}</t-tag>
            <span class="cluster-count">x{{ item.count }}</span>
            <span class="cluster-time">{{ item.latest_time }}</span>
          </div>
          <div class="cluster-signature">{{ item.signature }}</div>
          <div class="cluster-meta">模块：{{ item.module }}</div>
          <div class="cluster-msg">{{ item.sample_message }}</div>
          <t-button variant="text" theme="primary" size="small" @click="handlePick(item.signature)">按签名过滤日志</t-button>
        </div>
      </div>
    </t-loading>
  </t-card>
</template>

<style scoped>
.cluster-list {
  max-height: 360px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.cluster-item {
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  padding: 10px 12px;
  background: rgba(15, 23, 42, 0.02);
}
.cluster-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.cluster-count {
  color: #ef4444;
  font-weight: 700;
}
.cluster-time {
  margin-left: auto;
  color: #6b7280;
  font-size: 12px;
}
.cluster-signature {
  margin-top: 6px;
  font-weight: 600;
  color: #111827;
}
.cluster-meta {
  margin-top: 2px;
  color: #6b7280;
  font-size: 12px;
}
.cluster-msg {
  margin-top: 6px;
  color: #4b5563;
  font-size: 12px;
  line-height: 1.4;
}
</style>
