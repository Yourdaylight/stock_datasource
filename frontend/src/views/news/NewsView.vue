<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useNewsStore } from '@/stores/news'
import NewsFilterPanel from './components/NewsFilterPanel.vue'
import NewsListPanel from './components/NewsListPanel.vue'
import HotTopicsPanel from './components/HotTopicsPanel.vue'
import SentimentChart from './components/SentimentChart.vue'
import NewsDetailDialog from './components/NewsDetailDialog.vue'

const newsStore = useNewsStore()

// 响应式状态
const loading = computed(() => newsStore.loading)
const filteredNews = computed(() => newsStore.filteredNews)
const hotTopics = computed(() => newsStore.hotTopics)
const sentimentStats = computed(() => newsStore.sentimentStats)
const detailVisible = computed({
  get: () => newsStore.detailVisible,
  set: (value) => {
    if (!value) {
      newsStore.hideNewsDetail()
    }
  }
})
const selectedNews = computed(() => newsStore.selectedNews)

// 事件处理
const handleFilterChange = async (filters: any) => {
  await newsStore.applyFilters(filters)
}

const handleLoadMore = async () => {
  await newsStore.loadMoreNews()
}

const handleNewsClick = (news: any) => {
  newsStore.showNewsDetail(news)
}

const handleTopicClick = async (topic: any) => {
  // 点击热点话题时，应用相关筛选条件
  await newsStore.applyFilters({
    keywords: topic.topic
  })
}

const handleRefresh = async () => {
  await newsStore.refreshNews()
}

// 组件挂载时初始化数据
onMounted(async () => {
  // 并行获取初始数据
  await Promise.all([
    newsStore.fetchMarketNews({ reset: true }),
    newsStore.fetchHotTopics(),
    newsStore.fetchAvailableOptions()
  ])
})
</script>

<template>
  <div class="news-view">
    <t-layout class="news-layout">
      <!-- 左侧筛选面板 -->
      <t-aside width="280px" class="news-aside">
        <NewsFilterPanel 
          v-model:filters="newsStore.filters"
          :available-categories="newsStore.availableCategories"
          :available-sources="newsStore.availableSources"
          :loading="loading"
          @filter-change="handleFilterChange"
        />
      </t-aside>
      
      <!-- 中间新闻列表 -->
      <t-content class="news-content">
        <NewsListPanel 
          :news-items="filteredNews"
          :loading="loading"
          :has-more="newsStore.hasMore"
          :sort-by="newsStore.sortBy"
          :total="newsStore.total"
          @load-more="handleLoadMore"
          @news-click="handleNewsClick"
          @refresh="handleRefresh"
          @sort-change="newsStore.setSortBy"
        />
      </t-content>
      
      <!-- 右侧热点面板 -->
      <t-aside width="320px" class="news-aside">
        <div class="right-panels">
          <!-- 热点话题面板 -->
          <HotTopicsPanel 
            :hot-topics="hotTopics"
            :loading="newsStore.hotTopicsLoading"
            @topic-click="handleTopicClick"
          />
          
          <!-- 情绪分析图表 -->
          <SentimentChart 
            :sentiment-data="sentimentStats"
            :loading="newsStore.sentimentLoading"
          />
        </div>
      </t-aside>
    </t-layout>
    
    <!-- 新闻详情弹窗 -->
    <NewsDetailDialog 
      v-model:visible="detailVisible"
      :news-item="selectedNews"
    />
  </div>
</template>

<style scoped>
.news-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px;
  background: #e4e7ed;
}

.news-layout {
  flex: 1;
  height: 100%;
  background: transparent;
  gap: 16px;
}

.news-aside {
  background: transparent;
  padding: 0;
}

.news-content {
  background: transparent;
  padding: 0;
  min-width: 0; /* 防止内容溢出 */
}

.right-panels {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
}

/* 响应式设计 */
@media (max-width: 1280px) {
  .news-layout {
    flex-direction: column;
  }
  
  .news-aside {
    width: 100% !important;
    height: auto;
  }
  
  .right-panels {
    flex-direction: row;
    height: auto;
  }
  
  .right-panels > * {
    flex: 1;
  }
}

@media (max-width: 768px) {
  .news-view {
    padding: 8px;
  }
  
  .news-layout {
    gap: 8px;
  }
  
  .right-panels {
    flex-direction: column;
  }
}
</style>