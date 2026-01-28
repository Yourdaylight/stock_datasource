<script setup lang="ts">
import { computed, ref } from 'vue'
import { FileSearchIcon, FileIcon, QueueIcon, TimeIcon, SearchIcon, ControlPlatformIcon } from 'tdesign-icons-vue-next'
import type { NewsItem } from '@/types/news'
import SentimentTag from './SentimentTag.vue'

interface Props {
  visible: boolean
  newsItem: NewsItem | null
}

interface Emits {
  (e: 'update:visible', visible: boolean): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 本地状态
const copying = ref(false)
const favorited = ref(false)

// 计算属性
const dialogVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value)
})

const formattedTime = computed(() => {
  if (!props.newsItem) return ''
  
  const date = new Date(props.newsItem.publish_time)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
})

const categoryLabel = computed(() => {
  if (!props.newsItem) return ''
  
  const categoryMap: Record<string, string> = {
    'announcement': '公司公告',
    'news': '市场快讯',
    'analysis': '深度分析',
    'research': '研究报告'
  }
  return categoryMap[props.newsItem.category] || props.newsItem.category
})

const categoryTheme = computed(() => {
  if (!props.newsItem) return 'default'
  
  const themeMap: Record<string, string> = {
    'announcement': 'warning',
    'news': 'primary',
    'analysis': 'success',
    'research': 'default'
  }
  return themeMap[props.newsItem.category] || 'default'
})

const sentimentAnalysis = computed(() => {
  if (!props.newsItem?.sentiment) return null
  
  const { sentiment, score, reasoning, impact_level } = props.newsItem.sentiment
  
  return {
    sentiment,
    score,
    reasoning,
    impact_level,
    scoreText: score ? `${Math.abs(score * 100).toFixed(0)}%` : '',
    impactText: {
      high: '高影响',
      medium: '中等影响',
      low: '低影响'
    }[impact_level] || ''
  }
})

// 事件处理
const handleClose = () => {
  dialogVisible.value = false
}

const handleShare = async () => {
  if (!props.newsItem) return
  
  try {
    if (navigator.share) {
      await navigator.share({
        title: props.newsItem.title,
        text: props.newsItem.content.substring(0, 100) + '...',
        url: props.newsItem.url || window.location.href
      })
    } else {
      // 降级到复制链接
      await handleCopyLink()
    }
  } catch (error) {
    console.error('分享失败:', error)
  }
}

const handleFavorite = () => {
  favorited.value = !favorited.value
  // TODO: 调用API保存收藏状态
}

const handleCopyLink = async () => {
  if (!props.newsItem) return
  
  copying.value = true
  try {
    const url = props.newsItem.url || window.location.href
    await navigator.clipboard.writeText(url)
    // TODO: 显示成功提示
  } catch (error) {
    console.error('复制失败:', error)
  } finally {
    copying.value = false
  }
}

const handleStockClick = (stockCode: string) => {
  // TODO: 跳转到股票详情页面或筛选相关新闻
  console.log('点击股票:', stockCode)
}

const handleOpenOriginal = () => {
  if (props.newsItem?.url) {
    window.open(props.newsItem.url, '_blank')
  }
}
</script>

<template>
  <t-dialog
    v-model:visible="dialogVisible"
    header="新闻详情"
    width="800px"
    :close-on-overlay-click="true"
    :show-overlay="true"
    class="news-detail-dialog"
  >
    <div v-if="newsItem" class="news-detail-content">
      <!-- 新闻头部 -->
      <div class="news-header">
        <div class="news-title-section">
          <h2 class="news-title">{{ newsItem.title }}</h2>
          
          <div class="news-meta">
            <t-tag :theme="categoryTheme" size="small" variant="light">
              {{ categoryLabel }}
            </t-tag>
            
            <t-tag size="small" variant="outline">
              {{ newsItem.source }}
            </t-tag>
            
            <span class="news-time">
              <TimeIcon size="14px" />
              {{ formattedTime }}
            </span>
          </div>
        </div>

        <!-- 情绪分析 -->
        <div v-if="sentimentAnalysis" class="sentiment-section">
          <SentimentTag 
            :sentiment="newsItem.sentiment!"
            :show-score="true"
            :show-icon="true"
            size="medium"
          />
          
          <div class="impact-info">
            <t-tag 
              size="small" 
              variant="outline"
              :theme="sentimentAnalysis.impact_level === 'high' ? 'danger' : 
                     sentimentAnalysis.impact_level === 'medium' ? 'warning' : 'default'"
            >
              {{ sentimentAnalysis.impactText }}
            </t-tag>
          </div>
        </div>
      </div>

      <!-- 新闻内容 -->
      <div class="news-content">
        <div class="content-text">
          {{ newsItem.content }}
        </div>
      </div>

      <!-- AI 分析结果 -->
      <div v-if="sentimentAnalysis?.reasoning" class="ai-analysis">
        <t-card title="AI 情绪分析" size="small" :bordered="false" class="analysis-card">
          <div class="analysis-content">
            <p>{{ sentimentAnalysis.reasoning }}</p>
          </div>
        </t-card>
      </div>

      <!-- 相关股票 -->
      <div v-if="newsItem.stock_codes.length > 0" class="related-stocks">
        <div class="section-title">相关股票</div>
        <div class="stock-tags">
          <t-tag
            v-for="code in newsItem.stock_codes"
            :key="code"
            size="medium"
            variant="outline"
            theme="primary"
            class="stock-tag"
            @click="handleStockClick(code)"
          >
            {{ code }}
          </t-tag>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="news-actions">
        <t-button variant="outline" @click="handleShare">
          <template #icon>
            <FileSearchIcon />
          </template>
          分享
        </t-button>
        
        <t-button 
          variant="outline" 
          :theme="favorited ? 'primary' : 'default'"
          @click="handleFavorite"
        >
          <template #icon>
            <FileIcon />
          </template>
          {{ favorited ? '已收藏' : '收藏' }}
        </t-button>
        
        <t-button 
          variant="outline" 
          :loading="copying"
          @click="handleCopyLink"
        >
          <template #icon>
            <ControlPlatformIcon />
          </template>
          复制链接
        </t-button>
        
        <t-button 
          v-if="newsItem.url"
          variant="outline"
          @click="handleOpenOriginal"
        >
          <template #icon>
            <QueueIcon />
          </template>
          查看原文
        </t-button>
      </div>
    </div>

    <template #footer>
      <t-button theme="primary" @click="handleClose">
        关闭
      </t-button>
    </template>
  </t-dialog>
</template>

<style scoped>
.news-detail-dialog :deep(.t-dialog__body) {
  padding: 0;
  max-height: 70vh;
  overflow-y: auto;
}

.news-detail-content {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.news-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--td-component-stroke);
}

.news-title-section {
  flex: 1;
  min-width: 0;
}

.news-title {
  margin: 0 0 12px 0;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.4;
  color: var(--td-text-color-primary);
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
  font-size: 13px;
  color: var(--td-text-color-secondary);
}

.sentiment-section {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  flex-shrink: 0;
}

.impact-info {
  display: flex;
  align-items: center;
  gap: 4px;
}

.news-content {
  flex: 1;
}

.content-text {
  font-size: 15px;
  line-height: 1.6;
  color: var(--td-text-color-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

.ai-analysis {
  background: var(--td-bg-color-container);
  border-radius: 8px;
  overflow: hidden;
}

.analysis-card {
  background: transparent;
  border: none;
  box-shadow: none;
}

.analysis-card :deep(.t-card__header) {
  background: var(--td-brand-color-light);
  padding: 12px 16px;
  border-bottom: 1px solid var(--td-component-stroke);
}

.analysis-card :deep(.t-card__title) {
  font-size: 14px;
  font-weight: 500;
  color: var(--td-brand-color);
}

.analysis-content {
  padding: 16px;
}

.analysis-content p {
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
  color: var(--td-text-color-secondary);
}

.related-stocks {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--td-text-color-primary);
}

.stock-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.stock-tag {
  cursor: pointer;
  transition: all 0.2s ease;
}

.stock-tag:hover {
  background: var(--td-brand-color-light);
  border-color: var(--td-brand-color);
  transform: translateY(-1px);
}

.news-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding-top: 16px;
  border-top: 1px solid var(--td-component-stroke);
}

/* 滚动条样式 */
.news-detail-dialog :deep(.t-dialog__body)::-webkit-scrollbar {
  width: 6px;
}

.news-detail-dialog :deep(.t-dialog__body)::-webkit-scrollbar-track {
  background: var(--td-bg-color-container);
  border-radius: 3px;
}

.news-detail-dialog :deep(.t-dialog__body)::-webkit-scrollbar-thumb {
  background: var(--td-bg-color-component-hover);
  border-radius: 3px;
}

.news-detail-dialog :deep(.t-dialog__body)::-webkit-scrollbar-thumb:hover {
  background: var(--td-bg-color-component-active);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .news-detail-dialog {
    width: 95vw !important;
    margin: 0 auto;
  }
  
  .news-detail-content {
    padding: 16px;
    gap: 16px;
  }
  
  .news-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .sentiment-section {
    align-items: flex-start;
    width: 100%;
  }
  
  .news-title {
    font-size: 18px;
  }
  
  .content-text {
    font-size: 14px;
  }
  
  .news-actions {
    justify-content: center;
  }
}
</style>