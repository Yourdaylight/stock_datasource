<script setup lang="ts">
import { computed } from 'vue'
import { TrendingUpIcon, ChartLineIcon, FilterIcon } from 'tdesign-icons-vue-next'
import type { NewsSentiment } from '@/types/news'

interface Props {
  sentiment: NewsSentiment
  showScore?: boolean
  showIcon?: boolean
  size?: 'small' | 'medium' | 'large'
}

const props = withDefaults(defineProps<Props>(), {
  showScore: false,
  showIcon: true,
  size: 'small'
})

// 计算属性
const sentimentConfig = computed(() => {
  const { sentiment, score, impact_level } = props.sentiment
  
  const configs = {
    positive: {
      label: '利好',
      theme: 'success' as const,
      icon: TrendingUpIcon,
      color: 'var(--td-success-color)',
      bgColor: 'var(--td-success-color-1)'
    },
    negative: {
      label: '利空',
      theme: 'danger' as const,
      icon: ChartLineIcon,
      color: 'var(--td-error-color)',
      bgColor: 'var(--td-error-color-1)'
    },
    neutral: {
      label: '中性',
      theme: 'default' as const,
      icon: FilterIcon,
      color: 'var(--td-text-color-secondary)',
      bgColor: 'var(--td-bg-color-component)'
    }
  }
  
  return configs[sentiment] || configs.neutral
})

const impactLevelText = computed(() => {
  const levelMap = {
    high: '高',
    medium: '中',
    low: '低'
  }
  return levelMap[props.sentiment.impact_level] || ''
})

const scoreText = computed(() => {
  const score = props.sentiment.score
  if (score === undefined || score === null) return ''
  
  // 将分数转换为百分比显示
  const percentage = Math.abs(score * 100).toFixed(0)
  return `${percentage}%`
})

const scoreColor = computed(() => {
  const score = props.sentiment.score
  if (score === undefined || score === null) return 'var(--td-text-color-secondary)'
  
  if (score > 0.3) return 'var(--td-success-color)'
  if (score < -0.3) return 'var(--td-error-color)'
  return 'var(--td-text-color-secondary)'
})
</script>

<template>
  <div class="sentiment-tag" :class="[`sentiment-${sentiment.sentiment}`, `size-${size}`]">
    <t-tag 
      :theme="sentimentConfig.theme"
      :size="size"
      variant="light"
      class="sentiment-main-tag"
    >
      <template #icon v-if="showIcon">
        <component :is="sentimentConfig.icon" />
      </template>
      {{ sentimentConfig.label }}
    </t-tag>
    
    <!-- 情绪分数 -->
    <span 
      v-if="showScore && scoreText"
      class="sentiment-score"
      :style="{ color: scoreColor }"
    >
      {{ scoreText }}
    </span>
    
    <!-- 影响程度 -->
    <t-tag
      v-if="impactLevelText"
      size="small"
      variant="outline"
      class="impact-level"
      :class="`impact-${sentiment.impact_level}`"
    >
      {{ impactLevelText }}
    </t-tag>
  </div>
</template>

<style scoped>
.sentiment-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.sentiment-tag.size-small {
  gap: 3px;
}

.sentiment-tag.size-medium {
  gap: 4px;
}

.sentiment-tag.size-large {
  gap: 6px;
}

.sentiment-main-tag {
  flex-shrink: 0;
}

.sentiment-score {
  font-size: 11px;
  font-weight: 500;
  flex-shrink: 0;
}

.size-medium .sentiment-score {
  font-size: 12px;
}

.size-large .sentiment-score {
  font-size: 13px;
}

.impact-level {
  flex-shrink: 0;
  font-size: 10px;
  min-width: 20px;
  text-align: center;
}

.impact-level.impact-high {
  border-color: var(--td-error-color);
  color: var(--td-error-color);
}

.impact-level.impact-medium {
  border-color: var(--td-warning-color);
  color: var(--td-warning-color);
}

.impact-level.impact-low {
  border-color: var(--td-text-color-placeholder);
  color: var(--td-text-color-placeholder);
}

/* 情绪类型特定样式 */
.sentiment-positive .sentiment-main-tag {
  background: var(--td-success-color-1);
  border-color: var(--td-success-color-3);
  color: var(--td-success-color);
}

.sentiment-negative .sentiment-main-tag {
  background: var(--td-error-color-1);
  border-color: var(--td-error-color-3);
  color: var(--td-error-color);
}

.sentiment-neutral .sentiment-main-tag {
  background: var(--td-bg-color-component);
  border-color: var(--td-component-stroke);
  color: var(--td-text-color-secondary);
}

/* 悬停效果 */
.sentiment-tag:hover .sentiment-main-tag {
  transform: scale(1.05);
  transition: transform 0.2s ease;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .sentiment-tag {
    gap: 2px;
  }
  
  .sentiment-score {
    font-size: 10px;
  }
  
  .impact-level {
    font-size: 9px;
    min-width: 18px;
  }
}
</style>