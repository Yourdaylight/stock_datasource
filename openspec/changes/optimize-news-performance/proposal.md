# Proposal: optimize-news-performance

## Problem Statement

**新闻资讯模块加载速度严重缓慢**：用户打开页面后长时间显示骨架屏（skeleton），新闻条数显示"共0条"，体验极差。

### 根因分析

1. **情绪分析阻塞主请求路径（最严重）**：`service.py` 中 `get_market_news()` 每次从缓存读取新闻数据后，仍会对**所有新闻**调用 `analyze_news_sentiment()`（LLM API 调用），导致即使有缓存也需要等待数秒的 LLM 响应。
2. **热点话题级联调用**：`get_hot_topics()` 内部先调用 `get_market_news(limit=50)` 获取 50 条新闻（触发情绪分析），再调用 LLM 提取热点 — 串行两次 LLM 调用。
3. **前端缓存层已实现但未接入**：`newsCache.ts` 已实现完整的内存缓存管理器，但 `stores/news.ts` 和 `api/news.ts` 中并未使用，每次都直接打到后端。
4. **初始加载并行请求中存在重复调用**：`NewsView.vue` 的 `fetchMarketNews` 和 `fetchHotTopics` 内部都会调用 `get_market_news()`，首次冷启动时触发两次外部 API + 两次情绪分析。

## Proposed Solution

### 策略：只做性能优化（不改页面结构）

#### 一、后端性能优化

1. **情绪分析异步化**：从 `get_market_news()` 主路径中移除情绪分析调用
2. **情绪结果持久化**：将情绪分析结果保存到本地文件存储中
3. **热点话题缓存增强**：延长热点话题缓存 TTL

#### 二、前端性能优化

4. **启用前端缓存层**：在 `stores/news.ts` 中接入已有的 `NewsCacheManager`
5. **骨架屏超时降级**：增加骨架屏最大显示时间
6. **优化初始加载**：避免重复请求
7. **情绪标签降级显示**：sentiment 为 null 时不显示标签

## Impact

- **前端**：修改 `stores/news.ts`、`api/news.ts`、`NewsListPanel.vue`、`NewsItemCard.vue`
- **后端**：修改 `src/stock_datasource/modules/news/service.py`、`storage.py`
- **预计效果**：新闻列表首次加载时间从 5-10s+ 降低到 1-2s 内

## Risks

- 情绪分析异步化后，部分新闻初次展示时无情绪标签（可接受的折中）
- 前端缓存可能导致短时间内数据不够新（5 分钟 TTL，对新闻场景可接受）
