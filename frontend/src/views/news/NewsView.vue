<script setup lang="ts">
import { ref, onMounted, computed, defineAsyncComponent } from 'vue'
import { useNewsStore } from '@/stores/news'
import { useSignalAggregatorStore } from '@/stores/signalAggregator'
import NewsListPanel from './components/NewsListPanel.vue'
import NewsFilterPanel from './components/NewsFilterPanel.vue'
import AnalysisPanel from './components/AnalysisPanel.vue'
import NewsDetailDialog from './components/NewsDetailDialog.vue'
import type { StockSignalSummary } from '@/api/signalAggregator'

const InstitutionalSurveyPanel = defineAsyncComponent(
  () => import('@/views/research/components/InstitutionalSurveyPanel.vue')
)
const ResearchReportPanel = defineAsyncComponent(
  () => import('@/views/research/components/ResearchReportPanel.vue')
)
const SignalTimeline = defineAsyncComponent(
  () => import('@/views/signal/SignalTimeline.vue')
)

const newsStore = useNewsStore()
const signalStore = useSignalAggregatorStore()
const activeTab = ref('news')

// 信号筛选状态
const signalDirection = ref<'bullish' | 'bearish' | 'neutral' | ''>('')
const minSignalScore = ref(0)

// 信号时序弹窗
const timelineVisible = ref(false)
const timelineStock = ref('')

const loading = computed(() => newsStore.loading)
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

// 构建信号 Map（用于新闻卡片徽章）
const signalMap = computed(() => {
  const map = new Map<string, StockSignalSummary>()
  for (const s of signalStore.stocks) {
    map.set(s.ts_code, s)
  }
  return map
})

// 过滤后的新闻（加入信号筛选）
const filteredNews = computed(() => {
  let items = newsStore.filteredNews || []

  if (signalDirection.value || minSignalScore.value > 0) {
    items = items.filter(item => {
      // 找该新闻关联的任一股票有信号数据
      const signals = item.stock_codes
        .map(code => signalMap.value.get(code))
        .filter((s): s is StockSignalSummary => !!s)

      if (signals.length === 0) {
        // 如果有信号筛选条件但该新闻没有信号数据，过滤掉
        return false
      }

      // 至少一个关联股票满足条件
      return signals.some(s => {
        const dirMatch = !signalDirection.value || s.composite_direction === signalDirection.value
        const scoreMatch = s.composite_score >= minSignalScore.value
        return dirMatch && scoreMatch
      })
    })
  }

  return items
})

// 加载新闻关联股票的信号数据（带防重入锁）
let _loadingSignals = false
const loadNewsSignals = async () => {
  if (_loadingSignals) return
  _loadingSignals = true
  try {
    const codes = new Set<string>()
    for (const item of newsStore.filteredNews || []) {
      for (const code of item.stock_codes) {
        codes.add(code)
      }
    }
    if (codes.size > 0 && codes.size <= 30) {
      await signalStore.fetchAggregate(Array.from(codes))
    }
  } catch (e) {
    console.warn('[NewsView] loadNewsSignals failed:', e)
  } finally {
    _loadingSignals = false
  }
}

const handleFilterChange = async (filters: any) => {
  await newsStore.applyFilters(filters)
  // 加载新筛选结果的信号
  await loadNewsSignals()
}

const handleLoadMore = async () => {
  await newsStore.loadMoreNews()
}

const handleStockSearch = async (stockCode: string) => {
  newsStore.setActiveStockCode(stockCode)
  await newsStore.fetchNewsByStock(stockCode, 30)
  // 自动加载该股票信号
  if (stockCode) {
    await signalStore.fetchSingleStock(stockCode)
  }
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
  await loadNewsSignals()
}

const handlePageChange = async (page: number) => {
  await newsStore.goToPage(page)
  await loadNewsSignals()
}

const handlePageSizeChange = async (size: number) => {
  await newsStore.setPageSize(size)
  await loadNewsSignals()
}

const handleOpenTimeline = (tsCode: string) => {
  timelineStock.value = tsCode
  timelineVisible.value = true
}

const handleCategoryFilter = async (category: string) => {
  newsStore.filters.categories = [category]
  await newsStore.applyFilters(newsStore.filters)
  await loadNewsSignals()
}

onMounted(async () => {
  await newsStore.fetchAvailableOptions()

  if (newsStore.filters.stock_codes.length > 0) {
    const stockCode = newsStore.filters.stock_codes[0]
    newsStore.setActiveStockCode(stockCode)
    await newsStore.fetchNewsByStock(stockCode, 30)
    await signalStore.fetchSingleStock(stockCode)
    return
  }

  await newsStore.fetchMarketNews({ page: 1, reset: true })
  loadNewsSignals()
})
</script>

<template>
  <div class="news-view">
    <t-card :bordered="false" class="news-card">
      <template #title>
        <div class="news-title">资讯中心 + 信号观测</div>
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
            <!-- 左侧：筛选面板 -->
            <t-aside width="240px" class="news-aside-left">
              <NewsFilterPanel
                v-model:filters="newsStore.filters"
                :available-categories="newsStore.availableCategories"
                :available-sources="newsStore.availableSources"
                :loading="loading"
                v-model:signal-direction="signalDirection"
                v-model:min-signal-score="minSignalScore"
                @filter-change="handleFilterChange"
              />
            </t-aside>

            <!-- 中间：新闻列表 -->
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
                :signal-map="signalMap"
                :current-page="newsStore.currentPage"
                :page-size="newsStore.pageSize"
                @filter-change="handleFilterChange"
                @load-more="handleLoadMore"
                @news-click="handleNewsClick"
                @refresh="handleRefresh"
                @sort-change="newsStore.setSortBy"
                @stock-search="handleStockSearch"
                @stock-clear="handleStockClear"
                @page-change="handlePageChange"
                @page-size-change="handlePageSizeChange"
              />
            </t-content>

            <!-- 右侧：分析面板 -->
            <t-aside width="360px" class="news-aside-right">
              <AnalysisPanel
                :news-items="filteredNews"
                :active-stock-code="activeStockCode"
                :sentiment-data="sentimentStats"
                :sentiment-loading="newsStore.sentimentLoading"
                @open-timeline="handleOpenTimeline"
                @stock-search="handleStockSearch"
                @news-click="handleNewsClick"
                @category-filter="handleCategoryFilter"
              />
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

    <!-- 信号时序追踪弹窗 -->
    <t-dialog
      v-model:visible="timelineVisible"
      :header="`${timelineStock} 信号时序追踪`"
      width="800px"
      :footer="false"
      destroy-on-close
    >
      <SignalTimeline v-if="timelineVisible" :ts-code="timelineStock" />
    </t-dialog>
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

.news-aside-left {
  background: transparent;
  padding: 0;
  overflow-y: auto;
}

.news-aside-right {
  background: transparent;
  padding: 0;
}

.news-content {
  background: transparent;
  padding: 0;
  min-width: 0;
  flex: 1;
}

:deep(.t-card__body) {
  padding: 16px;
}

:deep(.t-tabs__content) {
  padding-top: 16px;
}

@media (max-width: 1400px) {
  .news-aside-left {
    width: 200px !important;
  }
}

@media (max-width: 1280px) {
  .news-layout {
    flex-direction: column;
  }

  .news-aside-left,
  .news-aside-right {
    width: 100% !important;
    height: auto;
  }
}

@media (max-width: 768px) {
  .news-view {
    padding: 8px;
  }

  .news-layout {
    gap: 8px;
  }
}
</style>
