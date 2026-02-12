<script setup lang="ts">
import { ref, onMounted, computed, defineAsyncComponent } from 'vue'
import { useNewsStore } from '@/stores/news'
import NewsListPanel from './components/NewsListPanel.vue'
import HotTopicsPanel from './components/HotTopicsPanel.vue'
import SentimentChart from './components/SentimentChart.vue'
import NewsDetailDialog from './components/NewsDetailDialog.vue'

const InstitutionalSurveyPanel = defineAsyncComponent(
  () => import('@/views/research/components/InstitutionalSurveyPanel.vue')
)
const ResearchReportPanel = defineAsyncComponent(
  () => import('@/views/research/components/ResearchReportPanel.vue')
)

const newsStore = useNewsStore()
const activeTab = ref('news')

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
const activeStockCode = computed(() => newsStore.activeStockCode)

// 事件处理
const handleFilterChange = async (filters: any) => {
  await newsStore.applyFilters(filters)
}

const handleLoadMore = async () => {
  await newsStore.loadMoreNews()
}

const handleStockSearch = async (stockCode: string) => {
  newsStore.setActiveStockCode(stockCode)
  await newsStore.fetchNewsByStock(stockCode, 30)
}

const handleStockClear = async () => {
  newsStore.setActiveStockCode(null)
  newsStore.clearNewsResults()
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

const handleHotTopicsRefresh = async () => {
  await newsStore.fetchHotTopics(10)
}

// 组件挂载时初始化数据
onMounted(async () => {
  await newsStore.fetchAvailableOptions()

  await newsStore.fetchHotTopics(10)

  if (newsStore.filters.stock_codes.length > 0) {
    const stockCode = newsStore.filters.stock_codes[0]
    newsStore.setActiveStockCode(stockCode)
    await newsStore.fetchNewsByStock(stockCode, 30)
    return
  }

  await newsStore.fetchMarketNews({ page: 1, reset: true })
})
</script>

<template>
  <div class="news-view">
    <t-card :bordered="false" class="news-card">
      <template #title>
        <div class="news-title">资讯中心</div>
      </template>
      <t-tabs v-model="activeTab" size="large">
        <t-tab-panel value="news" label="新闻快讯">
          <t-layout class="news-layout">
            <!-- 新闻列表 -->
            <t-content class="news-content">
              <NewsListPanel 
                v-model:filters="newsStore.filters"
                :available-categories="newsStore.availableCategories"
                :available-sources="newsStore.availableSources"
                :news-items="filteredNews"
                :loading="loading"
                :has-more="newsStore.hasMore"
                :sort-by="newsStore.sortBy"
                :total="newsStore.total"
                :active-stock-code="activeStockCode"
                @filter-change="handleFilterChange"
                @load-more="handleLoadMore"
                @news-click="handleNewsClick"
                @refresh="handleRefresh"
                @sort-change="newsStore.setSortBy"
                @stock-search="handleStockSearch"
                @stock-clear="handleStockClear"
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
                  @refresh="handleHotTopicsRefresh"
                />
                
                <!-- 情绪分析图表 -->
                <SentimentChart 
                  :sentiment-data="sentimentStats"
                  :loading="newsStore.sentimentLoading"
                />
              </div>
            </t-aside>
          </t-layout>
        </t-tab-panel>

        <t-tab-panel value="survey" label="机构调研">
          <InstitutionalSurveyPanel />
        </t-tab-panel>

        <t-tab-panel value="report" label="研报数据">
          <ResearchReportPanel />
        </t-tab-panel>
      </t-tabs>
    </t-card>
    
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

.news-card {
  flex: 1;
  border-radius: 12px;
}

.news-title {
  font-size: 18px;
  font-weight: 600;
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

:deep(.t-card__body) {
  padding: 16px;
}

:deep(.t-tabs__content) {
  padding-top: 16px;
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