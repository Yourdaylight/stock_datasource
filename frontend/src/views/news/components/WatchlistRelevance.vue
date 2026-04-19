<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import type { NewsItem } from '@/types/news'
import { memoryApi, type WatchlistItem } from '@/api/memory'

interface Props {
  newsItems: NewsItem[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'stock-search', tsCode: string): void
}>()

const watchlist = ref<WatchlistItem[]>([])
const loading = ref(false)

const loadWatchlist = async () => {
  loading.value = true
  try {
    watchlist.value = await memoryApi.getWatchlist()
  } catch (e) {
    console.warn('[WatchlistRelevance] Failed to load watchlist:', e)
    watchlist.value = []
  } finally {
    loading.value = false
  }
}

// 按自选股分组的新闻统计
const stockNewsMap = computed(() => {
  const map = new Map<string, {
    code: string
    name: string
    newsCount: number
    latestTitle: string
    latestTime: string
    posCount: number
    negCount: number
  }>()

  for (const w of watchlist.value) {
    map.set(w.ts_code, {
      code: w.ts_code,
      name: w.stock_name || w.ts_code,
      newsCount: 0,
      latestTitle: '',
      latestTime: '',
      posCount: 0,
      negCount: 0,
    })
  }

  for (const news of props.newsItems) {
    for (const code of news.stock_codes) {
      const entry = map.get(code)
      if (entry) {
        entry.newsCount++
        if (!entry.latestTitle || new Date(news.publish_time) > new Date(entry.latestTime)) {
          entry.latestTitle = news.title
          entry.latestTime = news.publish_time
        }
        if (news.sentiment?.sentiment === 'positive') entry.posCount++
        if (news.sentiment?.sentiment === 'negative') entry.negCount++
      }
    }
  }

  return map
})

// 有关联新闻的自选股（按新闻数降序）
const relevantStocks = computed(() => {
  return Array.from(stockNewsMap.value.values())
    .filter(s => s.newsCount > 0)
    .sort((a, b) => b.newsCount - a.newsCount)
})

// 无关联新闻的自选股
const quietStocks = computed(() => {
  return Array.from(stockNewsMap.value.values())
    .filter(s => s.newsCount === 0)
})

const matchedNewsCount = computed(() =>
  relevantStocks.value.reduce((sum, s) => sum + s.newsCount, 0)
)

const sentimentColor = (pos: number, neg: number) => {
  if (pos > neg) return '#00a870'
  if (neg > pos) return '#d54941'
  return '#8b8b8b'
}

onMounted(loadWatchlist)
</script>

<template>
  <div class="watchlist-relevance">
    <!-- Loading -->
    <div v-if="loading" class="wl-loading">
      <t-loading size="small" text="加载自选股..." />
    </div>

    <template v-else-if="watchlist.length > 0">
      <!-- 概览统计 -->
      <div class="wl-summary">
        <t-tag theme="primary" variant="light" size="small">
          {{ matchedNewsCount }} 条新闻关联 {{ relevantStocks.length }}/{{ watchlist.length }} 只自选股
        </t-tag>
      </div>

      <!-- 有关联新闻的股票 -->
      <div class="wl-list" v-if="relevantStocks.length > 0">
        <div
          v-for="stock in relevantStocks"
          :key="stock.code"
          class="wl-item"
          @click="emit('stock-search', stock.code)"
        >
          <div class="wl-item-header">
            <span class="wl-stock-name">{{ stock.name }}</span>
            <span class="wl-stock-code">{{ stock.code }}</span>
            <t-tag size="small" theme="primary" variant="light">{{ stock.newsCount }}条</t-tag>
          </div>
          <div class="wl-item-sentiment">
            <span :style="{ color: sentimentColor(stock.posCount, stock.negCount) }">
              ▲{{ stock.posCount }} ▼{{ stock.negCount }}
            </span>
          </div>
          <div class="wl-item-headline" v-if="stock.latestTitle">
            {{ stock.latestTitle }}
          </div>
        </div>
      </div>

      <!-- 无新闻的自选股 -->
      <div v-if="quietStocks.length > 0" class="wl-quiet">
        <div class="wl-quiet-label">暂无新闻</div>
        <div class="wl-quiet-tags">
          <t-tag v-for="s in quietStocks" :key="s.code" size="small" variant="outline">
            {{ s.name || s.code }}
          </t-tag>
        </div>
      </div>
    </template>

    <!-- 空状态 -->
    <t-empty v-else size="small" description="暂无自选股，请先添加关注的股票">
      <template #image>
        <div style="font-size: 32px">⭐</div>
      </template>
    </t-empty>
  </div>
</template>

<style scoped>
.watchlist-relevance {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  overflow-y: auto;
}

.wl-loading {
  display: flex;
  justify-content: center;
  padding: 24px 0;
}

.wl-summary {
  display: flex;
  gap: 6px;
}

.wl-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.wl-item {
  padding: 10px;
  border-radius: 6px;
  border: 1px solid var(--td-component-stroke);
  cursor: pointer;
  transition: all 0.2s;
}

.wl-item:hover {
  border-color: var(--td-brand-color);
  background: var(--td-brand-color-light);
}

.wl-item-header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.wl-stock-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--td-text-color-primary);
}

.wl-stock-code {
  font-size: 11px;
  color: var(--td-text-color-secondary);
}

.wl-item-sentiment {
  font-size: 11px;
  margin-top: 4px;
}

.wl-item-headline {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  margin-top: 4px;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wl-quiet {
  margin-top: 4px;
}

.wl-quiet-label {
  font-size: 11px;
  color: var(--td-text-color-placeholder);
  margin-bottom: 6px;
}

.wl-quiet-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>
