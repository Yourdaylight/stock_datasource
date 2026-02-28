# Capability: quant-deep-analysis

深度分析引擎，对目标池内个股进行技术指标实时监控和管理层讨论AI辅助分析，为投资决策提供深度信息支持。

**核心约束**：
- 技术指标计算仅从 ClickHouse 本地数据读取，禁止调用 TuShare/AKShare 远程插件
- 执行前 MUST 进行数据就绪检查
- 技术指标快照、AI分析结果（可信度/乐观度/验证点）MUST 在前端完整展示

## ADDED Requirements

### Requirement: Data Readiness Check Before Analysis
The system MUST check data readiness before executing technical analysis, returning a structured missing data report if local data is insufficient.

#### Scenario: Check Analysis Data Readiness
- **Given** 用户触发深度分析
- **When** `DataReadinessChecker` 检查目标池股票的日线数据完整性
- **Then** 数据就绪则继续分析；缺失则返回 `MissingDataSummary` 含缺失详情和需触发的插件

### Requirement: Technical Indicator Monitoring
The system MUST provide daily-updated technical indicator monitoring data for stocks in the target pool, computed entirely from local ClickHouse data.

#### Scenario: MA Position Analysis
- **Given** 目标池内某只股票的日线数据已在本地 ClickHouse 中
- **When** 执行技术指标监控
- **Then** 返回 MA25 和 MA120 的当前值，以及股价与均线的位置关系（站上MA25=短期强势，跌破MA120=风险警告）

#### Scenario: Auxiliary Indicators
- **Given** 目标池内股票的日线数据已在本地 ClickHouse 中
- **When** 执行技术指标监控
- **Then** 同时返回成交量变化、MACD信号线状态、RSI值，并标注超买(>80)/超卖(<20)区域

#### Scenario: Technical Score and Snapshot
- **Given** 所有技术指标已计算
- **When** 生成技术评分
- **Then** 综合 MA 位置、MACD、RSI 等指标输出 0-100 的技术面得分，并返回完整 `tech_snapshot` JSON 供前端图表渲染

### Requirement: Management Discussion NLP Analysis
The system MUST use LLM to analyze the "Management Discussion and Analysis" section of financial reports.

#### Scenario: Extract Key Information
- **Given** 某只股票的最新财报管理层讨论文本
- **When** 提交AI分析
- **Then** 返回结构化提取结果：行业趋势描述、公司战略规划、风险因素列表

#### Scenario: Credibility and Prospect Scoring
- **Given** 管理层讨论文本已提交AI分析
- **When** 分析完成
- **Then** 返回可信度评分(0-100)和前景乐观度评分(0-100)，附带评分理由

#### Scenario: Verification Points Generation
- **Given** 管理层讨论分析完成
- **When** 生成验证点
- **Then** 输出可跟踪的未来验证指标列表（如"Q3订单目标达成率"、"新产线产能利用率"等）

#### Scenario: Peer Comparison
- **Given** 同行业多家公司的管理层讨论已分析
- **When** 执行同行对比
- **Then** 输出行业共识（多家提及的趋势）与分歧（各家观点不同的方面）

### Requirement: Batch Deep Analysis with Progress
The system MUST support batch deep analysis for all stocks in the target pool, with progress tracking for frontend display.

#### Scenario: Batch Technical Analysis
- **Given** 目标池包含70只股票
- **When** 执行批量技术分析
- **Then** 70只股票全部完成技术指标计算（纯本地数据），结果存入数据库

#### Scenario: Batch NLP Analysis with Progress
- **Given** 目标池包含70只股票需要NLP分析
- **When** 执行批量NLP分析
- **Then** 分析任务进入队列依次处理，前端可通过 `GET /api/quant/analysis/batch/status` 查询进度（已完成/总数/当前处理），完成后结果存入 `quant_deep_analysis` 表

### Requirement: Analysis Dashboard for Frontend
The system MUST provide comprehensive dashboard data for frontend visualization.

#### Scenario: Get Dashboard Data with Tech Snapshots
- **Given** 目标池的技术指标和AI分析结果已生成
- **When** 用户请求仪表盘数据
- **Then** 返回每只股票的技术得分、MA位置状态、AI分析摘要、技术指标快照（`tech_snapshot`），支持按得分排序，前端可直接渲染图表

#### Scenario: Individual Stock Deep Analysis
- **Given** 用户指定某只股票
- **When** 发送 `POST /api/quant/analysis/{ts_code}`
- **Then** 先检查该股票日线数据就绪；就绪则返回完整深度分析报告（含所有技术指标图表数据、AI分析结果和历史分析对比）；缺失则返回 `MissingDataSummary`
