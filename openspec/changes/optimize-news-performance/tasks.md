# Tasks: optimize-news-performance

## Task List

### Phase 1: 后端情绪分析解耦（最大性能收益）

- [ ] **T1**: 修改 `service.py` — 在 `get_market_news()` 中移除同步的 `analyze_news_sentiment()` 调用
  - 从文件缓存读取新闻时，直接使用已存储的 sentiment 字段
  - 从外部 API 获取新闻后，先返回数据再异步分析情绪
  - 使用 `asyncio.create_task()` 在后台执行情绪分析
  - **验证**：调用 `/api/news/list` 响应时间从 5s+ 降到 1s 内

- [ ] **T2**: 修改 `service.py` — 在 `get_news_by_stock()` 中同样解耦情绪分析
  - 跳过已有 sentiment 字段的新闻
  - 仅对 `sentiment is None` 的新闻异步触发分析
  - **验证**：股票新闻接口响应时间显著降低

- [ ] **T3**: 修改 `storage.py` — 确保保存新闻时持久化 sentiment 字段
  - `save_news()` 方法在保存新闻 JSON 时包含 sentiment 数据
  - `get_latest_news()` 方法读取时自动加载已有 sentiment
  - **验证**：重启服务后已分析的新闻仍带有情绪数据

- [ ] **T4**: 修改 `service.py` — 新增后台情绪分析任务方法
  - 创建 `_background_analyze_sentiment()` 异步方法
  - 过滤掉已有 sentiment 的新闻，仅分析缺失的
  - 分析完成后通过 storage 持久化结果
  - **验证**：后台任务正常完成，结果持久化到文件

### Phase 2: 前端性能优化

- [ ] **T5**: 修改 `stores/news.ts` — 接入前端缓存层 `NewsCacheManager`
  - 在 `fetchMarketNews` 中先检查 `newsCache.get()` 缓存
  - 缓存命中时直接使用缓存数据，跳过 API 调用
  - API 成功响应后写入缓存 `newsCache.set()`
  - **验证**：短时间内重复加载新闻页面，第二次无 HTTP 请求

- [ ] **T6**: 修改 `NewsListPanel.vue` — 添加骨架屏超时降级
  - 设置骨架屏最大显示时间 10 秒
  - 超时后显示"加载超时，点击重试"提示
  - **验证**：网络慢时骨架屏不会无限显示

- [ ] **T7**: 修改 `NewsItemCard.vue` — sentiment 为 null 时优雅降级
  - 当 `sentiment` 字段为 null 时不显示情绪标签（而非显示错误）
  - **验证**：无 sentiment 的新闻卡片正常渲染，无报错

### Phase 3: 初始加载优化

- [ ] **T8**: 修改 `NewsView.vue` — 避免重复请求
  - 优化 `fetchMarketNews` 与 `fetchHotTopics` 的并行调用
  - **验证**：初始加载时后端日志只出现一次新闻获取调用

## Dependencies

- T1 ↔ T3（情绪分析解耦与存储持久化需配合）
- T1 → T4（后台任务依赖主路径解耦）
- T7 依赖 T1（后端可能返回 null sentiment）
- 其余任务互不依赖
