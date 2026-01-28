<script setup lang="ts">
import { ref, computed } from 'vue'
import { RefreshIcon, TimeIcon, TrendingUpIcon, HeartIcon } from 'tdesign-icons-vue-next'
import type { NewsItem, NewsSortBy } from '@/types/news'
import NewsItemCard from './NewsItemCard.vue'

interface Props {
  newsItems: NewsItem[]
  loading?: boolean
  hasMore?: boolean
  sortBy?: NewsSortBy
  total?: number
}

interface Emits {
  (e: 'load-more'): void
  (e: 'news-click', news: NewsItem): void
  (e: 'refresh'): void
  (e: 'sort-change', sortBy: NewsSortBy, sortOrder: 'asc' | 'desc'): void
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  hasMore: true,
  sortBy: 'time',
  total: 0
})

const emit = defineEmits<Emits>()

// 排序选项
const sortOptions = [
  { label: '按时间', value: 'time', icon: TimeIcon },
  { label: '按热度', value: 'heat', icon: TrendingUpIcon },
  { label: '按情绪', value: 'sentiment', icon: HeartIcon }
]

// 当前排序顺序
const sortOrder = ref<'asc' | 'desc'>('desc')

// 列表容器引用
const listContainer = ref<HTMLElement>()

// 计算属性
const currentSortOption = computed(() => {
  return sortOptions.find(option => option.value === props.sortBy) || sortOptions[0]
})

const sortOrderText = computed(() => {
  return sortOrder.value === 'desc' ? '降序' : '升序'
})

// 事件处理
const handleRefresh = () => {
  emit('refresh')
}

const handleSortChange = (newSortBy: NewsSortBy) => {
  // 如果点击的是当前排序方式，则切换排序顺序
  if (newSortBy === props.sortBy) {
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortOrder.value = 'desc' // 新的排序方式默认降序
  }
  emit('sort-change', newSortBy, sortOrder.value)
}

const handleNewsClick = (news: NewsItem) => {
  emit('news-click', news)
}

const handleLoadMore = () => {
  if (!props.loading && props.hasMore) {
    emit('load-more')
  }
}

// 滚动到底部检测
const handleScroll = (event: Event) => {
  const target = event.target as HTMLElement
  const { scrollTop, scrollHeight, clientHeight } = target
  
  // 当滚动到距离底部100px时触发加载更多
  if (scrollHeight - scrollTop - clientHeight < 100) {
    handleLoadMore()
  }
}
</script>

<template>
  <div class="news-list-panel">
    <t-card :bordered="false" class="news-list-card">
      <!-- 头部工具栏 -->
      <template #title>
        <div class="news-header">
          <div class="news-title">
            <span>新闻资讯</span>
            <t-tag size="small" theme="primary" variant="light">
              共 {{ total }} 条
            </t-tag>
          </div>
          
          <div class="news-actions">
            <!-- 排序选择 -->
            <t-dropdown
              :options="sortOptions.map(opt => ({
                content: opt.label,
                value: opt.value,
                prefixIcon: opt.icon
              }))"
              @click="handleSortChange"
              :disabled="loading"
            >
              <t-button size="small" variant="outline">
                <template #icon>
                  <component :is="currentSortOption.icon" />
                </template>
                {{ currentSortOption.label }}
                <span class="sort-order">({{ sortOrderText }})</span>
              </t-button>
            </t-dropdown>
            
            <!-- 刷新按钮 -->
            <t-button 
              size="small" 
              variant="outline"
              @click="handleRefresh"
              :loading="loading"
            >
              <template #icon>
                <RefreshIcon />
              </template>
              刷新
            </t-button>
          </div>
        </div>
      </template>

      <!-- 新闻列表内容 -->
      <div 
        ref="listContainer"
        class="news-list-content"
        @scroll="handleScroll"
      >
        <!-- 新闻列表 -->
        <div class="news-list" v-if="newsItems.length > 0">
          <NewsItemCard
            v-for="news in newsItems"
            :key="news.id"
            :news-item="news"
            @click="handleNewsClick(news)"
          />
        </div>

        <!-- 空状态 -->
        <div v-else-if="!loading" class="empty-state">
          <t-empty 
            description="暂无新闻数据"
            image="https://tdesign.gtimg.com/pro-template/personal/empty.png"
          >
            <t-button @click="handleRefresh">
              刷新试试
            </t-button>
          </t-empty>
        </div>

        <!-- 加载更多 -->
        <div v-if="hasMore && newsItems.length > 0" class="load-more">
          <t-button
            v-if="!loading"
            variant="text"
            @click="handleLoadMore"
            block
          >
            加载更多
          </t-button>
          <div v-else class="loading-more">
            <t-loading size="small" />
            <span>加载中...</span>
          </div>
        </div>

        <!-- 没有更多数据 -->
        <div v-else-if="!hasMore && newsItems.length > 0" class="no-more">
          <t-divider>没有更多数据了</t-divider>
        </div>

        <!-- 初始加载状态 -->
        <div v-if="loading && newsItems.length === 0" class="initial-loading">
          <t-skeleton 
            theme="article" 
            :row-col="[
              { width: '100%' },
              { width: '80%' },
              { width: '60%' }
            ]"
          />
          <t-skeleton 
            theme="article" 
            :row-col="[
              { width: '100%' },
              { width: '90%' },
              { width: '70%' }
            ]"
            style="margin-top: 16px;"
          />
          <t-skeleton 
            theme="article" 
            :row-col="[
              { width: '100%' },
              { width: '85%' },
              { width: '65%' }
            ]"
            style="margin-top: 16px;"
          />
        </div>
      </div>
    </t-card>
  </div>
</template>

<style scoped>
.news-list-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.news-list-card {
  flex: 1;
  height: 100%;
  background: #ffffff;
  border: 1px solid #e8e8e8;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
}

.news-list-card :deep(.t-card__body) {
  flex: 1;
  padding: 0;
  overflow: hidden;
}

.news-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.news-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 500;
}

.news-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sort-order {
  font-size: 11px;
  color: var(--td-text-color-secondary);
  margin-left: 2px;
}

.news-list-content {
  height: 100%;
  overflow-y: auto;
  padding: 16px;
}

.news-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 300px;
}

.load-more {
  margin-top: 16px;
  padding: 8px 0;
}

.loading-more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px;
  color: var(--td-text-color-secondary);
  font-size: 14px;
}

.no-more {
  margin-top: 16px;
  text-align: center;
}

.no-more :deep(.t-divider__content) {
  color: var(--td-text-color-placeholder);
  font-size: 12px;
}

.initial-loading {
  padding: 16px 0;
}

/* 滚动条样式 */
.news-list-content::-webkit-scrollbar {
  width: 6px;
}

.news-list-content::-webkit-scrollbar-track {
  background: var(--td-bg-color-container);
  border-radius: 3px;
}

.news-list-content::-webkit-scrollbar-thumb {
  background: var(--td-bg-color-component-hover);
  border-radius: 3px;
}

.news-list-content::-webkit-scrollbar-thumb:hover {
  background: var(--td-bg-color-component-active);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .news-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .news-actions {
    width: 100%;
    justify-content: flex-end;
  }
  
  .news-list-content {
    padding: 8px;
  }
  
  .news-list {
    gap: 8px;
  }
}
</style>