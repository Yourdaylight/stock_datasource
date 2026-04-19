<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  score: number
  direction?: 'bullish' | 'bearish' | 'neutral'
  size?: 'small' | 'medium'
}

const props = withDefaults(defineProps<Props>(), {
  direction: 'neutral',
  size: 'small'
})

const dotColor = computed(() => {
  const map: Record<string, string> = {
    bullish: '#00a870',
    bearish: '#e34d59',
    neutral: '#8b8d98',
  }
  return map[props.direction] || '#8b8d98'
})

const scoreColor = computed(() => {
  if (props.score >= 70) return '#00a870'
  if (props.score >= 55) return '#0052d9'
  if (props.score >= 40) return '#e37318'
  return '#d54941'
})

const directionLabel = computed(() => {
  const map: Record<string, string> = {
    bullish: '多',
    bearish: '空',
    neutral: '平',
  }
  return map[props.direction] || '平'
})
</script>

<template>
  <span
    class="signal-badge"
    :class="[`signal-badge--${size}`]"
    :title="`综合评分: ${score.toFixed(1)} 方向: ${directionLabel}`"
  >
    <span class="signal-dot" :style="{ backgroundColor: dotColor }" />
    <span class="signal-score" :style="{ color: scoreColor }">
      {{ score.toFixed(0) }}
    </span>
  </span>
</template>

<style scoped>
.signal-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 6px;
  border-radius: 10px;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-stroke);
  white-space: nowrap;
  cursor: default;
}

.signal-badge--small {
  font-size: 11px;
}

.signal-badge--medium {
  font-size: 13px;
  padding: 3px 8px;
  border-radius: 12px;
}

.signal-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.signal-badge--medium .signal-dot {
  width: 8px;
  height: 8px;
}

.signal-score {
  font-weight: 600;
  line-height: 1;
}
</style>
