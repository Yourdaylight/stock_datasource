<script setup lang="ts">
import { computed } from 'vue'
import { RefreshIcon, ErrorCircleFilledIcon, TimeIcon, InfoCircleFilledIcon } from 'tdesign-icons-vue-next'

interface Props {
  type?: 'network' | 'timeout' | 'server' | 'unknown'
  message?: string
  showRetry?: boolean
  retrying?: boolean
}

interface Emits {
  (e: 'retry'): void
}

const props = withDefaults(defineProps<Props>(), {
  type: 'unknown',
  showRetry: true,
  retrying: false
})

const emit = defineEmits<Emits>()

const errorConfig = computed(() => {
  const configs = {
    network: {
      icon: ErrorCircleFilledIcon,
      title: '网络连接失败',
      description: '请检查网络连接后重试',
      color: 'var(--td-error-color)'
    },
    timeout: {
      icon: TimeIcon,
      title: '请求超时',
      description: '服务器响应时间过长，请稍后重试',
      color: 'var(--td-warning-color)'
    },
    server: {
      icon: ErrorCircleFilledIcon,
      title: '服务器错误',
      description: '服务器暂时无法处理请求，请稍后重试',
      color: 'var(--td-error-color)'
    },
    unknown: {
      icon: InfoCircleFilledIcon,
      title: '加载失败',
      description: '发生未知错误，请重试',
      color: 'var(--td-text-color-secondary)'
    }
  }
  
  return configs[props.type] || configs.unknown
})

const displayMessage = computed(() => {
  return props.message || errorConfig.value.description
})

const handleRetry = () => {
  if (!props.retrying) {
    emit('retry')
  }
}
</script>

<template>
  <div class="news-error-state">
    <div class="error-content">
      <div class="error-icon" :style="{ color: errorConfig.color }">
        <component :is="errorConfig.icon" size="48px" />
      </div>
      
      <div class="error-text">
        <h3 class="error-title">{{ errorConfig.title }}</h3>
        <p class="error-description">{{ displayMessage }}</p>
      </div>
      
      <div class="error-actions" v-if="showRetry">
        <t-button 
          theme="primary"
          variant="outline"
          :loading="retrying"
          @click="handleRetry"
        >
          <template #icon>
            <RefreshIcon />
          </template>
          {{ retrying ? '重试中...' : '重试' }}
        </t-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.news-error-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  padding: 40px 20px;
  background: #ffffff;
  border: 1px solid var(--td-component-stroke);
  border-radius: 8px;
}

.error-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  max-width: 400px;
}

.error-icon {
  margin-bottom: 16px;
  opacity: 0.8;
}

.error-text {
  margin-bottom: 24px;
}

.error-title {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}

.error-description {
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
  color: var(--td-text-color-secondary);
}

.error-actions {
  display: flex;
  gap: 12px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .news-error-state {
    min-height: 200px;
    padding: 20px 16px;
  }
  
  .error-icon {
    margin-bottom: 12px;
  }
  
  .error-icon :deep(svg) {
    width: 40px !important;
    height: 40px !important;
  }
  
  .error-title {
    font-size: 16px;
  }
  
  .error-description {
    font-size: 13px;
  }
  
  .error-text {
    margin-bottom: 20px;
  }
}

/* 动画效果 */
.news-error-state {
  animation: fadeIn 0.3s ease-in-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>