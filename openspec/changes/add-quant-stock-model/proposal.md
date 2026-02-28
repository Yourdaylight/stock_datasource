# Proposal: add-quant-stock-model

## Summary

为系统新增一套完整的量化选股模型，从"全市场初筛 → 核心池构建 → 深度分析 → 交易信号生成"四大阶段，将现有的数据源和AI能力串联为一个端到端的自动化量化投资决策管线。

## Motivation

当前系统已具备丰富的数据采集（70+ TuShare/AKShare 插件）、AI Agent 协作（13个专业 Agent）、策略引擎（7种内置策略 + AI生成器）和回测能力，但缺少一个将这些能力**系统性整合**为量化选股模型的框架。用户需要：

1. **从5000+股票中自动筛选出基本面优质标的**（当前选股模块仅支持单一条件过滤，缺少财务健康度综合判断、本福德定律检验等高级筛选）。
2. **构建动态核心持仓池**（多因子打分 + RPS热点补充，当前无 RPS 计算能力）。
3. **AI辅助深度分析**（管理层讨论NLP分析 + 技术指标监控仪表盘，复用现有 `ReportAgent` 和技术指标系统）。
4. **自动化交易信号生成与风控**（基于均线系统 + 海龟交易法，复用并增强现有 `turtle_strategy` 和技术指标）。

## 核心约束

### C1: 纯本地数据计算，禁止引擎内调用 TuShare 插件
所有量化指标计算（初筛/打分/RPS/信号）**只能从 ClickHouse 本地已有数据中读取**，不允许在计算过程中调用任何 TuShare/AKShare 数据插件。原因：
- 避免 TuShare 积分消耗不可控
- 保证计算速度（本地查询 vs 远程API调用）
- 计算过程可离线运行

### C2: 数据就绪检查 + 前端一键触发补数据
每个引擎执行前 MUST 先进行**数据就绪检查（Data Readiness Check）**：
- 检查所需数据表是否存在、所需日期范围的数据是否完整
- 数据缺失时**不自动拉取**，而是返回结构化的缺失报告（missing data report）
- 前端展示缺失详情，提供**批量一键触发**按钮调用已有的 `batchTriggerSync` API 补充数据
- 复用现有 `MissingDataPanel` 组件模式 + `datamanageApi.batchTriggerSync()` 接口

### C3: 每步计算过程在前端全链路可视化
量化模型的每个阶段（初筛→核心池→深度分析→交易信号）的计算过程和关键信息 MUST 在前端界面实时展示：
- **Pipeline 总览**：展示当前执行到哪一步、每步状态（未开始/进行中/完成/数据缺失）
- **初筛**：展示每条规则的命中/未命中数量、被剔除的股票及具体原因
- **核心池**：展示每个因子的得分分布、排名变化、入池/出池变动
- **深度分析**：展示技术指标图表、AI 分析卡片（可信度/乐观度/验证点）
- **交易信号**：展示信号列表、触发原因、风控状态、仓位建议

## Scope

### In Scope

| 模块 | 描述 | 复用现有能力 |
|------|------|-------------|
| **全市场初筛引擎** | 多规则财报筛选（营收/净利/ROE/现金流同步率/费用分析/应收联动/本福德检验） | 复用财务数据插件（income/balancesheet/cashflow/fina_indicator） |
| **核心池构建** | 多因子加权打分（质量/成长/估值/动量）+ RPS指标计算 + 动态池管理 | 复用 `screener` 模块十维画像框架 + `daily_basic` 数据 |
| **深度分析** | 技术指标监控仪表盘 + 管理层讨论NLP分析 | 复用 `market/indicators.py` + `ReportAgent` + LLM |
| **交易信号生成** | 均线突破信号 + 仓位管理 + 止损止盈 + 市场风控 | 复用 `turtle_strategy` + `backtest` 引擎 |
| **调度与自动化** | 定时任务：日度信号/周度RPS/季度初筛 | 复用 `APScheduler` / `schedule` + `tasks/` 模块 |
| **数据就绪检查** | 每步执行前检查本地数据完整性，缺失时前端提示一键补数据 | 复用 `MissingDataPanel` + `batchTriggerSync` + 依赖检查系统 |
| **API与前端** | Pipeline全链路可视化 + 每步关键信息展示 + 数据缺失提示 + 一键触发 | 复用 FastAPI 路由框架 + Vue3/TDesign 前端 |

### Out of Scope

- 自动交易下单（需对接券商API，安全风险高，本期仅生成信号）
- 实时行情推送（使用日频数据，不涉及tick级别数据）
- 港股量化模型（本期聚焦A股，港股可后续扩展）
- 策略竞技场集成（`arena` 模块已独立，可后续对接）

## Approach

### 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                  量化选股模型 Pipeline                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ① 全市场初筛引擎 (QuantScreeningEngine)                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │传统指标筛选│  │自定义指标 │  │本福德检验 │              │
│  │ROE/营收/  │  │现金流同步 │  │首位数字   │              │
│  │净利润     │  │费用分析   │  │分布检验   │              │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
│       └──────────┬───┘             │                    │
│                  ▼                 │                    │
│  ② 核心池构建 (CorePoolBuilder)     │                    │
│  ┌──────────┐  ┌──────────┐       │                    │
│  │多因子打分 │  │RPS热点   │◄──────┘                    │
│  │Top 50    │  │补充 20   │                            │
│  └────┬─────┘  └────┬─────┘                            │
│       └──────┬───────┘                                  │
│              ▼                                          │
│  ③ 深度分析 (DeepAnalyzer)                               │
│  ┌──────────┐  ┌──────────────┐                        │
│  │技术指标   │  │管理层讨论NLP │                        │
│  │监控仪表盘 │  │分析 (AI辅助) │                        │
│  └────┬─────┘  └────┬─────────┘                        │
│       └──────┬───────┘                                  │
│              ▼                                          │
│  ④ 交易信号 (TradingSignalGenerator)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │均线突破   │  │仓位管理   │  │风控框架   │             │
│  │入场信号   │  │分批建仓   │  │止损止盈   │             │
│  └──────────┘  └──────────┘  └──────────┘             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 技术决策

1. **新建 `modules/quant/` 模块**：作为量化模型的主模块，包含四大引擎。
2. **新建 `agents/quant_agent.py`**：量化模型专用 Agent，整合到 `OrchestratorAgent` 路由。
3. **复用 `strategies/` 框架**：新增 `quant_ma_crossover_strategy` 作为核心交易策略。
4. **ClickHouse 存储**：新建 `quant_screening_result`、`quant_core_pool`、`quant_rps_rank`、`quant_trading_signal` 等表。
5. **配置化规则引擎**：所有筛选规则通过 JSON/YAML 配置，支持动态调整阈值。
6. **纯本地数据计算**：所有引擎仅从 ClickHouse 读取数据，不调用任何远程数据插件；数据缺失时返回结构化报告，由前端引导用户触发补数据。
7. **前端全链路可视化**：Pipeline 四阶段进度 + 每步计算的关键数据均在前端展示，复用 TDesign 组件库。

### 与现有系统的关系

| 现有模块 | 复用方式 |
|---------|---------|
| `plugins/tushare_finace_indicator` | 获取ROE、营收增速等财务指标数据 |
| `plugins/tushare_income` | 获取利润表数据（营收、净利润、费用分解） |
| `plugins/tushare_balancesheet` | 获取资产负债表（应收账款等） |
| `plugins/tushare_cashflow` | 获取现金流量表（经营活动现金流） |
| `plugins/tushare_daily` + `tushare_daily_basic` | 获取行情数据（计算RPS、均线） |
| `plugins/tushare_adj_factor` | 前复权因子 |
| `plugins/tushare_index_daily` | 指数行情（市场风控基准） |
| `modules/screener/profile.py` | 十维画像框架可作为多因子打分参考 |
| `modules/market/indicators.py` | MA/MACD/RSI等技术指标计算 |
| `strategies/builtin/turtle_strategy.py` | 海龟交易法仓位管理 |
| `agents/report_agent.py` | 财报AI分析能力 |
| `agents/screener_agent.py` | 选股Agent框架 |
| `services/daily_analysis_service.py` | 每日分析服务调度 |

## Risks

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 本地数据不完整 | 计算结果不准确或无法执行 | 数据就绪检查 + 前端缺失数据提示 + 一键批量补数据 |
| 本福德检验误判率 | 可能错误剔除正常公司 | 设为软条件（标记而非直接剔除） |
| 多因子模型过拟合 | 历史表现好但未来失效 | 定期回测验证 + 因子权重可调 |
| 财报更新滞后 | 季报发布有时间差 | 支持快报/预告数据补充 |
| 前端信息过载 | 用户难以消化大量计算细节 | 分层展示：概览→详情→明细，渐进式信息披露 |

## Dependencies

- ClickHouse 数据库可用
- 本地数据表已通过数据插件填充（系统会检查并提示缺失的数据）
- LLM API 可用（用于管理层讨论NLP分析）
- 前端一键触发补数据依赖现有 `batchTriggerSync` / `triggerSync` API

## Affected Capabilities

| Capability | Type | Description |
|-----------|------|-------------|
| `quant-screening` | NEW | 全市场财报初筛引擎 |
| `quant-core-pool` | NEW | 核心池构建与管理 |
| `quant-deep-analysis` | NEW | 深度分析（技术+NLP） |
| `quant-trading-signals` | NEW | 交易信号生成与风控 |
| `quant-data-readiness` | NEW | 数据就绪检查与缺失报告 |
| `quant-pipeline-ui` | NEW | 前端Pipeline全链路可视化 |
| `chat-orchestration` | MODIFIED | OrchestratorAgent 新增量化模型路由 |
| `data-management` | MODIFIED | 数据管理新增量化相关数据表 |
