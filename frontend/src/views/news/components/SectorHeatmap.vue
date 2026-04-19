<script setup lang="ts">
import { computed, ref } from 'vue'
import type { NewsItem } from '@/types/news'

interface Props {
  newsItems: NewsItem[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'category-filter', category: string): void
}>()

// 按新闻分类聚合情绪
const sectorData = computed(() => {
  const map = new Map<string, {
    name: string
    label: string
    newsCount: number
    posCount: number
    negCount: number
    neuCount: number
    avgScore: number
  }>()

  const categoryLabels: Record<string, string> = {
    announcement: '公司公告',
    flash: '市场快讯',
    analysis: '深度分析',
    industry: '行业动态',
    research: '券商研报',
    policy: '政策法规',
    cctv: '央视新闻',
    npr: '新闻联播',
  }

  for (const news of props.newsItems) {
    const cat = news.category || 'other'
    if (!map.has(cat)) {
      map.set(cat, {
        name: cat,
        label: categoryLabels[cat] || cat,
        newsCount: 0,
        posCount: 0,
        negCount: 0,
        neuCount: 0,
        avgScore: 0,
      })
    }
    const entry = map.get(cat)!
    entry.newsCount++
    if (news.sentiment) {
      if (news.sentiment.sentiment === 'positive') entry.posCount++
      else if (news.sentiment.sentiment === 'negative') entry.negCount++
      else entry.neuCount++
      entry.avgScore += news.sentiment.score ?? 0
    } else {
      entry.neuCount++
    }
  }

  // 计算平均分
  for (const entry of map.values()) {
    if (entry.newsCount > 0) {
      entry.avgScore = entry.avgScore / entry.newsCount
    }
  }

  return Array.from(map.values()).sort((a, b) => b.newsCount - a.newsCount)
})

// 股票提及排行
const stockMentions = computed(() => {
  const map = new Map<string, number>()
  for (const news of props.newsItems) {
    for (const code of news.stock_codes) {
      map.set(code, (map.get(code) || 0) + 1)
    }
  }
  return Array.from(map.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([code, count]) => ({ code, count }))
})

const viewMode = ref<'heatmap' | 'ranking'>('heatmap')

// 情绪色（-1红 → 0灰 → 1绿）
const sentimentBg = (score: number) => {
  if (score > 0.15) return `rgba(0, 168, 112, ${Math.min(score * 1.5, 0.8)})`
  if (score < -0.15) return `rgba(213, 73, 65, ${Math.min(Math.abs(score) * 1.5, 0.8)})`
  return 'rgba(139, 139, 139, 0.15)'
}

const sentimentText = (score: number) => {
  if (score > 0.15) return '#fff'
  if (score < -0.15) return '#fff'
  return 'var(--td-text-color-primary)'
}
</script>

<template>
  <div class="sector-heatmap">
    <!-- 切换视图 -->
    <div class="hm-view-switch">
      <t-radio-group v-model="viewMode" variant="default-filled" size="small">
        <t-radio-button value="heatmap">板块热力</t-radio-button>
        <t-radio-button value="ranking">个股热度</t-radio-button>
      </t-radio-group>
    </div>

    <!-- 板块热力视图 -->
    <template v-if="viewMode === 'heatmap'">
      <div class="hm-grid" v-if="sectorData.length > 0">
        <div
          v-for="sector in sectorData"
          :key="sector.name"
          class="hm-cell"
          :style="{
            background: sentimentBg(sector.avgScore),
            color: sentimentText(sector.avgScore),
          }"
          @click="emit('category-filter', sector.name)"
        >
          <div class="hm-cell-label">{{ sector.label }}</div>
          <div class="hm-cell-count">{{ sector.newsCount }}条</div>
          <div class="hm-cell-sentiment">
            <span v-if="sector.posCount" style="color:#00a870">▲{{ sector.posCount }}</span>
            <span v-if="sector.negCount" style="color:#d54941">▼{{ sector.negCount }}</span>
          </div>
        </div>
      </div>
      <t-empty v-else size="small" description="暂无新闻数据" />
    </template>

    <!-- 个股热度排行 -->
    <template v-else>
      <div class="hm-ranking" v-if="stockMentions.length > 0">
        <div
          v-for="(item, idx) in stockMentions"
          :key="item.code"
          class="hm-rank-item"
        >
          <span class="hm-rank-idx" :class="{ 'hm-rank-top': idx < 3 }">{{ idx + 1 }}</span>
          <span class="hm-rank-code">{{ item.code }}</span>
          <t-progress
            :percentage="Math.round((item.count / stockMentions[0].count) * 100)"
            size="small"
            :label="`${item.count}次`"
            class="hm-rank-bar"
          />
        </div>
      </div>
      <t-empty v-else size="small" description="暂无个股提及" />
    </template>
  </div>
</template>

<style scoped>
.sector-heatmap {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  overflow-y: auto;
}

.hm-view-switch {
  display: flex;
}

.hm-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.hm-cell {
  padding: 10px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}

.hm-cell:hover {
  transform: scale(1.03);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}

.hm-cell-label {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.3;
}

.hm-cell-count {
  font-size: 11px;
  opacity: 0.8;
  margin-top: 2px;
}

.hm-cell-sentiment {
  font-size: 10px;
  margin-top: 2px;
  display: flex;
  justify-content: center;
  gap: 6px;
}

.hm-ranking {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hm-rank-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hm-rank-idx {
  width: 20px;
  text-align: center;
  font-size: 12px;
  font-weight: 600;
  color: var(--td-text-color-secondary);
}

.hm-rank-idx.hm-rank-top {
  color: var(--td-brand-color);
}

.hm-rank-code {
  font-size: 12px;
  font-weight: 500;
  width: 80px;
  flex-shrink: 0;
}

.hm-rank-bar {
  flex: 1;
}
</style>
