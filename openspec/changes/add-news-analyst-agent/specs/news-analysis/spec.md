# news-analysis Specification

## ADDED Requirements

### Requirement: News Data Retrieval
系统 SHALL 能够获取和展示 A 股市场相关的财经新闻和上市公司公告。

#### Scenario: 获取股票相关新闻
- **WHEN** 用户请求特定股票的新闻
- **THEN** 系统返回该股票近期相关的新闻列表
- **AND** 每条新闻包含标题、内容摘要、来源、发布时间
- **AND** 默认返回最近 7 天的新闻，最多 20 条

#### Scenario: 获取市场整体新闻
- **WHEN** 用户请求市场新闻
- **THEN** 系统返回最新的财经快讯和市场动态
- **AND** 支持按分类筛选（公告/快讯/分析）
- **AND** 新闻按发布时间倒序排列

#### Scenario: 新闻数据缓存
- **WHEN** 系统频繁请求相同的新闻数据
- **THEN** 系统使用 Redis 缓存减少外部 API 调用
- **AND** 快讯类新闻缓存 TTL 为 5 分钟
- **AND** 公告类新闻缓存 TTL 为 1 小时

### Requirement: News Sentiment Analysis
系统 SHALL 能够分析新闻内容的情绪倾向，判断对股价的潜在影响。

#### Scenario: 单条新闻情绪分析
- **WHEN** 用户请求分析特定新闻的情绪
- **THEN** 系统返回情绪标签（利好/利空/中性）
- **AND** 返回情绪分数（-1.0 到 1.0）
- **AND** 返回分析理由说明
- **AND** 返回影响程度（高/中/低）

#### Scenario: 批量新闻情绪分析
- **WHEN** 用户请求分析多条新闻
- **THEN** 系统批量处理并返回每条新闻的情绪分析结果
- **AND** 生成整体情绪总结
- **AND** 单次请求最多分析 10 条新闻

#### Scenario: 股票背景关联分析
- **WHEN** 提供股票背景信息进行情绪分析
- **THEN** 系统结合股票当前状态评估新闻影响
- **AND** 返回针对该股票的定制化分析

### Requirement: Hot Topic Tracking
系统 SHALL 能够追踪和展示当前市场热点话题。

#### Scenario: 获取市场热点
- **WHEN** 用户请求查看市场热点
- **THEN** 系统返回当前热门话题列表
- **AND** 每个话题包含关键词、热度分数、相关新闻数量
- **AND** 展示与热点相关的股票列表

#### Scenario: 热点趋势分析
- **WHEN** 用户查看热点话题详情
- **THEN** 系统展示该话题的相关新闻
- **AND** 提供话题热度趋势
- **AND** 关联分析受影响的行业板块

### Requirement: AI News Summary
系统 SHALL 能够使用 AI 生成新闻摘要和要点分析。

#### Scenario: 新闻列表摘要
- **WHEN** 用户请求对多条新闻生成摘要
- **THEN** 系统使用 LLM 提取关键信息
- **AND** 生成结构化的要点列表
- **AND** 标注重要事件和潜在影响

#### Scenario: 针对性摘要
- **WHEN** 用户指定关注重点（如"政策影响"或"业绩相关"）
- **THEN** 系统生成针对该重点的定制化摘要
- **AND** 过滤无关信息，突出相关内容

### Requirement: NewsAnalystAgent Integration
系统 SHALL 提供专业的新闻分析 Agent，集成到多 Agent 系统中。

#### Scenario: Agent 意图识别
- **WHEN** 用户输入新闻相关查询
- **THEN** OrchestratorAgent 正确识别意图并路由到 NewsAnalystAgent
- **AND** 识别关键词包括：新闻、资讯、公告、热点、舆情等

#### Scenario: Agent 工具调用
- **WHEN** NewsAnalystAgent 处理用户请求
- **THEN** Agent 能够调用以下工具：
  - get_news_by_stock: 获取股票新闻
  - get_market_news: 获取市场新闻
  - analyze_news_sentiment: 情绪分析
  - get_hot_topics: 热点追踪
  - summarize_news: 新闻摘要
- **AND** 工具调用结果正确格式化返回给用户

#### Scenario: 多轮对话支持
- **WHEN** 用户进行新闻相关的多轮对话
- **THEN** Agent 保持上下文连贯
- **AND** 能够基于前文进行追问分析

### Requirement: News Data Sources
系统 SHALL 集成多个新闻数据源，提供丰富的新闻内容。

#### Scenario: Tushare 公告集成
- **WHEN** 系统需要获取上市公司公告
- **THEN** 通过 Tushare API 获取公告数据
- **AND** 支持按股票代码、日期范围查询
- **AND** 正确处理 API 限流和错误

#### Scenario: Sina 财经新闻集成
- **WHEN** 系统需要获取财经新闻
- **THEN** 通过 Sina 财经 API 获取新闻数据
- **AND** 支持关键词搜索
- **AND** 实现请求重试和降级机制

#### Scenario: 数据源优雅降级
- **WHEN** 某个数据源不可用
- **THEN** 系统自动切换到备用数据源
- **AND** 返回可用的数据并标注来源
- **AND** 记录错误日志供排查

### Requirement: News API Endpoints
系统 SHALL 提供 HTTP API 供前端和外部调用新闻功能。

#### Scenario: 股票新闻 API
- **WHEN** 调用 `GET /api/news/stock/{code}` 
- **THEN** 返回指定股票的相关新闻
- **AND** 支持 `days` 和 `limit` 查询参数
- **AND** 返回格式为 JSON

#### Scenario: 市场新闻 API
- **WHEN** 调用 `GET /api/news/market`
- **THEN** 返回市场整体财经新闻
- **AND** 支持 `category` 分类筛选
- **AND** 返回格式为 JSON

#### Scenario: 热点话题 API
- **WHEN** 调用 `GET /api/news/hot-topics`
- **THEN** 返回当前市场热点话题列表
- **AND** 包含热度排名和相关股票
- **AND** 返回格式为 JSON

#### Scenario: 情绪分析 API
- **WHEN** 调用 `POST /api/news/analyze`
- **THEN** 对提交的新闻内容进行情绪分析
- **AND** 返回情绪标签、分数和分析理由
- **AND** 返回格式为 JSON
