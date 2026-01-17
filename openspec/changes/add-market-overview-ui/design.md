# Design: ETF/指数行情展示与每日概览

## 架构设计

### 1. AI Agent 架构设计

复用现有的 LangGraph Agent 架构，新增 ETF Agent 和 Market Overview Agent：

```
┌─────────────────────────────────────────────────────────────┐
│                   LangGraphAgent (Base)                      │
│  - MemorySaver for checkpoint-based memory                   │
│  - Tool result compression                                   │
│  - Session-based shared state                                │
└─────────────────────────────────────────────────────────────┘
                              ▲
          ┌───────────────────┼───────────────────┐
          │                   │                   │
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  IndexAgent     │  │   EtfAgent      │  │ OverviewAgent   │
│  (已存在)        │  │   (新增)         │  │   (新增)         │
└─────────────────┘  └─────────────────┘  └─────────────────┘
          │                   │                   │
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  index_tools    │  │   etf_tools     │  │ overview_tools  │
│  (已存在)        │  │   (新增)         │  │   (新增)         │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 2. ETF Agent 工具集设计

```python
# etf_tools.py
@tool
def get_etf_basic_info(ts_code: str) -> dict:
    """获取ETF基础信息"""
    
@tool  
def get_etf_daily_data(ts_code: str, days: int = 30) -> dict:
    """获取ETF日线数据"""

@tool
def get_etf_tracking_index(ts_code: str) -> dict:
    """获取ETF跟踪指数信息"""

@tool
def calculate_etf_metrics(ts_code: str) -> dict:
    """计算ETF关键指标（跟踪误差、折溢价、流动性等）"""

@tool
def compare_etf_with_index(ts_code: str, days: int = 30) -> dict:
    """ETF与跟踪指数对比分析"""

@tool
def get_etf_comprehensive_analysis(ts_code: str) -> dict:
    """ETF综合分析（快速分析用）"""
```

### 3. Market Overview Agent 工具集设计

```python
# overview_tools.py
@tool
def get_major_indices_status(date: str = None) -> dict:
    """获取主要指数状态（沪深300、中证500等）"""

@tool
def get_market_breadth(date: str = None) -> dict:
    """获取市场广度（涨跌家数、涨跌停数量）"""

@tool
def get_sector_performance(date: str = None, limit: int = 10) -> dict:
    """获取板块表现排名"""

@tool
def get_hot_etfs_analysis(date: str = None, sort_by: str = "amount") -> dict:
    """获取热门ETF分析"""

@tool
def get_market_sentiment(date: str = None) -> dict:
    """获取市场情绪指标"""

@tool
def get_market_daily_summary(date: str = None) -> dict:
    """获取市场每日综合摘要（快速分析用）"""
```

### 4. 通用列表服务设计

为了实现列表筛选界面/后端接口的复用性，设计通用的列表查询模式：

```
┌─────────────────────────────────────────────────────────────┐
│                    BaseListService                          │
├─────────────────────────────────────────────────────────────┤
│ - get_list(filters, pagination, sorting)                    │
│ - get_filter_options()                                      │
│ - get_detail(id)                                            │
│ - search(keyword)                                           │
└─────────────────────────────────────────────────────────────┘
                              ▲
          ┌───────────────────┼───────────────────┐
          │                   │                   │
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  IndexService   │  │   EtfService    │  │  StockService   │
│  (已存在)        │  │   (新增)         │  │  (未来扩展)      │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 5. 前端组件复用设计

```
┌─────────────────────────────────────────────────────────────┐
│                  DataListView (通用列表组件)                  │
├─────────────────────────────────────────────────────────────┤
│ Props:                                                       │
│ - columns: TableColumn[]                                     │
│ - fetchData: (params) => Promise<ListResponse>               │
│ - filterConfig: FilterConfig[]                               │
│ - searchPlaceholder: string                                  │
│ - rowKey: string                                             │
├─────────────────────────────────────────────────────────────┤
│ Slots:                                                       │
│ - #quickAccess - 快捷访问区域                                  │
│ - #[column] - 自定义列渲染                                    │
│ - #operation - 操作列                                         │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ IndexScreener   │  │  EtfScreener    │  │  StockScreener  │
│ View.vue        │  │  View.vue       │  │  View.vue       │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 6. AI分析面板复用设计

```
┌─────────────────────────────────────────────────────────────┐
│                  BaseAnalysisPanel (通用分析面板)             │
├─────────────────────────────────────────────────────────────┤
│ Props:                                                       │
│ - analyzeApi: (question) => Promise<AnalysisResponse>        │
│ - quickAnalyzeApi: () => Promise<QuickAnalysisResponse>      │
│ - presetQuestions: string[]                                  │
│ - title: string                                              │
├─────────────────────────────────────────────────────────────┤
│ Features:                                                    │
│ - 快速分析展示                                                │
│ - AI对话输入框                                                │
│ - 对话历史展示                                                │
│ - 预设问题快捷按钮                                            │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ IndexAnalysis   │  │  EtfAnalysis    │  │  MarketAI       │
│ Panel.vue       │  │  Panel.vue      │  │  Panel.vue      │
│ (已存在)         │  │  (新增)          │  │  (新增)          │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 7. 行情展示统一接口设计

为股票、ETF、指数提供统一的K线数据接口：

```typescript
// 统一的K线请求接口
interface KLineRequest {
  code: string           // 证券代码
  type: 'stock' | 'etf' | 'index'
  start_date: string
  end_date: string
  adjust?: 'qfq' | 'hfq' | 'none'  // 复权类型
}

// 统一的K线响应
interface KLineResponse {
  code: string
  name: string
  type: string
  data: KLineData[]
}

interface KLineData {
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  vol: number
  amount: number
  pct_chg?: number
}
```

### 8. 每日概览数据聚合设计

```
┌─────────────────────────────────────────────────────────────┐
│                   OverviewService                            │
├─────────────────────────────────────────────────────────────┤
│ get_daily_overview(date?)                                    │
│   ├── get_major_indices()      → 主要指数涨跌                 │
│   ├── get_market_stats()       → 涨跌家数/成交统计            │
│   └── get_market_sentiment()   → 市场情绪指标                 │
│                                                              │
│ get_hot_etfs(date?, limit?)                                  │
│   ├── by_amount()              → 按成交额排序                 │
│   └── by_pct_chg()             → 按涨跌幅排序                 │
│                                                              │
│ analyze_market(question, user_id)  → AI市场分析              │
└─────────────────────────────────────────────────────────────┘
```

### 9. 模块依赖关系

```
                    ┌─────────────┐
                    │   Router    │
                    └──────┬──────┘
                           │
     ┌─────────────────────┼─────────────────────┐
     │                     │                     │
┌────▼────┐          ┌─────▼─────┐         ┌─────▼─────┐
│  /etf   │          │  /index   │         │ /overview │
└────┬────┘          └─────┬─────┘         └─────┬─────┘
     │                     │                     │
┌────▼────────┐      ┌─────▼─────────┐    ┌─────▼──────────┐
│ EtfService  │      │ IndexService  │    │OverviewService │
│ + EtfAgent  │      │ + IndexAgent  │    │+ OverviewAgent │
└────┬────────┘      └─────┬─────────┘    └─────┬──────────┘
     │                     │                     │
     └──────────┬──────────┴──────────┬──────────┘
                │                     │
         ┌──────▼──────┐       ┌──────▼──────┐
         │ ClickHouse  │       │  LangGraph  │
         │   Tables    │       │   Memory    │
         └─────────────┘       └─────────────┘
```

## 数据流设计

### ETF行情数据流

```
ods_etf_basic + ods_etf_fund_daily + ods_etf_fund_adj
                        │
                        ▼
              ┌─────────────────┐
              │   EtfService    │
              │  (复权计算)      │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │   /etf/kline    │
              │   API 接口       │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  EtfKLinePanel  │
              │   前端组件       │
              └─────────────────┘
```

### AI分析数据流

```
用户问题
    │
    ▼
┌─────────────────┐
│  API Endpoint   │
│ POST /analyze   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Agent        │
│ (ETF/Overview) │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌───────────┐
│ Tools │ │ LangGraph │
│       │ │  Memory   │
└───┬───┘ └─────┬─────┘
    │           │
    ▼           ▼
┌───────────────────┐
│   AI Response     │
│ (with context)    │
└───────────────────┘
```

## 前端路由设计

```typescript
const routes = [
  // ... 现有路由
  {
    path: '/etf',
    name: 'Etf',
    component: () => import('@/views/etf/EtfScreenerView.vue'),
    meta: { title: 'ETF筛选' }
  },
  // 改造现有 /market 路由，支持多类型
  {
    path: '/market',
    name: 'Market',
    component: () => import('@/views/market/MarketView.vue'),
    meta: { title: '行情分析' }
  }
]
```

## API设计

### ETF模块API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/etf/etfs` | 获取ETF列表 |
| GET | `/api/etf/etfs/{ts_code}` | 获取ETF详情 |
| GET | `/api/etf/etfs/{ts_code}/daily` | 获取ETF日线数据 |
| GET | `/api/etf/etfs/{ts_code}/kline` | 获取ETF K线（支持复权） |
| GET | `/api/etf/etfs/{ts_code}/quick-analysis` | ETF快速分析 |
| POST | `/api/etf/analyze` | ETF AI量化分析 |
| GET | `/api/etf/exchanges` | 获取交易所列表 |
| GET | `/api/etf/types` | 获取ETF类型列表 |

### 概览模块API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/overview/daily` | 获取每日概览 |
| GET | `/api/overview/hot-etfs` | 获取热门ETF |
| GET | `/api/overview/indices` | 获取主要指数行情 |
| GET | `/api/overview/quick-analysis` | 市场快速分析 |
| POST | `/api/overview/analyze` | 市场AI分析 |

### Index模块扩展API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/index/indices/{ts_code}/daily` | 获取指数日线数据 |
| GET | `/api/index/indices/{ts_code}/kline` | 获取指数K线 |

## 技术选型

### 后端
- FastAPI（现有）
- ClickHouse（现有）
- LangGraph + MemorySaver（现有，用于AI对话记忆）
- 插件系统 Service 层（现有）

### 前端
- Vue 3 + TypeScript（现有）
- TDesign（现有）
- ECharts（现有，用于K线图）
- Pinia（现有）

## 扩展性考虑

1. **新增资产类型**：通过继承 BaseListService 快速支持新的资产类型（如期货、债券）
2. **新增筛选条件**：FilterConfig 配置化，无需修改组件代码
3. **新增概览指标**：OverviewService 模块化设计，易于添加新指标
4. **新增AI Agent**：复用 LangGraphAgent 基类，只需定义新的工具集
5. **多数据源支持**：Service 层抽象数据访问，可切换数据源
