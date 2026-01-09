# AI 智能选股与分析平台 - 系统设计文档

> 版本: 1.2.0  
> 日期: 2026-01-09  
> 状态: 设计阶段  
> 更新: 新增 M05 用户记忆、M06 数据管理、M07 持仓管理、M08 策略回测模块

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [技术栈选型](#3-技术栈选型)
4. [功能模块设计](#4-功能模块设计)
5. [DeepAgents 多Agent系统](#5-deepagents-多agent系统)
6. [记忆系统设计](#6-记忆系统设计)
7. [开发规范与解耦架构](#7-开发规范与解耦架构)
8. [目录结构规范](#8-目录结构规范)
9. [接口规范](#9-接口规范)
10. [数据库扩展](#10-数据库扩展)
11. [开发任务分解](#11-开发任务分解)
12. [里程碑规划](#12-里程碑规划)

---

## 1. 项目概述

### 1.1 项目背景

基于现有的 `stock_datasource` 金融数据采集系统，构建一个 AI 原生的智能选股与分析平台。该平台支持：

- **自然语言交互**：用户通过对话获取金融信息
- **智能选股**：基于多维度指标自动筛选符合条件的股票
- **行情分析**：技术指标分析（MACD、RSI、KDJ等）
- **财报研读**：AI 辅助解读财务报表
- **持仓管理**：模拟持仓录入、盈亏跟踪、每日AI自动分析
- **策略回测**：内置经典策略回测，验证交易策略有效性
- **用户记忆**：记住用户偏好和历史交互

### 1.2 核心目标

| 目标 | 描述 |
|------|------|
| AI 原生 | 以 LLM 为核心，自然语言作为主要交互方式 |
| 模块解耦 | 支持多人并行开发，每个功能独立闭环 |
| 可扩展 | 插件化架构，便于新增功能 |
| 高性能 | 利用 ClickHouse 处理海量金融数据 |

### 1.3 现有系统能力

```
已有数据表:
├── ods_daily           # A股日线数据
├── ods_adj_factor      # 复权因子
├── ods_daily_basic     # 日线基础指标(PE/PB/换手率等)
├── ods_stock_basic     # 股票基础信息
├── ods_stk_limit       # 涨跌停数据
├── ods_suspend_d       # 停复牌数据
├── ods_trade_calendar  # 交易日历
├── ods_hk_daily        # 港股日线
└── ods_hk_stock_list   # 港股列表

已有服务:
├── FastAPI HTTP Server  # RESTful API
├── MCP Server           # Model Context Protocol
├── 插件化数据采集       # 自动发现、自动路由生成
└── Airflow DAGs         # 定时任务调度
```

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              前端层 (Frontend)                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  对话界面   │  │  行情分析   │  │  智能选股   │  │  财报研读   │        │
│  │  ChatView   │  │ MarketView  │  │ScreenerView │  │ ReportView  │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│  ┌─────────────┐  ┌─────────────┐                                          │
│  │  持仓管理   │  │  策略回测   │                                          │
│  │PortfolioView│  │BacktestView │                                          │
│  └──────┬──────┘  └──────┬──────┘                                          │
│         └────────────────┴────────────────┴────────────────┘                │
│                                    │                                         │
│                          TDesign + Vue 3 + Pinia                            │
└────────────────────────────────────┼─────────────────────────────────────────┘
                                     │ HTTP/WebSocket
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            API Gateway 层                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     FastAPI Application                              │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │   │
│  │  │ /chat    │  │ /market  │  │ /screener│  │ /report  │            │   │
│  │  │  Router  │  │  Router  │  │  Router  │  │  Router  │            │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │   │
│  │  ┌──────────┐  ┌──────────┐                                         │   │
│  │  │/portfolio│  │/backtest │                                         │   │
│  │  │  Router  │  │  Router  │                                         │   │
│  │  └────┬─────┘  └────┬─────┘                                         │   │
│  └───────┼─────────────┼─────────────┼─────────────┼───────────────────┘   │
└──────────┼─────────────┼─────────────┼─────────────┼─────────────────────────┘
           │             │             │             │
           ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Agent 层 (DeepAgents)                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Orchestrator Agent (编排器)                       │   │
│  │         意图识别 → 任务分解 → Agent调度 → 结果聚合                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │              │              │              │                      │
│         ▼              ▼              ▼              ▼                      │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐               │
│  │  Chat     │  │  Market   │  │  Screener │  │  Report   │               │
│  │  Agent    │  │  Agent    │  │  Agent    │  │  Agent    │               │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘               │
│  ┌───────────┐  ┌───────────┐                                              │
│  │ Portfolio │  │ Backtest  │                                              │
│  │  Agent    │  │  Agent    │                                              │
│  └─────┬─────┘  └─────┬─────┘                                              │
│        │              │                                                     │
│  ┌─────┴──────────────┴──────────────┴──────────────┴─────┐                │
│  │                    Memory Agent (记忆管理)              │                │
│  └─────────────────────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────┘
           │              │              │              │
           ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           服务层 (Services)                                  │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐               │
│  │ LLM       │  │ Technical │  │ Screener  │  │ Financial │               │
│  │ Service   │  │ Indicator │  │ Service   │  │ Report    │               │
│  │           │  │ Service   │  │           │  │ Service   │               │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘               │
│  ┌───────────┐  ┌───────────┐                                              │
│  │ Portfolio │  │ Backtest  │                                              │
│  │ Service   │  │ Engine    │                                              │
│  └───────────┘  └───────────┘                                              │
└─────────────────────────────────────────────────────────────────────────────┘
           │              │              │              │
           ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           数据层 (Data Layer)                                │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌──────────────────┐   │
│  │     ClickHouse      │  │       Redis         │  │   Vector DB      │   │
│  │  (行情/财报/元数据)  │  │  (会话/缓存/记忆)   │  │  (语义检索)      │   │
│  └─────────────────────┘  └─────────────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心设计原则

| 原则 | 说明 |
|------|------|
| **垂直切片** | 每个功能模块包含完整的前端→API→Agent→Service链路 |
| **接口契约** | 模块间通过明确定义的接口通信，不直接依赖实现 |
| **插件化** | Agent、Service、前端组件均可独立开发和部署 |
| **事件驱动** | 模块间通过事件/消息解耦，支持异步处理 |

---

## 3. 技术栈选型

### 3.1 前端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue 3 | ^3.4 | 前端框架 |
| TDesign Vue Next | ^1.9 | UI 组件库 |
| Pinia | ^2.1 | 状态管理 |
| Vue Router | ^4.2 | 路由管理 |
| Vite | ^5.0 | 构建工具 |
| TypeScript | ^5.3 | 类型系统 |
| ECharts | ^5.5 | 图表可视化 |
| Axios | ^1.6 | HTTP 客户端 |

### 3.2 后端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 后端语言 |
| FastAPI | ^0.109 | Web 框架 |
| DeepAgents | latest | Agent 框架 |
| Pydantic | ^2.5 | 数据验证 |
| ClickHouse | 23.x | 时序数据库 |
| Redis | 7.x | 缓存/会话/记忆 |
| Milvus/Chroma | - | 向量数据库(可选) |

### 3.3 AI/LLM 技术栈

| 技术 | 用途 |
|------|------|
| DeepAgents | 多Agent编排框架 |
| OpenAI API / 本地模型 | LLM 推理 |
| LangChain (可选) | 工具链辅助 |

---

## 4. 功能模块设计

### 4.1 模块总览

| 模块ID | 模块名称 | 功能描述 | 优先级 |
|--------|----------|----------|--------|
| M01 | 对话交互 | 自然语言对话，意图理解 | P0 |
| M02 | 行情分析 | 技术指标计算与可视化 | P0 |
| M03 | 智能选股 | 多条件筛选，AI推荐 | P0 |
| M04 | 财报研读 | 财务数据分析，AI解读 | P1 |
| M05 | 用户记忆 | 偏好记录，个性化推荐 | P1 |
| M06 | 数据管理 | 数据源管理，采集监控 | P2 |
| M07 | 持仓管理 | 模拟持仓，盈亏跟踪，每日AI分析 | P1 |
| M08 | 策略回测 | 内置策略回测，绩效分析 | P1 |

### 4.2 模块详细设计

#### M01: 对话交互模块

```yaml
前端组件:
  - ChatView.vue          # 对话主界面
  - MessageList.vue       # 消息列表
  - InputBox.vue          # 输入框(支持语音)
  - SuggestionChips.vue   # 快捷建议

后端接口:
  - POST /api/chat/message     # 发送消息
  - GET  /api/chat/history     # 获取历史
  - WS   /api/chat/stream      # 流式响应

Agent:
  - ChatAgent              # 对话管理
  - IntentAgent            # 意图识别

功能:
  - 自然语言理解
  - 多轮对话上下文
  - 流式输出
  - 快捷指令
```

#### M02: 行情分析模块

```yaml
前端组件:
  - MarketView.vue         # 行情主界面
  - KLineChart.vue         # K线图
  - IndicatorPanel.vue     # 指标面板
  - StockSearch.vue        # 股票搜索

后端接口:
  - POST /api/market/kline          # K线数据
  - POST /api/market/indicators     # 技术指标
  - POST /api/market/analysis       # AI分析

Agent:
  - MarketAgent            # 行情分析Agent

Service:
  - TechnicalIndicatorService  # 技术指标计算
    - calculate_macd()
    - calculate_rsi()
    - calculate_kdj()
    - calculate_boll()
    - calculate_ma()

功能:
  - 实时/历史K线
  - 技术指标计算(MACD/RSI/KDJ/BOLL/MA)
  - AI走势分析
  - 估值分析
```

#### M03: 智能选股模块

```yaml
前端组件:
  - ScreenerView.vue       # 选股主界面
  - ConditionBuilder.vue   # 条件构建器
  - ResultTable.vue        # 结果表格
  - NLScreener.vue         # 自然语言选股

后端接口:
  - POST /api/screener/filter       # 条件筛选
  - POST /api/screener/nl           # 自然语言选股
  - GET  /api/screener/presets      # 预设策略

Agent:
  - ScreenerAgent          # 选股Agent

Service:
  - ScreenerService        # 选股服务
    - filter_by_conditions()
    - parse_nl_conditions()
    - recommend_stocks()

功能:
  - 多条件组合筛选
  - 自然语言描述转条件
  - 预设策略(低估值/高成长等)
  - AI选股推荐
```

#### M04: 财报研读模块

```yaml
前端组件:
  - ReportView.vue         # 财报主界面
  - FinancialTable.vue     # 财务数据表
  - TrendChart.vue         # 趋势图表
  - AIInsight.vue          # AI洞察

后端接口:
  - POST /api/report/financial      # 财务数据
  - POST /api/report/analysis       # AI分析
  - POST /api/report/compare        # 对比分析

Agent:
  - ReportAgent            # 财报分析Agent

Service:
  - FinancialReportService # 财报服务
    - get_income_statement()
    - get_balance_sheet()
    - get_cashflow()
    - analyze_financial_health()

功能:
  - 三大报表展示
  - 财务指标计算
  - 同业对比
  - AI财报解读
```

#### M05: 用户记忆模块

```yaml
前端组件:
  - MemoryView.vue           # 记忆管理主界面
  - PreferencePanel.vue      # 偏好设置面板
  - WatchlistManager.vue     # 自选股管理
  - HistoryTimeline.vue      # 历史交互时间线
  - UserProfile.vue          # 用户画像展示

后端接口:
  - GET    /api/memory/list              # 获取用户记忆列表
  - POST   /api/memory/save              # 保存记忆
  - DELETE /api/memory/{id}              # 删除记忆
  - GET    /api/memory/search            # 语义搜索记忆
  - GET    /api/preference/get           # 获取用户偏好
  - PUT    /api/preference/update        # 更新用户偏好
  - GET    /api/watchlist/list           # 获取自选股列表
  - POST   /api/watchlist/add            # 添加自选股
  - DELETE /api/watchlist/{ts_code}      # 删除自选股
  - GET    /api/history/interactions     # 获取交互历史
  - GET    /api/profile/summary          # 获取用户画像

Agent:
  - MemoryAgent              # 记忆管理Agent
    - 记忆存储与检索
    - 记忆重要性评估
    - 记忆过期清理
    - 上下文记忆注入

Service:
  - MemoryService            # 记忆服务
    - save_memory()
    - get_memories()
    - search_memories()
    - cleanup_expired()
  - PreferenceService        # 偏好服务
    - get_preference()
    - update_preference()
    - get_risk_profile()
  - WatchlistService         # 自选股服务
    - add_to_watchlist()
    - remove_from_watchlist()
    - get_watchlist()
  - UserProfileService       # 用户画像服务
    - build_profile()
    - get_profile_summary()
    - update_profile()

记忆类型:
  - short_term               # 短期记忆(会话上下文，Redis)
  - long_term                # 长期记忆(用户偏好，ClickHouse)
  - episodic                 # 情景记忆(历史交互，ClickHouse)
  - semantic                 # 语义记忆(向量检索，可选Vector DB)

功能:
  - 自选股管理(添加/删除/分组)
  - 用户偏好设置(风险偏好/行业偏好/投资风格)
  - 历史交互记录查看
  - 用户画像展示(投资偏好/关注热点/活跃度)
  - 个性化推荐数据支撑
  - 对话上下文记忆(多轮对话)
  - 记忆自动过期与清理
```

#### M06: 数据管理模块

```yaml
前端组件:
  - DataManageView.vue       # 数据管理主界面
  - DataSourceList.vue       # 数据源列表
  - SyncTaskPanel.vue        # 同步任务面板
  - QualityDashboard.vue     # 数据质量仪表盘
  - PluginManager.vue        # 插件管理器
  - DataExplorer.vue         # 数据浏览器

后端接口:
  - GET    /api/datasource/list          # 获取数据源列表
  - POST   /api/datasource/create        # 创建数据源配置
  - PUT    /api/datasource/{id}          # 更新数据源配置
  - DELETE /api/datasource/{id}          # 删除数据源
  - POST   /api/datasource/{id}/test     # 测试数据源连接
  - GET    /api/sync/tasks               # 获取同步任务列表
  - POST   /api/sync/trigger             # 手动触发同步
  - GET    /api/sync/status/{task_id}    # 获取同步状态
  - GET    /api/sync/history             # 获取同步历史
  - GET    /api/quality/report           # 获取数据质量报告
  - GET    /api/quality/metrics          # 获取质量指标
  - GET    /api/plugin/list              # 获取插件列表
  - POST   /api/plugin/{name}/enable     # 启用插件
  - POST   /api/plugin/{name}/disable    # 禁用插件
  - GET    /api/metadata/tables          # 获取数据表元信息
  - GET    /api/metadata/stats           # 获取数据统计

Agent:
  - DataManageAgent          # 数据管理Agent
    - 数据异常检测
    - 同步任务调度建议
    - 数据质量分析

Service:
  - DataSourceService        # 数据源服务
    - create_datasource()
    - update_datasource()
    - test_connection()
    - list_datasources()
  - SyncSchedulerService     # 同步调度服务
    - schedule_sync()
    - trigger_sync()
    - get_sync_status()
    - get_sync_history()
  - QualityService           # 数据质量服务
    - check_data_quality()
    - generate_quality_report()
    - get_quality_metrics()
  - PluginManagerService     # 插件管理服务
    - list_plugins()
    - enable_plugin()
    - disable_plugin()
    - get_plugin_status()
  - MetadataService          # 元数据服务
    - get_table_metadata()
    - get_data_stats()
    - refresh_metadata()

定时任务:
  - DataSyncScheduler        # 数据同步调度器(基于cron)
  - QualityCheckTask         # 每日数据质量检查
  - MetadataRefreshTask      # 元数据定期刷新

与现有插件系统集成:
  - 复用 src/stock_datasource/plugins/ 下的插件架构
  - 支持 TuShare/AKShare 等已有数据源
  - 提供统一的插件管理界面

功能:
  - 数据源配置管理(API密钥/连接参数/同步策略)
  - 同步任务调度(定时/手动/增量/全量)
  - 同步状态监控(进度/成功率/错误日志)
  - 数据质量检测(完整性/一致性/时效性)
  - 数据质量报告(可视化仪表盘)
  - 插件启用/禁用管理
  - 数据表元信息浏览
  - 数据统计概览(记录数/更新时间/存储占用)
```

#### M07: 持仓管理模块

```yaml
前端组件:
  - PortfolioView.vue      # 持仓主界面
  - PositionList.vue       # 持仓列表
  - AddPositionModal.vue   # 添加持仓弹窗
  - ProfitChart.vue        # 盈亏图表
  - DailyAnalysis.vue      # 每日分析报告

后端接口:
  - GET    /api/portfolio/positions      # 获取持仓列表
  - POST   /api/portfolio/positions      # 添加持仓
  - PUT    /api/portfolio/positions/{id} # 更新持仓
  - DELETE /api/portfolio/positions/{id} # 删除持仓
  - GET    /api/portfolio/summary        # 持仓汇总
  - GET    /api/portfolio/profit-history # 盈亏历史
  - POST   /api/portfolio/daily-analysis # 触发每日分析
  - GET    /api/portfolio/analysis/{date}# 获取分析报告

Agent:
  - PortfolioAgent         # 持仓分析Agent

Service:
  - PortfolioService       # 持仓服务
    - add_position()
    - update_position()
    - calculate_profit()
    - get_portfolio_summary()
  - DailyAnalysisService   # 每日分析服务
    - run_daily_analysis()
    - generate_analysis_report()

定时任务:
  - DailyPortfolioAnalysisTask  # 每日18:30自动分析用户持仓

功能:
  - 持仓录入(股票代码/数量/成本价/买入日期)
  - 实时盈亏计算(基于最新行情)
  - 持仓汇总(总市值/总成本/总盈亏/日涨跌)
  - 每日AI自动分析(技术面/基本面/风险提示)
  - 持仓预警(涨跌幅/止盈止损)
```

#### M08: 策略回测模块

```yaml
前端组件:
  - BacktestView.vue       # 回测主界面
  - StrategySelector.vue   # 策略选择器
  - ParamConfig.vue        # 参数配置面板
  - BacktestResult.vue     # 回测结果展示
  - TradeHistory.vue       # 交易记录表
  - PerformanceChart.vue   # 绩效曲线图

后端接口:
  - GET  /api/backtest/strategies        # 获取可用策略列表
  - GET  /api/backtest/strategies/{id}   # 获取策略详情及参数
  - POST /api/backtest/run               # 执行回测
  - GET  /api/backtest/results           # 获取历史回测结果
  - GET  /api/backtest/results/{id}      # 获取回测详情

Agent:
  - BacktestAgent          # 回测分析Agent

Service:
  - StrategyRegistry       # 策略注册中心
    - register_strategy()
    - get_strategy()
    - list_strategies()
  - BacktestEngine         # 回测引擎
    - run_backtest()
    - calculate_metrics()
    - generate_report()

内置策略:
  - MAStrategy             # 均线策略(金叉死叉)
  - MACDStrategy           # MACD策略
  - KDJStrategy            # KDJ策略
  - RSIStrategy            # RSI超买超卖策略
  - BollStrategy           # 布林带策略
  - DualMAStrategy         # 双均线策略
  - TurtleStrategy         # 海龟交易策略

扩展接口:
  - BaseStrategy           # 策略基类(预留用户自定义)

功能:
  - 策略选择与参数配置
  - 单股/多股回测
  - 自定义时间范围
  - 绩效指标计算(收益率/最大回撤/夏普比率/胜率)
  - 交易记录明细
  - 收益曲线可视化
  - 策略对比分析
```

---

## 5. DeepAgents 多Agent系统

### 5.1 Agent 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     Orchestrator Agent                          │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  1. 接收用户输入                                           │ │
│  │  2. 意图识别 (Intent Classification)                       │ │
│  │  3. 任务分解 (Task Decomposition)                          │ │
│  │  4. Agent 调度 (Agent Routing)                             │ │
│  │  5. 结果聚合 (Result Aggregation)                          │ │
│  │  6. 响应生成 (Response Generation)                         │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│  MarketAgent  │     │ ScreenerAgent │     │  ReportAgent  │
│               │     │               │     │               │
│ Tools:        │     │ Tools:        │     │ Tools:        │
│ - get_kline   │     │ - filter      │     │ - get_report  │
│ - calc_macd   │     │ - recommend   │     │ - analyze     │
│ - analyze     │     │ - parse_nl    │     │ - compare     │
└───────────────┘     └───────────────┘     └───────────────┘

┌───────────────┐     ┌───────────────┐
│PortfolioAgent│     │ BacktestAgent │
│               │     │               │
│ Tools:        │     │ Tools:        │
│ - get_positions│    │ - run_backtest│
│ - calc_profit │     │ - get_metrics │
│ - daily_report│     │ - compare     │
└───────────────┘     └───────────────┘
        │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                    ┌───────────────┐
                    │  MemoryAgent  │
                    │               │
                    │ - 上下文管理  │
                    │ - 偏好存储    │
                    │ - 历史检索    │
                    └───────────────┘
```

### 5.2 Agent 定义规范

每个 Agent 需要遵循以下结构：

```python
# src/stock_datasource/agents/base_agent.py

from abc import ABC, abstractmethod
from typing import Any, Dict, List
from pydantic import BaseModel

class AgentConfig(BaseModel):
    """Agent 配置"""
    name: str
    description: str
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 2000

class BaseTool(BaseModel):
    """工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]

class BaseAgent(ABC):
    """Agent 基类"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.tools: List[BaseTool] = []
        self._register_tools()
    
    @abstractmethod
    def _register_tools(self) -> None:
        """注册 Agent 可用的工具"""
        pass
    
    @abstractmethod
    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务"""
        pass
    
    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        return f"""你是 {self.config.name}。
{self.config.description}

你可以使用以下工具:
{self._format_tools()}
"""
    
    def _format_tools(self) -> str:
        return "\n".join([
            f"- {tool.name}: {tool.description}"
            for tool in self.tools
        ])
```

### 5.3 Agent 实现示例

```python
# src/stock_datasource/agents/market_agent.py

from .base_agent import BaseAgent, AgentConfig, BaseTool
from ..services.technical_indicator import TechnicalIndicatorService

class MarketAgent(BaseAgent):
    """行情分析 Agent"""
    
    def __init__(self):
        config = AgentConfig(
            name="MarketAgent",
            description="负责股票行情分析，包括技术指标计算、走势分析、估值分析等"
        )
        super().__init__(config)
        self.indicator_service = TechnicalIndicatorService()
    
    def _register_tools(self) -> None:
        self.tools = [
            BaseTool(
                name="get_kline",
                description="获取股票K线数据",
                parameters={
                    "code": {"type": "string", "description": "股票代码"},
                    "start_date": {"type": "string", "description": "开始日期"},
                    "end_date": {"type": "string", "description": "结束日期"}
                }
            ),
            BaseTool(
                name="calculate_indicators",
                description="计算技术指标(MACD/RSI/KDJ等)",
                parameters={
                    "code": {"type": "string", "description": "股票代码"},
                    "indicators": {"type": "array", "description": "指标列表"}
                }
            ),
            BaseTool(
                name="analyze_trend",
                description="分析股票走势",
                parameters={
                    "code": {"type": "string", "description": "股票代码"}
                }
            )
        ]
    
    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # 调用 LLM 进行任务理解和工具调用
        # 返回分析结果
        pass
```

### 5.3.1 MemoryAgent 实现示例 (M05)

```python
# src/stock_datasource/agents/memory_agent.py

from .base_agent import BaseAgent, AgentConfig, BaseTool
from ..modules.memory.service import MemoryService
from ..modules.memory.preference_service import PreferenceService
from ..modules.memory.watchlist_service import WatchlistService

class MemoryAgent(BaseAgent):
    """用户记忆管理 Agent"""
    
    def __init__(self):
        config = AgentConfig(
            name="MemoryAgent",
            description="负责用户记忆管理，包括偏好设置、自选股管理、历史交互检索、用户画像构建"
        )
        super().__init__(config)
        self.memory_service = MemoryService()
        self.preference_service = PreferenceService()
        self.watchlist_service = WatchlistService()
    
    def _register_tools(self) -> None:
        self.tools = [
            BaseTool(
                name="get_user_preference",
                description="获取用户偏好设置",
                parameters={
                    "user_id": {"type": "string", "description": "用户ID"}
                }
            ),
            BaseTool(
                name="update_user_preference",
                description="更新用户偏好设置",
                parameters={
                    "user_id": {"type": "string", "description": "用户ID"},
                    "preference_type": {"type": "string", "description": "偏好类型"},
                    "preference_value": {"type": "object", "description": "偏好值"}
                }
            ),
            BaseTool(
                name="get_watchlist",
                description="获取用户自选股列表",
                parameters={
                    "user_id": {"type": "string", "description": "用户ID"},
                    "group_name": {"type": "string", "description": "分组名称", "optional": True}
                }
            ),
            BaseTool(
                name="add_to_watchlist",
                description="添加股票到自选股",
                parameters={
                    "user_id": {"type": "string", "description": "用户ID"},
                    "ts_code": {"type": "string", "description": "股票代码"},
                    "group_name": {"type": "string", "description": "分组名称"}
                }
            ),
            BaseTool(
                name="search_memory",
                description="搜索用户历史记忆",
                parameters={
                    "user_id": {"type": "string", "description": "用户ID"},
                    "query": {"type": "string", "description": "搜索关键词"}
                }
            ),
            BaseTool(
                name="get_user_profile",
                description="获取用户画像",
                parameters={
                    "user_id": {"type": "string", "description": "用户ID"}
                }
            )
        ]
    
    async def inject_context_memory(self, user_id: str, current_query: str) -> Dict[str, Any]:
        """注入上下文记忆到对话中"""
        # 1. 获取用户偏好
        preference = await self.preference_service.get_preference(user_id)
        
        # 2. 获取自选股
        watchlist = await self.watchlist_service.get_watchlist(user_id)
        
        # 3. 搜索相关历史记忆
        relevant_memories = await self.memory_service.search_memories(
            user_id, current_query, limit=5
        )
        
        # 4. 获取最近交互摘要
        recent_summary = await self.memory_service.get_recent_summary(user_id)
        
        return {
            "preference": preference,
            "watchlist": [w.ts_code for w in watchlist],
            "relevant_memories": relevant_memories,
            "recent_summary": recent_summary
        }
    
    async def save_interaction_memory(
        self, 
        user_id: str, 
        intent: str, 
        user_input: str, 
        response: str,
        stocks_mentioned: List[str]
    ) -> None:
        """保存交互记忆"""
        await self.memory_service.save_interaction(
            user_id=user_id,
            intent=intent,
            user_input=user_input,
            response=response,
            stocks_mentioned=stocks_mentioned
        )
        
        # 如果提到新股票，自动更新用户关注记忆
        for stock in stocks_mentioned:
            await self.memory_service.update_stock_memory(user_id, stock)
```

### 5.3.2 DataManageAgent 实现示例 (M06)

```python
# src/stock_datasource/agents/datamanage_agent.py

from .base_agent import BaseAgent, AgentConfig, BaseTool
from ..modules.datamanage.service import DataSourceService
from ..modules.datamanage.sync_scheduler import SyncSchedulerService
from ..modules.datamanage.quality_service import QualityService

class DataManageAgent(BaseAgent):
    """数据管理 Agent"""
    
    def __init__(self):
        config = AgentConfig(
            name="DataManageAgent",
            description="负责数据源管理、同步任务调度、数据质量监控"
        )
        super().__init__(config)
        self.datasource_service = DataSourceService()
        self.sync_service = SyncSchedulerService()
        self.quality_service = QualityService()
    
    def _register_tools(self) -> None:
        self.tools = [
            BaseTool(
                name="list_datasources",
                description="获取数据源列表",
                parameters={}
            ),
            BaseTool(
                name="get_datasource_status",
                description="获取数据源状态",
                parameters={
                    "source_id": {"type": "string", "description": "数据源ID"}
                }
            ),
            BaseTool(
                name="trigger_sync",
                description="触发数据同步",
                parameters={
                    "source_id": {"type": "string", "description": "数据源ID"},
                    "sync_type": {"type": "string", "description": "同步类型: full/incremental"}
                }
            ),
            BaseTool(
                name="get_sync_status",
                description="获取同步任务状态",
                parameters={
                    "task_id": {"type": "string", "description": "任务ID"}
                }
            ),
            BaseTool(
                name="get_quality_report",
                description="获取数据质量报告",
                parameters={
                    "table_name": {"type": "string", "description": "表名", "optional": True},
                    "date": {"type": "string", "description": "日期", "optional": True}
                }
            ),
            BaseTool(
                name="analyze_data_issue",
                description="分析数据问题",
                parameters={
                    "table_name": {"type": "string", "description": "表名"},
                    "issue_type": {"type": "string", "description": "问题类型"}
                }
            )
        ]
    
    async def get_system_data_overview(self) -> Dict[str, Any]:
        """获取系统数据概览"""
        # 1. 获取所有数据源状态
        datasources = await self.datasource_service.list_datasources()
        
        # 2. 获取最近同步任务
        recent_tasks = await self.sync_service.get_recent_tasks(limit=10)
        
        # 3. 获取数据质量概览
        quality_summary = await self.quality_service.get_quality_summary()
        
        return {
            "datasources": datasources,
            "recent_sync_tasks": recent_tasks,
            "quality_summary": quality_summary,
            "total_tables": quality_summary.get("total_tables", 0),
            "overall_quality_score": quality_summary.get("overall_score", 0)
        }
    
    async def diagnose_sync_failure(self, task_id: str) -> str:
        """诊断同步失败原因 (需要 LLM)"""
        # 1. 获取任务详情
        task = await self.sync_service.get_task_detail(task_id)
        
        # 2. 获取错误日志
        error_log = task.get("error_message", "")
        
        # 3. 构建诊断 Prompt
        prompt = f"""请分析以下数据同步任务失败的原因:

任务信息:
- 数据源: {task.get('source_name')}
- 任务类型: {task.get('task_type')}
- 开始时间: {task.get('started_at')}
- 处理记录数: {task.get('records_processed')}

错误信息:
{error_log}

请分析:
1. 失败的可能原因
2. 建议的解决方案
3. 预防措施
"""
        return await self.llm.generate(prompt)
```

### 5.3.3 PortfolioAgent 实现示例 (M07)

```python
# src/stock_datasource/agents/portfolio_agent.py

from .base_agent import BaseAgent, AgentConfig, BaseTool
from ..modules.portfolio.service import PortfolioService

class PortfolioAgent(BaseAgent):
    """持仓管理 Agent"""
    
    def __init__(self):
        config = AgentConfig(
            name="PortfolioAgent",
            description="负责用户持仓管理，包括持仓查询、盈亏计算、每日分析报告生成"
        )
        super().__init__(config)
        self.service = PortfolioService()
    
    def _register_tools(self) -> None:
        self.tools = [
            BaseTool(
                name="get_positions",
                description="获取用户持仓列表",
                parameters={
                    "user_id": {"type": "string", "description": "用户ID"}
                }
            ),
            BaseTool(
                name="calculate_profit",
                description="计算持仓盈亏",
                parameters={
                    "user_id": {"type": "string", "description": "用户ID"}
                }
            ),
            BaseTool(
                name="generate_daily_report",
                description="生成每日持仓分析报告",
                parameters={
                    "user_id": {"type": "string", "description": "用户ID"},
                    "date": {"type": "string", "description": "分析日期"}
                }
            )
        ]
    
    async def generate_daily_analysis(self, user_id: str) -> str:
        """生成每日持仓分析报告 (需要 LLM)"""
        # 1. 获取持仓数据
        positions = await self.service.get_positions(user_id)
        summary = await self.service.get_portfolio_summary(user_id)
        
        # 2. 获取每只股票的技术指标
        stock_data = []
        for pos in positions:
            indicators = await self.service.get_stock_indicators(pos.ts_code)
            stock_data.append({
                "code": pos.ts_code,
                "name": pos.stock_name,
                "profit_rate": pos.profit_rate,
                "indicators": indicators
            })
        
        # 3. 构建分析 Prompt
        prompt = self._build_analysis_prompt(summary, stock_data)
        
        # 4. 调用 LLM 生成分析
        analysis = await self.llm.generate(prompt)
        
        # 5. 保存分析报告
        await self.service.save_analysis_report(user_id, analysis)
        
        return analysis
    
    def _build_analysis_prompt(self, summary: dict, stock_data: list) -> str:
        return f"""请分析以下用户的持仓组合:

持仓汇总:
- 总市值: {summary['total_value']:,.2f}
- 总成本: {summary['total_cost']:,.2f}
- 总盈亏: {summary['total_profit']:,.2f} ({summary['profit_rate']:.2f}%)
- 日涨跌: {summary['daily_change']:,.2f} ({summary['daily_change_rate']:.2f}%)

个股持仓:
{self._format_positions(stock_data)}

请从以下角度分析:
1. 整体持仓风险评估
2. 各持仓股票的技术面分析
3. 需要关注的风险点
4. 操作建议(持有/加仓/减仓)
"""
```

### 5.3.4 BacktestAgent 实现示例 (M08)

```python
# src/stock_datasource/agents/backtest_agent.py

from .base_agent import BaseAgent, AgentConfig, BaseTool
from ..modules.backtest.service import BacktestService
from ..modules.backtest.engine import BacktestEngine

class BacktestAgent(BaseAgent):
    """策略回测 Agent"""
    
    def __init__(self):
        config = AgentConfig(
            name="BacktestAgent",
            description="负责策略回测，包括策略选择、参数配置、回测执行、结果分析"
        )
        super().__init__(config)
        self.service = BacktestService()
        self.engine = BacktestEngine()
    
    def _register_tools(self) -> None:
        self.tools = [
            BaseTool(
                name="list_strategies",
                description="获取可用策略列表",
                parameters={}
            ),
            BaseTool(
                name="run_backtest",
                description="执行策略回测",
                parameters={
                    "strategy_id": {"type": "string", "description": "策略ID"},
                    "ts_codes": {"type": "array", "description": "股票代码列表"},
                    "start_date": {"type": "string", "description": "开始日期"},
                    "end_date": {"type": "string", "description": "结束日期"},
                    "params": {"type": "object", "description": "策略参数"}
                }
            ),
            BaseTool(
                name="analyze_result",
                description="分析回测结果",
                parameters={
                    "task_id": {"type": "string", "description": "回测任务ID"}
                }
            )
        ]
    
    async def run_backtest(self, request: BacktestRequest) -> BacktestResult:
        """执行回测"""
        # 1. 获取策略
        strategy = self.service.get_strategy(request.strategy_id)
        
        # 2. 加载历史数据
        data = await self.service.load_historical_data(
            request.ts_codes, 
            request.start_date, 
            request.end_date
        )
        
        # 3. 执行回测
        result = await self.engine.run(
            strategy=strategy,
            data=data,
            initial_capital=request.initial_capital,
            params=request.params
        )
        
        # 4. 保存结果
        await self.service.save_result(request.user_id, result)
        
        return result
    
    async def analyze_result_with_ai(self, task_id: str) -> str:
        """AI 分析回测结果"""
        result = await self.service.get_result(task_id)
        
        prompt = f"""请分析以下策略回测结果:

策略: {result.strategy_name}
回测区间: {result.start_date} ~ {result.end_date}
初始资金: {result.initial_capital:,.2f}

绩效指标:
- 总收益率: {result.total_return:.2f}%
- 年化收益率: {result.annual_return:.2f}%
- 最大回撤: {result.max_drawdown:.2f}%
- 夏普比率: {result.sharpe_ratio:.2f}
- 胜率: {result.win_rate:.2f}%
- 交易次数: {result.trade_count}

请分析:
1. 策略整体表现评价
2. 风险收益特征
3. 策略优缺点
4. 改进建议
"""
        return await self.llm.generate(prompt)
```

### 5.4 Orchestrator 编排逻辑

```python
# src/stock_datasource/agents/orchestrator.py

class OrchestratorAgent:
    """编排器 Agent"""
    
    INTENT_MAPPING = {
        "market_analysis": MarketAgent,
        "stock_screening": ScreenerAgent,
        "financial_report": ReportAgent,
        "portfolio_management": PortfolioAgent,
        "strategy_backtest": BacktestAgent,
        "general_chat": ChatAgent,
    }
    
    async def process(self, user_input: str, session_id: str) -> AsyncGenerator[str, None]:
        # 1. 获取会话上下文
        context = await self.memory.get_context(session_id)
        
        # 2. 意图识别
        intent = await self._classify_intent(user_input, context)
        
        # 3. 路由到对应 Agent
        agent_class = self.INTENT_MAPPING.get(intent, ChatAgent)
        agent = agent_class()
        
        # 4. 执行并流式返回
        async for chunk in agent.execute_stream(user_input, context):
            yield chunk
        
        # 5. 更新记忆
        await self.memory.update_context(session_id, user_input, result)
```

---

## 6. 记忆系统设计

### 6.1 记忆层次结构

```
┌─────────────────────────────────────────────────────────────────┐
│                        记忆系统架构                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              短期记忆 (Short-term Memory)                │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │  Redis: session:{session_id}                     │    │   │
│  │  │  - 当前对话上下文 (最近N轮)                       │    │   │
│  │  │  - 临时状态 (当前查看的股票等)                    │    │   │
│  │  │  - TTL: 24小时                                   │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              长期记忆 (Long-term Memory)                 │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │  ClickHouse: user_memory                         │    │   │
│  │  │  - 用户偏好 (关注板块/风险偏好/投资风格)          │    │   │
│  │  │  - 历史交互摘要                                  │    │   │
│  │  │  - 自选股列表                                    │    │   │
│  │  │  - 常用筛选条件                                  │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              语义记忆 (Semantic Memory) [可选]           │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │  Vector DB (Milvus/Chroma)                       │    │   │
│  │  │  - 历史对话向量化存储                            │    │   │
│  │  │  - 支持语义相似度检索                            │    │   │
│  │  │  - 用于 RAG 增强                                 │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 记忆数据模型

```python
# src/stock_datasource/memory/models.py

from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime

class ConversationTurn(BaseModel):
    """对话轮次"""
    role: str  # user / assistant
    content: str
    timestamp: datetime
    metadata: Optional[Dict] = None

class SessionContext(BaseModel):
    """会话上下文 (短期记忆)"""
    session_id: str
    user_id: str
    turns: List[ConversationTurn]
    current_stock: Optional[str] = None  # 当前关注的股票
    current_intent: Optional[str] = None  # 当前意图
    created_at: datetime
    updated_at: datetime

class UserPreference(BaseModel):
    """用户偏好 (长期记忆)"""
    user_id: str
    risk_level: str  # conservative / moderate / aggressive
    investment_style: str  # value / growth / momentum
    favorite_sectors: List[str]  # 关注板块
    watchlist: List[str]  # 自选股
    saved_screeners: List[Dict]  # 保存的筛选条件
    updated_at: datetime

class InteractionSummary(BaseModel):
    """交互摘要 (长期记忆)"""
    user_id: str
    date: str
    summary: str  # AI 生成的当日交互摘要
    key_stocks: List[str]  # 涉及的股票
    key_topics: List[str]  # 涉及的话题
```

### 6.3 ClickHouse 记忆表设计

```sql
-- 用户偏好表
CREATE TABLE IF NOT EXISTS user_preference (
    user_id LowCardinality(String),
    risk_level LowCardinality(String),
    investment_style LowCardinality(String),
    favorite_sectors Array(String),
    watchlist Array(String),
    saved_screeners String,  -- JSON
    version UInt64,
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(version)
ORDER BY user_id;

-- 交互历史表
CREATE TABLE IF NOT EXISTS user_interaction_log (
    user_id LowCardinality(String),
    session_id String,
    timestamp DateTime,
    intent LowCardinality(String),
    user_input String,
    assistant_response String,
    stocks_mentioned Array(String),
    metadata String  -- JSON
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (user_id, timestamp);

-- 交互摘要表 (每日)
CREATE TABLE IF NOT EXISTS user_interaction_summary (
    user_id LowCardinality(String),
    date Date,
    summary String,
    key_stocks Array(String),
    key_topics Array(String),
    version UInt64,
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(version)
ORDER BY (user_id, date);
```

### 6.4 Memory Service 实现

```python
# src/stock_datasource/memory/service.py

class MemoryService:
    """记忆服务"""
    
    def __init__(self):
        self.redis = RedisClient()
        self.db = ClickHouseClient()
    
    # ===== 短期记忆 =====
    
    async def get_session_context(self, session_id: str) -> SessionContext:
        """获取会话上下文"""
        data = await self.redis.get(f"session:{session_id}")
        if data:
            return SessionContext.model_validate_json(data)
        return None
    
    async def update_session_context(
        self, 
        session_id: str, 
        turn: ConversationTurn
    ) -> None:
        """更新会话上下文"""
        context = await self.get_session_context(session_id)
        if not context:
            context = SessionContext(session_id=session_id, turns=[])
        
        context.turns.append(turn)
        # 保留最近 20 轮
        context.turns = context.turns[-20:]
        context.updated_at = datetime.now()
        
        await self.redis.set(
            f"session:{session_id}",
            context.model_dump_json(),
            ex=86400  # 24小时过期
        )
    
    # ===== 长期记忆 =====
    
    async def get_user_preference(self, user_id: str) -> UserPreference:
        """获取用户偏好"""
        query = """
            SELECT * FROM user_preference 
            WHERE user_id = %(user_id)s
            ORDER BY version DESC LIMIT 1
        """
        result = self.db.execute_query(query, {"user_id": user_id})
        if not result.empty:
            return UserPreference(**result.iloc[0].to_dict())
        return None
    
    async def update_user_preference(self, pref: UserPreference) -> None:
        """更新用户偏好"""
        pref.version = int(datetime.now().timestamp() * 1000)
        self.db.insert_dataframe("user_preference", pref.to_dataframe())
    
    # ===== 记忆检索 =====
    
    async def get_relevant_history(
        self, 
        user_id: str, 
        query: str, 
        limit: int = 5
    ) -> List[InteractionSummary]:
        """获取相关历史交互"""
        # 基于关键词匹配或向量相似度检索
        pass
```

---

## 7. 开发规范与解耦架构

### 7.1 核心解耦原则

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         功能模块解耦架构                                     │
│                                                                              │
│   每个功能 = 前端组件 + API Router + Agent + Service                        │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    Module: market (行情分析)                         │  │
│   │                                                                      │  │
│   │   frontend/                  backend/                                │  │
│   │   └── views/                 └── modules/                            │  │
│   │       └── market/                └── market/                         │  │
│   │           ├── MarketView.vue         ├── router.py    # API 路由    │  │
│   │           ├── components/            ├── agent.py     # Agent       │  │
│   │           │   ├── KLineChart.vue     ├── service.py   # 业务逻辑    │  │
│   │           │   └── IndicatorPanel.vue ├── schemas.py   # 数据模型    │  │
│   │           ├── composables/           └── tests/       # 单元测试    │  │
│   │           │   └── useMarket.ts                                       │  │
│   │           └── types.ts                                               │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   模块间通信:                                                                │
│   - 前端: 通过 Pinia Store 共享状态                                         │
│   - 后端: 通过 Service 层接口调用，禁止 Agent 间直接调用                     │
│   - 跨模块: 通过 EventBus 或 消息队列                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 模块开发流程

```
开发一个新功能的标准流程:

1. 定义接口契约
   └── 编写 schemas.py (Pydantic 模型)
   └── 编写 types.ts (TypeScript 类型)

2. 后端开发 (可并行)
   ├── 2.1 Service 层
   │   └── 实现业务逻辑，调用数据层
   ├── 2.2 Agent 层
   │   └── 实现 AI 能力，调用 Service
   └── 2.3 Router 层
       └── 暴露 API 接口，调用 Agent

3. 前端开发 (可并行)
   ├── 3.1 API 层
   │   └── 封装 API 调用
   ├── 3.2 Store 层
   │   └── 状态管理
   └── 3.3 View 层
       └── 页面和组件

4. 集成测试
   └── 端到端测试
```

### 7.3 模块接口规范

#### 7.3.1 后端 Router 规范

```python
# src/stock_datasource/modules/market/router.py

from fastapi import APIRouter, Depends
from .schemas import KLineRequest, KLineResponse, IndicatorRequest, IndicatorResponse
from .agent import MarketAgent

router = APIRouter(prefix="/market", tags=["行情分析"])

@router.post("/kline", response_model=KLineResponse)
async def get_kline(request: KLineRequest):
    """获取K线数据"""
    agent = MarketAgent()
    return await agent.get_kline(request)

@router.post("/indicators", response_model=IndicatorResponse)
async def get_indicators(request: IndicatorRequest):
    """获取技术指标"""
    agent = MarketAgent()
    return await agent.calculate_indicators(request)

@router.post("/analysis")
async def analyze_stock(request: AnalysisRequest):
    """AI分析股票"""
    agent = MarketAgent()
    async def generate():
        async for chunk in agent.analyze_stream(request):
            yield f"data: {chunk}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

#### 7.3.2 后端 Schema 规范

```python
# src/stock_datasource/modules/market/schemas.py

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date

class KLineRequest(BaseModel):
    """K线请求"""
    code: str = Field(..., description="股票代码", example="000001.SZ")
    start_date: date = Field(..., description="开始日期")
    end_date: date = Field(..., description="结束日期")
    adjust: str = Field(default="qfq", description="复权类型: qfq/hfq/none")

class KLineData(BaseModel):
    """K线数据"""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float

class KLineResponse(BaseModel):
    """K线响应"""
    code: str
    name: str
    data: List[KLineData]

class IndicatorRequest(BaseModel):
    """技术指标请求"""
    code: str = Field(..., description="股票代码")
    indicators: List[str] = Field(
        default=["macd", "rsi", "kdj"],
        description="指标列表"
    )
    period: int = Field(default=60, description="计算周期(天)")

class IndicatorValue(BaseModel):
    """指标值"""
    date: str
    values: dict  # {"macd": 0.5, "rsi": 65, ...}

class IndicatorResponse(BaseModel):
    """技术指标响应"""
    code: str
    indicators: List[IndicatorValue]
```

#### 7.3.3 前端 API 规范

```typescript
// frontend/src/api/market.ts

import { request } from '@/utils/request'
import type { KLineRequest, KLineResponse, IndicatorRequest, IndicatorResponse } from '@/types/market'

export const marketApi = {
  /**
   * 获取K线数据
   */
  getKLine(params: KLineRequest): Promise<KLineResponse> {
    return request.post('/market/kline', params)
  },

  /**
   * 获取技术指标
   */
  getIndicators(params: IndicatorRequest): Promise<IndicatorResponse> {
    return request.post('/market/indicators', params)
  },

  /**
   * AI分析股票 (流式)
   */
  analyzeStock(params: AnalysisRequest): EventSource {
    return new EventSource(`/api/market/analysis?${new URLSearchParams(params)}`)
  }
}
```

#### 7.3.4 前端 Store 规范

```typescript
// frontend/src/stores/market.ts

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { marketApi } from '@/api/market'
import type { KLineData, IndicatorValue } from '@/types/market'

export const useMarketStore = defineStore('market', () => {
  // State
  const currentCode = ref<string>('')
  const klineData = ref<KLineData[]>([])
  const indicators = ref<IndicatorValue[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const latestPrice = computed(() => {
    if (klineData.value.length === 0) return null
    return klineData.value[klineData.value.length - 1].close
  })

  // Actions
  async function fetchKLine(code: string, startDate: string, endDate: string) {
    loading.value = true
    error.value = null
    try {
      const response = await marketApi.getKLine({ code, start_date: startDate, end_date: endDate })
      currentCode.value = code
      klineData.value = response.data
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchIndicators(code: string, indicatorList: string[]) {
    loading.value = true
    try {
      const response = await marketApi.getIndicators({ code, indicators: indicatorList })
      indicators.value = response.indicators
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  return {
    currentCode,
    klineData,
    indicators,
    loading,
    error,
    latestPrice,
    fetchKLine,
    fetchIndicators
  }
})
```

### 7.4 Agent 开发规范

```python
# src/stock_datasource/modules/market/agent.py

from typing import AsyncGenerator
from ..base_agent import BaseAgent, AgentConfig
from .service import MarketService
from .schemas import KLineRequest, KLineResponse

class MarketAgent(BaseAgent):
    """行情分析 Agent"""
    
    def __init__(self):
        config = AgentConfig(
            name="MarketAgent",
            description="负责股票行情分析，包括K线、技术指标、走势分析"
        )
        super().__init__(config)
        self.service = MarketService()
    
    async def get_kline(self, request: KLineRequest) -> KLineResponse:
        """获取K线数据 (直接调用 Service，无需 LLM)"""
        return await self.service.get_kline(request)
    
    async def calculate_indicators(self, request: IndicatorRequest) -> IndicatorResponse:
        """计算技术指标 (直接调用 Service)"""
        return await self.service.calculate_indicators(request)
    
    async def analyze_stream(self, request: AnalysisRequest) -> AsyncGenerator[str, None]:
        """AI 分析股票走势 (需要 LLM)"""
        # 1. 获取数据
        kline = await self.service.get_kline(request.code, request.period)
        indicators = await self.service.calculate_all_indicators(request.code)
        
        # 2. 构建 Prompt
        prompt = self._build_analysis_prompt(kline, indicators)
        
        # 3. 调用 LLM 流式生成
        async for chunk in self.llm.stream(prompt):
            yield chunk
    
    def _build_analysis_prompt(self, kline: list, indicators: dict) -> str:
        return f"""请分析以下股票的走势:

K线数据 (最近30天):
{self._format_kline(kline[-30:])}

技术指标:
- MACD: {indicators['macd']}
- RSI: {indicators['rsi']}
- KDJ: {indicators['kdj']}

请从以下角度分析:
1. 当前趋势判断
2. 技术指标信号
3. 支撑位和压力位
4. 短期操作建议
"""
```

### 7.5 Service 开发规范

```python
# src/stock_datasource/modules/market/service.py

from typing import List, Dict
import pandas as pd
from ...models.database import db_client
from .schemas import KLineRequest, KLineResponse, KLineData

class MarketService:
    """行情服务层 - 纯业务逻辑，不涉及 AI"""
    
    def __init__(self):
        self.db = db_client
    
    async def get_kline(self, request: KLineRequest) -> KLineResponse:
        """获取K线数据"""
        query = """
            SELECT 
                trade_date,
                open, high, low, close,
                vol as volume,
                amount
            FROM ods_daily
            WHERE ts_code = %(code)s
              AND trade_date BETWEEN %(start)s AND %(end)s
            ORDER BY trade_date
        """
        df = self.db.execute_query(query, {
            "code": request.code,
            "start": request.start_date.strftime("%Y%m%d"),
            "end": request.end_date.strftime("%Y%m%d")
        })
        
        # 复权处理
        if request.adjust != "none":
            df = self._adjust_price(df, request.code, request.adjust)
        
        return KLineResponse(
            code=request.code,
            name=self._get_stock_name(request.code),
            data=[KLineData(**row) for row in df.to_dict('records')]
        )
    
    async def calculate_macd(self, prices: pd.Series, fast=12, slow=26, signal=9) -> Dict:
        """计算 MACD 指标"""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        macd = (dif - dea) * 2
        return {
            "dif": dif.tolist(),
            "dea": dea.tolist(),
            "macd": macd.tolist()
        }
    
    async def calculate_rsi(self, prices: pd.Series, period=14) -> List[float]:
        """计算 RSI 指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.tolist()
    
    async def calculate_kdj(self, high: pd.Series, low: pd.Series, close: pd.Series, n=9) -> Dict:
        """计算 KDJ 指标"""
        low_n = low.rolling(window=n).min()
        high_n = high.rolling(window=n).max()
        rsv = (close - low_n) / (high_n - low_n) * 100
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        j = 3 * k - 2 * d
        return {"k": k.tolist(), "d": d.tolist(), "j": j.tolist()}
```

### 7.6 策略回测引擎设计

```python
# src/stock_datasource/modules/backtest/strategies/base.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import pandas as pd

class SignalType(Enum):
    """交易信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

@dataclass
class Signal:
    """交易信号"""
    date: str
    signal_type: SignalType
    price: float
    reason: str

@dataclass
class StrategyParam:
    """策略参数定义"""
    name: str
    type: str  # int/float/bool
    default: Any
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    description: str = ""

class BaseStrategy(ABC):
    """
    策略基类 - 所有策略必须继承此类
    
    扩展性设计:
    - 子类只需实现 generate_signals() 方法
    - 参数通过 get_params() 定义，支持动态配置
    - 后续可扩展为用户自定义策略
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """策略描述"""
        pass
    
    @property
    def category(self) -> str:
        """策略分类: trend/momentum/mean_reversion"""
        return "trend"
    
    @abstractmethod
    def get_params(self) -> List[StrategyParam]:
        """获取策略参数定义"""
        pass
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame, params: Dict[str, Any]) -> List[Signal]:
        """
        生成交易信号
        
        Args:
            data: 包含 OHLCV 的 DataFrame
            params: 策略参数
            
        Returns:
            信号列表
        """
        pass


# src/stock_datasource/modules/backtest/strategies/ma_strategy.py

class MAStrategy(BaseStrategy):
    """均线策略 - 金叉买入，死叉卖出"""
    
    @property
    def name(self) -> str:
        return "均线策略"
    
    @property
    def description(self) -> str:
        return "基于短期均线和长期均线的交叉信号进行交易。短期均线上穿长期均线(金叉)买入，下穿(死叉)卖出。"
    
    def get_params(self) -> List[StrategyParam]:
        return [
            StrategyParam("short_period", "int", 5, 2, 30, "短期均线周期"),
            StrategyParam("long_period", "int", 20, 10, 120, "长期均线周期"),
        ]
    
    def generate_signals(self, data: pd.DataFrame, params: Dict[str, Any]) -> List[Signal]:
        short_period = params.get("short_period", 5)
        long_period = params.get("long_period", 20)
        
        # 计算均线
        data["ma_short"] = data["close"].rolling(window=short_period).mean()
        data["ma_long"] = data["close"].rolling(window=long_period).mean()
        
        signals = []
        position = 0  # 0: 空仓, 1: 持仓
        
        for i in range(long_period, len(data)):
            row = data.iloc[i]
            prev_row = data.iloc[i-1]
            
            # 金叉: 短期均线上穿长期均线
            if prev_row["ma_short"] <= prev_row["ma_long"] and row["ma_short"] > row["ma_long"]:
                if position == 0:
                    signals.append(Signal(
                        date=str(row["trade_date"]),
                        signal_type=SignalType.BUY,
                        price=row["close"],
                        reason=f"金叉: MA{short_period}上穿MA{long_period}"
                    ))
                    position = 1
            
            # 死叉: 短期均线下穿长期均线
            elif prev_row["ma_short"] >= prev_row["ma_long"] and row["ma_short"] < row["ma_long"]:
                if position == 1:
                    signals.append(Signal(
                        date=str(row["trade_date"]),
                        signal_type=SignalType.SELL,
                        price=row["close"],
                        reason=f"死叉: MA{short_period}下穿MA{long_period}"
                    ))
                    position = 0
        
        return signals


# src/stock_datasource/modules/backtest/engine.py

class BacktestEngine:
    """回测引擎"""
    
    def __init__(self):
        self.commission_rate = 0.0003  # 手续费率
        self.slippage = 0.001  # 滑点
    
    async def run(
        self,
        strategy: BaseStrategy,
        data: pd.DataFrame,
        initial_capital: float = 100000,
        params: Dict[str, Any] = None
    ) -> BacktestResult:
        """执行回测"""
        params = params or {}
        
        # 1. 生成信号
        signals = strategy.generate_signals(data, params)
        
        # 2. 模拟交易
        trades, equity_curve = self._simulate_trades(data, signals, initial_capital)
        
        # 3. 计算绩效指标
        metrics = self._calculate_metrics(trades, equity_curve, initial_capital)
        
        return BacktestResult(
            strategy_name=strategy.name,
            initial_capital=initial_capital,
            final_capital=equity_curve[-1] if equity_curve else initial_capital,
            trades=trades,
            equity_curve=equity_curve,
            **metrics
        )
    
    def _simulate_trades(
        self, 
        data: pd.DataFrame, 
        signals: List[Signal], 
        initial_capital: float
    ) -> Tuple[List[Trade], List[float]]:
        """模拟交易执行"""
        cash = initial_capital
        position = 0
        trades = []
        equity_curve = []
        
        signal_dict = {s.date: s for s in signals}
        
        for i, row in data.iterrows():
            date_str = str(row["trade_date"])
            
            if date_str in signal_dict:
                signal = signal_dict[date_str]
                price = signal.price * (1 + self.slippage if signal.signal_type == SignalType.BUY else 1 - self.slippage)
                
                if signal.signal_type == SignalType.BUY and position == 0:
                    # 买入
                    quantity = int(cash * 0.95 / price / 100) * 100  # 按手买入
                    if quantity > 0:
                        amount = quantity * price
                        commission = amount * self.commission_rate
                        cash -= (amount + commission)
                        position = quantity
                        trades.append(Trade(
                            date=date_str,
                            direction="buy",
                            price=price,
                            quantity=quantity,
                            amount=amount,
                            commission=commission
                        ))
                
                elif signal.signal_type == SignalType.SELL and position > 0:
                    # 卖出
                    amount = position * price
                    commission = amount * self.commission_rate
                    cash += (amount - commission)
                    trades.append(Trade(
                        date=date_str,
                        direction="sell",
                        price=price,
                        quantity=position,
                        amount=amount,
                        commission=commission
                    ))
                    position = 0
            
            # 记录权益
            equity = cash + position * row["close"]
            equity_curve.append(equity)
        
        return trades, equity_curve
    
    def _calculate_metrics(
        self, 
        trades: List[Trade], 
        equity_curve: List[float], 
        initial_capital: float
    ) -> Dict[str, float]:
        """计算绩效指标"""
        if not equity_curve:
            return {}
        
        final_capital = equity_curve[-1]
        total_return = (final_capital - initial_capital) / initial_capital * 100
        
        # 最大回撤
        peak = equity_curve[0]
        max_drawdown = 0
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak * 100
            max_drawdown = max(max_drawdown, drawdown)
        
        # 胜率
        wins = 0
        for i in range(0, len(trades) - 1, 2):
            if i + 1 < len(trades):
                buy_trade = trades[i]
                sell_trade = trades[i + 1]
                if sell_trade.price > buy_trade.price:
                    wins += 1
        
        trade_pairs = len(trades) // 2
        win_rate = (wins / trade_pairs * 100) if trade_pairs > 0 else 0
        
        # 夏普比率 (简化计算)
        returns = pd.Series(equity_curve).pct_change().dropna()
        sharpe_ratio = (returns.mean() / returns.std() * (252 ** 0.5)) if len(returns) > 0 and returns.std() > 0 else 0
        
        return {
            "total_return": total_return,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "sharpe_ratio": sharpe_ratio,
            "trade_count": len(trades)
        }
```

### 7.7 并行开发分工示例

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           并行开发分工                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  开发者 A: 对话交互模块                                                      │
│  ├── frontend/views/chat/*                                                  │
│  ├── backend/modules/chat/*                                                 │
│  └── 依赖: 无 (基础模块)                                                    │
│                                                                              │
│  开发者 B: 行情分析模块                                                      │
│  ├── frontend/views/market/*                                                │
│  ├── backend/modules/market/*                                               │
│  └── 依赖: 现有 ods_daily 数据                                              │
│                                                                              │
│  开发者 C: 智能选股模块                                                      │
│  ├── frontend/views/screener/*                                              │
│  ├── backend/modules/screener/*                                             │
│  └── 依赖: 现有 ods_daily_basic 数据                                        │
│                                                                              │
│  开发者 D: 财报研读模块                                                      │
│  ├── frontend/views/report/*                                                │
│  ├── backend/modules/report/*                                               │
│  ├── backend/plugins/tushare_income/*      (新增数据插件)                   │
│  └── 依赖: 需先开发财报数据插件                                             │
│                                                                              │
│  开发者 E: 用户记忆模块 (M05)                                                │
│  ├── frontend/views/memory/*                                                │
│  ├── backend/modules/memory/*                                               │
│  ├── backend/agents/memory_agent.py                                         │
│  └── 依赖: Redis + ClickHouse 记忆表                                        │
│                                                                              │
│  开发者 F: 数据管理模块 (M06)                                                │
│  ├── frontend/views/datamanage/*                                            │
│  ├── backend/modules/datamanage/*                                           │
│  ├── backend/agents/datamanage_agent.py                                     │
│  └── 依赖: 现有插件系统                                                     │
│                                                                              │
│  开发者 G: Agent 框架 & Orchestrator                                        │
│  ├── backend/agents/base_agent.py                                           │
│  ├── backend/agents/orchestrator.py                                         │
│  └── 依赖: 各模块 Agent 接口定义                                            │
│                                                                              │
│  开发者 H: 持仓管理模块 (M07)                                                │
│  ├── frontend/views/portfolio/*                                             │
│  ├── backend/modules/portfolio/*                                            │
│  ├── backend/agents/portfolio_agent.py                                      │
│  └── 依赖: 现有 ods_daily 数据 + 记忆系统                                   │
│                                                                              │
│  开发者 I: 策略回测模块 (M08)                                                │
│  ├── frontend/views/backtest/*                                              │
│  ├── backend/modules/backtest/*                                             │
│  ├── backend/agents/backtest_agent.py                                       │
│  └── 依赖: 现有 ods_daily 数据 + 技术指标服务                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. 目录结构规范

### 8.1 项目整体结构

```
stock_datasource/
├── frontend/                          # 前端项目 (Vue 3 + TDesign)
│   ├── public/
│   ├── src/
│   │   ├── api/                       # API 调用封装
│   │   │   ├── chat.ts
│   │   │   ├── market.ts
│   │   │   ├── screener.ts
│   │   │   ├── report.ts
│   │   │   ├── portfolio.ts
│   │   │   └── backtest.ts
│   │   ├── assets/                    # 静态资源
│   │   ├── components/                # 通用组件
│   │   │   ├── common/
│   │   │   │   ├── StockSearch.vue
│   │   │   │   └── LoadingSpinner.vue
│   │   │   └── charts/
│   │   │       ├── KLineChart.vue
│   │   │       └── IndicatorChart.vue
│   │   ├── composables/               # 组合式函数
│   │   │   ├── useChat.ts
│   │   │   └── useStock.ts
│   │   ├── layouts/                   # 布局组件
│   │   │   └── MainLayout.vue
│   │   ├── router/                    # 路由配置
│   │   │   └── index.ts
│   │   ├── stores/                    # Pinia 状态管理
│   │   │   ├── chat.ts
│   │   │   ├── market.ts
│   │   │   ├── screener.ts
│   │   │   ├── report.ts
│   │   │   ├── memory.ts
│   │   │   ├── datamanage.ts
│   │   │   ├── portfolio.ts
│   │   │   ├── backtest.ts
│   │   │   └── user.ts
│   │   ├── styles/                    # 全局样式
│   │   ├── types/                     # TypeScript 类型
│   │   │   ├── chat.ts
│   │   │   ├── market.ts
│   │   │   └── common.ts
│   │   ├── utils/                     # 工具函数
│   │   │   ├── request.ts
│   │   │   └── format.ts
│   │   ├── views/                     # 页面视图
│   │   │   ├── chat/
│   │   │   │   ├── ChatView.vue
│   │   │   │   └── components/
│   │   │   │       ├── MessageList.vue
│   │   │   │       └── InputBox.vue
│   │   │   ├── market/
│   │   │   │   ├── MarketView.vue
│   │   │   │   └── components/
│   │   │   │       └── IndicatorPanel.vue
│   │   │   ├── screener/
│   │   │   │   ├── ScreenerView.vue
│   │   │   │   └── components/
│   │   │   │       └── ConditionBuilder.vue
│   │   │   └── report/
│   │   │       ├── ReportView.vue
│   │   │       └── components/
│   │   │           └── FinancialTable.vue
│   │   │   ├── memory/
│   │   │   │   ├── MemoryView.vue
│   │   │   │   └── components/
│   │   │   │       ├── PreferencePanel.vue
│   │   │   │       ├── WatchlistManager.vue
│   │   │   │       ├── HistoryTimeline.vue
│   │   │   │       └── UserProfile.vue
│   │   │   ├── datamanage/
│   │   │   │   ├── DataManageView.vue
│   │   │   │   └── components/
│   │   │   │       ├── DataSourceList.vue
│   │   │   │       ├── SyncTaskPanel.vue
│   │   │   │       ├── QualityDashboard.vue
│   │   │   │       ├── PluginManager.vue
│   │   │   │       └── DataExplorer.vue
│   │   │   ├── portfolio/
│   │   │   │   ├── PortfolioView.vue
│   │   │   │   └── components/
│   │   │   │       ├── PositionList.vue
│   │   │   │       ├── AddPositionModal.vue
│   │   │   │       └── DailyAnalysis.vue
│   │   │   └── backtest/
│   │   │       ├── BacktestView.vue
│   │   │       └── components/
│   │   │           ├── StrategySelector.vue
│   │   │           ├── ParamConfig.vue
│   │   │           └── BacktestResult.vue
│   │   ├── App.vue
│   │   └── main.ts
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
│
├── src/stock_datasource/              # 后端项目 (已有 + 扩展)
│   ├── agents/                        # Agent 层 (新增)
│   │   ├── __init__.py
│   │   ├── base_agent.py              # Agent 基类
│   │   ├── orchestrator.py            # 编排器
│   │   ├── chat_agent.py              # 对话 Agent
│   │   ├── market_agent.py            # 行情 Agent
│   │   ├── screener_agent.py          # 选股 Agent
│   │   ├── report_agent.py            # 财报 Agent
│   │   ├── memory_agent.py            # 记忆 Agent
│   │   ├── datamanage_agent.py        # 数据管理 Agent
│   │   ├── portfolio_agent.py         # 持仓 Agent
│   │   └── backtest_agent.py          # 回测 Agent
│   │
│   ├── modules/                       # 业务模块 (新增)
│   │   ├── __init__.py
│   │   ├── chat/
│   │   │   ├── __init__.py
│   │   │   ├── router.py              # API 路由
│   │   │   ├── schemas.py             # 数据模型
│   │   │   └── service.py             # 业务逻辑
│   │   ├── market/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   ├── screener/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   └── report/
│   │       ├── __init__.py
│   │       ├── router.py
│   │       ├── schemas.py
│   │       └── service.py
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── preference_service.py  # 偏好服务
│   │   │   └── watchlist_service.py   # 自选股服务
│   │   ├── datamanage/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── sync_scheduler.py      # 同步调度器
│   │   │   ├── quality_service.py     # 质量服务
│   │   │   └── plugin_manager.py      # 插件管理
│   │   ├── portfolio/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   └── backtest/
│   │       ├── __init__.py
│   │       ├── router.py
│   │       ├── schemas.py
│   │       ├── service.py
│   │       ├── engine.py              # 回测引擎
│   │       └── strategies/            # 策略目录
│   │           ├── __init__.py
│   │           ├── base.py            # 策略基类
│   │           ├── ma_strategy.py     # 均线策略
│   │           ├── macd_strategy.py   # MACD策略
│   │           ├── kdj_strategy.py    # KDJ策略
│   │           ├── rsi_strategy.py    # RSI策略
│   │           └── boll_strategy.py   # 布林带策略
│   │
│   ├── memory/                        # 记忆系统 (新增)
│   │   ├── __init__.py
│   │   ├── models.py                  # 记忆数据模型
│   │   ├── service.py                 # 记忆服务
│   │   ├── redis_client.py            # Redis 客户端
│   │   └── vector_store.py            # 向量存储(可选)
│   │
│   ├── llm/                           # LLM 集成 (新增)
│   │   ├── __init__.py
│   │   ├── base.py                    # LLM 基类
│   │   ├── openai_client.py           # OpenAI 客户端
│   │   └── local_client.py            # 本地模型客户端
│   │
│   ├── config/                        # 配置 (已有)
│   │   └── settings.py
│   │
│   ├── core/                          # 核心模块 (已有)
│   │   ├── base_plugin.py
│   │   ├── base_service.py
│   │   ├── plugin_manager.py
│   │   └── service_generator.py
│   │
│   ├── models/                        # 数据模型 (已有)
│   │   ├── database.py
│   │   └── schemas.py
│   │
│   ├── plugins/                       # 数据插件 (已有 + 扩展)
│   │   ├── tushare_daily/
│   │   ├── tushare_income/            # 利润表 (新增)
│   │   ├── tushare_balance/           # 资产负债表 (新增)
│   │   └── tushare_cashflow/          # 现金流量表 (新增)
│   │
│   ├── services/                      # 服务层 (已有)
│   │   ├── http_server.py
│   │   └── mcp_server.py
│   │
│   └── utils/                         # 工具 (已有)
│       └── logger.py
│
├── tests/                             # 测试
│   ├── frontend/                      # 前端测试
│   ├── backend/                       # 后端测试
│   │   ├── test_agents/
│   │   ├── test_modules/
│   │   └── test_memory/
│   └── e2e/                           # 端到端测试
│
├── docs/                              # 文档
│   ├── AI_STOCK_PLATFORM_DESIGN.md    # 本设计文档
│   ├── API_REFERENCE.md               # API 参考
│   └── DEVELOPMENT_GUIDE.md           # 开发指南
│
├── scripts/                           # 脚本
│   ├── init_db.py                     # 初始化数据库
│   └── seed_data.py                   # 种子数据
│
├── cli.py                             # CLI 入口
├── pyproject.toml                     # Python 依赖
└── README.md
```

### 8.2 模块内部结构规范

每个业务模块遵循统一结构：

```
modules/{module_name}/
├── __init__.py           # 模块导出
├── router.py             # FastAPI 路由定义
├── schemas.py            # Pydantic 请求/响应模型
├── service.py            # 业务逻辑实现
└── tests/                # 模块单元测试
    ├── test_router.py
    └── test_service.py
```

---

## 9. 接口规范

### 9.1 RESTful API 规范

| 方法 | 路径模式 | 用途 |
|------|----------|------|
| GET | `/api/{module}/{resource}` | 获取资源列表 |
| GET | `/api/{module}/{resource}/{id}` | 获取单个资源 |
| POST | `/api/{module}/{action}` | 执行操作 |
| PUT | `/api/{module}/{resource}/{id}` | 更新资源 |
| DELETE | `/api/{module}/{resource}/{id}` | 删除资源 |

### 9.2 统一响应格式

```python
# 成功响应
{
    "code": 0,
    "message": "success",
    "data": { ... }
}

# 错误响应
{
    "code": 40001,
    "message": "Invalid stock code",
    "data": null
}

# 流式响应 (SSE)
data: {"type": "chunk", "content": "分析结果..."}
data: {"type": "chunk", "content": "继续输出..."}
data: {"type": "done", "content": ""}
```

### 9.3 错误码定义

| 错误码 | 说明 |
|--------|------|
| 0 | 成功 |
| 40001 | 参数错误 |
| 40002 | 资源不存在 |
| 40101 | 未授权 |
| 50001 | 服务器内部错误 |
| 50002 | 数据库错误 |
| 50003 | LLM 调用失败 |

### 9.4 WebSocket 消息格式

```typescript
// 客户端发送
{
    "type": "chat",
    "session_id": "xxx",
    "content": "帮我分析一下贵州茅台"
}

// 服务端响应
{
    "type": "message",
    "role": "assistant",
    "content": "正在分析贵州茅台(600519.SH)...",
    "metadata": {
        "intent": "market_analysis",
        "stocks": ["600519.SH"]
    }
}
```

---

## 10. 数据库扩展

### 10.1 新增数据表

#### 财报数据表

```sql
-- 利润表
CREATE TABLE IF NOT EXISTS ods_income (
    ts_code LowCardinality(String),
    ann_date Date,
    end_date Date,
    report_type LowCardinality(String),
    revenue Nullable(Float64),
    operate_profit Nullable(Float64),
    total_profit Nullable(Float64),
    n_income Nullable(Float64),
    n_income_attr_p Nullable(Float64),
    -- ... 更多字段
    version UInt64,
    _ingested_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(version)
PARTITION BY toYear(end_date)
ORDER BY (ts_code, end_date, report_type);

-- 资产负债表
CREATE TABLE IF NOT EXISTS ods_balance (
    ts_code LowCardinality(String),
    ann_date Date,
    end_date Date,
    report_type LowCardinality(String),
    total_assets Nullable(Float64),
    total_liab Nullable(Float64),
    total_hldr_eqy_exc_min_int Nullable(Float64),
    -- ... 更多字段
    version UInt64,
    _ingested_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(version)
PARTITION BY toYear(end_date)
ORDER BY (ts_code, end_date, report_type);

-- 现金流量表
CREATE TABLE IF NOT EXISTS ods_cashflow (
    ts_code LowCardinality(String),
    ann_date Date,
    end_date Date,
    report_type LowCardinality(String),
    n_cashflow_act Nullable(Float64),
    n_cashflow_inv_act Nullable(Float64),
    n_cash_flows_fnc_act Nullable(Float64),
    -- ... 更多字段
    version UInt64,
    _ingested_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(version)
PARTITION BY toYear(end_date)
ORDER BY (ts_code, end_date, report_type);
```

#### M05 记忆系统表

```sql
-- 用户偏好表
CREATE TABLE IF NOT EXISTS user_preference (
    user_id LowCardinality(String),
    risk_level LowCardinality(String) DEFAULT 'moderate',  -- conservative/moderate/aggressive
    investment_style LowCardinality(String) DEFAULT 'balanced',  -- value/growth/balanced/momentum
    favorite_sectors Array(String) DEFAULT [],              -- 偏好行业
    notification_settings String DEFAULT '{}',              -- 通知设置JSON
    ui_preferences String DEFAULT '{}',                     -- UI偏好JSON
    version UInt64,
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(version)
ORDER BY user_id;

-- 用户自选股表
CREATE TABLE IF NOT EXISTS user_watchlist (
    user_id LowCardinality(String),
    ts_code LowCardinality(String),                         -- 股票代码
    stock_name String,                                      -- 股票名称
    group_name LowCardinality(String) DEFAULT 'default',    -- 分组名称
    add_reason String DEFAULT '',                           -- 添加原因
    target_price Nullable(Float64),                         -- 目标价
    stop_loss_price Nullable(Float64),                      -- 止损价
    notes String DEFAULT '',                                -- 备注
    sort_order Int32 DEFAULT 0,                             -- 排序
    version UInt64,
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(version)
ORDER BY (user_id, ts_code);

-- 用户记忆表 (长期记忆)
CREATE TABLE IF NOT EXISTS user_memory (
    id String,                                              -- 记忆ID
    user_id LowCardinality(String),
    memory_type LowCardinality(String),                     -- stock/industry/strategy/insight
    memory_key String,                                      -- 记忆键(如股票代码、行业名称)
    memory_value String,                                    -- 记忆内容JSON
    importance Int8 DEFAULT 5,                              -- 重要程度(1-10)
    access_count Int32 DEFAULT 0,                           -- 访问次数
    last_accessed_at DateTime DEFAULT now(),
    expired_at Nullable(DateTime),                          -- 过期时间(NULL表示永不过期)
    version UInt64,
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(version)
ORDER BY (user_id, memory_type, id);

-- 交互日志表
CREATE TABLE IF NOT EXISTS user_interaction_log (
    user_id LowCardinality(String),
    session_id String,
    timestamp DateTime,
    intent LowCardinality(String),
    user_input String,
    assistant_response String,
    stocks_mentioned Array(String),
    indicators_used Array(String),                          -- 使用的指标
    tools_called Array(String),                             -- 调用的工具
    response_time_ms Int32,                                 -- 响应时间
    feedback Nullable(Int8),                                -- 用户反馈(-1/0/1)
    metadata String                                         -- JSON
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (user_id, timestamp);

-- 交互摘要表 (每日)
CREATE TABLE IF NOT EXISTS user_interaction_summary (
    user_id LowCardinality(String),
    date Date,
    interaction_count Int32,                                -- 交互次数
    top_intents Array(String),                              -- 主要意图
    top_stocks Array(String),                               -- 关注股票
    top_topics Array(String),                               -- 关注话题
    summary String,                                         -- AI生成摘要
    version UInt64,
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(version)
ORDER BY (user_id, date);

-- 用户画像表
CREATE TABLE IF NOT EXISTS user_profile (
    user_id LowCardinality(String),
    profile_date Date,
    active_level LowCardinality(String),                    -- 活跃度: low/medium/high
    expertise_level LowCardinality(String),                 -- 专业度: beginner/intermediate/expert
    focus_industries Array(String),                         -- 关注行业
    focus_stocks Array(String),                             -- 关注股票
    trading_style LowCardinality(String),                   -- 交易风格
    risk_tolerance Float32,                                 -- 风险容忍度(0-1)
    avg_holding_period LowCardinality(String),              -- 平均持仓周期
    profile_vector Array(Float32),                          -- 用户向量(用于相似用户推荐)
    version UInt64,
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(version)
ORDER BY (user_id, profile_date);
```

#### M06 数据管理表

```sql
-- 数据源配置表
CREATE TABLE IF NOT EXISTS data_source_config (
    id String,                                              -- 数据源ID
    source_name String,                                     -- 数据源名称
    source_type LowCardinality(String),                     -- 类型: api/database/file
    provider LowCardinality(String),                        -- 提供商: tushare/akshare/custom
    connection_config String,                               -- 连接配置JSON(加密存储)
    sync_strategy LowCardinality(String) DEFAULT 'incremental',  -- full/incremental
    sync_frequency LowCardinality(String) DEFAULT 'daily',  -- realtime/hourly/daily/weekly
    priority Int8 DEFAULT 5,                                -- 优先级(1-10)
    is_enabled UInt8 DEFAULT 1,
    last_sync_at Nullable(DateTime),
    version UInt64,
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(version)
ORDER BY id;

-- 同步任务表
CREATE TABLE IF NOT EXISTS sync_task (
    task_id String,                                         -- 任务ID
    source_id String,                                       -- 数据源ID
    plugin_name LowCardinality(String),                     -- 插件名称
    task_type LowCardinality(String),                       -- full_sync/incremental/retry
    cron_expression String,                                 -- 调度表达式
    params String DEFAULT '{}',                             -- 任务参数JSON
    status LowCardinality(String),                          -- pending/running/completed/failed/cancelled
    progress Float32 DEFAULT 0,                             -- 进度(0-100)
    records_processed Int64 DEFAULT 0,                      -- 处理记录数
    records_failed Int64 DEFAULT 0,                         -- 失败记录数
    error_message String DEFAULT '',                        -- 错误信息
    started_at Nullable(DateTime),
    completed_at Nullable(DateTime),
    next_run_at Nullable(DateTime),
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (source_id, created_at);

-- 同步任务历史表
CREATE TABLE IF NOT EXISTS sync_task_history (
    task_id String,
    source_id String,
    plugin_name LowCardinality(String),
    task_type LowCardinality(String),
    status LowCardinality(String),
    records_processed Int64,
    records_failed Int64,
    duration_seconds Int32,                                 -- 执行时长
    error_message String,
    started_at DateTime,
    completed_at DateTime,
    _ingested_at DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(started_at)
ORDER BY (source_id, started_at);

-- 数据质量日志表
CREATE TABLE IF NOT EXISTS data_quality_log (
    id String,
    table_name LowCardinality(String),                      -- 表名
    check_date Date,
    check_type LowCardinality(String),                      -- completeness/consistency/timeliness/accuracy
    check_rule String,                                      -- 检查规则描述
    total_records Int64,                                    -- 总记录数
    passed_records Int64,                                   -- 通过记录数
    failed_records Int64,                                   -- 失败记录数
    pass_rate Float32,                                      -- 通过率
    severity LowCardinality(String),                        -- info/warning/error/critical
    details String,                                         -- 详细信息JSON
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(check_date)
ORDER BY (table_name, check_date);

-- 数据质量指标表 (每日汇总)
CREATE TABLE IF NOT EXISTS data_quality_metrics (
    table_name LowCardinality(String),
    metric_date Date,
    completeness_score Float32,                             -- 完整性得分(0-100)
    consistency_score Float32,                              -- 一致性得分
    timeliness_score Float32,                               -- 时效性得分
    accuracy_score Float32,                                 -- 准确性得分
    overall_score Float32,                                  -- 综合得分
    record_count Int64,                                     -- 记录总数
    null_count Int64,                                       -- 空值数
    duplicate_count Int64,                                  -- 重复数
    latest_update DateTime,                                 -- 最新更新时间
    version UInt64,
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(version)
ORDER BY (table_name, metric_date);

-- 插件状态表
CREATE TABLE IF NOT EXISTS plugin_status (
    plugin_name LowCardinality(String),                     -- 插件名称
    plugin_type LowCardinality(String),                     -- 插件类型
    is_enabled UInt8 DEFAULT 1,
    config String DEFAULT '{}',                             -- 插件配置JSON
    last_run_at Nullable(DateTime),
    last_run_status LowCardinality(String),
    error_count Int32 DEFAULT 0,                            -- 累计错误次数
    success_count Int32 DEFAULT 0,                          -- 累计成功次数
    version UInt64,
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(version)
ORDER BY plugin_name;

-- 数据表元信息表
CREATE TABLE IF NOT EXISTS data_table_metadata (
    table_name LowCardinality(String),
    database_name LowCardinality(String) DEFAULT 'default',
    table_type LowCardinality(String),                      -- ods/dm/fact/dim/meta
    description String,
    source_plugin LowCardinality(String),                   -- 来源插件
    update_frequency LowCardinality(String),                -- 更新频率
    retention_days Int32 DEFAULT 0,                         -- 保留天数(0表示永久)
    row_count Int64 DEFAULT 0,
    size_bytes Int64 DEFAULT 0,
    partition_key String,
    order_key String,
    last_updated_at Nullable(DateTime),
    version UInt64,
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(version)
ORDER BY table_name;
```

#### M07 持仓管理表

```sql
-- 用户持仓表
CREATE TABLE IF NOT EXISTS user_position (
    id String,                              -- 持仓记录ID
    user_id LowCardinality(String),         -- 用户ID
    ts_code LowCardinality(String),         -- 股票代码
    stock_name String,                      -- 股票名称
    quantity Int32,                         -- 持仓数量
    cost_price Float64,                     -- 成本价
    buy_date Date,                          -- 买入日期
    status LowCardinality(String) DEFAULT 'holding',  -- holding/sold
    sell_price Nullable(Float64),           -- 卖出价格
    sell_date Nullable(Date),               -- 卖出日期
    notes String DEFAULT '',                -- 备注
    version UInt64,
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(version)
ORDER BY (user_id, id);

-- 持仓每日快照表 (用于历史盈亏追踪)
CREATE TABLE IF NOT EXISTS user_position_snapshot (
    user_id LowCardinality(String),
    snapshot_date Date,
    ts_code LowCardinality(String),
    quantity Int32,
    cost_price Float64,
    close_price Float64,                    -- 当日收盘价
    market_value Float64,                   -- 市值
    profit_loss Float64,                    -- 盈亏金额
    profit_rate Float64,                    -- 收益率
    _ingested_at DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(snapshot_date)
ORDER BY (user_id, snapshot_date, ts_code);

-- 持仓每日分析报告表
CREATE TABLE IF NOT EXISTS user_portfolio_analysis (
    user_id LowCardinality(String),
    analysis_date Date,
    total_value Float64,                    -- 总市值
    total_cost Float64,                     -- 总成本
    total_profit Float64,                   -- 总盈亏
    daily_change Float64,                   -- 日涨跌额
    daily_change_rate Float64,              -- 日涨跌幅
    analysis_summary String,                -- AI分析摘要
    stock_analyses String,                  -- 个股分析JSON
    risk_alerts String,                     -- 风险提示JSON
    recommendations String,                 -- 操作建议JSON
    version UInt64,
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(version)
ORDER BY (user_id, analysis_date);
```

#### 策略回测表

```sql
-- 策略定义表 (内置策略元数据)
CREATE TABLE IF NOT EXISTS backtest_strategy (
    strategy_id LowCardinality(String),     -- 策略ID
    name String,                            -- 策略名称
    description String,                     -- 策略描述
    category LowCardinality(String),        -- 分类: trend/momentum/mean_reversion
    params_schema String,                   -- 参数定义JSON Schema
    default_params String,                  -- 默认参数JSON
    is_builtin UInt8 DEFAULT 1,             -- 是否内置策略
    is_active UInt8 DEFAULT 1,              -- 是否启用
    version UInt64,
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(version)
ORDER BY strategy_id;

-- 回测任务表
CREATE TABLE IF NOT EXISTS backtest_task (
    task_id String,                         -- 任务ID
    user_id LowCardinality(String),         -- 用户ID
    strategy_id LowCardinality(String),     -- 策略ID
    ts_codes Array(String),                 -- 回测标的
    start_date Date,                        -- 开始日期
    end_date Date,                          -- 结束日期
    params String,                          -- 策略参数JSON
    initial_capital Float64 DEFAULT 100000, -- 初始资金
    status LowCardinality(String),          -- pending/running/completed/failed
    created_at DateTime DEFAULT now(),
    completed_at Nullable(DateTime)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (user_id, created_at);

-- 回测结果表
CREATE TABLE IF NOT EXISTS backtest_result (
    task_id String,                         -- 任务ID
    user_id LowCardinality(String),         -- 用户ID
    strategy_id LowCardinality(String),     -- 策略ID
    strategy_name String,                   -- 策略名称
    ts_codes Array(String),                 -- 回测标的
    start_date Date,
    end_date Date,
    initial_capital Float64,                -- 初始资金
    final_capital Float64,                  -- 最终资金
    total_return Float64,                   -- 总收益率
    annual_return Float64,                  -- 年化收益率
    max_drawdown Float64,                   -- 最大回撤
    sharpe_ratio Float64,                   -- 夏普比率
    win_rate Float64,                       -- 胜率
    profit_factor Float64,                  -- 盈亏比
    trade_count Int32,                      -- 交易次数
    avg_holding_days Float64,               -- 平均持仓天数
    benchmark_return Float64,               -- 基准收益率
    alpha Float64,                          -- Alpha
    beta Float64,                           -- Beta
    equity_curve String,                    -- 权益曲线JSON
    monthly_returns String,                 -- 月度收益JSON
    version UInt64,
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(version)
ORDER BY (user_id, task_id);

-- 回测交易记录表
CREATE TABLE IF NOT EXISTS backtest_trade (
    task_id String,                         -- 任务ID
    trade_id Int32,                         -- 交易序号
    ts_code LowCardinality(String),         -- 股票代码
    trade_date Date,                        -- 交易日期
    direction LowCardinality(String),       -- buy/sell
    price Float64,                          -- 成交价格
    quantity Int32,                         -- 成交数量
    amount Float64,                         -- 成交金额
    commission Float64,                     -- 手续费
    signal_reason String,                   -- 信号原因
    position_after Int32,                   -- 交易后持仓
    cash_after Float64,                     -- 交易后现金
    _ingested_at DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(trade_date)
ORDER BY (task_id, trade_id);
```

---

## 11. 开发任务分解

### 11.1 Phase 1: 基础框架 (Week 1-2)

| 任务 | 负责人 | 依赖 | 产出 |
|------|--------|------|------|
| 前端项目初始化 | FE | 无 | Vue3 + TDesign 项目骨架 |
| Agent 基础框架 | BE | 无 | BaseAgent, Orchestrator |
| 记忆系统基础 | BE | Redis | MemoryService |
| LLM 集成层 | BE | 无 | LLM Client |
| 统一 API 网关 | BE | 无 | 路由注册机制 |

### 11.2 Phase 2: 核心功能 (Week 3-5)

| 任务 | 负责人 | 依赖 | 产出 |
|------|--------|------|------|
| 对话交互模块 | FE+BE | Phase1 | ChatView + ChatAgent |
| 行情分析模块 | FE+BE | Phase1 | MarketView + MarketAgent |
| 技术指标服务 | BE | 现有数据 | TechnicalIndicatorService |
| 智能选股模块 | FE+BE | Phase1 | ScreenerView + ScreenerAgent |
| 用户记忆模块 (M05) | FE+BE | Phase1 | MemoryView + MemoryAgent |
| 自选股管理 | FE+BE | 记忆模块 | WatchlistService |

### 11.3 Phase 3: 增强功能 (Week 6-8)

| 任务 | 负责人 | 依赖 | 产出 |
|------|--------|------|------|
| 财报数据插件 | BE | TuShare | income/balance/cashflow 插件 |
| 财报研读模块 | FE+BE | 财报数据 | ReportView + ReportAgent |
| 数据管理模块 (M06) | FE+BE | 插件系统 | DataManageView + DataManageAgent |
| 同步任务调度 | BE | 数据管理 | SyncSchedulerService |
| 数据质量监控 | BE | 数据管理 | QualityService + 仪表盘 |
| 持仓管理模块 (M07) | FE+BE | Phase2 | PortfolioView + PortfolioAgent |
| 每日持仓分析 | BE | 持仓模块 | DailyAnalysisService + 定时任务 |
| 策略回测引擎 (M08) | BE | 技术指标 | BacktestEngine + 内置策略 |
| 回测前端界面 | FE | 回测引擎 | BacktestView + 结果可视化 |

### 11.4 Phase 4: 优化上线 (Week 9-10)

| 任务 | 负责人 | 依赖 | 产出 |
|------|--------|------|------|
| 性能优化 | ALL | 全部 | 缓存、查询优化 |
| 端到端测试 | QA | 全部 | 测试用例 |
| 文档完善 | ALL | 全部 | API 文档、用户手册 |
| 部署上线 | DevOps | 全部 | 生产环境 |

---

## 12. 里程碑规划

```
Week 1-2:  ████████░░░░░░░░░░░░  基础框架搭建
Week 3-4:  ████████████░░░░░░░░  对话 + 行情模块
Week 5-6:  ████████████████░░░░  选股 + 技术指标
Week 7-8:  ████████████████████  财报 + 记忆系统
Week 9-10: ████████████████████  优化 + 上线
```

### 关键里程碑

| 里程碑 | 时间 | 交付物 |
|--------|------|--------|
| M1 | Week 2 | 基础框架可运行 |
| M2 | Week 4 | 对话 + 行情 MVP |
| M3 | Week 6 | 智能选股可用 |
| M4 | Week 8 | 全功能完成 |
| M5 | Week 10 | 生产上线 |

---

## 附录

### A. 参考资料

- [LangChain DeepAgents 文档](https://docs.langchain.com/oss/python/deepagents/overview)
- [TDesign Vue Next](https://tdesign.tencent.com/vue-next)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [ClickHouse 文档](https://clickhouse.com/docs)

### B. 术语表

| 术语 | 说明 |
|------|------|
| Agent | 具有特定能力的 AI 代理 |
| Orchestrator | 编排多个 Agent 的调度器 |
| Tool | Agent 可调用的工具/函数 |
| Memory | 存储对话上下文和用户偏好的系统 |
| RAG | 检索增强生成 |

---

*文档版本: 1.2.0*  
*最后更新: 2026-01-09*  
*更新内容: 新增 M05 用户记忆模块、M06 数据管理模块详细设计*
