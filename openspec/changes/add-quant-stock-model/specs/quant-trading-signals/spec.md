# Capability: quant-trading-signals

交易信号生成与风控框架，基于均线系统和海龟交易法思想，为目标池个股生成买卖信号，并嵌入多层次风控机制。

**核心约束**：
- 所有信号计算仅从 ClickHouse 本地数据读取，禁止调用 TuShare/AKShare 远程插件
- 执行前 MUST 进行数据就绪检查，数据缺失时返回结构化报告供前端展示和一键补数据
- 每个信号 MUST 附带完整的触发上下文（前日MA值、突破日期等），在前端展示触发原因

## ADDED Requirements

### Requirement: Data Readiness Check Before Signal Generation
The system MUST check data readiness before generating trading signals, returning a structured missing data report if local data is insufficient.

#### Scenario: Check Signal Data Readiness
- **Given** 用户触发或定时任务触发信号生成
- **When** `DataReadinessChecker` 检查目标池股票日线数据和指数日线数据完整性
- **Then** 数据就绪则继续生成信号；缺失则返回 `MissingDataSummary` 含缺失详情和需触发的插件

#### Scenario: Scheduled Signal Check with Data Validation
- **Given** 定时调度触发每日信号检查
- **When** 数据就绪检查发现当日收盘数据尚未入库
- **Then** 记录到 `quant_pipeline_run` 表(status='data_missing')，前端可查看并一键触发数据补充

### Requirement: Entry Signal Generation
The system MUST generate entry signals based on moving average crossover, using only local ClickHouse data.

#### Scenario: Golden Cross Entry for Core Pool
- **Given** 核心池某只股票的日线数据已在本地数据库中
- **When** MA25 上穿 MA120（金叉）
- **Then** 生成买入信号(signal_type='buy', pool_type='core')，附带 `signal_context` JSON(含前日MA25/MA120值、金叉确认日期、当前价位等)，供前端展示

#### Scenario: Golden Cross Entry for Supplement Pool
- **Given** 补充池某只股票的日线数据已在本地数据库中
- **When** MA25 上穿 MA120（金叉）
- **Then** 生成买入信号(signal_type='buy', pool_type='rps_supplement')，仓位建议低于核心池（如1/4仓位），附带完整 `signal_context`

### Requirement: Position Management
The system MUST support staged position building strategy with fractional entries.

#### Scenario: First Entry
- **Given** 入场信号已触发
- **When** 首次建仓
- **Then** 建议买入目标仓位的1/3

#### Scenario: Add on Pullback
- **Given** 已持有某只股票1/3仓位
- **When** 股价回踩MA25不破后反弹
- **Then** 生成加仓信号(signal_type='add')，建议再买入1/3，附带回踩详情(最低价、反弹确认日期)

#### Scenario: Add on Breakout
- **Given** 已持有某只股票2/3仓位
- **When** 股价突破前期高点
- **Then** 生成加仓信号(signal_type='add')，建议买满至满仓，附带突破高点值

#### Scenario: Max Position Limit
- **Given** 某只股票仓位计算
- **When** 建仓/加仓
- **Then** 单只个股最大仓位不超过总资金的5%

### Requirement: Exit Signal Generation
The system MUST generate exit signals based on multiple conditions, each with detailed trigger context for frontend display.

#### Scenario: MA120 Stop Loss
- **Given** 持有某只股票
- **When** 股价跌破 MA120
- **Then** 生成卖出信号(signal_type='sell', signal_source='stop_loss')，`signal_context` 含MA120值、跌破日期、跌幅

#### Scenario: Max Loss Stop
- **Given** 持有某只股票，成本价已知
- **When** 亏损达到 -15%
- **Then** 生成卖出信号(signal_type='sell', signal_source='stop_loss')，`signal_context` 含成本价、当前价、亏损幅度

#### Scenario: Trailing Stop Profit
- **Given** 持有某只股票且处于盈利状态
- **When** 从最高点回撤 10%
- **Then** 生成卖出信号(signal_type='sell', signal_source='stop_profit')，`signal_context` 含历史最高价、回撤幅度、盈利幅度

#### Scenario: RPS Exit
- **Given** 持有某只股票
- **When** 该股票的 RPS_250 跌破 75
- **Then** 生成卖出信号(signal_type='sell', signal_source='stop_profit')，`signal_context` 含当前RPS值、前期RPS值

### Requirement: Market Risk Control
The system MUST monitor market-level risk and trigger position reduction under systemic risk, using only local index data.

#### Scenario: Index Below MA250
- **Given** 沪深300指数行情数据已在本地数据库中
- **When** 沪深300收盘价跌破 MA250（年线）
- **Then** 生成市场风控信号，建议将总仓位降至50%以下，前端展示市场风控状态面板(含指数当前值、MA250值、偏离幅度)

#### Scenario: Individual Black Swan
- **Given** 持仓个股的最新财报数据已在本地数据库中
- **When** 财报出现重大恶化（如净利润转负、营收大幅下滑>30%）
- **Then** 生成紧急卖出信号(signal_type='sell', signal_source='risk_control')，`signal_context` 含财务恶化详情

### Requirement: Industry Concentration Control
The system MUST control industry concentration risk.

#### Scenario: Industry Limit
- **Given** 当前持仓组合
- **When** 同一行业持仓占比超过20%
- **Then** 新增该行业买入信号的置信度降低，前端提示行业集中度过高

### Requirement: Signal Persistence and API with Context
Trading signals MUST be persisted with full trigger context and exposed via query API for frontend display.

#### Scenario: Save Trading Signals with Context
- **Given** 信号生成器完成每日运行
- **When** 新信号产生
- **Then** 所有信号存入 `quant_trading_signal` 表，包含 `signal_context` JSON（触发上下文详情）

#### Scenario: Get Latest Signals with Context
- **Given** 用户发送 `GET /api/quant/signals`
- **When** 请求被处理
- **Then** 返回最近一个交易日的所有信号，每个信号含完整触发上下文(前日MA、突破/跌破详情等)，供前端展示触发原因

#### Scenario: Get Signal History
- **Given** 用户发送 `GET /api/quant/signals/history` 并指定日期范围
- **When** 请求被处理
- **Then** 返回指定日期范围内的历史信号列表

#### Scenario: Get Market Risk Status for Frontend
- **Given** 用户发送 `GET /api/quant/risk`
- **When** 请求被处理
- **Then** 返回当前市场风控状态(沪深300当前值/MA250值/偏离度、建议仓位、行业集中度告警列表)，供前端风控状态面板展示

### Requirement: Daily Signal Scheduling with Data Check
The system MUST run daily signal checks on trading days, with data readiness validation before execution.

#### Scenario: Auto Daily Signal Check
- **Given** 当日为交易日
- **When** 定时任务触发（如每日17:00）
- **Then** 先检查当日收盘数据是否已入库；就绪则自动检查目标池所有个股信号并入库；缺失则记录到 `quant_pipeline_run` 表，前端可查看缺失状态并一键触发数据补充

### Requirement: Pipeline Progress for Frontend
The system MUST provide pipeline execution status for frontend progress display.

#### Scenario: Get Pipeline Run Status
- **Given** 用户或调度触发了 Pipeline 运行
- **When** 用户发送 `GET /api/quant/pipeline/status/{run_id}`
- **Then** 返回每个阶段的状态(pending/running/completed/data_missing/error)、开始和结束时间、结果摘要、数据就绪检查结果

#### Scenario: Display Pipeline Progress in Frontend
- **Given** Pipeline 正在运行
- **When** 前端轮询 Pipeline 状态
- **Then** 展示四阶段进度条(初筛→核心池→深度分析→交易信号)，每步显示状态图标和关键数字(如"初筛: 250/5000通过")
