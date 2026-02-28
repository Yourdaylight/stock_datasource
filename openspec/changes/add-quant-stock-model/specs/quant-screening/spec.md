# Capability: quant-screening

全市场财报初筛引擎，通过可配置的规则链对全市场5000+只A股进行财务健康度筛选，剔除约95%的劣质标的。

**核心约束**：
- 所有指标计算仅从 ClickHouse 本地数据读取，禁止调用 TuShare/AKShare 远程插件
- 执行前 MUST 进行数据就绪检查，数据缺失时返回结构化报告供前端展示
- 每条规则的执行详情（命中/未命中/跳过数量）MUST 在前端展示

## ADDED Requirements

### Requirement: Data Readiness Check Before Screening
The system MUST check data readiness before executing any screening computation, and return a structured missing data report if data is insufficient.

#### Scenario: Data Ready - Proceed with Screening
- **Given** 用户触发全市场初筛
- **When** `DataReadinessChecker` 检查所有所需表(fact_fina_indicator/fact_income/fact_balancesheet/fact_cashflow)的数据完整性
- **Then** 所有数据就绪，初筛引擎开始执行计算

#### Scenario: Data Missing - Return Report Without Computation
- **Given** 用户触发全市场初筛
- **When** `DataReadinessChecker` 发现 `fact_income` 缺少最新季报数据
- **Then** 不执行任何计算，返回结构化的 `MissingDataSummary`，包含缺失表名、缺失日期范围、需要触发的插件列表(`tushare_income`)和数据用途说明

#### Scenario: Frontend Display Missing Data and One-Click Fix
- **Given** 后端返回 `MissingDataSummary`
- **When** 前端展示数据缺失面板
- **Then** 显示每项缺失的详情(表名/缺失日期/影响的计算步骤)，提供"一键补数据"按钮，点击后调用 `batchTriggerSync` API 触发对应的 TuShare 插件

### Requirement: Traditional Financial Screening
The system MUST support traditional financial screening rules including revenue growth rate, net profit, and ROE, computing all indicators from local ClickHouse data only.

#### Scenario: Filter by Revenue Growth
- **Given** 全市场股票列表和近两年财务数据已在本地 ClickHouse 中
- **When** 执行初筛引擎
- **Then** 连续两年营收增长率 < 0 的股票被标记为"剔除"，原因为"营收衰退"

#### Scenario: Filter by Net Profit
- **Given** 全市场股票近一年财务数据已在本地 ClickHouse 中
- **When** 执行初筛引擎
- **Then** 近一年净利润为负的股票被标记为"剔除"，原因为"净利润为负"

#### Scenario: Filter by ROE
- **Given** 全市场股票近三年财务指标数据已在本地 ClickHouse 中
- **When** 执行初筛引擎
- **Then** 近三年平均 ROE < 5% 的股票被标记为"剔除"，原因为"低盈利"

### Requirement: Custom Financial Screening
The system MUST support custom financial screening rules including cashflow sync ratio, expense anomaly detection, and receivable-revenue linkage analysis, all computed from local data.

#### Scenario: Cashflow Sync Ratio Check
- **Given** 股票近两年经营现金流、营收、费用数据已在本地数据库中
- **When** 执行现金流同步率检查
- **Then** "经营活动现金流净额 / (营收 + 费用)" 连续两年 ≤ 0.5 的股票被标记为"剔除"，原因为"现金流支撑不足"

#### Scenario: Expense Anomaly Detection
- **Given** 股票近三年费用拆项数据已在本地数据库中
- **When** 执行费用异常检测
- **Then** 销售/管理/研发费用率出现 >50% 异常波动且无合理解释的股票被标记为"可疑"

#### Scenario: Receivable-Revenue Linkage
- **Given** 股票近两年应收账款和营收数据已在本地数据库中
- **When** 执行应收营收联动分析
- **Then** (应收账款增速 - 营收增速) > 20% 且连续两年的股票被标记为"剔除"，原因为"疑似虚增收入"

### Requirement: Benford Law Verification
The system MUST support Benford's First Digit Law verification on specific financial statement items, using only local data.

#### Scenario: Benford Check on Revenue and Profit
- **Given** 股票近年营收和利润数据已在本地数据库中
- **When** 执行本福德检验
- **Then** 卡方检验 p-value < 0.05 的股票被标记为"本福德检验异常"（软条件，不直接剔除）

### Requirement: Configurable Screening Rules
All screening rules MUST be configurable, allowing users to adjust thresholds, enable/disable rules, and set hard/soft reject conditions.

#### Scenario: Modify ROE Threshold
- **Given** 管理员访问筛选规则配置
- **When** 将 ROE 阈值从 5% 调整为 8%
- **Then** 下次运行初筛时使用新阈值，且配置变更有审计记录

#### Scenario: Disable Benford Check
- **Given** 管理员访问筛选规则配置
- **When** 禁用本福德检验规则
- **Then** 下次运行初筛时跳过本福德检验步骤

### Requirement: Screening Rule Execution Details for Frontend
The system MUST return detailed execution statistics for each screening rule, enabling the frontend to display per-rule hit/miss counts.

#### Scenario: Display Rule Statistics Table
- **Given** 初筛引擎完成运行
- **When** 结果返回前端
- **Then** 包含每条规则的 `RuleExecutionDetail`：规则名称、通过数、剔除数、跳过数（数据不足）、执行耗时、阈值说明、示例被剔除股票

#### Scenario: Display Rejected Stocks with Reasons
- **Given** 初筛引擎完成运行
- **When** 用户在前端查看剔除列表
- **Then** 每只被剔除的股票显示具体的剔除原因列表（可能被多条规则剔除）

### Requirement: Screening Result Persistence
Screening results MUST be persisted in storage, supporting historical queries and comparison.

#### Scenario: Save Screening Results
- **Given** 初筛引擎完成运行
- **When** 结果生成
- **Then** 每只股票的通过/剔除状态、原因、各指标值存入 `quant_screening_result` 表，运行统计存入 `quant_screening_run_stats` 表

#### Scenario: Query Historical Screening
- **Given** 有多期初筛结果
- **When** 用户查询指定日期的初筛结果
- **Then** 返回该期所有通过的股票列表，包含详细指标数据和规则执行统计

### Requirement: Screening API
The system MUST provide RESTful API to trigger screening and query results, with data readiness checks built-in.

#### Scenario: Trigger Screening Run
- **Given** 用户发送 `POST /api/quant/screening/run` 请求
- **When** 请求被处理
- **Then** 先执行数据就绪检查；数据就绪则异步启动初筛任务返回任务ID；数据缺失则返回 `MissingDataSummary`

#### Scenario: Get Screening Result with Rule Details
- **Given** 初筛已完成
- **When** 用户发送 `GET /api/quant/screening/result` 请求
- **Then** 返回最新一期初筛通过的股票列表（约250只），包含各指标值、通过/剔除状态、以及每条规则的执行统计
