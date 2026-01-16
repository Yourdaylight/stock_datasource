# Change: 新增ETF/指数行情展示界面与每日概览

## Why

当前系统存在以下问题：
1. **ETF数据无前端展示**：已完成4个ETF数据插件（etf_basic、etf_fund_daily、etf_fund_adj、etf_stk_mins），但缺少专门的前端展示界面
2. **指数行情展示不完整**：指数选股界面已有列表和分析功能，但缺少行情展示（K线、技术指标）
3. **行情分析页面功能单一**：当前MarketView仅支持股票行情，无法展示ETF和指数行情
4. **缺少每日概览**：用户无法快速了解当日市场整体表现（主要指数涨跌、热门ETF等）

用户需求：
- ETF界面使用新增的数据库内容展示
- 指数行情展示使用插件系统提供的接口
- 列表筛选界面/后端接口应具备复用性和扩展性
- 评估适合展示在行情分析上的每日概览数据

## What Changes

### 1. 后端模块：新增ETF模块（含AI分析）

创建 `src/stock_datasource/modules/etf/` 模块，参考 Index 模块实现：

**API端点**：
- `GET /etfs` - ETF列表（支持分页、筛选）
- `GET /etfs/{ts_code}` - ETF详情
- `GET /etfs/{ts_code}/daily` - ETF日线行情
- `GET /etfs/{ts_code}/kline` - ETF K线数据（复权）
- `GET /exchanges` - 交易所列表
- `GET /etf-types` - ETF类型列表
- `POST /analyze` - ETF AI量化分析（支持多轮对话）
- `GET /etfs/{ts_code}/quick-analysis` - ETF快速分析（无AI）

**复用设计**：
- 抽象通用的列表查询模式（分页、筛选、搜索）
- 创建可复用的 `BaseListService` 基类

### 2. 后端增强：Index模块补充行情接口

扩展现有 Index 模块：
- `GET /indices/{ts_code}/daily` - 指数日线行情
- `GET /indices/{ts_code}/kline` - 指数K线数据

### 3. 后端模块：每日概览接口（含AI分析）

创建 `src/stock_datasource/modules/overview/` 模块：

**API端点**：
- `GET /overview/daily` - 每日市场概览
  - 主要指数涨跌（沪深300、中证500、上证50、创业板指等）
  - 涨跌家数统计
  - 成交量/成交额
- `GET /overview/hot-etfs` - 热门ETF（按成交额/涨跌幅排序）
- `GET /overview/market-sentiment` - 市场情绪指标
- `POST /overview/analyze` - 市场概览AI分析（支持多轮对话）
- `GET /overview/quick-analysis` - 市场快速分析（无AI）

### 4. 后端：AI Agent 扩展

**新增 ETF Agent**：
- 创建 `src/stock_datasource/agents/etf_agent.py`
- 实现ETF量化分析工具集
- 支持多轮对话记忆（复用LangGraph MemorySaver）

**新增 Market Overview Agent**：
- 创建 `src/stock_datasource/agents/overview_agent.py`
- 实现市场概览分析工具集
- 支持基于当日数据的智能问答

### 4. 前端：ETF展示界面（含AI分析）

创建 `frontend/src/views/etf/` 目录：

**组件结构**：
- `EtfScreenerView.vue` - ETF主视图（参考IndexScreenerView）
- `components/EtfDetailDialog.vue` - ETF详情弹窗
- `components/EtfKLinePanel.vue` - ETF K线面板
- `components/EtfAnalysisPanel.vue` - ETF AI分析面板

**功能**：
- ETF列表（支持按交易所、类型、管理人筛选）
- ETF详情（基础信息、跟踪指数、管理费率等）
- ETF行情图表（K线、成交量）
- **ETF AI分析**（支持多轮对话问答）

### 5. 前端：增强行情分析页面（含AI问答）

改造 `MarketView.vue`：

**新增功能**：
- 每日概览卡片（主要指数涨跌、市场情绪）
- 支持切换股票/ETF/指数行情
- 热门ETF快捷入口
- **市场AI问答面板**（基于当日概览数据的智能问答）

### 6. 前端：通用列表组件

创建可复用组件：
- `components/common/DataListView.vue` - 通用列表视图
- `components/common/FilterPanel.vue` - 通用筛选面板

## Impact

### Affected Specs
- etf-display（新增）
- market-overview（新增）

### Affected Code

**后端**：
- `src/stock_datasource/modules/etf/` - 新增ETF模块
- `src/stock_datasource/modules/overview/` - 新增概览模块
- `src/stock_datasource/modules/index/router.py` - 扩展行情接口
- `src/stock_datasource/core/base_service.py` - 新增通用服务基类
- `src/stock_datasource/agents/etf_agent.py` - 新增ETF AI Agent
- `src/stock_datasource/agents/etf_tools.py` - ETF分析工具集
- `src/stock_datasource/agents/overview_agent.py` - 新增市场概览AI Agent
- `src/stock_datasource/agents/overview_tools.py` - 市场概览分析工具集

**前端**：
- `frontend/src/views/etf/` - 新增ETF视图
- `frontend/src/views/etf/components/EtfAnalysisPanel.vue` - ETF AI分析面板
- `frontend/src/views/market/MarketView.vue` - 增强行情页面
- `frontend/src/views/market/components/MarketAIPanel.vue` - 市场AI问答面板
- `frontend/src/api/etf.ts` - 新增ETF API
- `frontend/src/api/overview.ts` - 新增概览API
- `frontend/src/stores/etf.ts` - 新增ETF Store
- `frontend/src/stores/overview.ts` - 新增概览Store
- `frontend/src/router/index.ts` - 新增路由
- `frontend/src/components/common/` - 通用组件

### Dependencies
- 依赖已完成的ETF数据插件（ods_etf_basic、ods_etf_fund_daily等）
- 依赖已完成的指数数据插件（dim_index_basic、ods_idx_factor_pro等）

### Data Tables Used
| 表名 | 用途 |
|------|------|
| `ods_etf_basic` | ETF基础信息展示 |
| `ods_etf_fund_daily` | ETF日线行情 |
| `ods_etf_fund_adj` | ETF复权因子 |
| `dim_index_basic` | 指数基础信息 |
| `ods_idx_factor_pro` | 指数技术因子/行情 |
| `ods_index_weight` | 指数成分权重 |

## 每日概览数据评估

### 推荐展示的数据

| 数据类型 | 数据来源 | 展示方式 | 优先级 |
|---------|---------|---------|--------|
| **主要指数涨跌** | ods_idx_factor_pro | 卡片+涨跌色 | P0 |
| 沪深300、中证500、上证50、创业板指、中证1000 | | | |
| **市场涨跌家数** | ods_daily_basic | 柱状图 | P0 |
| 上涨/下跌/平盘数量 | | | |
| **成交统计** | ods_daily_basic | 数字卡片 | P1 |
| 两市成交额、成交量 | | | |
| **热门ETF Top10** | ods_etf_fund_daily | 列表 | P1 |
| 按成交额排序 | | | |
| **涨幅榜ETF Top10** | ods_etf_fund_daily | 列表 | P1 |
| 按涨跌幅排序 | | | |
| **指数技术信号** | ods_idx_factor_pro | 信号标签 | P2 |
| MACD金叉/死叉、KDJ超买超卖 | | | |
| **连涨/连跌统计** | ods_idx_factor_pro | 数字 | P2 |
| updays/downdays字段 | | | |

### 数据刷新策略
- 每日概览数据在交易日收盘后更新（18:00后）
- 前端可设置自动刷新（每5分钟检查是否有新数据）
