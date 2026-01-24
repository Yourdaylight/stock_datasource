# Proposal: add-financial-statement-plugins

## Summary

添加 Tushare 财务数据完整系列插件：利润表(income)、资产负债表(balancesheet)、现金流量表(cashflow)、业绩预告(forecast)、业绩快报(express)，覆盖 Tushare 财务数据模块的全部 5 个接口。

## Background

当前系统已有 `tushare_finace_indicator` 插件提供财务指标数据，但缺少原始财务报表及业绩预测数据。根据 https://tushare.pro/document/2?doc_id=16 页面，Tushare 财务数据模块提供 5 个接口：

| 接口 | 说明 | 文档链接 |
|------|------|----------|
| **利润表 (income)** | 营业收入、净利润、EPS 等 (~80 字段) | [doc_id=33](https://tushare.pro/document/2?doc_id=33) |
| **资产负债表 (balancesheet)** | 资产、负债、所有者权益 (~120 字段) | [doc_id=36](https://tushare.pro/document/2?doc_id=36) |
| **现金流量表 (cashflow)** | 经营、投资、筹资现金流 (~90 字段) | [doc_id=44](https://tushare.pro/document/2?doc_id=44) |
| **业绩预告 (forecast)** | 预告类型、净利润变动幅度 (12 字段) | [doc_id=45](https://tushare.pro/document/2?doc_id=45) |
| **业绩快报 (express)** | 快速披露的核心财务数据 (30 字段) | [doc_id=46](https://tushare.pro/document/2?doc_id=46) |

三大报表是财务分析的基础，业绩预告/快报则提供事件驱动型投资的关键信息。

## Goals

1. 创建 5 个独立的 Tushare 数据插件，完整覆盖财务数据模块
2. 遵循现有插件架构模式（参考 `tushare_finace_indicator`），保持代码一致性
3. 集成到现有的 `financial-report-analysis` 规范中，支持完整的财务分析功能
4. 提供统一的查询服务接口，供 Agent 和 API 调用

## Non-Goals

- 不涉及前端 UI 变更（已有 financial-report-analysis 规范覆盖）
- 不修改现有的 tushare_finace_indicator 插件
- 不实现 VIP 接口（income_vip 等需 5000 积分，按季度全量获取）

## Affected Specs

- `financial-report-analysis`: 需要新增数据获取相关的 Requirements

## Design Considerations

### 插件架构
每个插件遵循现有模式，包含：
- `__init__.py`: 模块导出
- `config.json`: 配置文件（限频、调度、参数 schema）
- `schema.json`: ClickHouse 表结构
- `extractor.py`: 数据提取器（TuShare API 调用 + 限流 + 重试）
- `plugin.py`: 插件主类（继承 BasePlugin）
- `service.py`: 查询服务（继承 BaseService）

### API 参数对照

| 插件 | Tushare API | 必选参数 | 可选参数 |
|------|-------------|----------|----------|
| tushare_income | `pro.income()` | ts_code | ann_date, f_ann_date, start_date, end_date, period, report_type, comp_type |
| tushare_balancesheet | `pro.balancesheet()` | ts_code | ann_date, start_date, end_date, period, report_type, comp_type |
| tushare_cashflow | `pro.cashflow()` | ts_code | ann_date, f_ann_date, start_date, end_date, period, report_type, comp_type, is_calc |
| tushare_forecast | `pro.forecast()` | ts_code 或 ann_date | start_date, end_date, period, type |
| tushare_express | `pro.express()` | ts_code | ann_date, start_date, end_date, period |

**批处理模式**:
- 所有插件支持批处理模式：当未提供 `ts_code` 时，自动从 `ods_stock_basic` 获取所有活跃股票（`list_status = 'L'`）
- 批处理模式下，插件会遍历所有股票并逐个调用 API 提取数据
- 添加 0.1 秒的速率限制以避免超过 API 调用频率限制
- 数据合并后统一添加系统列（`version`, `_ingested_at`）

### 数据表命名
| 插件 | 表名 | 分区键 | 排序键 |
|------|------|--------|--------|
| tushare_income | `ods_income_statement` | `toYYYYMM(end_date)` | `[ts_code, end_date, report_type]` |
| tushare_balancesheet | `ods_balance_sheet` | `toYYYYMM(end_date)` | `[ts_code, end_date, report_type]` |
| tushare_cashflow | `ods_cash_flow` | `toYYYYMM(end_date)` | `[ts_code, end_date, report_type]` |
| tushare_forecast | `ods_forecast` | `toYYYYMM(end_date)` | `[ts_code, end_date, ann_date]` |
| tushare_express | `ods_express` | `toYYYYMM(end_date)` | `[ts_code, end_date, ann_date]` |

### 关键字段（核心输出）

**利润表 (income)**
- 基础: ts_code, ann_date, f_ann_date, end_date, report_type, comp_type
- 核心: basic_eps, diluted_eps, total_revenue, revenue, operate_profit, total_profit, n_income, n_income_attr_p, ebit, ebitda
- 费用: total_cogs, oper_cost, sell_exp, admin_exp, fin_exp, rd_exp, assets_impair_loss

**资产负债表 (balancesheet)**
- 资产: money_cap, accounts_receiv, inventories, total_cur_assets, fix_assets, intan_assets, total_nca, total_assets
- 负债: st_borr, lt_borr, accounts_pay, total_cur_liab, total_ncl, total_liab
- 权益: total_share, cap_rese, surplus_rese, undistr_porfit, total_hldr_eqy_exc_min_int

**现金流量表 (cashflow)**
- 经营: c_fr_sale_sg, c_paid_goods_s, n_cashflow_act
- 投资: c_disp_withdrwl_invest, c_pay_acq_const_fiolta, n_cashflow_inv_act
- 筹资: c_recp_borrow, c_prepay_amt_borr, n_cash_flows_fnc_act
- 期末: n_incr_cash_cash_equ, c_cash_equ_end_period, free_cashflow

**业绩预告 (forecast)**
- ts_code, ann_date, end_date, type, p_change_min, p_change_max, net_profit_min, net_profit_max, last_parent_net, summary, change_reason

**业绩快报 (express)**
- 核心: revenue, operate_profit, total_profit, n_income, total_assets, diluted_eps, diluted_roe, bps
- 同比: yoy_sales, yoy_op, yoy_tp, yoy_dedu_np, yoy_eps, yoy_roe

### report_type 说明（三大报表通用）
| 代码 | 类型 | 说明 |
|:---:|:---|:---|
| 1 | 合并报表 | 默认，上市公司最新报表 |
| 2 | 单季合并 | 单一季度的合并报表 |
| 4 | 调整合并报表 | 本年度公布上年同期数据 |
| 6 | 母公司报表 | 母公司财务报表 |

## Risks & Mitigations

| 风险 | 缓解措施 |
|------|----------|
| Tushare 积分限制（需 2000 积分） | 按单只股票获取，实现增量更新 |
| 字段数量多（balancesheet ~120 字段） | schema.json 完整定义，按需选择核心字段 |
| API 调用频率限制 | 复用现有 rate limiting 机制（120次/分） |
| 数据量大 | 实现合理的分页和批量处理 |
| 批处理模式性能问题 | 批处理模式下遍历所有股票（16410只），API 调用次数多，需要较长时间完成 |

## Open Questions

无

## References

- Tushare 财务数据概览: https://tushare.pro/document/2?doc_id=16
- Tushare 利润表文档: https://tushare.pro/document/2?doc_id=33
- Tushare 资产负债表文档: https://tushare.pro/document/2?doc_id=36
- Tushare 现金流量表文档: https://tushare.pro/document/2?doc_id=44
- Tushare 业绩预告文档: https://tushare.pro/document/2?doc_id=45
- Tushare 业绩快报文档: https://tushare.pro/document/2?doc_id=46
- 现有插件参考: `tushare_finace_indicator`, `tushare_report_rc`
- 规范: `financial-report-analysis`
