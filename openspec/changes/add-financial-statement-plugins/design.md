# Design: add-financial-statement-plugins

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Tushare API                               │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   income()      │  balancesheet() │      cashflow()              │
└────────┬────────┴────────┬────────┴────────────┬────────────────┘
         │                 │                     │
         ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Plugin Layer                                 │
├─────────────────┬─────────────────┬─────────────────────────────┤
│ tushare_income  │tushare_balance- │    tushare_cashflow          │
│                 │     sheet       │                              │
└────────┬────────┴────────┬────────┴────────────┬────────────────┘
         │                 │                     │
         ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ClickHouse Database                          │
├─────────────────┬─────────────────┬─────────────────────────────┤
│ods_income_stmt  │ods_balance_sheet│    ods_cash_flow             │
└────────┬────────┴────────┬────────┴────────────┬────────────────┘
         │                 │                     │
         └─────────────────┼─────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              FinancialStatementService                           │
│  (统一查询服务，整合三张报表数据)                                   │
└────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  ReportAgent  │   │   REST API    │   │  MCP Tools    │
└───────────────┘   └───────────────┘   └───────────────┘
```

## Plugin Implementation

### 1. 利润表插件 (tushare_income)

**config.json**:
```json
{
  "enabled": true,
  "rate_limit": 120,
  "timeout": 30,
  "retry_attempts": 3,
  "description": "TuShare income statement data plugin",
  "schedule": {
    "frequency": "quarterly",
    "time": "19:00"
  },
  "parameters_schema": {
    "ts_code": {
      "type": "string",
      "required": true,
      "description": "Stock code (e.g., 600000.SH)"
    },
    "start_date": {
      "type": "string",
      "format": "date",
      "required": false
    },
    "end_date": {
      "type": "string",
      "format": "date",
      "required": false
    },
    "period": {
      "type": "string",
      "required": false,
      "description": "Report period (e.g., 20231231)"
    },
    "report_type": {
      "type": "string",
      "required": false,
      "description": "Report type: 1=合并报表, 2=单季合并, etc."
    }
  }
}
```

**Key Output Fields**:
| 字段 | 类型 | 描述 |
|------|------|------|
| ts_code | str | 股票代码 |
| ann_date | str | 公告日期 |
| end_date | str | 报告期 |
| report_type | str | 报告类型 |
| basic_eps | float | 基本每股收益 |
| total_revenue | float | 营业总收入 |
| revenue | float | 营业收入 |
| operate_profit | float | 营业利润 |
| total_profit | float | 利润总额 |
| n_income | float | 净利润 |
| n_income_attr_p | float | 归母净利润 |

### 2. 资产负债表插件 (tushare_balancesheet)

**Key Output Fields**:
| 字段 | 类型 | 描述 |
|------|------|------|
| ts_code | str | 股票代码 |
| end_date | str | 报告期 |
| total_assets | float | 总资产 |
| total_liab | float | 总负债 |
| total_hldr_eqy_inc_min_int | float | 股东权益合计 |
| total_cur_assets | float | 流动资产合计 |
| total_cur_liab | float | 流动负债合计 |
| money_cap | float | 货币资金 |
| notes_receiv | float | 应收票据 |
| accounts_receiv | float | 应收账款 |
| inventories | float | 存货 |

### 3. 现金流量表插件 (tushare_cashflow)

**Key Output Fields**:
| 字段 | 类型 | 描述 |
|------|------|------|
| ts_code | str | 股票代码 |
| end_date | str | 报告期 |
| n_cashflow_act | float | 经营活动现金流净额 |
| n_cashflow_inv_act | float | 投资活动现金流净额 |
| n_cash_flows_fnc_act | float | 筹资活动现金流净额 |
| c_fr_sale_sg | float | 销售商品/服务收到的现金 |
| c_pay_acq_const_fiolta | float | 购建固定资产支付的现金 |
| free_cashflow | float | 自由现金流 |

## Service Layer Design

### FinancialStatementService

提供统一的财务报表查询和分析服务：

```python
class FinancialStatementService:
    """统一的财务报表查询服务"""
    
    def get_income_statement(self, code: str, periods: int = 8) -> List[Dict]:
        """获取利润表数据"""
        
    def get_balance_sheet(self, code: str, periods: int = 8) -> List[Dict]:
        """获取资产负债表数据"""
        
    def get_cashflow(self, code: str, periods: int = 8) -> List[Dict]:
        """获取现金流量表数据"""
        
    def get_all_statements(self, code: str, periods: int = 4) -> Dict:
        """获取全部三张报表数据"""
        
    def calculate_derived_metrics(self, code: str, period: str) -> Dict:
        """计算衍生指标（如自由现金流、营运资本等）"""
```

## Data Flow

1. **数据抽取**: Extractor 调用 Tushare API 按股票代码获取数据
2. **数据存储**: Plugin 将数据写入 ClickHouse 对应表
3. **数据查询**: Service 提供参数化查询，支持时间范围和报告类型过滤
4. **数据整合**: 支持跨表关联查询，计算衍生指标

## Report Type Mapping

| 代码 | 类型 | 说明 |
|------|------|------|
| 1 | 合并报表 | 上市公司最新报表（默认） |
| 2 | 单季合并 | 单一季度的合并报表 |
| 3 | 调整单季合并表 | 调整后的单季合并报表 |
| 4 | 调整合并报表 | 本年度公布上年同期数据 |
| 5 | 调整前合并报表 | 数据变更前的原数据 |
| 6 | 母公司报表 | 母公司财务报表数据 |

## Integration Points

### 与现有 ReportAgent 集成
```python
# 新增工具
@tool
def get_income_statement(code: str, periods: int = 4) -> Dict:
    """获取利润表数据"""
    
@tool
def get_balance_sheet(code: str, periods: int = 4) -> Dict:
    """获取资产负债表数据"""
    
@tool
def get_cashflow(code: str, periods: int = 4) -> Dict:
    """获取现金流量表数据"""
```

### 与 FinancialReportService 集成
现有的 `FinancialReportService` 将使用新插件的 Service 获取原始报表数据，结合财务指标数据提供完整的财务分析。

## 新增插件设计

### 4. 财务审计意见插件 (tushare_fina_audit)

**接口说明**:
- API: `pro.fina_audit()`
- 积分要求: 500 积分
- 文档: https://tushare.pro/document/2?doc_id=103

**config.json**:
```json
{
  "enabled": true,
  "rate_limit": 120,
  "timeout": 30,
  "retry_attempts": 3,
  "description": "TuShare financial audit opinion data plugin",
  "schedule": {
    "frequency": "quarterly",
    "time": "19:00"
  },
  "parameters_schema": {
    "ts_code": {
      "type": "string",
      "required": true,
      "description": "Stock code (e.g., 600000.SH)"
    },
    "start_date": {
      "type": "string",
      "format": "date",
      "required": false
    },
    "end_date": {
      "type": "string",
      "format": "date",
      "required": false
    },
    "period": {
      "type": "string",
      "required": false,
      "description": "Report period (e.g., 20231231)"
    }
  }
}
```

**Key Output Fields**:
| 字段 | 类型 | 描述 |
|------|------|------|
| ts_code | str | 股票代码 |
| ann_date | str | 公告日期 |
| end_date | str | 报告期 |
| audit_result | str | 审计结果（标准无保留意见/保留意见/否定意见等） |
| audit_fees | float | 审计费用（元） |
| audit_agency | str | 会计师事务所 |
| audit_sign | str | 签字会计师 |

**应用场景**:
- 识别审计风险：非标准审计意见可能提示财务风险
- 监管研究：分析审计意见与退市风险警示的关联性
- 行业统计：统计不同会计师事务所的市场份额

### 5. VIP 批量接口插件

VIP 接口支持按季度批量获取全市场数据，效率更高，适合构建完整的财务数据库。

**共同特点**:
- 积分要求: 5000 积分
- 支持按 `period` 参数一次性获取全市场数据
- 与基础接口共用相同的表结构
- 数据可合并存储，无需单独建表

#### 5.1 利润表 VIP (tushare_income_vip)

**接口说明**:
- API: `pro.income_vip()`
- 文档: https://tushare.pro/document/2?doc_id=80
- 复用表: `ods_income_statement`

**批量获取示例**:
```python
# 获取 2023 年三季报全部上市公司利润表
df = pro.income_vip(period='20230930', report_type='1')
```

#### 5.2 资产负债表 VIP (tushare_balancesheet_vip)

**接口说明**:
- API: `pro.balancesheet_vip()`
- 文档: https://tushare.pro/document/2?doc_id=162
- 复用表: `ods_balance_sheet`

**批量获取示例**:
```python
# 获取 2023 年年报全部上市公司资产负债表
df = pro.balancesheet_vip(period='20231231', report_type='1')
```

#### 5.3 现金流量表 VIP (tushare_cashflow_vip)

**接口说明**:
- API: `pro.cashflow_vip()`
- 文档: https://tushare.pro/document/2?doc_id=81
- 复用表: `ods_cash_flow`

**批量获取示例**:
```python
# 获取 2023 年年报全部上市公司现金流量表
df = pro.cashflow_vip(period='20231231', report_type='1')
```

### VIP 接口 vs 基础接口对比

| 特性 | 基础接口 | VIP 接口 |
|------|----------|----------|
| 积分要求 | 2000 | 5000 |
| 查询方式 | 单只股票历史数据 | 按季度批量获取 |
| 效率 | 低（需遍历股票） | 高（单次请求） |
| 适用场景 | 单股分析、增量更新 | 全市场数据构建 |
| 表结构 | 独立表 | 复用基础接口表 |

### 架构扩展

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Tushare API                                     │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────────────┤
│  income()   │balancesheet()│  cashflow() │ fina_audit()│    VIP APIs         │
│             │             │             │             │ income_vip()        │
│             │             │             │             │ balancesheet_vip()  │
│             │             │             │             │ cashflow_vip()      │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴─────────┬───────────┘
       │             │             │             │                │
       ▼             ▼             ▼             ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Plugin Layer                                      │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────────────┤
│tushare_     │tushare_     │tushare_     │tushare_     │ tushare_income_vip  │
│  income     │balancesheet │  cashflow   │ fina_audit  │ tushare_balance_vip │
│             │             │             │             │ tushare_cashflow_vip│
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴─────────┬───────────┘
       │             │             │             │                │
       ▼             ▼             ▼             ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ClickHouse Database                                  │
├─────────────┬─────────────┬─────────────┬─────────────────────────────────────┤
│ods_income   │ods_balance  │ods_cash     │ods_fina_audit                       │
│  _statement │  _sheet     │  _flow      │                                     │
│ (基础+VIP)  │ (基础+VIP)  │ (基础+VIP)  │                                     │
└─────────────┴─────────────┴─────────────┴─────────────────────────────────────┘
```

## 利润表完整字段前端展示

### 背景

`ods_income_statement` 表包含约 95 个字段，但前端 `FinancialReportPanel.vue` 仅展示了极少一部分（revenue、net_profit、gross_margin、net_margin）。后端 `get_profitability_metrics` 查询了一部分字段但未完全透传。

### 改动范围

#### 1. 后端 income service (`tushare_income/service.py`)

`get_profitability_metrics` 新增查询字段：
- `oper_cost`（营业成本）、`income_tax`（所得税）、`biz_tax_surchg`（税金及附加）
- `minority_gain`（少数股东损益）、`invest_income`（投资收益）
- `non_oper_income`/`non_oper_exp`（营业外收支）
- `t_compr_income`（综合收益）、`fin_exp_int_exp`/`fin_exp_int_inc`（利息收支）
- `diluted_eps`（稀释每股收益）

新增计算衍生指标（占营收比例）：
- `sell_exp_ratio`（销售费用率）、`admin_exp_ratio`（管理费用率）
- `fin_exp_ratio`（财务费用率）、`rd_exp_ratio`（研发费用率）

添加 `_safe_float` 函数处理 ClickHouse NULL 值。

#### 2. 后端 router (`modules/report/router.py`)

`FinancialData` Pydantic model 新增 25+ 字段：

| 分类 | 新增字段 |
|------|----------|
| 利润结构 | `net_profit_attr_p`, `operate_profit`, `total_profit`, `operating_margin` |
| 每股/估值 | `basic_eps`, `diluted_eps`, `ebit`, `ebitda` |
| 成本费用 | `oper_cost`, `sell_exp`, `admin_exp`, `fin_exp`, `rd_exp`, `total_cogs` |
| 费用率 | `sell_exp_ratio`, `admin_exp_ratio`, `fin_exp_ratio`, `rd_exp_ratio` |
| 税务及其他 | `income_tax`, `biz_tax_surchg`, `minority_gain`, `invest_income`, `non_oper_income`, `non_oper_exp` |

`field_validator` 改为通配符 `'*'` 模式，统一处理所有 float 字段的 NULL 值解析。

#### 3. 前端 API 类型 (`api/report.ts`)

`FinancialData` TypeScript 接口同步新增所有字段定义。

#### 4. 前端 Vue 组件 (`FinancialReportPanel.vue`)

**概览卡片**：
- 新增「利润结构（最新期）」卡片：营业收入、营业成本、营业利润、利润总额、归母净利润、基本EPS、EBITDA
- 新增「费用分析（最新期）」卡片：四项费用（销售/管理/研发/财务）+ 费用率标签 + 所得税

**财务指标表格**：
- 从单一表格改为 4 个子 Tab（综合/利润结构/费用分析/其他指标），通过 `RadioGroup` 切换
- 各子 Tab 展示对应分类的字段

**趋势图表**：
- 新增「利润结构」图表：营业收入/营业利润/利润总额/净利润分组柱状图
- 新增「费用率分析」图表：销售/管理/研发/财务费用率堆叠柱状图

### FinancialAuditService

提供财务审计意见查询服务：

```python
class FinancialAuditService:
    """财务审计意见查询服务"""
    
    def get_audit_opinion(self, code: str, periods: int = 5) -> List[Dict]:
        """获取审计意见数据"""
        
    def get_non_standard_opinions(self, start_date: str, end_date: str) -> List[Dict]:
        """获取指定时间范围内的非标准审计意见"""
        
    def get_audit_by_agency(self, agency: str, year: str) -> List[Dict]:
        """按会计师事务所查询审计数据"""
```