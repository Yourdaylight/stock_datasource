<script setup lang="ts">
import { computed } from 'vue'
import { FileSearchIcon, FileIcon, TimeIcon, SearchIcon } from 'tdesign-icons-vue-next'
import type { NewsItem } from '@/types/news'
import SentimentTag from './SentimentTag.vue'

interface Props {
  newsItem: NewsItem
}

interface Emits {
  (e: 'click'): void
  (e: 'share'): void
  (e: 'favorite'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 计算属性
const formattedTime = computed(() => {
  const date = new Date(props.newsItem.publish_time)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffHours / 24)
  
  if (diffHours < 1) {
    const diffMinutes = Math.floor(diffMs / (1000 * 60))
    return diffMinutes < 1 ? '刚刚' : `${diffMinutes}分钟前`
  } else if (diffHours < 24) {
    return `${diffHours}小时前`
  } else if (diffDays < 7) {
    return `${diffDays}天前`
  } else {
    return date.toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric'
    })
  }
})

const truncatedContent = computed(() => {
  const content = props.newsItem.content
  if (content.length <= 120) {
    return content
  }
  return content.substring(0, 120) + '...'
})

const categoryLabel = computed(() => {
  const categoryMap: Record<string, string> = {
    'announcement': '公告',
    'news': '快讯',
    'analysis': '分析',
    'research': '研报'
  }
  return categoryMap[props.newsItem.category] || props.newsItem.category
})

const categoryTheme = computed(() => {
  const themeMap: Record<string, string> = {
    'announcement': 'warning',
    'news': 'primary',
    'analysis': 'success',
    'research': 'default'
  }
  return themeMap[props.newsItem.category] || 'default'
})

// 事件处理
const handleClick = () => {
  emit('click')
}

const handleShare = (event: Event) => {
  event.stopPropagation()
  emit('share')
}

const handleFavorite = (event: Event) => {
  event.stopPropagation()
  emit('favorite')
}
</script>

<template>
  <t-card 
    class="news-item-card"
    hover
    @click="handleClick"
  >
    <div class="news-card-content">
      <!-- 新闻头部 -->
      <div class="news-header">
        <div class="news-title-row">
          <!-- 情绪标签 -->
          <SentimentTag 
            v-if="newsItem.sentiment"
            :sentiment="newsItem.sentiment"
            class="sentiment-tag"
          />
          
          <!-- 新闻标题 -->
          <h3 class="news-title">
            {{ newsItem.title }}
          </h3>
        </div>
        
        <!-- 新闻元信息 -->
        <div class="news-meta">
          <t-tag 
            size="small" 
            :theme="categoryTheme"
            variant="light"
          >
            {{ categoryLabel }}
          </t-tag>
          
          <t-tag size="small" variant="outline">
            {{ newsItem.source }}
          </t-tag>
          
          <span class="news-time">
            <TimeIcon size="12px" />
            {{ formattedTime }}
          </span>
        </div>
      </div>
      
      <!-- 新闻内容预览 -->
      <div class="news-content">
        <p>{{ truncatedContent }}</p>
      </div>
      
      <!-- 新闻底部 -->
      <div class="news-footer">
        <!-- 相关股票标签 -->
        <div class="stock-tags" v-if="newsItem.stock_codes.length > 0">
          <t-tag 
            v-for="code in newsItem.stock_codes.slice(0, 3)" 
            :key="code"
            size="small"
            variant="outline"
            theme="primary"
            class="stock-tag"
          >
            {{ code }}
          </t-tag>
          <t-tag 
            v-if="newsItem.stock_codes.length > 3"
            size="small"
            variant="outline"
            class="more-stocks"
          >
            +{{ newsItem.stock_codes.length - 3 }}
          </t-tag>
        </div>
        
        <!-- 操作按钮 -->
        <div class="news-actions">
          <t-button 
            size="small" 
            variant="text"
            @click="handleShare"
            class="action-btn"
          >
            <template #icon>
              <FileSearchIcon />
            </template>
            分享
          </t-button>
          
          <t-button 
            size="small" 
            variant="text"
            @click="handleFavorite"
            class="action-btn"
          >
            <template #icon>
              <FileIcon />
            </template>
            收藏
          </t-button>
        </div>
      </div>
    </div>
  </t-card>
</template>

<style scoped>
.news-item-card {
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid var(--td-component-stroke);
}

.news-item-card:hover {
  box-shadow: var(--td-shadow-2);
  transform: translateY(-1px);
}

.news-item-card :deep(.t-card__body) {
  padding: 16px;
}

.news-card-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.news-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.news-title-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.sentiment-tag {
  flex-shrink: 0;
  margin-top: 2px;
}

.news-title {
  flex: 1;
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  line-height: 1.4;
  color: var(--td-text-color-primary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.news-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.news-time {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}

.news-content {
  flex: 1;
}

.news-content p {
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
  color: var(--td-text-color-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.news-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.stock-tags {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  flex: 1;
}

.stock-tag {
  cursor: pointer;
}

.stock-tag:hover {
  background: var(--td-brand-color-light);
  border-color: var(--td-brand-color);
}

.more-stocks {
  color: var(--td-text-color-placeholder);
}

.news-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.action-btn {
  color: var(--td-text-color-secondary);
  transition: color 0.2s ease;
}

.action-btn:hover {
  color: var(--td-brand-color);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .news-item-card :deep(.t-card__body) {
    padding: 12px;
  }
  
  .news-card-content {
    gap: 8px;
  }
  
  .news-title {
    font-size: 15px;
  }
  
  .news-content p {
    font-size: 13px;
    -webkit-line-clamp: 2;
  }
  
  .news-footer {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .news-actions {
    width: 100%;
    justify-content: flex-end;
  }
}

/* 新闻卡片状态样式 */
.news-item-card.read {
  opacity: 0.8;
}

.news-item-card.read .news-title {
  color: var(--td-text-color-secondary);
}

/* 热点新闻样式 */
.news-item-card.hot {
  border-left: 3px solid var(--td-error-color);
}

.news-item-card.hot .news-title::before {
  content: '🔥';
  margin-right: 4px;
}
</style>