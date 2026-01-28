# Tasks: 新增新闻分析师 Agent

## 1. 基础架构搭建

- [x] 1.1 创建 news 模块目录结构
  - `src/stock_datasource/modules/news/__init__.py`
  - `src/stock_datasource/modules/news/service.py`
  - `src/stock_datasource/modules/news/router.py`
  - `src/stock_datasource/modules/news/schemas.py`

- [x] 1.2 定义新闻数据模型
  - NewsItem（新闻基础结构）
  - NewsSentiment（情绪分析结果）
  - HotTopic（热点主题）

## 2. 新闻数据源集成

- [x] 2.1 集成 Tushare 公告数据
  - 使用 `anns` 接口获取上市公司公告
  - 在 NewsService 中直接实现（无需单独插件）
  
- [x] 2.2 集成 Sina 财经新闻
  - 实现 Sina 新闻 API 爬取服务
  - 支持按股票代码、关键词查询

- [x] 2.3 新闻数据缓存策略
  - 使用 Redis 缓存热门新闻
  - 设置合理的缓存过期时间（快讯5分钟，公告1小时，热点10分钟）

## 3. 新闻服务实现

- [x] 3.1 实现 NewsService 核心服务
  - `get_news_by_stock(stock_code, days=7)` - 获取股票相关新闻
  - `get_market_news(category, limit=20)` - 获取市场新闻
  - `search_news(keyword, limit=20)` - 关键词搜索新闻

- [x] 3.2 实现新闻情绪分析服务
  - 使用 LLM 分析新闻情绪
  - 返回利好/利空/中性标签
  - 返回情绪分数（-1 到 1）
  - 包含规则降级方案

- [x] 3.3 实现热点话题服务
  - 分析最近新闻关键词
  - 提取市场热点主题
  - 使用 LLM 提取热点，包含规则降级方案

## 4. NewsAnalystAgent 实现

- [x] 4.1 创建 NewsAnalystAgent 类
  - 继承 `LangGraphAgent` 基类
  - 配置 Agent 名称和描述
  - 设置合适的 temperature (0.5)

- [x] 4.2 实现 Agent 工具函数
  - `get_news_by_stock` - 获取股票新闻
  - `get_market_news` - 获取市场新闻
  - `analyze_news_sentiment` - 情绪分析
  - `get_hot_topics` - 热点追踪
  - `summarize_news` - 新闻摘要

- [x] 4.3 编写 Agent System Prompt
  - 定义新闻分析师角色
  - 说明可用工具
  - 指导分析逻辑

## 5. 集成到编排器

- [x] 5.1 在 OrchestratorAgent 中注册 NewsAnalystAgent
  - Orchestrator 使用动态发现机制，无需手动注册
  - Agent 命名遵循 `*_agent.py` 规范，自动被发现

- [x] 5.2 更新 agents/__init__.py 导出
  - 添加 `NewsAnalystAgent` 和 `get_news_analyst_agent` 导出

## 6. HTTP API 路由

- [x] 6.1 创建 news router
  - `GET /api/news/stock/{code}` - 获取股票新闻
  - `GET /api/news/market` - 获取市场新闻
  - `GET /api/news/hot-topics` - 获取热点
  - `POST /api/news/analyze-sentiment` - 情绪分析
  - `POST /api/news/summarize` - 新闻摘要
  - `GET /api/news/search` - 搜索新闻

- [x] 6.2 注册路由到 main app
  - 更新 modules/__init__.py 添加 news router

## 7. 测试

- [ ] 7.1 编写单元测试
  - 测试新闻获取服务
  - 测试情绪分析功能
  - 测试 Agent 工具调用

- [ ] 7.2 编写集成测试
  - 测试 Agent 端到端流程
  - 测试与 Orchestrator 的路由

- [ ] 7.3 手动测试验证
  - 通过 AI 对话测试新闻查询
  - 验证情绪分析准确性

## 8. 文档和示例

- [ ] 8.1 更新 README 添加 NewsAnalystAgent 说明
- [ ] 8.2 添加使用示例（自然语言查询示例）

## Dependencies

- 任务 4 依赖任务 1、2、3
- 任务 5 依赖任务 4
- 任务 6 依赖任务 3
- 任务 7 依赖任务 4、5、6

## Parallelizable Work

- 任务 2.1 和 2.2 可并行（不同数据源集成）
- 任务 3.1、3.2、3.3 可并行（不同服务功能）
- 任务 6 和任务 5 可并行

## Implementation Notes

### 已完成实现的文件：
1. `src/stock_datasource/modules/news/__init__.py` - 模块入口
2. `src/stock_datasource/modules/news/schemas.py` - 数据模型定义
3. `src/stock_datasource/modules/news/service.py` - 核心服务实现
4. `src/stock_datasource/modules/news/router.py` - HTTP API 路由
5. `src/stock_datasource/agents/news_analyst_agent.py` - NewsAnalystAgent 实现

### 数据源说明：
- **Tushare 公告**：通过 `anns` 接口获取上市公司公告，需要较高权限
- **Sina 财经**：通过公开 API 获取财经新闻，无需额外配置

### 缓存策略：
- 快讯缓存 TTL：5 分钟
- 公告缓存 TTL：1 小时
- 热点话题缓存 TTL：10 分钟
