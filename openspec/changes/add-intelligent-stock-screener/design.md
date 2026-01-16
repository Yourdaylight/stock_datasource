# Design: M03智能选股模块技术设计

## Context

M03智能选股是AI智能选股与分析平台的核心功能模块（P0优先级），需要支持：
- 多维度条件筛选
- 十维画像评分
- 自然语言选股
- AI智能推荐

当前系统已有基础选股功能，本次设计在现有基础上进行增强。

## Goals / Non-Goals

### Goals
- 实现多维度条件筛选（估值/技术/量能/行业）
- 实现十维画像评分体系
- 增强自然语言选股能力
- 提供AI智能推荐功能
- 保持与现有系统的兼容性
- **集成 Langfuse 实现 LLM 调用可观测性**

### Non-Goals
- 不涉及实时行情推送（使用现有轮询机制）
- 不涉及用户自定义策略编辑器（后续迭代）
- 不涉及选股结果的持久化历史记录

## Architecture

### 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │ConditionBuilder│ │ NLScreener │  │ProfileRadar │                 │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
│         └────────────────┴────────────────┘                         │
│                          │                                           │
│                   ScreenerView.vue                                   │
└──────────────────────────┼───────────────────────────────────────────┘
                           │ HTTP
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        API Layer                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  /api/screener Router                         │   │
│  │  /filter  /nl  /profile  /recommendations  /sectors  /signals │   │
│  └─────────────────────────────────────────────────────────────┘   │
└──────────────────────────┼───────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Agent Layer                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    ScreenerAgent                              │   │
│  │  - parse_nl_conditions()                                      │   │
│  │  - generate_recommendations()                                 │   │
│  │  - analyze_stock_profile()                                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└──────────────────────────┼───────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Service Layer                                   │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐          │
│  │ScreenerService│  │ ProfileService│  │TechnicalService│          │
│  │               │  │               │  │               │          │
│  │- filter()     │  │- calculate()  │  │- get_signals()│          │
│  │- parse_nl()   │  │- batch_calc() │  │- calc_macd()  │          │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘          │
│          │                  │                  │                    │
│          └──────────────────┴──────────────────┘                    │
│                             │                                        │
│                             ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Plugin Services (优先调用)                 │   │
│  │  ┌─────────────────┐  ┌─────────────────┐                   │   │
│  │  │TuShareDailyBasic│  │TuShareStockBasic│                   │   │
│  │  │    Service      │  │    Service      │                   │   │
│  │  └─────────────────┘  └─────────────────┘                   │   │
│  │  ┌─────────────────┐  ┌─────────────────┐                   │   │
│  │  │ TuShareDaily    │  │TuShareFinaceInd.│                   │   │
│  │  │   Service       │  │    Service      │                   │   │
│  │  └─────────────────┘  └─────────────────┘                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
└──────────────────────────┼───────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Data Layer                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      ClickHouse                               │   │
│  │  ods_daily / ods_daily_basic / ods_stock_basic               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 数据访问原则

**优先使用 Plugin Services 获取数据**：

所有数据访问应优先通过 `plugins/` 目录下的 Service 类进行，而不是直接写 SQL 查询。这样做的好处：
1. **统一数据访问接口**：复用现有的数据访问逻辑
2. **安全性**：Plugin Services 已实现输入验证和 SQL 注入防护
3. **可维护性**：数据表结构变更只需修改 Plugin Service
4. **可测试性**：便于 Mock 测试

**可用的 Plugin Services**：

| Service | 路径 | 功能 |
|---------|------|------|
| `TuShareDailyBasicService` | `plugins/tushare_daily_basic/service.py` | PE/PB/换手率等估值指标 |
| `TuShareStockBasicService` | `plugins/tushare_stock_basic/service.py` | 股票基本信息/行业/上市状态 |
| `TuShareDailyService` | `plugins/tushare_daily/service.py` | 日线行情数据 |
| `TuShareFinaceIndicatorService` | `plugins/tushare_finace_indicator/service.py` | 财务指标数据 |
| `TuShareAdjFactorService` | `plugins/tushare_adj_factor/service.py` | 复权因子 |

**调用方式**：

```python
from stock_datasource.plugins.tushare_daily_basic.service import TuShareDailyBasicService
from stock_datasource.plugins.tushare_stock_basic.service import TuShareStockBasicService
from stock_datasource.plugins.tushare_daily.service import TuShareDailyService
from stock_datasource.plugins.tushare_finace_indicator.service import TuShareFinaceIndicatorService

class ScreenerService:
    def __init__(self):
        self.daily_basic_service = TuShareDailyBasicService()
        self.stock_basic_service = TuShareStockBasicService()
        self.daily_service = TuShareDailyService()
        self.fina_service = TuShareFinaceIndicatorService()
    
    def get_valuation_data(self, codes: List[str]) -> List[Dict]:
        """获取估值数据，优先使用 plugin service"""
        return self.daily_basic_service.get_latest_daily_basic(codes)
    
    def get_stocks_by_industry(self, industry: str) -> List[Dict]:
        """按行业筛选股票，优先使用 plugin service"""
        return self.stock_basic_service.get_stocks_by_industry(industry)
    
    def get_daily_data(self, code: str, start_date: str, end_date: str) -> List[Dict]:
        """获取日线数据，优先使用 plugin service"""
        return self.daily_service.get_daily_data(code, start_date, end_date)
```

**仅当 Plugin Service 不满足需求时，才扩展 Plugin Service 或在 ScreenerService 中写自定义查询**

## Decisions

### Decision 0: LLM 可观测性 - Langfuse 配置

**选择**：使用 Langfuse 作为 LLM 调用的可观测性平台

**原因**：
- 项目已集成 Langfuse（`src/stock_datasource/llm/client.py`）
- 可追踪 LLM 调用的输入/输出、token 消耗、延迟等指标
- 便于调试自然语言选股的解析效果
- 支持生产环境监控和成本分析

**配置要求**：
```bash
# .env 配置
LANGFUSE_PUBLIC_KEY=pk-xxx
LANGFUSE_SECRET_KEY=sk-xxx
LANGFUSE_HOST=https://cloud.langfuse.com  # 或私有部署地址
LANGFUSE_ENABLED=true
```

**在 ScreenerAgent 中使用**：
```python
from stock_datasource.llm.client import get_llm_client, get_langfuse_handler

class ScreenerAgent(LangGraphAgent):
    def __init__(self):
        super().__init__()
        self.llm_client = get_llm_client()
        # LangChain 集成时使用 callback handler
        self.langfuse_handler = get_langfuse_handler()
    
    async def parse_nl_conditions(self, query: str):
        """解析自然语言选股条件，带 Langfuse 追踪"""
        result = await self.llm_client.generate(
            prompt=query,
            system_prompt=self.system_prompt,
            trace_name="screener_nl_parse",  # Langfuse trace 名称
            trace_metadata={"module": "screener", "action": "nl_parse"}
        )
        return result
```

**追踪指标**：
- `screener_nl_parse`: 自然语言条件解析
- `screener_recommendation`: AI 推荐生成
- `screener_profile_analysis`: 画像分析建议

### Decision 1: 十维画像评分体系设计

**选择**：采用百分位排名 + 加权评分的方式

**原因**：
- 百分位排名消除了不同指标量纲差异
- 加权评分便于用户理解和比较
- 可根据市场状态动态调整权重

**实现**：
```python
class StockProfile:
    """股票十维画像"""
    ts_code: str
    stock_name: str  # 股票名称（必须包含）
    trade_date: str
    
    # 十个维度评分 (0-100)
    valuation_score: float    # 估值维度
    growth_score: float       # 成长维度
    profitability_score: float # 盈利维度
    momentum_score: float     # 动量维度
    trend_score: float        # 趋势维度
    volume_score: float       # 量能维度
    volatility_score: float   # 波动维度
    capital_flow_score: float # 资金维度
    sentiment_score: float    # 情绪维度
    risk_score: float         # 风险维度
    
    # 综合评分
    total_score: float
    
    # 各维度详细指标
    details: Dict[str, Any]
```

### Decision 2: 自然语言选股实现方案

**选择**：使用LLM解析 + 结构化条件转换

**原因**：
- 利用现有LangGraphAgent基础设施
- 可处理复杂的自然语言表达
- 支持模糊匹配和智能纠错

**流程**：
```
用户输入 → LLM解析 → 结构化条件 → SQL查询 → 结果返回
     ↓
"低估值高成长科技股"
     ↓
{
  conditions: [
    {field: "pe_ttm", operator: "lt", value: 20},
    {field: "revenue_growth", operator: "gt", value: 0.2},
    {field: "industry", operator: "in", value: ["电子", "计算机", "通信"]}
  ]
}
```

### Decision 3: 条件筛选SQL构建安全性

**选择**：使用白名单字段映射 + 参数化查询

**原因**：
- 防止SQL注入攻击
- 确保只能查询允许的字段
- 符合项目安全规范

**实现**：
```python
ALLOWED_FIELDS = {
    # 估值指标
    "pe": "b.pe_ttm",
    "pe_ttm": "b.pe_ttm",
    "pb": "b.pb",
    "ps": "b.ps_ttm",
    "dv_ratio": "b.dv_ratio",
    "total_mv": "b.total_mv",
    "circ_mv": "b.circ_mv",
    # 行情指标
    "pct_chg": "d.pct_chg",
    "close": "d.close",
    "vol": "d.vol",
    "amount": "d.amount",
    "turnover_rate": "b.turnover_rate",
    # 行业
    "industry": "s.industry",
}

ALLOWED_OPERATORS = {"gt", "gte", "lt", "lte", "eq", "neq", "in", "between"}
```

### Decision 4: 画像计算性能优化

**选择**：批量计算 + 按需计算（暂不使用 Redis 缓存）

**原因**：
- 画像计算涉及多表关联，单次计算成本高
- 批量计算减少数据库往返
- 暂时不引入 Redis 依赖，后续可按需添加

**优化策略**：
- 批量计算: 支持批量请求多个股票画像
- 按需计算: 用户请求时实时计算
- 后续优化: 如性能成为瓶颈，可引入 Redis 缓存

## Data Models

### 筛选条件模型
```python
class ScreenerCondition(BaseModel):
    field: str  # 字段名
    operator: str  # 操作符: gt/gte/lt/lte/eq/neq/in/between
    value: Union[float, int, str, List]  # 值

class ScreenerRequest(BaseModel):
    conditions: List[ScreenerCondition]
    sort_by: str = "pct_chg"
    sort_order: str = "desc"
    limit: int = 100
    offset: int = 0

### 筛选结果项模型（前端展示必须同时包含代码和名称）
class ScreenerResultItem(BaseModel):
    ts_code: str      # 股票代码（必须）
    stock_name: str   # 股票名称（必须）
    trade_date: str
    close: float
    pct_chg: float
    pe_ttm: Optional[float]
    pb: Optional[float]
    total_mv: Optional[float]
    turnover_rate: Optional[float]
    industry: Optional[str]
```

### 股票画像模型
```python
class ProfileDimension(BaseModel):
    name: str
    score: float  # 0-100
    level: str  # 优秀/良好/中等/较差
    indicators: Dict[str, Any]

class StockProfile(BaseModel):
    ts_code: str
    stock_name: str
    trade_date: str
    total_score: float
    dimensions: List[ProfileDimension]
    recommendation: str  # 综合建议
```

### 推荐结果模型
```python
class Recommendation(BaseModel):
    ts_code: str
    stock_name: str
    reason: str
    score: float
    category: str  # 低估值/高成长/技术突破等
    profile: Optional[StockProfile]
```

## API Design

### 多条件筛选（增强）
```
POST /api/screener/filter
Request:
{
  "conditions": [
    {"field": "pe_ttm", "operator": "lt", "value": 20},
    {"field": "pb", "operator": "lt", "value": 3},
    {"field": "industry", "operator": "in", "value": ["电子", "计算机"]}
  ],
  "sort_by": "pct_chg",
  "sort_order": "desc",
  "page": 1,
  "page_size": 20
}

Response:
{
  "items": [
    {
      "ts_code": "000001.SZ",
      "stock_name": "平安银行",  // 必须包含股票名称
      "trade_date": "20260114",
      "close": 12.50,
      "pct_chg": 2.35,
      "pe_ttm": 8.5,
      "pb": 0.85,
      "total_mv": 245000,
      "turnover_rate": 1.23,
      "industry": "银行"
    },
    ...
  ],
  "total": 156,
  "page": 1,
  "page_size": 20,
  "total_pages": 8
}
```

### 自然语言选股
```
POST /api/screener/nl
Request:
{
  "query": "找出市盈率低于20，换手率超过5%的科技股",
  "page": 1,
  "page_size": 20
}

Response:
{
  "parsed_conditions": [...],  // 解析出的条件
  "items": [
    {
      "ts_code": "002415.SZ",
      "stock_name": "海康威视",  // 必须包含股票名称
      ...
    },
    ...
  ],
  "total": 45,
  "explanation": "已为您筛选出PE<20、换手率>5%的电子/计算机/通信行业股票"
}
```

### 股票画像
```
GET /api/screener/profile/{ts_code}

Response:
{
  "ts_code": "600519.SH",
  "stock_name": "贵州茅台",
  "trade_date": "2026-01-14",
  "total_score": 78.5,
  "dimensions": [
    {"name": "估值", "score": 45, "level": "中等", "indicators": {...}},
    {"name": "成长", "score": 65, "level": "良好", "indicators": {...}},
    ...
  ],
  "recommendation": "该股估值偏高但盈利能力强，适合长期价值投资"
}
```

## Risks / Trade-offs

### Risk 1: 画像计算性能
- **风险**：全市场5000+股票画像计算耗时
- **缓解**：采用批量计算 + 按需计算，后续可引入缓存

### Risk 2: 自然语言解析准确性
- **风险**：LLM可能误解用户意图
- **缓解**：返回解析结果让用户确认，支持手动调整

### Risk 3: 数据依赖
- **风险**：部分维度依赖财报数据，更新频率低
- **缓解**：财务维度使用最新可用数据，标注数据日期

## Migration Plan

1. **Phase 1**：增强基础筛选能力
   - 扩展筛选字段（行业、技术指标）
   - 优化SQL查询性能

2. **Phase 2**：实现十维画像
   - 开发画像计算服务
   - 支持批量计算优化

3. **Phase 3**：增强NL选股
   - 优化ScreenerAgent
   - 添加条件解析和验证

4. **Phase 4**：AI推荐功能
   - 开发推荐算法
   - 集成用户偏好

## Open Questions

1. 十维画像的权重是否需要支持用户自定义？
2. 是否需要支持选股结果的订阅和推送？
3. 财务数据更新频率如何保证画像的时效性？
