# Design: 新闻资讯前端页面技术设计

## Context

本设计基于已完成的 `add-news-analyst-agent` 提案，为新闻分析功能提供完整的前端用户界面。

**依赖提案**:
- [add-news-analyst-agent](../add-news-analyst-agent/) - 提供后端新闻 API 和 Agent 功能

**技术约束**:
- 遵循现有 Vue 3 + TDesign 前端架构
- 复用现有组件和设计模式
- 保持与其他页面的一致性

## Goals / Non-Goals

### Goals
- 提供直观的新闻浏览和筛选界面
- 实现新闻情绪分析可视化
- 支持个性化新闻推荐和关注管理
- 无缝集成到现有导航和页面体系

### Non-Goals
- 新闻内容编辑和发布功能
- 实时推送和通知系统
- 移动端专门优化
- 新闻评论和社交功能

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend Architecture                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    NewsView.vue                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │ NewsFilter  │  │ NewsList    │  │ HotTopics   │     │   │
│  │  │ Panel.vue   │  │ Panel.vue   │  │ Panel.vue   │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  │  ┌─────────────┐  ┌─────────────┐                      │   │
│  │  │ NewsDetail  │  │ Sentiment   │                      │   │
│  │  │ Dialog.vue  │  │ Chart.vue   │                      │   │
│  │  └─────────────┘  └─────────────┘                      │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      State Management                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   news.ts (Pinia Store)                  │   │
│  │  - newsItems: NewsItem[]                                │   │
│  │  - filters: NewsFilters                                 │   │
│  │  - hotTopics: HotTopic[]                                │   │
│  │  - userPreferences: UserPreferences                     │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   news.ts (API Client)                   │   │
│  │  - getNewsByStock()                                     │   │
│  │  - getMarketNews()                                      │   │
│  │  - getHotTopics()                                       │   │
│  │  - analyzeSentiment()                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend APIs                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              NewsAnalystAgent + NewsService              │   │
│  │  GET /api/news/stock/{code}                             │   │
│  │  GET /api/news/market                                   │   │
│  │  GET /api/news/hot-topics                               │   │
│  │  POST /api/news/analyze-sentiment                       │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Decisions

### Decision 1: 页面布局设计

**选择**: 三栏布局 - 左侧筛选面板 + 中间新闻列表 + 右侧热点面板

**Alternatives considered**:
1. 单栏布局 - 简单但信息密度低
2. 双栏布局 - 缺乏热点展示空间
3. Tab 切换布局 - 增加操作步骤

**Rationale**:
- 参考 MarketView 和 ScreenerView 的成功布局模式
- 左侧筛选面板便于快速筛选，符合用户习惯
- 右侧热点面板提供额外价值，增强用户粘性
- 中间主内容区域最大化新闻展示空间

### Decision 2: 新闻列表展示方式

**选择**: 卡片式列表 + 虚拟滚动

**Alternatives considered**:
1. 表格式展示 - 信息密度高但可读性差
2. 瀑布流布局 - 视觉效果好但不适合文本内容
3. 分页加载 - 用户体验不如无限滚动

**Rationale**:
- 卡片式布局便于展示新闻标题、来源、时间、情绪等信息
- 虚拟滚动解决大量新闻数据的性能问题
- 支持实时更新和无限滚动，提升用户体验

### Decision 3: 情绪分析可视化

**选择**: ECharts 实现饼图 + 折线图组合

**Rationale**:
- 复用现有 ECharts 依赖，保持技术栈一致性
- 饼图展示情绪分布，折线图展示情绪趋势
- 与 MarketView 的图表风格保持一致

## Data Models

```typescript
// 新闻条目接口（与后端保持一致）
interface NewsItem {
  id: string
  title: string
  content: string
  source: string
  publish_time: string
  stock_codes: string[]
  category: string
  url?: string
  sentiment?: NewsSentiment
}

// 情绪分析结果
interface NewsSentiment {
  news_id: string
  sentiment: 'positive' | 'negative' | 'neutral'
  score: number // -1.0 到 1.0
  reasoning: string
  impact_level: 'high' | 'medium' | 'low'
}

// 热点话题
interface HotTopic {
  topic: string
  keywords: string[]
  heat_score: number
  related_stocks: string[]
  news_count: number
}

// 筛选条件
interface NewsFilters {
  stock_codes: string[]
  date_range: [string, string]
  categories: string[]
  sentiments: string[]
  sources: string[]
  keywords: string
}

// 用户偏好设置
interface UserPreferences {
  followed_stocks: string[]
  default_filters: NewsFilters
  notification_settings: {
    hot_topics: boolean
    followed_stocks: boolean
    sentiment_alerts: boolean
  }
}
```

## Component Specifications

### NewsView.vue (主页面)
```vue
<template>
  <div class="news-view">
    <t-layout>
      <t-aside width="280px">
        <NewsFilterPanel 
          v-model:filters="filters"
          @filter-change="handleFilterChange"
        />
      </t-aside>
      
      <t-content>
        <NewsListPanel 
          :news-items="filteredNews"
          :loading="loading"
          @load-more="loadMoreNews"
          @news-click="showNewsDetail"
        />
      </t-content>
      
      <t-aside width="320px">
        <HotTopicsPanel 
          :hot-topics="hotTopics"
          @topic-click="handleTopicClick"
        />
        <SentimentChart 
          :sentiment-data="sentimentStats"
        />
      </t-aside>
    </t-layout>
    
    <NewsDetailDialog 
      v-model:visible="detailVisible"
      :news-item="selectedNews"
    />
  </div>
</template>
```

### NewsFilterPanel.vue (筛选面板)
```vue
<template>
  <div class="news-filter-panel">
    <t-card title="筛选条件">
      <!-- 股票代码筛选 -->
      <t-form-item label="股票代码">
        <StockSelector 
          v-model="filters.stock_codes"
          multiple
          placeholder="输入股票代码或名称"
        />
      </t-form-item>
      
      <!-- 时间范围筛选 -->
      <t-form-item label="时间范围">
        <t-date-range-picker 
          v-model="filters.date_range"
          format="YYYY-MM-DD"
        />
      </t-form-item>
      
      <!-- 新闻类型筛选 -->
      <t-form-item label="新闻类型">
        <t-checkbox-group v-model="filters.categories">
          <t-checkbox value="announcement">公告</t-checkbox>
          <t-checkbox value="news">快讯</t-checkbox>
          <t-checkbox value="analysis">分析</t-checkbox>
        </t-checkbox-group>
      </t-form-item>
      
      <!-- 情绪筛选 -->
      <t-form-item label="情绪倾向">
        <t-radio-group v-model="filters.sentiment">
          <t-radio value="">全部</t-radio>
          <t-radio value="positive">利好</t-radio>
          <t-radio value="negative">利空</t-radio>
          <t-radio value="neutral">中性</t-radio>
        </t-radio-group>
      </t-form-item>
    </t-card>
  </div>
</template>
```

### NewsListPanel.vue (新闻列表)
```vue
<template>
  <div class="news-list-panel">
    <div class="news-header">
      <t-space>
        <t-button @click="refreshNews">
          <template #icon><RefreshIcon /></template>
          刷新
        </t-button>
        <t-select v-model="sortBy" placeholder="排序方式">
          <t-option value="time">按时间</t-option>
          <t-option value="heat">按热度</t-option>
          <t-option value="sentiment">按情绪</t-option>
        </t-select>
      </t-space>
    </div>
    
    <t-list 
      :data="newsItems"
      :loading="loading"
      @scroll-to-bottom="loadMore"
    >
      <template #default="{ data }">
        <NewsItemCard 
          :news-item="data"
          @click="$emit('news-click', data)"
        />
      </template>
    </t-list>
  </div>
</template>
```

### NewsItemCard.vue (新闻卡片)
```vue
<template>
  <t-card 
    class="news-item-card"
    hover
    @click="$emit('click')"
  >
    <div class="news-header">
      <div class="news-title">
        <SentimentTag :sentiment="newsItem.sentiment" />
        {{ newsItem.title }}
      </div>
      <div class="news-meta">
        <t-tag size="small">{{ newsItem.source }}</t-tag>
        <span class="news-time">{{ formatTime(newsItem.publish_time) }}</span>
      </div>
    </div>
    
    <div class="news-content">
      {{ truncateContent(newsItem.content) }}
    </div>
    
    <div class="news-footer">
      <t-space>
        <t-tag 
          v-for="code in newsItem.stock_codes" 
          :key="code"
          size="small"
          variant="outline"
        >
          {{ code }}
        </t-tag>
      </t-space>
      
      <div class="news-actions">
        <t-button size="small" variant="text">
          <template #icon><ShareIcon /></template>
          分享
        </t-button>
        <t-button size="small" variant="text">
          <template #icon><StarIcon /></template>
          收藏
        </t-button>
      </div>
    </div>
  </t-card>
</template>
```

## API Integration

### news.ts (API 封装)
```typescript
import { request } from '@/utils/request'

export interface NewsAPI {
  // 获取股票相关新闻
  getNewsByStock(params: {
    stock_code: string
    days?: number
    limit?: number
  }): Promise<NewsItem[]>
  
  // 获取市场新闻
  getMarketNews(params: {
    category?: string
    limit?: number
    offset?: number
  }): Promise<NewsItem[]>
  
  // 获取热点话题
  getHotTopics(params: {
    limit?: number
  }): Promise<HotTopic[]>
  
  // 分析新闻情绪
  analyzeSentiment(params: {
    news_items: NewsItem[]
    stock_context?: string
  }): Promise<NewsSentiment[]>
  
  // 搜索新闻
  searchNews(params: {
    keyword: string
    filters?: NewsFilters
    limit?: number
  }): Promise<NewsItem[]>
}

export const newsAPI: NewsAPI = {
  getNewsByStock: (params) => 
    request.get(`/api/news/stock/${params.stock_code}`, { params }),
    
  getMarketNews: (params) => 
    request.get('/api/news/market', { params }),
    
  getHotTopics: (params) => 
    request.get('/api/news/hot-topics', { params }),
    
  analyzeSentiment: (data) => 
    request.post('/api/news/analyze-sentiment', data),
    
  searchNews: (params) => 
    request.get('/api/news/search', { params })
}
```

## State Management

### news.ts (Pinia Store)
```typescript
import { defineStore } from 'pinia'
import { newsAPI } from '@/api/news'

export const useNewsStore = defineStore('news', () => {
  // 状态
  const newsItems = ref<NewsItem[]>([])
  const hotTopics = ref<HotTopic[]>([])
  const filters = ref<NewsFilters>({
    stock_codes: [],
    date_range: ['', ''],
    categories: [],
    sentiments: [],
    sources: [],
    keywords: ''
  })
  const loading = ref(false)
  const hasMore = ref(true)
  
  // 计算属性
  const filteredNews = computed(() => {
    return newsItems.value.filter(item => {
      // 应用筛选逻辑
      if (filters.value.stock_codes.length > 0) {
        const hasMatchingStock = item.stock_codes.some(code => 
          filters.value.stock_codes.includes(code)
        )
        if (!hasMatchingStock) return false
      }
      
      if (filters.value.sentiments.length > 0) {
        if (!item.sentiment || !filters.value.sentiments.includes(item.sentiment.sentiment)) {
          return false
        }
      }
      
      return true
    })
  })
  
  const sentimentStats = computed(() => {
    const stats = { positive: 0, negative: 0, neutral: 0 }
    filteredNews.value.forEach(item => {
      if (item.sentiment) {
        stats[item.sentiment.sentiment]++
      }
    })
    return stats
  })
  
  // 操作方法
  const fetchMarketNews = async (params?: any) => {
    loading.value = true
    try {
      const data = await newsAPI.getMarketNews(params)
      if (params?.offset === 0) {
        newsItems.value = data
      } else {
        newsItems.value.push(...data)
      }
      hasMore.value = data.length >= (params?.limit || 20)
    } finally {
      loading.value = false
    }
  }
  
  const fetchHotTopics = async () => {
    const data = await newsAPI.getHotTopics({ limit: 10 })
    hotTopics.value = data
  }
  
  const searchNews = async (keyword: string) => {
    loading.value = true
    try {
      const data = await newsAPI.searchNews({
        keyword,
        filters: filters.value,
        limit: 50
      })
      newsItems.value = data
    } finally {
      loading.value = false
    }
  }
  
  return {
    // 状态
    newsItems,
    hotTopics,
    filters,
    loading,
    hasMore,
    
    // 计算属性
    filteredNews,
    sentimentStats,
    
    // 方法
    fetchMarketNews,
    fetchHotTopics,
    searchNews
  }
})
```

## Risks / Trade-offs

### Risk 1: 性能问题
- **风险**: 大量新闻数据可能导致页面卡顿
- **缓解**: 使用虚拟滚动、分页加载、数据缓存

### Risk 2: 实时性要求
- **风险**: 用户期望新闻实时更新
- **缓解**: 定时刷新、WebSocket 推送（后续扩展）

### Risk 3: 移动端适配
- **风险**: 三栏布局在移动端体验不佳
- **缓解**: 响应式设计、移动端折叠侧边栏

## Migration Plan

1. **Phase 1**: 实现基础页面结构和路由
2. **Phase 2**: 实现新闻列表和筛选功能
3. **Phase 3**: 添加情绪分析可视化
4. **Phase 4**: 实现热点话题和个性化功能
5. **Phase 5**: 性能优化和用户体验改进

无需数据迁移，纯前端功能扩展。

## Open Questions

1. **缓存策略**: 新闻数据的缓存时间和更新策略？
2. **个性化程度**: 用户偏好设置的复杂度控制？
3. **移动端优先级**: 是否需要在初版中考虑移动端适配？