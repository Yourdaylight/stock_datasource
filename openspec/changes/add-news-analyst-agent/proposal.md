# Change: 新增新闻分析师 Agent（NewsAnalystAgent）

## Why

当前系统有 13 个专业 Agent（MarketAgent、ReportAgent、ScreenerAgent 等），但缺乏对市场新闻和资讯的分析能力。参考 TradingAgents 框架中的新闻分析师角色，市场新闻是影响股价走势的重要因素，投资者需要：

1. **及时获取财经新闻** - 了解影响股票的政策、公告、行业动态
2. **新闻情绪分析** - 判断新闻对股价的潜在影响（利好/利空/中性）
3. **新闻与股票关联** - 快速定位与特定股票相关的新闻
4. **市场热点追踪** - 发现当前市场关注的热点主题

这是实现完整智能投资助手的关键能力，也是 TradingAgents 多智能体交易框架的核心组件之一。

## What Changes

### 后端
- **新增 NewsAnalystAgent** - 基于 LangGraph 框架的新闻分析专业 Agent
- **新增 news 模块** - 提供新闻数据获取、情绪分析、热点追踪等服务
- **新增新闻数据源插件** - 集成财经新闻 API（如 Tushare 公告数据、Sina 财经新闻等）
- **集成到 OrchestratorAgent** - 支持自然语言路由到 NewsAnalystAgent

### Agent 工具
- `get_news_by_stock` - 获取指定股票相关新闻
- `get_market_news` - 获取市场整体新闻
- `analyze_news_sentiment` - 分析新闻情绪（利好/利空/中性）
- `get_hot_topics` - 获取当前市场热点主题
- `summarize_news` - AI 生成新闻摘要

### 前端（可选，后续扩展）
- 新增新闻资讯页面组件
- AI 对话中支持新闻查询

## Impact

- **Affected specs**: 新增 `news-analysis` capability
- **Affected code**:
  - `src/stock_datasource/agents/` - 新增 news_analyst_agent.py
  - `src/stock_datasource/modules/` - 新增 news/ 模块
  - `src/stock_datasource/plugins/` - 新增新闻数据源插件
  - `src/stock_datasource/agents/orchestrator.py` - 注册新 Agent

## Out of Scope

- 实时推送新闻订阅（可后续扩展）
- 社交媒体舆情分析（如微博、雪球等，可后续扩展）
- 新闻 embedding 向量化检索（可后续扩展）

## Data Sources

参考可用的新闻数据源：
1. **Tushare 公告数据** - 上市公司公告（已有 Tushare Token）
2. **Sina 财经** - 免费财经新闻 API
3. **东方财富** - 财经快讯和新闻
4. **第三方服务** - 如 FinnHub（需申请 API Key）

初始实现优先使用 Tushare 公告数据 + Sina 财经新闻，降低外部依赖。
