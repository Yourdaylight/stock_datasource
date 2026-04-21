<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  current: number
  initial: number
  questionCount: number
  maxQuestions?: number
}

const props = withDefaults(defineProps<Props>(), {
  maxQuestions: 12,
})

const percentEliminated = computed(() => {
  if (!props.initial) return 0
  const eliminated = props.initial - props.current
  return Math.min(100, Math.round((eliminated / props.initial) * 100))
})

const roundColor = computed(() => {
  if (props.questionCount >= 10) return '#d54941'
  if (props.questionCount >= 6) return '#e37318'
  return '#0052d9'
})
</script>

<template>
  <div class="progress-indicator">
    <div class="pi-row">
      <span class="pi-label">候选股票</span>
      <span class="pi-count">
        <span class="pi-current">{{ current }}</span>
        <span class="pi-sep">/</span>
        <span class="pi-initial">{{ initial }}</span>
      </span>
      <span class="pi-eliminated">（已排除 {{ percentEliminated }}%）</span>
    </div>
    <t-progress
      :percentage="percentEliminated"
      :label="false"
      theme="line"
      :color="['#0052d9', '#00a870']"
      size="small"
    />
    <div class="pi-row pi-row-second">
      <span class="pi-label">已用轮次</span>
      <span class="pi-rounds" :style="{ color: roundColor }">
        {{ questionCount }} / {{ maxQuestions }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.progress-indicator {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 16px;
  background: var(--td-bg-color-container);
  border-radius: 8px;
  border: 1px solid var(--td-component-stroke);
}

.pi-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 13px;
}

.pi-row-second {
  margin-top: 4px;
}

.pi-label {
  color: var(--td-text-color-secondary);
}

.pi-count {
  font-weight: 600;
  font-size: 16px;
}

.pi-current {
  color: var(--td-brand-color);
  font-size: 20px;
  transition: all 0.3s;
}

.pi-sep, .pi-initial {
  color: var(--td-text-color-secondary);
  font-weight: 400;
}

.pi-eliminated {
  color: var(--td-success-color);
  font-size: 12px;
}

.pi-rounds {
  font-weight: 600;
  font-size: 15px;
}
</style>
