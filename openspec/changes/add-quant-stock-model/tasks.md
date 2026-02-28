# Tasks: add-quant-stock-model

## Phase 1: 基础设施与数据层

- [x] **T1.1** 创建 ClickHouse 数据表 (`quant_screening_result`, `quant_screening_run_stats`, `quant_rps_rank`, `quant_core_pool`, `quant_trading_signal`, `quant_deep_analysis`, `quant_model_config`, `quant_pipeline_run`)
  - 验证：通过 ClickHouse 客户端确认表已创建，可执行 INSERT/SELECT

- [x] **T1.2** 创建 `modules/quant/` 模块骨架 (`__init__.py`, `schemas.py`, `router.py`, `service.py`)，注册路由到 `modules/__init__.py`
  - 验证：`/api/quant/health` 端点返回 200

- [x] **T1.3** 创建量化模型配置系统 (`quant_model_config` CRUD)，支持 JSON 配置的读写和版本管理
  - 验证：API 可存取筛选规则、因子权重、信号参数配置

## Phase 2: 数据就绪检查层 ★

- [x] **T2.0** 实现 `data_readiness.py`：数据就绪检查器，声明各引擎的数据依赖（表名/列/日期范围），提供 `check_screening_readiness` / `check_core_pool_readiness` / `check_signal_readiness` / `check_full_pipeline_readiness` 方法
  - ★ 仅执行 ClickHouse 元数据查询（SHOW TABLES / SELECT COUNT / MIN/MAX），不调用任何远程插件
  - ★ 返回结构化 `DataReadinessResult`（含 `MissingDataSummary` 和 `PluginTriggerInfo`），供前端展示
  - 验证：缺少 `fact_income` 数据时，返回的 `MissingDataSummary` 正确列出插件名和缺失日期
  - 依赖：T1.2

- [x] **T2.0b** 暴露数据就绪检查 API：`GET /api/quant/data-readiness`（全Pipeline）、`GET /api/quant/data-readiness/{stage}`（单阶段）
  - 验证：前端可调用API获取数据就绪状态
  - 依赖：T2.0

## Phase 3: 全市场初筛引擎

- [x] **T3.1** 实现 `screening_engine.py`：传统指标筛选规则（营收增长率、净利润、ROE），★ 仅从 ClickHouse 查询财务指标数据，不调用 TuShare
  - ★ 每条规则返回 `RuleExecutionDetail`（命中数/未命中数/跳过数/示例被剔除股票），供前端展示
  - 验证：对已知财务数据运行，确认剔除逻辑正确
  - 依赖：T1.1, T1.2, T2.0

- [x] **T3.2** 实现自定义指标筛选规则：现金流同步率、费用异常检测、应收营收联动分析
  - ★ 同样返回每条规则的 `RuleExecutionDetail`
  - 验证：用手工校验的案例验证计算结果
  - 依赖：T3.1

- [x] **T3.3** 实现 `benford_checker.py`：本福德首位数字定律检验，对营收/利润科目进行卡方检验
  - 验证：用已知符合/违反本福德分布的数据集测试
  - 依赖：T1.2

- [x] **T3.4** 整合初筛引擎：★ 执行前先调用 `DataReadinessChecker`，数据缺失直接返回缺失报告；规则链编排、可配置化、结果持久化到 `quant_screening_result` + `quant_screening_run_stats` 表
  - ★ 返回 `ScreeningResult`（含每条规则的执行详情 + 数据就绪状态），供前端全展示
  - 验证：运行全市场初筛，结果入库，可通过 API 查询；数据缺失时返回缺失报告而非报错
  - 依赖：T3.1, T3.2, T3.3, T2.0

- [x] **T3.5** 暴露初筛 API：`POST /api/quant/screening/run`、`GET /api/quant/screening/result`、`GET /api/quant/screening/stats`、筛选规则 CRUD
  - 验证：前端可调用 API 触发初筛、查看结果和规则统计
  - 依赖：T3.4

## Phase 4: RPS 计算与核心池构建

- [x] **T4.1** 实现 `rps_calculator.py`：全市场 RPS 计算（250/120/60日涨幅百分位排名），★ 仅从 ClickHouse 读取行情数据，结果存入 `quant_rps_rank` 表
  - ★ 执行前检查数据就绪，缺失返回报告
  - 验证：抽样验证 RPS 排名与手工计算一致
  - 依赖：T1.1, T2.0

- [x] **T4.2** 实现 `factor_scorer.py`：多因子打分模型（质量30%/成长30%/估值20%/动量20%），包含归一化处理
  - ★ 每个因子返回 `breakdown` 明细（如 `{roe: 85, gross_margin: 72}`），供前端因子雷达图展示
  - 验证：对测试股票集打分，确认排名合理
  - 依赖：T1.2, T2.0

- [x] **T4.3** 实现 `core_pool_builder.py`：从初筛结果中选 Top50（核心底仓）+ RPS补充（观察池），管理入池/出池逻辑
  - ★ 返回 `CorePoolResult`（含因子得分详情、池变动列表、因子分布统计），供前端全展示
  - ★ 池变动记录 `change_type`（new_entry/exit/rank_change），供前端变动日志展示
  - 验证：构建核心池，确认数量约 50+20=70 只，池变动记录正确
  - 依赖：T3.4, T4.1, T4.2

- [x] **T4.4** 暴露核心池 API：`GET /api/quant/pool`（含因子详情）、`POST /api/quant/pool/refresh`、`GET /api/quant/pool/changes`、`GET /api/quant/rps`
  - 验证：API 返回当前目标池（含因子得分明细）和 RPS 数据
  - 依赖：T4.3

## Phase 5: 深度分析引擎

- [x] **T5.1** 实现技术指标监控：对目标池个股计算 MA25/MA120/MACD/RSI/成交量，复用 `market/indicators.py`，★ 仅从本地数据计算
  - ★ 返回技术指标快照 `tech_snapshot`，供前端图表渲染
  - 验证：返回的技术指标数据与手工计算一致
  - 依赖：T4.3, T2.0

- [x] **T5.2** 实现管理层讨论 NLP 分析：调用 LLM 分析财报"管理层讨论与分析"章节，输出可信度/前景乐观度评分
  - 验证：对测试财报运行，AI 输出包含行业趋势、战略、风险、验证点
  - 依赖：T1.2

- [x] **T5.3** 整合深度分析引擎 `deep_analyzer.py`：批量分析 + 结果存储到 `quant_deep_analysis` 表
  - ★ 批量分析支持进度回调，供前端展示分析进度
  - 验证：对目标池运行批量分析，结果入库
  - 依赖：T5.1, T5.2

- [x] **T5.4** 暴露深度分析 API：`POST /api/quant/analysis/{ts_code}`、`GET /api/quant/analysis/dashboard`（含技术指标快照）、`GET /api/quant/analysis/batch/status`
  - 验证：API 返回技术指标仪表盘数据和 AI 分析结果
  - 依赖：T5.3

## Phase 6: 交易信号与风控

- [x] **T6.1** 实现 `signal_generator.py`：均线突破入场信号（MA25上穿MA120）、分批建仓逻辑，★ 仅从 ClickHouse 读取数据
  - ★ 每个信号附带 `signal_context`（前日MA值、突破日期等），供前端展示触发原因
  - 验证：对历史数据回测，确认金叉信号检测正确
  - 依赖：T4.3, T2.0

- [x] **T6.2** 实现止损/止盈/出场逻辑：跌破MA120止损、-15%止损、移动止盈(高点回撤10%)、RPS<75卖出
  - 验证：模拟场景测试各出场条件触发
  - 依赖：T6.1, T4.1

- [x] **T6.3** 实现市场风控框架：沪深300 vs MA250 风控、个股黑天鹅检测、行业集中度控制
  - 验证：沪深300跌破年线时确认触发降仓信号
  - 依赖：T6.1

- [x] **T6.4** 整合信号系统：信号存储到 `quant_trading_signal` 表（含 `signal_context`），暴露 API
  - 验证：`GET /api/quant/signals` 返回最新信号（含触发上下文），历史可查
  - 依赖：T6.1, T6.2, T6.3

## Phase 7: Pipeline 编排与调度

- [x] **T7.1** 实现 `service.py` Pipeline 编排：串联四大引擎，★ 每步执行前自动检查数据就绪，记录运行状态到 `quant_pipeline_run` 表
  - ★ `POST /api/quant/pipeline/run` 触发完整 Pipeline，返回 run_id
  - ★ `GET /api/quant/pipeline/status/{run_id}` 返回每步状态和中间结果
  - 验证：Pipeline 正确执行四个阶段，数据缺失时在对应阶段停止并报告
  - 依赖：T3.4, T4.3, T5.3, T6.4

- [ ] **T7.2** 实现 `quant_agent.py`：量化模型 Agent，集成工具集（check_data_readiness / run_screening / build_pool / get_signals / deep_analysis）
  - 验证：通过自然语言对话可触发量化模型各功能
  - 依赖：T7.1

- [ ] **T7.3** 将 `QuantAgent` 注册到 `OrchestratorAgent`，新增"量化模型"意图路由
  - 验证：用户输入"帮我运行量化选股"时正确路由到 QuantAgent
  - 依赖：T7.2

- [ ] **T7.4** 实现定时调度任务：日度信号检查、周度 RPS 计算、季度初筛（复用 APScheduler）
  - ★ 调度任务执行前先检查数据就绪，缺失时记录到 pipeline_run 表
  - 验证：调度任务按预期频率执行，日志记录正常
  - 依赖：T7.1

## Phase 8: 前端界面 ★ 全链路可视化

- [x] **T8.1** 实现前端 API 客户端 (`api/quant.ts`) 和状态管理 (`stores/quant.ts`)
  - 包含：数据就绪检查、Pipeline状态、初筛、核心池、RPS、信号等全部API调用
  - 依赖：T3.5, T4.4, T5.4, T6.4, T7.1

- [x] **T8.2** 实现量化模型主页 (`/quant`) + `PipelineProgress` 组件 + `DataReadinessPanel` 组件
  - ★ Pipeline 四阶段进度条：展示每步状态（未开始/进行中/完成/数据缺失）
  - ★ 数据就绪面板：展示缺失详情 + 需要触发的插件列表 + **一键补数据按钮**（调用 `batchTriggerSync`）
  - ★ 关键指标概览卡片
  - 验证：页面正确展示Pipeline进度和数据就绪状态，点击一键补数据可触发插件

- [x] **T8.3** 实现初筛结果页 (`/quant/screening`) + `ScreeningRuleStats` 组件 + `ScreeningRejectTable` 组件
  - ★ 规则执行统计表：每条规则的通过/剔除/跳过数量
  - ★ 通过列表和剔除列表：支持查看具体股票和剔除原因
  - ★ 规则配置弹窗：可调整阈值、启用/禁用规则
  - 验证：可查看初筛结果和每条规则的详细统计

- [x] **T8.4** 实现核心池页 (`/quant/pool`) + `FactorScoreDistribution` 组件 + `PoolChangeLog` 组件
  - ★ 因子得分分布图（箱线图/直方图）
  - ★ 入池/出池变动日志
  - ★ 因子雷达图（点击行展开）
  - 验证：展示池内股票及各因子得分，变动日志正确

- [x] **T8.5** 实现交易信号页 (`/quant/signals`) + `SignalList` 组件 + `RiskStatusPanel` 组件
  - ★ 信号列表：含触发原因和上下文详情
  - ★ 风控状态面板：沪深300 vs MA250、行业集中度
  - ★ 仓位建议
  - 验证：展示买卖信号，支持历史查询

- [x] **T8.6** 实现深度分析仪表盘 (`/quant/analysis`) + `TechIndicatorChart` 组件 + `AiAnalysisCard` 组件
  - ★ 技术指标图表(MA/MACD/RSI)
  - ★ AI 分析卡片（可信度/乐观度/验证点）
  - ★ 批量分析进度条
  - 验证：展示技术图表和 AI 分析摘要

- [x] **T8.7** 实现 RPS 排名页 (`/quant/rps`) + 模型配置页 (`/quant/config`)
  - RPS 排名 Top100 列表 + 多周期对比
  - 配置页：规则阈值、因子权重滑块、信号参数、风控参数
  - 验证：可查看RPS排名，可调整配置

## 任务依赖关系

```
T1.1 ─┬─ T2.0 ─ T2.0b
      │    │
T1.2 ─┤    │
      │    │
      ├────┼─ T3.1 ─ T3.2 ─┬─ T3.4 ─ T3.5 ─┐
      │    │                │                │
      │    │   T3.3 ────────┘                │
      │    │                                  │
      │    ├─ T4.1 ──┬─ T4.3 ─ T4.4 ─┐     ├─ T7.1 ─┬─ T7.2 ─ T7.3
      │    │         │                │     │        │
      │    └─ T4.2 ──┘                ├─────┤        └─ T7.4
      │                               │     │
T1.2 ─┼── T5.1 ──┬─ T5.3 ─ T5.4 ──┤     │
      │   T5.2 ──┘                  │     │
      │                              │     │
      └── T6.1 ──┬─ T6.4 ──────────┘     │
          T6.2 ──┤                        │
          T6.3 ──┘                        │
                                           │
          T8.1 ─┬─ T8.2 (Pipeline+数据就绪) │
                ├─ T8.3 (初筛)             │
                ├─ T8.4 (核心池)            │
                ├─ T8.5 (信号)             │
                ├─ T8.6 (深度分析)          │
                └─ T8.7 (RPS+配置)         │
                   (T8.x 可并行)  ─────────┘
```

## 可并行工作

- **T2.0**（数据就绪检查器）可在 T1.1/T1.2 完成后立即开始，与 Phase 3 并行
- **T3.3**（本福德检验）可与 **T3.1/T3.2**（传统/自定义指标）并行
- **T4.1**（RPS计算）可与 **Phase 3** 并行
- **T5.2**（NLP分析）可与 **T5.1**（技术指标监控）并行
- **Phase 8**（前端）的各页面（T8.2~T8.7）可并行开发
- **T7.2/T7.3**（Agent）可与 **Phase 8**（前端）并行
