<script setup lang="ts">
import { ref } from 'vue'
import type { NewsItem, SentimentStats } from '@/types/news'
import type { StockSignalSummary } from '@/api/signalAggregator'
import SignalPanel from './SignalPanel.vue'
import WatchlistRelevance from './WatchlistRelevance.vue'
import SectorHeatmap from './SectorHeatmap.vue'
import EventImpactPanel from './EventImpactPanel.vue'

interface Props {
  newsItems: NewsItem[]
  activeStockCode: string | null
  sentimentData: SentimentStats
  sentimentLoading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  sentimentLoading: false,
})

const emit = defineEmits<{
  (e: 'open-timeline', tsCode: string): void
  (e: 'stock-search', tsCode: string): void
  (e: 'news-click', news: NewsItem): void
  (e: 'category-filter', category: string): void
}>()

const activeTab = ref('impact')
</script>

<template>
  <div class="analysis-panel">
    <t-tabs v-model="activeTab" size="small">
      <t-tab-panel value="impact" label="事件影响">
        <EventImpactPanel
          :news-items="newsItems"
          @news-click="emit('news-click', $event)"
        />
      </t-tab-panel>

      <t-tab-panel value="watchlist" label="持仓关联">
        <WatchlistRelevance
          :news-items="newsItems"
          @stock-search="emit('stock-search', $event)"
        />
      </t-tab-panel>

      <t-tab-panel value="sector" label="板块热力">
        <SectorHeatmap
          :news-items="newsItems"
          @category-filter="emit('category-filter', $event)"
        />
      </t-tab-panel>

      <t-tab-panel value="signal" label="信号评分">
        <SignalPanel
          :active-stock-code="activeStockCode"
          :sentiment-data="sentimentData"
          :sentiment-loading="sentimentLoading"
          @open-timeline="emit('open-timeline', $event)"
        />
      </t-tab-panel>
    </t-tabs>
  </div>
</template>

<style scoped>
.analysis-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.analysis-panel :deep(.t-tabs__content) {
  padding-top: 12px;
  flex: 1;
  overflow: hidden;
}

.analysis-panel :deep(.t-tabs__nav) {
  background: transparent;
}

.analysis-panel :deep(.t-tab-panel) {
  height: 100%;
  overflow-y: auto;
}
</style>
