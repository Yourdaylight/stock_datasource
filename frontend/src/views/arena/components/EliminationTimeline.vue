<template>
  <div class="elimination-timeline">
    <t-timeline v-if="events.length > 0">
      <t-timeline-item
        v-for="event in events"
        :key="event.id"
        :label="formatTime(event.timestamp)"
        :dot-color="getEventColor(event.type)"
      >
        <t-card shadow class="event-card">
          <div class="event-header">
            <t-tag :theme="getEventTagTheme(event.type)" size="small">
              {{ getEventLabel(event.type) }}
            </t-tag>
            <span class="event-period">{{ event.period }}</span>
          </div>
          <div class="event-content">
            <template v-if="event.type === 'elimination'">
              <div class="strategy-info">
                <span class="strategy-name">{{ event.strategy_name }}</span>
                <span class="strategy-score">得分: {{ event.score?.toFixed(1) }}</span>
              </div>
              <div class="elimination-reason">
                <t-icon name="error-circle" />
                <span>{{ event.reason }}</span>
              </div>
            </template>
            <template v-else-if="event.type === 'supplement'">
              <div class="strategy-info">
                <span class="strategy-name">{{ event.strategy_name }}</span>
                <t-tag theme="success" size="small">新补充</t-tag>
              </div>
              <div class="supplement-info">
                <span>生成自: {{ event.generator }}</span>
              </div>
            </template>
            <template v-else-if="event.type === 'evaluation'">
              <div class="evaluation-summary">
                <span>参与策略: {{ event.total_strategies }}</span>
                <span>淘汰数量: {{ event.eliminated_count }}</span>
              </div>
            </template>
          </div>
        </t-card>
      </t-timeline-item>
    </t-timeline>
    <t-empty v-else description="暂无淘汰记录" />
  </div>
</template>

<script setup lang="ts">
interface TimelineEvent {
  id: string;
  type: 'elimination' | 'supplement' | 'evaluation';
  timestamp: string;
  period?: string;
  strategy_name?: string;
  strategy_id?: string;
  score?: number;
  reason?: string;
  generator?: string;
  total_strategies?: number;
  eliminated_count?: number;
}

defineProps<{
  events: TimelineEvent[];
}>();

function formatTime(timestamp: string) {
  const date = new Date(timestamp);
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getEventColor(type: string) {
  const colors: Record<string, string> = {
    elimination: 'red',
    supplement: 'green',
    evaluation: 'blue',
  };
  return colors[type] || 'gray';
}

function getEventTagTheme(type: string): 'default' | 'primary' | 'warning' | 'danger' | 'success' {
  const themes: Record<string, 'default' | 'primary' | 'warning' | 'danger' | 'success'> = {
    elimination: 'danger',
    supplement: 'success',
    evaluation: 'primary',
  };
  return themes[type] || 'default';
}

function getEventLabel(type: string) {
  const labels: Record<string, string> = {
    elimination: '策略淘汰',
    supplement: '策略补充',
    evaluation: '周期评估',
  };
  return labels[type] || type;
}
</script>

<style scoped>
.elimination-timeline {
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
}

.event-card {
  padding: 12px;
}

.event-card :deep(.t-card__body) {
  padding: 0;
}

.event-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.event-period {
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.event-content {
  font-size: 14px;
}

.strategy-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.strategy-name {
  font-weight: 600;
}

.strategy-score {
  color: var(--td-text-color-secondary);
}

.elimination-reason {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--td-error-color);
  font-size: 12px;
}

.supplement-info {
  font-size: 12px;
  color: var(--td-success-color);
}

.evaluation-summary {
  display: flex;
  gap: 20px;
  color: var(--td-text-color-primary);
}
</style>
