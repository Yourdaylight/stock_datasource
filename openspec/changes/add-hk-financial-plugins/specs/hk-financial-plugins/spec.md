# Specification: HK Financial Plugins

## Capability Overview

港股财务数据采集和查询能力，支持港股财务指标、资产负债表、利润表和现金流量表数据。

---

## ADDED Requirements

### Requirement: HK Financial Indicator Plugin
**ID**: HK-FIN-001
**Priority**: High

系统 SHALL 实现港股财务指标数据采集插件，MUST 支持从 TuShare Pro API 获取港股公司的综合财务指标数据。

#### Scenario: 获取单只港股的财务指标
```gherkin
Given 系统已配置 TuShare Pro API Token
And 用户请求获取港股 "00700.HK" 的财务指标
When 调用 hk_fina_indicator 插件
Then 系统从 TuShare API 获取数据
And 数据存入 ods_hk_fina_indicator 表
And 返回包含 ROE、EPS、毛利率等指标的数据
```

#### Scenario: 批量获取港股财务指标
```gherkin
Given 系统已配置 TuShare Pro API Token
And ods_hk_stock_list 表中有港股列表
When 调用 hk_fina_indicator 插件的批量模式
Then 系统遍历港股列表提取数据
And 应用 0.1 秒间隔限频
And 所有数据存入 ods_hk_fina_indicator 表
```

#### Scenario: 按报告期查询财务指标
```gherkin
Given ods_hk_fina_indicator 表中有历史数据
When 用户查询 "00700.HK" 的 2024 年年报财务指标
Then 返回 report_type='Q4' 且 end_date 为 2024 年末的记录
And 包含所有财务指标字段
```

---

### Requirement: HK Balance Sheet Plugin
**ID**: HK-FIN-002
**Priority**: High

系统 SHALL 实现港股资产负债表数据采集插件，MUST 采用纵表结构（EAV 模型）存储。

#### Scenario: 获取港股资产负债表
```gherkin
Given 系统已配置 TuShare Pro API Token
And 用户请求获取港股 "00700.HK" 的资产负债表
When 调用 hk_balancesheet 插件
Then 系统从 TuShare API 获取纵表数据
And 每个财务科目存储为一行（ts_code, end_date, ind_name, ind_value）
And 数据存入 ods_hk_balancesheet 表
```

#### Scenario: 按指标名称查询资产负债表
```gherkin
Given ods_hk_balancesheet 表中有数据
When 用户查询 "00700.HK" 的 "资产总额" 历年数据
Then 返回该股票所有报告期的 "资产总额" 指标值
And 结果按 end_date 降序排列
```

#### Scenario: PIVOT 查询资产负债表
```gherkin
Given ods_hk_balancesheet 表中有数据
When 用户请求 "00700.HK" 的宽表格式资产负债表
Then 系统执行条件聚合查询
And 返回每个报告期一行，多个指标作为列
And 包含 total_assets, total_liabilities, shareholders_equity 等关键指标
```

---

### Requirement: HK Income Statement Plugin
**ID**: HK-FIN-003
**Priority**: High

系统 SHALL 实现港股利润表数据采集插件，MUST 采用纵表结构（EAV 模型）存储。

#### Scenario: 获取港股利润表
```gherkin
Given 系统已配置 TuShare Pro API Token
And 用户请求获取港股 "00700.HK" 的利润表
When 调用 hk_income 插件
Then 系统从 TuShare API 获取纵表数据
And 数据存入 ods_hk_income 表
```

#### Scenario: 查询营业收入趋势
```gherkin
Given ods_hk_income 表中有数据
When 用户查询 "00700.HK" 的 "营业额" 历年趋势
Then 返回该股票所有报告期的 "营业额" 指标值
And 可用于绘制趋势图表
```

---

### Requirement: HK Cash Flow Statement Plugin
**ID**: HK-FIN-004
**Priority**: High

系统 SHALL 实现港股现金流量表数据采集插件，MUST 采用纵表结构（EAV 模型）存储。

#### Scenario: 获取港股现金流量表
```gherkin
Given 系统已配置 TuShare Pro API Token
And 用户请求获取港股 "00700.HK" 的现金流量表
When 调用 hk_cashflow 插件
Then 系统从 TuShare API 获取纵表数据
And 数据存入 ods_hk_cashflow 表
```

#### Scenario: 查询现金流指标
```gherkin
Given ods_hk_cashflow 表中有数据
When 用户查询 "00700.HK" 的 "经营业务现金净额" 数据
Then 返回该股票的经营现金流历史数据
```

---

### Requirement: HK Financial Query Service
**ID**: HK-FIN-005
**Priority**: Medium

系统 SHALL 提供统一的港股财务数据查询服务，MUST 支持纵表的 PIVOT 转换查询。

#### Scenario: 统一查询入口
```gherkin
Given 四个港股财务插件已部署
When 用户通过 HKFinancialService 查询财务数据
Then 可以查询财务指标（宽表）
And 可以查询三大报表（纵表或 PIVOT 宽表）
And 支持按股票代码、报告期、指标名称筛选
```

#### Scenario: Agent 自然语言查询
```gherkin
Given Agent 已注册港股财务查询工具
When 用户询问 "腾讯 2024 年的 ROE 是多少？"
Then Agent 调用 hk_fina_indicator 查询
And 返回 roe_avg 或 roe_yearly 字段值
```

---

## Data Models

### ods_hk_fina_indicator（宽表）

| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | String | 港股代码 |
| name | String | 股票名称 |
| end_date | Date | 报告期 |
| report_type | String | 报告期类型 |
| basic_eps | Float64 | 基本每股收益 |
| bps | Float64 | 每股净资产 |
| roe_avg | Float64 | 平均 ROE |
| roa | Float64 | ROA |
| gross_profit_ratio | Float64 | 毛利率 |
| net_profit_ratio | Float64 | 净利率 |
| current_ratio | Float64 | 流动比率 |
| debt_asset_ratio | Float64 | 资产负债率 |
| pe_ttm | Float64 | 滚动市盈率 |
| pb_ttm | Float64 | 滚动市净率 |
| ... | ... | ~60 个字段 |

### ods_hk_balancesheet / ods_hk_income / ods_hk_cashflow（纵表）

| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | String | 港股代码 |
| name | String | 股票名称 |
| end_date | Date | 报告期 |
| ind_name | String | 财务科目名称 |
| ind_value | Float64 | 财务科目值 |

---

## API Endpoints

### REST API

```
GET /api/hk/financial/indicator
  - ts_code: 港股代码（必填）
  - start_date: 开始日期
  - end_date: 结束日期
  - report_type: 报告期类型

GET /api/hk/financial/balancesheet
  - ts_code: 港股代码（必填）
  - period: 报告期
  - ind_name: 指标名称
  - format: raw | pivot

GET /api/hk/financial/income
  - ts_code: 港股代码（必填）
  - period: 报告期
  - ind_name: 指标名称
  - format: raw | pivot

GET /api/hk/financial/cashflow
  - ts_code: 港股代码（必填）
  - period: 报告期
  - ind_name: 指标名称
  - format: raw | pivot
```

---

## Cross-References

- 依赖: `ods_hk_stock_list` 港股基础数据表
- 相关: `openspec/specs/financial-report-analysis/` A 股财务分析规范
- 相关: `openspec/changes/add-financial-statement-plugins/` A 股财务插件提案
