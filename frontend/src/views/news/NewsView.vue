<script setup lang="ts">
import { ref, onMounted, computed, defineAsyncComponent } from 'vue'
import { useNewsStore } from '@/stores/news'
import NewsListPanel from './components/NewsListPanel.vue'
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

const loading = computed(() => newsStore.loading)
const filteredNews = computed(() => newsStore.filteredNews)
const sentimentStats = computed(() => newsStore.sentimentStats)
const detailVisible = computed({
  get: () => newsStore.detailVisible,
  set: (value) => {
    if (!value) newsStore.hideNewsDetail()
  }
})
const selectedNews = computed(() => newsStore.selectedNews)
const activeStockCode = computed(() => newsStore.activeStockCode)
const partialData = computed(() => newsStore.partialData)
const failedSources = computed(() => newsStore.failedSources)
const showGlobalPartialAlert = computed(() => {
  return activeTab.value === 'news' && partialData.value
})
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
  await newsStore.fetchMarketNews({ page: 1, reset: true })
}

const handleNewsClick = (news: any) => {
  newsStore.showNewsDetail(news)
}

const handleRefresh = async () => {
  await newsStore.refreshNews()
}

onMounted(async () => {
  await newsStore.fetchAvailableOptions()

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

      <t-alert
        v-if="showGlobalPartialAlert"
        theme="warning"
        :message="`部分数据源拉取失败：${failedSources.join('、')}`"
        close
        class="partial-alert"
      />

      <t-tabs v-model="activeTab" size="large">
        <t-tab-panel value="news" label="新闻快讯">
          <t-layout class="news-layout">
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

            <t-aside width="320px" class="news-aside">
              <div class="right-panels">
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

.partial-alert {
  margin-bottom: 12px;
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
  min-width: 0;
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