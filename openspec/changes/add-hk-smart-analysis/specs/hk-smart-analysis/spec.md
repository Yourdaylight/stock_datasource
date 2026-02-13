# Spec: hk-smart-analysis

## MODIFIED Requirements

### Requirement: MarketAgent MUST 支持港股技术分析

MarketAgent SHALL 识别港股代码（*.HK）并提供完整的技术分析能力，包括 K 线数据、技术指标（MACD/RSI/KDJ/BOLL/MA 等）、趋势分析。

#### Scenario: 用户请求港股技术指标分析
- **Given** 用户输入"分析 00700.HK 的技术指标"
- **When** OrchestratorAgent 分类意图为 market_analysis
- **Then** MarketAgent 被选中执行
- **And** MarketAgent 调用 `get_kline("00700.HK")` 获取 K 线数据
- **And** MarketAgent 调用 `calculate_indicators("00700.HK", "MACD,RSI,KDJ")` 计算技术指标
- **And** 返回包含 MACD、RSI、KDJ 等指标值和交易信号的分析结果

#### Scenario: 用户用中文名称查询港股
- **Given** 用户输入"分析腾讯的走势"，上下文包含港股关键词
- **When** OrchestratorAgent 提取到港股代码
- **Then** MarketAgent 能正确处理港股代码格式

### Requirement: tools.py 工具函数 MUST 支持港股代码

DeepAgent 使用的工具函数（get_stock_info、get_stock_kline、calculate_technical_indicators）SHALL 检测 `.HK` 后缀并查询正确的数据表。

#### Scenario: get_stock_info 查询港股信息
- **Given** 调用 `get_stock_info("00700.HK")`
- **When** 函数检测到 `.HK` 后缀
- **Then** 查询 `ods_hk_daily` 表获取最新行情
- **And** 查询 `ods_hk_basic` 表获取股票名称
- **And** 返回格式化的港股信息（收盘价、涨跌幅、成交量等）

#### Scenario: get_stock_kline 查询港股 K 线
- **Given** 调用 `get_stock_kline("00700.HK", days=30)`
- **When** 函数检测到 `.HK` 后缀
- **Then** 查询 `ods_hk_daily` 表获取 K 线数据
- **And** 返回格式化的 K 线表格

#### Scenario: calculate_technical_indicators 计算港股技术指标
- **Given** 调用 `calculate_technical_indicators("00700.HK")`
- **When** 函数检测到 `.HK` 后缀
- **Then** 从 `ods_hk_daily` 获取 OHLCV 数据
- **And** 计算均线、趋势、量能等技术指标
- **And** 返回格式化的技术指标分析结果

## ADDED Requirements

### Requirement: Orchestrator MUST 支持港股综合分析多 Agent 编排

当用户请求涉及港股的综合分析（技术面+基本面）时，OrchestratorAgent SHALL 自动组合 MarketAgent + HKReportAgent 并发执行。

#### Scenario: 港股综合分析自动组合
- **Given** 用户输入"全面分析腾讯 00700.HK 的技术面和财务情况"
- **When** OrchestratorAgent 检测到港股代码且意图涉及技术分析
- **Then** 构建多 Agent 执行计划: [MarketAgent, HKReportAgent]
- **And** 两个 Agent 并发执行
- **And** MarketAgent 返回技术分析（K 线、技术指标、趋势）
- **And** HKReportAgent 返回财务分析（盈利能力、资产质量、现金流）
- **And** 结果合并后流式返回给用户

#### Scenario: 纯港股财报请求不触发技术分析
- **Given** 用户输入"00700.HK 的财报分析"
- **When** OrchestratorAgent 分类意图为 hk_financial_report
- **Then** 仅路由到 HKReportAgent
- **And** 不触发 MarketAgent

#### Scenario: A 股分析不受影响
- **Given** 用户输入"分析 600519.SH 的技术指标和财务情况"
- **When** OrchestratorAgent 检测到 A 股代码
- **Then** 保持原有逻辑: MarketAgent + ReportAgent 并发执行
- **And** 不路由到 HKReportAgent
