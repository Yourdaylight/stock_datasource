# Design: 新闻分析师 Agent 技术设计

## Context

本设计基于 TradingAgents 多智能体交易框架中的新闻分析师角色，为 A 股赛博操盘手平台添加新闻分析能力。

**参考实现**:
- [TradingAgents](https://github.com/TauricResearch/TradingAgents) - MIT 多智能体交易框架
- [FinanceNews-MCP](https://github.com/guangxiangdebizi/FinanceNews-MCP) - 财经新闻 MCP 服务

**约束**:
- 复用现有 LangGraph Agent 架构
- 优先使用已有的 Tushare 数据源
- 避免引入过多外部依赖

## Goals / Non-Goals

### Goals
- 提供 A 股市场新闻获取能力
- 支持新闻情绪分析（利好/利空/中性）
- 支持股票关联新闻查询
- 无缝集成到现有 Agent 编排系统

### Non-Goals
- 实时新闻推送（WebSocket）
- 社交媒体舆情分析（微博、雪球）
- 新闻向量化检索（Embedding）
- 历史新闻大规模存储

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     OrchestratorAgent                            │
│    "查看茅台最近的新闻" → 路由到 NewsAnalystAgent               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     NewsAnalystAgent                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Tools:                                                   │   │
│  │  - get_news_by_stock    获取股票相关新闻                  │   │
│  │  - get_market_news      获取市场整体新闻                  │   │
│  │  - analyze_sentiment    分析新闻情绪                      │   │
│  │  - get_hot_topics       获取市场热点                      │   │
│  │  - summarize_news       生成新闻摘要                      │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       NewsService                                │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│  │ Announcement  │  │   SinaNews    │  │  HotTopics    │       │
│  │   Service     │  │   Service     │  │   Service     │       │
│  └───────────────┘  └───────────────┘  └───────────────┘       │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│   Tushare     │     │  Sina API     │     │    Redis      │
│   公告数据    │     │  财经新闻     │     │    缓存       │
└───────────────┘     └───────────────┘     └───────────────┘
```

## Decisions

### Decision 1: 数据源选择

**选择**: 优先使用 Tushare 公告 + Sina 财经新闻

**Alternatives considered**:
1. FinnHub API - 需要额外 API Key，增加配置复杂度
2. 东方财富爬虫 - 法律风险，维护成本高
3. 付费新闻服务 - 成本过高

**Rationale**:
- Tushare 已有 Token，公告数据权威可靠
- Sina 财经免费且数据丰富，接口相对稳定
- 两者结合覆盖公告和市场新闻两个维度

### Decision 2: 情绪分析方案

**选择**: 使用 LLM（GPT-4）进行情绪分析

**Alternatives considered**:
1. 规则匹配 - 准确率低，维护成本高
2. 专用情绪分类模型 - 需要训练数据和额外部署
3. 第三方 NLP 服务 - 增加外部依赖

**Rationale**:
- 项目已集成 OpenAI API，复用现有基础设施
- LLM 理解能力强，无需额外训练
- 可以同时生成情绪标签和分析理由

### Decision 3: Agent 架构设计

**选择**: 继承 `LangGraphAgent` 基类，遵循现有 Agent 模式

**Rationale**:
- 与 MarketAgent、ReportAgent 等保持一致
- 自动获得 Langfuse 可观测性
- 无缝集成到 OrchestratorAgent

## Data Models

```python
# 新闻数据结构
class NewsItem(BaseModel):
    """新闻条目"""
    id: str                      # 新闻唯一标识
    title: str                   # 标题
    content: str                 # 内容/摘要
    source: str                  # 来源（tushare/sina/etc）
    publish_time: datetime       # 发布时间
    stock_codes: List[str] = []  # 关联股票代码
    category: str = ""           # 分类（公告/快讯/分析）
    url: Optional[str] = None    # 原文链接

class NewsSentiment(BaseModel):
    """情绪分析结果"""
    news_id: str
    sentiment: Literal["positive", "negative", "neutral"]
    score: float                 # -1.0 到 1.0
    reasoning: str               # 分析理由
    impact_level: Literal["high", "medium", "low"]

class HotTopic(BaseModel):
    """热点话题"""
    topic: str                   # 话题名称
    keywords: List[str]          # 关键词
    heat_score: float            # 热度分数
    related_stocks: List[str]    # 相关股票
    news_count: int              # 相关新闻数量
```

## Agent Tools Specification

```python
# Tool 1: 获取股票相关新闻
def get_news_by_stock(
    stock_code: str,     # 股票代码，如 600519.SH
    days: int = 7,       # 查询天数
    limit: int = 20      # 返回数量
) -> List[NewsItem]:
    """获取指定股票的相关新闻和公告"""
    pass

# Tool 2: 获取市场新闻
def get_market_news(
    category: str = "all",  # 分类: all/announcement/flash/analysis
    limit: int = 20
) -> List[NewsItem]:
    """获取市场整体财经新闻"""
    pass

# Tool 3: 分析新闻情绪
def analyze_news_sentiment(
    news_items: List[NewsItem],
    stock_context: Optional[str] = None  # 股票背景信息
) -> List[NewsSentiment]:
    """分析新闻列表的情绪倾向"""
    pass

# Tool 4: 获取市场热点
def get_hot_topics(
    limit: int = 10
) -> List[HotTopic]:
    """获取当前市场热点话题"""
    pass

# Tool 5: 生成新闻摘要
def summarize_news(
    news_items: List[NewsItem],
    focus: Optional[str] = None  # 关注重点
) -> str:
    """AI 生成新闻摘要和要点"""
    pass
```

## Risks / Trade-offs

### Risk 1: Sina API 稳定性
- **风险**: Sina 财经 API 可能变更或限流
- **缓解**: 实现重试机制和降级策略，缓存热门数据

### Risk 2: LLM 情绪分析成本
- **风险**: 大量新闻情绪分析消耗 Token
- **缓解**: 批量分析、缓存结果、限制分析数量

### Risk 3: 新闻时效性
- **风险**: 缓存可能导致新闻不够及时
- **缓解**: 设置合理的缓存 TTL（快讯 5 分钟，公告 1 小时）

## Migration Plan

1. **Phase 1**: 实现基础新闻获取（Tushare 公告）
2. **Phase 2**: 添加 Sina 新闻源
3. **Phase 3**: 实现情绪分析功能
4. **Phase 4**: 集成到 Orchestrator
5. **Phase 5**: 前端展示（后续迭代）

无需数据迁移，纯增量功能。

## Open Questions

1. **缓存策略细节**: Redis key 命名规范？缓存过期时间？
2. **情绪分析 Prompt**: 是否需要针对 A 股市场特点定制？
3. **前端集成优先级**: 是否在本次迭代中实现前端组件？
