# Capability: quant-core-pool

核心池构建与管理，包括多因子打分模型（选出Top50核心底仓）、RPS相对强度指标计算（补充市场热点）和动态目标池维护。

**核心约束**：
- 所有因子计算和RPS计算仅从 ClickHouse 本地数据读取，禁止调用 TuShare/AKShare 远程插件
- 执行前 MUST 进行数据就绪检查，数据缺失时返回结构化报告供前端展示和一键补数据
- 每个因子的得分明细、排名变化、入池/出池变动 MUST 在前端展示

## ADDED Requirements

### Requirement: Data Readiness Check Before Pool Building
The system MUST check data readiness before executing core pool building or RPS calculation, returning a structured missing data report if data is insufficient.

#### Scenario: Check Pool Building Data Readiness
- **Given** 用户触发核心池构建
- **When** `DataReadinessChecker` 检查所需表(fact_daily_basic/fact_daily_bar/fact_adj_factor + 财务指标表)
- **Then** 数据就绪则继续执行；缺失则返回 `MissingDataSummary` 含缺失详情和需触发的插件列表

#### Scenario: Frontend One-Click Data Fix for Pool
- **Given** 核心池构建因数据缺失而中止
- **When** 前端展示 `DataReadinessPanel`
- **Then** 用户可看到缺失的具体数据（如"fact_daily_bar 缺少最近5个交易日数据"），点击"一键补数据"触发 `batchTriggerSync` 补充 `tushare_daily` 插件

### Requirement: Multi-Factor Scoring Model
The system MUST implement a multi-factor weighted scoring model to rank stocks, computing all factors from local ClickHouse data only.

#### Scenario: Score Stocks by Four Factors
- **Given** 初筛通过约250只股票
- **When** 执行多因子打分
- **Then** 每只股票获得质量(30%)、成长(30%)、估值(20%)、动量(20%)四个维度得分及加权总分

#### Scenario: Quality Factor Calculation with Breakdown
- **Given** 股票的ROE、毛利率、负债率数据已在本地数据库中
- **When** 计算质量因子
- **Then** 返回归一化后的质量得分（0-100）及明细 `{roe: 85, gross_margin: 72, debt_ratio: 90}`，供前端因子雷达图展示

#### Scenario: Growth Factor Calculation with Breakdown
- **Given** 股票的营收增速、利润增速数据已在本地数据库中
- **When** 计算成长因子
- **Then** 返回归一化后的成长得分（0-100）及明细 `{revenue_growth: 88, profit_growth: 76}`

#### Scenario: Value Factor Calculation with Breakdown
- **Given** 股票的PE、PB及其历史分位数数据可从本地计算
- **When** 计算估值因子
- **Then** 返回归一化后的估值得分（0-100）及明细 `{pe_percentile: 30, pb_percentile: 25}`

#### Scenario: Momentum Factor Calculation with Breakdown
- **Given** 股票近半年行情数据已在本地数据库中
- **When** 计算动量因子
- **Then** 返回归一化后的动量得分（0-100）及明细 `{half_year_return: 0.15, rps_250: 82}`

### Requirement: Core Pool Selection with Change Tracking
The system MUST select top 50 stocks by score into the core pool, and track all pool changes for frontend display.

#### Scenario: Select Top 50
- **Given** 所有初筛通过的股票已完成多因子打分
- **When** 构建核心池
- **Then** 选出总分排名前50的股票进入核心池（pool_type='core'），记录入池日期和各因子得分

#### Scenario: Monthly Pool Update with Change Log
- **Given** 核心池已存在且新一期打分完成
- **When** 执行月度更新
- **Then** 新排名进入前50但不在池中的股票入池(change_type='new_entry')，排名跌出前50的股票标记出池(change_type='exit')，排名大幅变化的标记(change_type='rank_change')

#### Scenario: Display Factor Score Distribution
- **Given** 核心池构建完成
- **When** 前端请求池数据
- **Then** 返回四个因子的得分分布统计(均值/中位数/标准差/分位数)，供前端箱线图/直方图展示

### Requirement: RPS Calculation
The system MUST implement market-wide RPS calculation using only local ClickHouse data.

#### Scenario: Calculate 250-day RPS
- **Given** 全市场活跃股票250个交易日行情数据已在本地数据库中
- **When** 计算250日RPS
- **Then** 每只股票获得0-100的RPS值，代表其涨幅超过了百分之多少的股票

#### Scenario: Multi-Period RPS
- **Given** 全市场行情数据已在本地数据库中
- **When** 计算多周期RPS
- **Then** 同时输出250日、120日、60日三个周期的RPS值

#### Scenario: Store RPS Results
- **Given** RPS计算完成
- **When** 结果生成
- **Then** 全市场RPS排名数据存入 `quant_rps_rank` 表，按日期分区

### Requirement: RPS Supplement Pool
The system MUST use RPS indicators to supplement strong stocks outside the core pool, forming a watchlist.

#### Scenario: Weekly RPS Supplement
- **Given** 最新一期RPS计算完成
- **When** 执行周度补充筛选
- **Then** 不在核心池但 RPS_250 > 80 且通过简化财务快检（净利润>0 且 ROE>3%）的股票进入补充池（pool_type='rps_supplement'）

#### Scenario: Supplement Pool Size Control
- **Given** RPS补充筛选完成
- **When** 补充池股票超过20只
- **Then** 按RPS得分排序，仅保留前20只

### Requirement: Factor Weight Configuration
Factor weights MUST be user-configurable with validation.

#### Scenario: Adjust Factor Weights
- **Given** 用户访问模型配置
- **When** 将质量因子权重从30%调整为40%，成长因子从30%调整为20%
- **Then** 下次构建核心池时使用新权重，且权重总和仍为100%

### Requirement: Core Pool API with Factor Details
The system MUST provide RESTful API to query and manage core pool, including factor score details for frontend display.

#### Scenario: Get Current Pool with Factor Breakdown
- **Given** 核心池和补充池已构建
- **When** 用户发送 `GET /api/quant/pool`
- **Then** 返回当前目标池所有股票（核心50 + 补充20），包含各因子得分、因子明细(breakdown)、RPS值、入池日期

#### Scenario: Get Pool Changes
- **Given** 核心池经过多次更新
- **When** 用户发送 `GET /api/quant/pool/changes`
- **Then** 返回入池/出池变动日志列表，包含变动类型(new_entry/exit/rank_change)、变动日期、得分变化

#### Scenario: Get RPS Rankings
- **Given** RPS已计算
- **When** 用户发送 `GET /api/quant/rps`
- **Then** 返回全市场RPS排名前100的股票列表，包含多周期RPS值

#### Scenario: Refresh Core Pool
- **Given** 用户发送 `POST /api/quant/pool/refresh`
- **When** 请求被处理
- **Then** 先检查数据就绪；就绪则异步触发核心池重新构建并返回任务ID；缺失则返回 `MissingDataSummary`
