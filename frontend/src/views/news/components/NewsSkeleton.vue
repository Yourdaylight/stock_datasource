<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  loading?: boolean
  rows?: number
  showAvatar?: boolean
  showTitle?: boolean
  showContent?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: true,
  rows: 3,
  showAvatar: false,
  showTitle: true,
  showContent: true
})

const skeletonRows = computed(() => {
  const rows = []
  for (let i = 0; i < props.rows; i++) {
    rows.push({
      width: i === 0 ? '100%' : i === props.rows - 1 ? '60%' : '80%'
    })
  }
  return rows
})
</script>

<template>
  <div class="news-skeleton" v-if="loading">
    <div class="skeleton-item" v-for="i in 3" :key="i">
      <div class="skeleton-header">
        <div class="skeleton-avatar" v-if="showAvatar"></div>
        <div class="skeleton-meta">
          <div class="skeleton-title" v-if="showTitle"></div>
          <div class="skeleton-subtitle"></div>
        </div>
      </div>
      
      <div class="skeleton-content" v-if="showContent">
        <div 
          v-for="(row, index) in skeletonRows" 
          :key="index"
          class="skeleton-line"
          :style="{ width: row.width }"
        ></div>
      </div>
      
      <div class="skeleton-footer">
        <div class="skeleton-tag"></div>
        <div class="skeleton-tag"></div>
        <div class="skeleton-time"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.news-skeleton {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}

.skeleton-item {
  background: #ffffff;
  border: 1px solid var(--td-component-stroke);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skeleton-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.skeleton-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
}

.skeleton-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skeleton-title {
  height: 20px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: 4px;
  width: 70%;
}

.skeleton-subtitle {
  height: 14px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: 4px;
  width: 40%;
}

.skeleton-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skeleton-line {
  height: 16px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: 4px;
}

.skeleton-footer {
  display: flex;
  align-items: center;
  gap: 8px;
}

.skeleton-tag {
  width: 60px;
  height: 20px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: 10px;
}

.skeleton-time {
  width: 80px;
  height: 14px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: 4px;
  margin-left: auto;
}

@keyframes skeleton-loading {
  0% {
    background-position: -200% 0;
  }
  100% {
    background-position: 200% 0;
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .news-skeleton {
    padding: 8px;
    gap: 12px;
  }
  
  .skeleton-item {
    padding: 12px;
    gap: 8px;
  }
  
  .skeleton-header {
    gap: 8px;
  }
  
  .skeleton-avatar {
    width: 32px;
    height: 32px;
  }
}
</style>