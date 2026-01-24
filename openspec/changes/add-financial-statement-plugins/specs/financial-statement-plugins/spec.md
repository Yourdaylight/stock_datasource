# financial-statement-plugins Specification

## Purpose

提供 Tushare 三大财务报表（利润表、资产负债表、现金流量表）的数据获取、存储和查询能力，作为财务分析的基础数据源。

## ADDED Requirements

### Requirement: Income Statement Data Plugin
系统 SHALL 提供利润表数据插件，能够从 Tushare 获取并存储上市公司利润表数据。

#### Scenario: 获取单只股票利润表数据
- **GIVEN** 用户提供有效的股票代码（如 600000.SH）
- **WHEN** 调用利润表数据提取功能
- **THEN** 系统从 Tushare income 接口获取该股票的利润表数据
- **AND** 数据包含基本每股收益、营业收入、净利润等核心字段
- **AND** 数据按报告期降序排列

#### Scenario: 利润表数据存储
- **WHEN** 利润表数据成功提取
- **THEN** 数据存储到 ClickHouse 的 `ods_income_statement` 表
- **AND** 支持按 ts_code 和 end_date 的组合唯一键去重
- **AND** 保留 report_type 字段以区分合并报表、单季报表等类型

#### Scenario: 利润表数据查询
- **GIVEN** ClickHouse 中已有利润表数据
- **WHEN** 用户按股票代码查询利润表
- **THEN** 返回指定期数的利润表数据列表
- **AND** 支持按报告类型过滤
- **AND** 日期字段格式化为 YYYYMMDD 字符串

### Requirement: Balance Sheet Data Plugin
系统 SHALL 提供资产负债表数据插件，能够从 Tushare 获取并存储上市公司资产负债表数据。

#### Scenario: 获取单只股票资产负债表数据
- **GIVEN** 用户提供有效的股票代码
- **WHEN** 调用资产负债表数据提取功能
- **THEN** 系统从 Tushare balancesheet 接口获取该股票的资产负债表数据
- **AND** 数据包含总资产、总负债、股东权益等核心字段
- **AND** 数据包含流动资产、流动负债等明细字段

#### Scenario: 资产负债表数据存储
- **WHEN** 资产负债表数据成功提取
- **THEN** 数据存储到 ClickHouse 的 `ods_balance_sheet` 表
- **AND** 支持按 ts_code 和 end_date 的组合唯一键去重
- **AND** 数值字段保留原始精度

#### Scenario: 资产负债表数据查询
- **GIVEN** ClickHouse 中已有资产负债表数据
- **WHEN** 用户按股票代码查询资产负债表
- **THEN** 返回指定期数的资产负债表数据列表
- **AND** 支持计算衍生指标如流动比率、速动比率

### Requirement: Cash Flow Statement Data Plugin
系统 SHALL 提供现金流量表数据插件，能够从 Tushare 获取并存储上市公司现金流量表数据。

#### Scenario: 获取单只股票现金流量表数据
- **GIVEN** 用户提供有效的股票代码
- **WHEN** 调用现金流量表数据提取功能
- **THEN** 系统从 Tushare cashflow 接口获取该股票的现金流量表数据
- **AND** 数据包含经营、投资、筹资活动现金流净额
- **AND** 数据包含销售收现、购建资产付现等明细字段

#### Scenario: 现金流量表数据存储
- **WHEN** 现金流量表数据成功提取
- **THEN** 数据存储到 ClickHouse 的 `ods_cash_flow` 表
- **AND** 支持按 ts_code 和 end_date 的组合唯一键去重

#### Scenario: 现金流量表数据查询
- **GIVEN** ClickHouse 中已有现金流量表数据
- **WHEN** 用户按股票代码查询现金流量表
- **THEN** 返回指定期数的现金流量表数据列表
- **AND** 支持计算自由现金流等衍生指标

### Requirement: Unified Financial Statement Service
系统 SHALL 提供统一的财务报表查询服务，整合三张报表数据。

#### Scenario: 获取完整财务报表
- **GIVEN** 用户提供股票代码和报告期数
- **WHEN** 调用统一财务报表查询接口
- **THEN** 返回包含利润表、资产负债表、现金流量表的完整数据
- **AND** 数据按报告期对齐
- **AND** 包含计算后的衍生指标

#### Scenario: 跨报表指标计算
- **GIVEN** 已获取某股票的三张报表数据
- **WHEN** 请求计算衍生指标
- **THEN** 系统计算以下指标:
  - 营运资本 = 流动资产 - 流动负债
  - 自由现金流 = 经营现金流 - 资本支出
  - 现金转换周期相关指标
- **AND** 指标计算结果附加到响应中

### Requirement: Report Type Support
系统 SHALL 支持不同类型的财务报表查询，包括合并报表和单季报表。

#### Scenario: 按报告类型过滤
- **GIVEN** 用户指定报告类型代码（如 1=合并报表, 2=单季合并）
- **WHEN** 查询财务报表数据
- **THEN** 仅返回匹配报告类型的数据
- **AND** 默认返回合并报表（report_type=1）数据

#### Scenario: 获取调整后报表
- **GIVEN** 用户请求调整后的财务数据
- **WHEN** 查询 report_type=4 的数据
- **THEN** 返回公司公布的上年同期调整后数据
- **AND** 明确标识数据来源和调整说明
