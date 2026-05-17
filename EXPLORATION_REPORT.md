# Stock Datasource Project - Frontend & Database Exploration Report

## Executive Summary
This is a comprehensive AI-driven stock analysis platform with:
- **Frontend**: Vue 3 with TypeScript (T-Design UI components)
- **Database**: ClickHouse (time-series optimized)
- **Persistence**: File-based JSON storage for workflows + ClickHouse for operational data
- **Architecture**: Modular with Pinia stores, composables, and specialized components

---

## 1. Frontend Menu Structure (`frontend/src/App.vue`)

### Current Menu Hierarchy

#### **Top-Level Items (No Submenu)**
1. **行情分析** (Market Analysis) - `/market` - Public
   - Icon: `ChartLineIcon`
   - Shows market overview, sectors, indices, hot stocks/ETFs

2. **财报分析** (Financial Reports) - `/research` - Public
   - Icon: `FileSearchIcon`
   - Navigates to research/financial data analysis

3. **资讯中心** (News Center) - `/news` - Auth Required
   - Icon: `NotificationIcon`

4. **智能对话** (AI Chat) - `/chat` - Auth Required
   - Icon: `ChatIcon`

5. **智能选股** (Stock Screener) - `/screener` - Auth Required
   - Icon: `FilterIcon`

6. **哨兵选股** (Sentinel Screening) - `/sentinel` - Auth Required
   - Icon: `PreciseMonitorIcon`

7. **持仓管理** (Portfolio Management) - `/portfolio` - Auth Required
   - Icon: `WalletIcon`

8. **智能选ETF** (ETF Screener) - `/etf` - Auth Required
   - Icon: `ControlPlatformIcon`

9. **指数行情** (Index Market Quotes) - `/index` - Auth Required
   - Icon: `TrendingUpIcon`

#### **Submenu Groups**

**策略系统** (Strategy System) - `/strategy` - Pro tier + Auth
- Icon: `ToolsIcon`
- Children:
  - 策略工具台 `/strategy` (Strategy Workbench)
  - Agent竞技场 `/arena` (Agent Arena)

**量化选股** (Quant Screening) - `/quant` - Pro tier + Auth
- Icon: `PreciseMonitorIcon`
- Children:
  - 模型总览 `/quant` (Model Overview)
  - 全市场初筛 `/quant/screening` (Market-Wide Pre-screening)
  - 核心目标池 `/quant/pool` (Core Target Pool)
  - RPS排名 `/quant/rps` (RPS Ranking)
  - 深度分析 `/quant/analysis` (Deep Analysis)
  - 交易信号 `/quant/signals` (Trading Signals)
  - 模型配置 `/quant/config` (Model Configuration)

**其他项**
- **AI工作流** `/workflow` - Pro tier + Auth - `QueueIcon`
- **微信联动** `/wechat-bridge` - Admin required - `RootListIcon`
- **用户记忆** `/memory` - Auth Required - `UserIcon`

#### **Admin Menus**

**系统日志** (System Logs) - `/system-logs` - Admin + Auth
- Icon: `FileIcon`

**开放API** (Open API) - `/api-access` - Admin + Auth
- Icon: `LinkIcon`

**数据管理** (Data Management) - `/datamanage` - Admin + Auth
- Icon: `ServerIcon`
- Children:
  - 数据概览 `/datamanage` (Data Overview)
  - 数据浏览器 `/datamanage/explorer` (Data Explorer)
  - 同步任务 `/datamanage/tasks` (Sync Tasks)
  - 知识库 `/datamanage/knowledge` (Knowledge Base)
  - 数据配置 `/datamanage/config` (Data Configuration)

### Menu Visibility Rules
- **Tier Levels**: `free: 0`, `pro: 1`, `admin: 2`
- Admin users can see all items regardless of tier
- Pro users see: Pro tier items only + free items
- Free users see: Public + free-tier auth items

---

## 2. Market-Related Views

### `/views/market/` - **行情分析** (Market Analysis Page)
**File**: `frontend/src/views/market/MarketView.vue`

**Purpose**: Main market overview dashboard with real-time data

**Main Features**:
1. **Major Indices** (8 index codes):
   - 000001.SH (Shanghai Index)
   - 399001.SZ, 399006.SZ (Shenzhen, Growth Index)
   - 000016.SH (Shanghai 50)
   - 000300.SH (CSI 300)
   - 000905.SH (CSI 500)
   - 000852.SH (CSI 1000)
   - 000688.SH (Tech Index)

2. **Market Overview Section** (4-column layout):
   - **Market Sentiment** (市场情绪)
     - Up/Down count
     - Limit up/down count
     - Total trading volume (in 100M RMB)
     - Sentiment tag (Bullish/Bearish/Neutral)
   
   - **Sector Heatmap** (板块热力图)
     - Visual heatmap of sector performance
     - Click to view sector details
   
   - **Hot Stocks** (热门股票)
     - Top 10 by trading volume
     - Shows price change %
   
   - **Hot ETFs** (热门ETF)
     - Top 10 by volume
     - Shows price change %

3. **Main Section** (2-column):
   - **Sector Ranking** (板块涨跌排行)
   - **Index Comparison Chart** (指数走势对比)

**Components**:
- `SectorHeatmap.vue` - Visual heatmap
- `SectorDetailDialog.vue` - Drill-down details
- `SectorRankingTable.vue` - Ranking table
- `IndexCompareChart.vue` - Multi-line chart
- `MarketAiFloatButton.vue` + `MarketAiDialog.vue` - AI analysis

**Data Sources**:
- `useOverviewStore()` - Daily overview data
- `realtimeApi.getBatchMinuteData()` - Real-time minute data
- `request.get('/api/market/hot-stocks')` - Hot stocks

**Polling**:
- Real-time index polling every 30 seconds (trading hours only)
- Hot ETF refresh on 300ms debounce

---

### `/views/index/` - **指数行情** (Index Market Quotes)
**File**: `frontend/src/views/index/IndexScreenerView.vue`

**Purpose**: Comprehensive index screening and analysis tool

**Main Features**:
1. **Quick Access**:
   - Common indices (沪深300, 中证500, 上证50, etc.)

2. **Filtering System**:
   - Market filter (市场)
   - Category filter (类别)
   - Publisher filter (发布方)
   - Trade date filter (交易日期)
   - Pct change range (涨跌幅 range)

3. **Table Display**:
   - Columns: Code, Name, Date, Close, % Change, Volume, Amount, Market, Category, Publisher
   - Pagination support
   - Row click to show detail dialog

4. **Analysis Features**:
   - `IndexAnalysisPanel.vue` - Detailed analysis
   - `IndexDetailDialog.vue` - Modal details

**Data Management**:
- `useIndexStore()` for state management
- Fetch market/category/publisher stats for filter dropdowns
- Support for "no data" dialogs and data update requests

---

### `/views/etf/` - **智能选ETF** (ETF Screening)
**Files**: 
- `EtfView.vue` (main)
- `EtfScreenerContent.vue` (screener)
- `EtfBenchmarkIndexPanel.vue` (benchmark indices)

**Purpose**: ETF discovery, analysis, and benchmark comparison

**Main Features**:
1. **Two Main Tabs**:
   - **ETF行情** (ETF Market Quotes)
     - Screener with filters
     - Table display of ETF data
     - Analysis panels
   
   - **基准指数** (Benchmark Indices)
     - Benchmark index comparison
     - Historical performance

2. **Store**: `useEtfStore()`
   - Manages ETF list
   - Filters and sorting
   - Selected ETF details

3. **Components**:
   - `EtfAnalysisPanel.vue`
   - `EtfDetailDialog.vue`

---

## 3. Database Schema

### Infrastructure (docker-compose.infra.yml)

**Services**:
- **ClickHouse 24** (Time-series database)
  - Port: 8123 (HTTP), 9000 (Native)
  - User: configurable (default: clickhouse)
  - Database: `default` for Langfuse, `stock_data` for app
  
- **Redis 7-Alpine** (Cache layer)
  - Port: 6379
  - Max memory: 1GB (LRU eviction)
  - Persistence: AOF (appendonly)

- **Backend** (depends on both)

### ClickHouse Initialization

**Database**: `stock_data`

**Main Tables** (from `docker/init-clickhouse.sql`):
- `system_structured_logs` - Request tracing + log analysis
  - Columns: timestamp, level, request_id, user_id, module, function, line, message, exception, extra
  - Partitioned by date, TTL 90 days
  - Order by: timestamp, level, request_id

### Sentinel System Tables (from `modules/sentinel/persistence/tables.py`)

**1. sentinel_alerts**
```
- alert_id: String
- sentinel_type: String
- category: String
- severity: String
- ts_code, sector_code, index_code: Nullable String
- signal_type: String
- description: String
- metric_name, metric_value: Float64
- threshold, deviation_pct: Float64
- context: String
- created_at: DateTime
ORDER BY: (created_at, sentinel_type)
TTL: 90 days
```

**2. sentinel_analyst_reports**
```
- report_id: String
- analyst_type: String
- trigger_count: UInt32
- market_regime: Nullable String
- overall_conviction: Float64
- insights_json: String
- source_alert_ids: Array(String)
- created_at: DateTime
ORDER BY: (created_at, analyst_type)
TTL: 90 days
```

**3. sentinel_decisions**
```
- decision_id: String
- trade_date: String
- market_regime: String
- market_risk_level: String
- suggested_position: Float64
- buy_count, sell_count: UInt32
- confidence: Float64
- decision_json: String
- created_at: DateTime
ORDER BY: (trade_date, created_at)
TTL: 365 days
```

---

## 4. Workflow & Agent Configuration Storage

### Storage Architecture

**Hybrid Approach**:
1. **File-based JSON** (Primary for workflows)
   - Location: `/data/workflows/{workflow_id}.json`
   - Stores: AIWorkflow configurations
   
2. **ClickHouse** (For operational events)
   - Future: Could store execution logs, alerts, decisions

### Workflow Data Model (`models/workflow.py`)

**AIWorkflow**:
```python
{
  id: str (UUID)
  name: str
  description: str
  system_prompt: str          # AI role definition
  user_prompt_template: str   # Supports {{variable}} substitution
  selected_tools: list[str]   # MCP tool names
  variables: list[WorkflowVariable]
  is_template: bool
  category: str               # "custom", "analysis", "comparison", "screening"
  tags: list[str]
  created_at: datetime
  updated_at: datetime
}

WorkflowVariable:
  name: str
  label: str
  type: str                   # "string", "number", "date", "stock_code", "stock_list"
  required: bool
  default: str
  description: str
```

### Workflow Service (`services/workflow_service.py`)

**Operations**:
- `list_workflows()` - Get all workflows
- `get_workflow(id)` - Fetch specific workflow
- `create_workflow()` - Create new from request
- `update_workflow()` - Update fields
- `delete_workflow()` - Remove workflow
- `get_templates()` - Load built-in templates
- `get_available_tools()` - List MCP tools
- `cloneFromTemplate()` - Clone template to user workflow
- `execute()` - Run workflow (stream)
- `generate()` - AI-generate workflow (stream)

### Built-in Templates (4):
1. **template_single_stock** - 单股深度分析
   - Tools: tushare_daily, tushare_valuation
   - Variables: stock_code

2. **template_stock_compare** - 股票对比分析
   - Tools: tushare_daily, tushare_valuation
   - Variables: stock_list

3. **template_value_investing** - 价值投资筛选
   - Tools: tushare_valuation, tushare_daily
   - Variables: max_pe, max_pb

4. **template_technical_analysis** - 技术面分析
   - Tools: tushare_daily_get_daily_data
   - Variables: stock_code, days

### API Routes (`api/workflow_routes.py`)

**Endpoints** (all require auth, delete requires admin):
- `GET /api/workflows/` - List workflows
- `POST /api/workflows/` - Create
- `GET /api/workflows/templates` - Get templates
- `GET /api/workflows/tools` - Get available tools
- `GET /api/workflows/{id}` - Get detail
- `PUT /api/workflows/{id}` - Update
- `DELETE /api/workflows/{id}` - Delete (admin only)
- `POST /api/workflows/{id}/execute` - Execute (stream)
- `POST /api/workflows/generate` - AI generate (stream)

---

## 5. Frontend Stores (`frontend/src/stores/`)

### Key Stores for Planning

1. **auth.ts** - Authentication state
   - `user` object with `subscription_tier`, `is_admin`
   - Token management
   - Auth check

2. **workflow.ts** - AI Workflow state
   - `workflows[]`, `templates[]`, `availableTools[]`
   - Execution state: `executionThinking`, `executionContent`, `executionError`
   - Generation state: `generatingContent`, `generatedWorkflow`
   - Methods: load, create, update, delete, execute, generate

3. **overview.ts** - Market overview
   - Daily indices, analysis, sentiment
   - Methods: `fetchDailyOverview()`, `fetchQuickAnalysis()`

4. **index.ts** - Index screening
   - Markets, categories, publishers, trade dates
   - Filter options

5. **etf.ts** - ETF data
   - ETF list, filters, selection

6. **arena.ts** - Agent Arena
   - Discussion orchestration
   - Agent responses

7. **chat.ts** - Chat conversations
   - Messages, streaming responses

8. **quant.ts** - Quantitative models
   - Model state, screening results

---

## 6. Key Insights for Agent Menu Planning

### Current Structure Analysis

**Market-Related Views** (potential consolidation candidates):
- `/market` - 行情分析 (comprehensive overview)
- `/index` - 指数行情 (index screener)
- `/etf` - 智能选ETF (ETF screener)

**Observation**: These three could potentially be merged into a "Market & Indices" submenu:
```
行情中心 (Market Center)
├── 市场概览 → /market
├── 指数行情 → /index
└── 智能选ETF → /etf
```

### Database for Agent Config Storage

**Current Approach**: File-based JSON (simple but not queryable)

**Recommended Enhancement**: Add ClickHouse table for agent configurations:
```sql
CREATE TABLE agent_configurations (
    id String,
    name String,
    category String,
    description String,
    system_prompt String,
    user_prompt_template String,
    selected_tools Array(String),
    variables String,              -- JSON
    config_metadata String,         -- JSON (for extensibility)
    is_active Boolean,
    is_template Boolean,
    created_by String,
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (category, created_at)
```

Benefits:
- Query and filter configurations by category, creator, etc.
- Full audit trail with timestamps
- Integrate with existing observability (system_structured_logs)
- Scale better than file storage

---

## 7. Technology Stack Summary

| Layer | Technology | Details |
|-------|-----------|---------|
| **Frontend** | Vue 3 + TypeScript | T-Design UI, Pinia stores, Vue Router |
| **Components** | TDesign Vue Next | Professional UI components library |
| **State** | Pinia | Reactive store management |
| **HTTP** | Custom request util | Built-in request interceptor |
| **Database** | ClickHouse 24 | Time-series optimized, MergeTree engine |
| **Cache** | Redis 7 | 1GB LRU, AOF persistence |
| **Workflow Storage** | JSON files | `/data/workflows/{id}.json` |
| **Authentication** | Token-based | Via `get_current_user` dependency |

---

## 8. Recommendations

1. **For Agent Menu Integration**:
   - Consider a two-level submenu: "行情中心" containing market-related pages
   - Ensure auth/tier checking works with new submenus

2. **For Agent Config Storage**:
   - Migrate workflows to ClickHouse table for better queryability
   - Maintain JSON export/import for portability
   - Add versioning column for config history

3. **For Real-time Updates**:
   - Current polling: Market real-time every 30s, Hot ETF every 300ms
   - Consider WebSocket for lower latency on critical pages

4. **For Agent Coordination**:
   - Arena's discussion_orchestrator pattern is excellent for multi-agent scenarios
   - Workflow templates provide good baseline for custom agents
   - Consider expanding templates library as new agent types emerge

