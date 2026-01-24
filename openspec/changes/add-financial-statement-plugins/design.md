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
└────────────────────────────┬────────────────────────────────────┘
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
