<script setup lang="ts">
import { computed, ref } from 'vue'
import type { NewsItem } from '@/types/news'

interface Props {
  newsItems: NewsItem[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'news-click', news: NewsItem): void
}>()

// 筛选控件状态
const impactFilter = ref<'all' | 'high' | 'medium'>('all')
const directionFilter = ref<'all' | 'positive' | 'negative' | 'neutral'>('all')

// 有影响评估的新闻
const impactNews = computed(() => {
  let items = props.newsItems.filter(
    n => n.sentiment && n.sentiment.impact_level && n.sentiment.impact_level !== 'low'
  )

  if (impactFilter.value !== 'all') {
    items = items.filter(n => n.sentiment?.impact_level === impactFilter.value)
  }
  if (directionFilter.value !== 'all') {
    items = items.filter(n => n.sentiment?.sentiment === directionFilter.value)
  }

  // 按影响等级(high优先) → 时间排序
  return items.sort((a, b) => {
    const rank = (level: string | undefined) => level === 'high' ? 2 : level === 'medium' ? 1 : 0
    const diff = rank(b.sentiment?.impact_level) - rank(a.sentiment?.impact_level)
    if (diff !== 0) return diff
    return new Date(b.publish_time).getTime() - new Date(a.publish_time).getTime()
  })
})

// 统计
const stats = computed(() => {
  const all = props.newsItems.filter(n => n.sentiment?.impact_level && n.sentiment.impact_level !== 'low')
  return {
    total: all.length,
    high: all.filter(n => n.sentiment?.impact_level === 'high').length,
    positive: all.filter(n => n.sentiment?.sentiment === 'positive').length,
    negative: all.filter(n => n.sentiment?.sentiment === 'negative').length,
  }
})

const impactTheme = (level: string | undefined) => {
  if (level === 'high') return 'danger'
  if (level === 'medium') return 'warning'
  return 'default'
}

const impactLabel = (level: string | undefined) => {
  if (level === 'high') return '高影响'
  if (level === 'medium') return '中影响'
  return '低影响'
}

const directionTheme = (dir: string | undefined) => {
  if (dir === 'positive') return 'success'
  if (dir === 'negative') return 'danger'
  return 'default'
}

const directionLabel = (dir: string | undefined) => {
  if (dir === 'positive') return '利好'
  if (dir === 'negative') return '利空'
  return '中性'
}

const formatTime = (time: string) => {
  const d = new Date(time)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 60) return `${diffMin}分钟前`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour}小时前`
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>

<template>
  <div class="event-impact-panel">
    <!-- 统计概览 -->
    <div class="impact-stats" v-if="stats.total > 0">
      <t-tag theme="primary" variant="light" size="small">
        {{ stats.total }} 条重要事件
      </t-tag>
      <t-tag v-if="stats.high" theme="danger" variant="light" size="small">
        {{ stats.high }} 高影响
      </t-tag>
      <t-tag v-if="stats.positive" theme="success" variant="light" size="small">
        {{ stats.positive }} 利好
      </t-tag>
      <t-tag v-if="stats.negative" theme="danger" variant="outline" size="small">
        {{ stats.negative }} 利空
      </t-tag>
    </div>

    <!-- 筛选行 -->
    <div class="impact-filters">
      <t-radio-group v-model="impactFilter" variant="default-filled" size="small">
        <t-radio-button value="all">全部</t-radio-button>
        <t-radio-button value="high">高影响</t-radio-button>
        <t-radio-button value="medium">中影响</t-radio-button>
      </t-radio-group>
      <t-radio-group v-model="directionFilter" variant="default-filled" size="small">
        <t-radio-button value="all">全部</t-radio-button>
        <t-radio-button value="positive">利好</t-radio-button>
        <t-radio-button value="negative">利空</t-radio-button>
        <t-radio-button value="neutral">中性</t-radio-button>
      </t-radio-group>
    </div>

    <!-- 事件列表 -->
    <div class="impact-list" v-if="impactNews.length > 0">
      <div
        v-for="news in impactNews"
        :key="news.id"
        class="impact-item"
        @click="emit('news-click', news)"
      >
        <div class="impact-badges">
          <t-tag :theme="impactTheme(news.sentiment?.impact_level)" size="small" variant="light">
            {{ impactLabel(news.sentiment?.impact_level) }}
          </t-tag>
          <t-tag :theme="directionTheme(news.sentiment?.sentiment)" size="small" variant="outline">
            {{ directionLabel(news.sentiment?.sentiment) }}
          </t-tag>
        </div>
        <div class="impact-title">{{ news.title }}</div>
        <div class="impact-meta">
          <span class="impact-time">{{ formatTime(news.publish_time) }}</span>
          <span v-if="news.stock_codes.length" class="impact-stocks">
            <t-tag v-for="code in news.stock_codes.slice(0, 3)" :key="code" size="small" variant="outline">
              {{ code }}
            </t-tag>
          </span>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <t-empty v-else size="small" description="当前页面无重要事件">
      <template #image>
        <div style="font-size: 32px">📰</div>
      </template>
    </t-empty>
  </div>
</template>

<style scoped>
.event-impact-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  overflow-y: auto;
}

.impact-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.impact-filters {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.impact-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.impact-item {
  padding: 10px;
  border-radius: 6px;
  border: 1px solid var(--td-component-stroke);
  cursor: pointer;
  transition: all 0.2s;
}

.impact-item:hover {
  border-color: var(--td-brand-color);
  background: var(--td-brand-color-light);
}

.impact-badges {
  display: flex;
  gap: 4px;
  margin-bottom: 6px;
}

.impact-title {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.4;
  color: var(--td-text-color-primary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.impact-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
}

.impact-stocks {
  display: flex;
  gap: 4px;
}
</style>
