# Capability: Market Analysis (行情分析)

## Overview

行情分析模块提供股票K线数据获取、技术指标计算、AI走势分析和市场概览功能。

## ADDED Requirements

### Requirement: K-Line Data Retrieval

系统 SHALL 提供股票K线数据获取能力，支持指定日期范围和复权类型。

#### Scenario: Get K-Line Data Success
- **WHEN** 用户请求股票 `600519.SH` 从 `2024-01-01` 到 `2024-01-31` 的K线数据
- **THEN** 系统返回该时间段内每个交易日的开盘价、最高价、最低价、收盘价、成交量、成交额
- **AND** 数据按日期升序排列

#### Scenario: Get K-Line Data with Adjustment
- **WHEN** 用户请求前复权K线数据 (adjust=qfq)
- **THEN** 系统返回经过复权因子调整后的价格数据

#### Scenario: Get K-Line Data - Stock Not Found
- **WHEN** 用户请求不存在的股票代码
- **THEN** 系统返回空数据集并提示股票不存在

---

### Requirement: Technical Indicator Calculation

系统 SHALL 提供完整的技术指标计算能力，包括MA、EMA、MACD、RSI、KDJ、BOLL等常用指标。

#### Scenario: Calculate MA (Moving Average)
- **WHEN** 用户请求计算 `600519.SH` 的MA指标，周期为 [5, 10, 20]
- **THEN** 系统返回MA5、MA10、MA20三条均线数据
- **AND** 每条均线包含日期和对应均值

#### Scenario: Calculate MACD
- **WHEN** 用户请求计算MACD指标，参数为 fast=12, slow=26, signal=9
- **THEN** 系统返回DIF、DEA、MACD柱状图数据
- **AND** 数据包含金叉/死叉信号标记

#### Scenario: Calculate RSI
- **WHEN** 用户请求计算RSI指标，周期为14
- **THEN** 系统返回RSI值序列（0-100范围）
- **AND** 标注超买(>70)和超卖(<30)区域

#### Scenario: Calculate KDJ
- **WHEN** 用户请求计算KDJ指标，参数为 n=9, m1=3, m2=3
- **THEN** 系统返回K、D、J三线数据
- **AND** 数据包含金叉/死叉信号标记

#### Scenario: Calculate BOLL (Bollinger Bands)
- **WHEN** 用户请求计算布林带指标，参数为 period=20, std=2
- **THEN** 系统返回上轨、中轨、下轨三条线数据

#### Scenario: Calculate Multiple Indicators
- **WHEN** 用户请求同时计算 ["MA", "MACD", "RSI"]
- **THEN** 系统批量计算并返回所有请求的指标数据
- **AND** 单次请求最多支持5个指标

#### Scenario: Invalid Indicator Parameters
- **WHEN** 用户提供非法的指标参数（如MA周期为负数）
- **THEN** 系统返回参数校验错误信息

---

### Requirement: Market Overview

系统 SHALL 提供市场概览信息，包括大盘指数、涨跌统计和成交情况。

#### Scenario: Get Market Overview
- **WHEN** 用户请求市场概览
- **THEN** 系统返回当日主要指数（上证、深证、创业板）行情
- **AND** 返回涨跌家数统计（上涨、下跌、平盘）
- **AND** 返回市场总成交额

#### Scenario: Get Index Data
- **WHEN** 用户请求指数 `000001.SH`（上证指数）的行情数据
- **THEN** 系统返回该指数的最新价格、涨跌幅、成交额
- **AND** 返回近期K线数据

#### Scenario: Get Hot Sectors
- **WHEN** 用户请求热门板块
- **THEN** 系统返回当日涨幅前10的行业板块
- **AND** 每个板块包含涨跌幅和领涨股

---

### Requirement: AI Trend Analysis

系统 SHALL 提供基于LLM的AI走势分析能力，分析股票技术面并给出操作建议。

#### Scenario: AI Analysis Success
- **WHEN** 用户请求 `600519.SH` 的AI走势分析
- **THEN** 系统调用LLM分析该股票的技术指标
- **AND** 返回趋势判断（上涨/下跌/震荡）
- **AND** 返回支撑位和压力位
- **AND** 返回技术信号列表（如"MACD金叉"）
- **AND** 返回分析摘要文本
- **AND** 返回风险提示免责声明

#### Scenario: AI Analysis with Langfuse Tracing
- **WHEN** 系统执行AI分析
- **THEN** LLM调用过程被Langfuse追踪记录
- **AND** 追踪包含trace_name="market_trend_analysis"

#### Scenario: AI Analysis - LLM Unavailable
- **WHEN** LLM服务不可用
- **THEN** 系统返回错误提示"AI分析服务暂不可用"
- **AND** 仍返回基础技术指标数据

---

### Requirement: Stock Search

系统 SHALL 提供股票搜索功能，支持按代码或名称模糊匹配。

#### Scenario: Search by Code
- **WHEN** 用户搜索 "600519"
- **THEN** 系统返回匹配的股票列表，包括代码和名称

#### Scenario: Search by Name
- **WHEN** 用户搜索 "茅台"
- **THEN** 系统返回名称包含"茅台"的股票列表

#### Scenario: Search Limit
- **WHEN** 搜索结果超过20条
- **THEN** 系统仅返回前20条匹配结果

---

### Requirement: K-Line Chart Visualization

前端 SHALL 提供专业的K线图表可视化组件，支持多指标叠加显示。

#### Scenario: Display K-Line Chart
- **WHEN** 用户选择股票并加载K线数据
- **THEN** 前端显示蜡烛图形式的K线图
- **AND** 主图下方显示成交量柱状图
- **AND** 支持鼠标悬停显示详情

#### Scenario: Overlay MA Lines
- **WHEN** 用户选择显示MA指标
- **THEN** MA线叠加在K线主图上
- **AND** 不同周期的MA线使用不同颜色区分

#### Scenario: Display Sub-Chart Indicators
- **WHEN** 用户选择显示MACD/RSI/KDJ指标
- **THEN** 这些指标显示在K线主图下方的副图区域
- **AND** 副图与主图X轴（日期）对齐联动

#### Scenario: Chart Interaction
- **WHEN** 用户在图表上进行缩放或平移操作
- **THEN** 图表响应用户操作更新显示范围
- **AND** 十字光标跟随鼠标移动

---

### Requirement: Indicator Panel

前端 SHALL 提供指标控制面板，允许用户选择和配置技术指标。

#### Scenario: Select Indicators
- **WHEN** 用户在指标面板中勾选 ["MA", "MACD"]
- **THEN** 系统加载并显示所选指标

#### Scenario: Configure Indicator Parameters
- **WHEN** 用户修改MA指标的周期参数为 [5, 20, 60]
- **THEN** 系统使用新参数重新计算并更新图表

#### Scenario: Indicator Limit
- **WHEN** 用户尝试选择超过5个指标
- **THEN** 系统提示"最多同时显示5个指标"

---

### Requirement: Data Access via Plugin Services

后端 SHALL 通过Plugin Services获取所有数据，不直接编写SQL查询。

#### Scenario: Use TuShareDailyService
- **WHEN** 系统需要获取日线行情数据
- **THEN** 调用 `TuShareDailyService.get_daily_data()` 方法
- **AND** 不直接编写SQL查询ods_daily表

#### Scenario: Use TuShareIndexDailyService
- **WHEN** 系统需要获取指数行情数据
- **THEN** 调用 `TuShareIndexDailyService` 相关方法

#### Scenario: Use TuShareAdjFactorService
- **WHEN** 系统需要复权因子数据
- **THEN** 调用 `TuShareAdjFactorService` 相关方法
