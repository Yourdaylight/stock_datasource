# Design: optimize-news-performance

## Architecture Overview

#### 当前新闻请求的数据流（慢路径）：
```
前端请求 → 后端 get_market_news()
         → 读缓存/调外部API获取新闻
         → 【阻塞】analyze_news_sentiment() 调用 LLM
         → 返回带情绪标注的新闻
```

#### 优化后的数据流（快路径）：
```
前端请求 → 前端缓存命中? → 直接返回
         → 后端 get_market_news()
         → 读缓存/调外部API获取新闻
         → 从存储中加载已有情绪结果（毫秒级）
         → 立即返回新闻数据（sentiment 可能部分为 null）
         → 【后台】对缺少 sentiment 的新闻异步触发情绪分析并持久化
```

## 核心设计决策

### 1. 情绪分析解耦方案

**方案选择**：后台异步 + 存储持久化

在 `NewsService.get_market_news()` 中：
- 移除同步的 `analyze_news_sentiment()` 调用
- 从 storage 中读取已有的情绪分析结果，合并到新闻数据中
- 对缺少情绪的新闻，使用 `asyncio.create_task()` 在后台异步分析并保存

直接在新闻数据中持久化 sentiment 字段，因为：
- 不引入新的存储文件
- 读取新闻时自动获得情绪数据
- 实现最简单

### 2. 前端缓存接入方案

`newsCache.ts` 已实现 `NewsCacheManager`，提供 `get(key)` / `set(key, data, ttl)` 方法。

接入点选择：**在 `stores/news.ts` 层接入**
- 在 fetchMarketNews 前检查缓存
- 缓存命中直接返回
- 缓存未命中则调用后端，成功后写入缓存
- 缓存 key 基于请求参数生成

### 3. 骨架屏超时处理

在 `NewsListPanel.vue` 中添加加载超时逻辑：
- 默认骨架屏显示最多 10 秒
- 超时后切换为错误/空状态提示，提供重试按钮

### 4. 情绪标签降级显示

当新闻 `sentiment` 为 null 时，卡片不显示情绪标签区域，避免误导与报错。

## 不变量

- 新闻页面布局结构保持不变
- 后端 API 接口签名不变
- 情绪分析功能保留，仅改变执行时机
- 缓存层级体系不变，仅激活前端缓存层
