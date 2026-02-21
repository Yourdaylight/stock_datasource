# Design: Add HK Financial Plugins

## Overview

本文档详细描述港股财务数据插件的数据库设计、复用分析和实现架构。

## Database Schema Design

### 1. 港股财务指标表（宽表）

**表名**: `ods_hk_fina_indicator`

**设计思路**：
- 与 A 股 `ods_fina_indicator` 类似的宽表结构
- 包含 60+ 个固定字段，覆盖每股指标、盈利能力、营运能力、估值等维度
- 支持直接 SQL 查询，无需 PIVOT

**Schema 定义**:

```json
{
  "table_name": "ods_hk_fina_indicator",
  "table_type": "ods",
  "columns": [
    // === 基础信息 ===
    {"name": "ts_code", "data_type": "LowCardinality(String)", "nullable": false, "comment": "港股代码"},
    {"name": "name", "data_type": "String", "nullable": true, "comment": "股票名称"},
    {"name": "end_date", "data_type": "Date", "nullable": false, "comment": "报告期"},
    {"name": "ann_date", "data_type": "Nullable(Date)", "nullable": true, "comment": "公告日期"},
    {"name": "report_type", "data_type": "LowCardinality(String)", "nullable": true, "comment": "报告期类型(Q1/Q2/Q3/Q4)"},
    {"name": "std_report_date", "data_type": "Nullable(Date)", "nullable": true, "comment": "标准报告期"},
    {"name": "report_date_sq", "data_type": "Nullable(Date)", "nullable": true, "comment": "季报日期"},
    {"name": "currency", "data_type": "LowCardinality(String)", "nullable": true, "comment": "币种"},
    {"name": "fiscal_year", "data_type": "Nullable(Date)", "nullable": true, "comment": "会计年度截止日"},
    
    // === 每股指标 ===
    {"name": "basic_eps", "data_type": "Nullable(Float64)", "nullable": true, "comment": "基本每股收益(元)"},
    {"name": "diluted_eps", "data_type": "Nullable(Float64)", "nullable": true, "comment": "稀释每股收益(元)"},
    {"name": "eps_ttm", "data_type": "Nullable(Float64)", "nullable": true, "comment": "TTM每股收益(元)"},
    {"name": "bps", "data_type": "Nullable(Float64)", "nullable": true, "comment": "每股净资产(元)"},
    {"name": "per_oi", "data_type": "Nullable(Float64)", "nullable": true, "comment": "每股营业收入(元)"},
    {"name": "per_netcash_operate", "data_type": "Nullable(Float64)", "nullable": true, "comment": "每股经营现金流(元)"},
    {"name": "dps_hkd", "data_type": "Nullable(Float64)", "nullable": true, "comment": "每股股息(港元)"},
    {"name": "dps_hkd_ly", "data_type": "Nullable(Float64)", "nullable": true, "comment": "上一年每股股息"},
    {"name": "per_shares", "data_type": "Nullable(Int32)", "nullable": true, "comment": "每手股数"},
    
    // === 盈利能力 ===
    {"name": "operate_income", "data_type": "Nullable(Float64)", "nullable": true, "comment": "营业总收入(元)"},
    {"name": "operate_income_yoy", "data_type": "Nullable(Float64)", "nullable": true, "comment": "营业总收入同比增长(%)"},
    {"name": "operate_income_qoq", "data_type": "Nullable(Float64)", "nullable": true, "comment": "营业总收入滚动环比增长(%)"},
    {"name": "gross_profit", "data_type": "Nullable(Float64)", "nullable": true, "comment": "毛利润(元)"},
    {"name": "gross_profit_yoy", "data_type": "Nullable(Float64)", "nullable": true, "comment": "毛利润同比增长(%)"},
    {"name": "gross_profit_ratio", "data_type": "Nullable(Float64)", "nullable": true, "comment": "毛利率(%)"},
    {"name": "holder_profit", "data_type": "Nullable(Float64)", "nullable": true, "comment": "归母净利润(元)"},
    {"name": "holder_profit_yoy", "data_type": "Nullable(Float64)", "nullable": true, "comment": "归母净利润同比增长(%)"},
    {"name": "net_profit_ratio", "data_type": "Nullable(Float64)", "nullable": true, "comment": "净利率(%)"},
    {"name": "roe_avg", "data_type": "Nullable(Float64)", "nullable": true, "comment": "平均净资产收益率(%)"},
    {"name": "roe_yearly", "data_type": "Nullable(Float64)", "nullable": true, "comment": "年化净资产收益率(%)"},
    {"name": "roa", "data_type": "Nullable(Float64)", "nullable": true, "comment": "总资产净利率(%)"},
    {"name": "roic_yearly", "data_type": "Nullable(Float64)", "nullable": true, "comment": "年化投资回报率(%)"},
    
    // === 营运能力与现金流 ===
    {"name": "ocf_sales", "data_type": "Nullable(Float64)", "nullable": true, "comment": "经营现金流/营业收入(%)"},
    {"name": "netcash_operate", "data_type": "Nullable(Float64)", "nullable": true, "comment": "经营活动现金流量净额"},
    {"name": "netcash_invest", "data_type": "Nullable(Float64)", "nullable": true, "comment": "投资活动现金流量净额"},
    {"name": "netcash_finance", "data_type": "Nullable(Float64)", "nullable": true, "comment": "融资活动现金流量净额"},
    {"name": "end_cash", "data_type": "Nullable(Float64)", "nullable": true, "comment": "期末现金及现金等价物"},
    {"name": "accounts_rece_tdays", "data_type": "Nullable(Float64)", "nullable": true, "comment": "应收账款周转率(次)"},
    {"name": "inventory_tdays", "data_type": "Nullable(Float64)", "nullable": true, "comment": "存货周转率(次)"},
    {"name": "current_assets_tdays", "data_type": "Nullable(Float64)", "nullable": true, "comment": "流动资产周转率(次)"},
    {"name": "total_assets_tdays", "data_type": "Nullable(Float64)", "nullable": true, "comment": "总资产周转率(次)"},
    
    // === 偿债能力与资本结构 ===
    {"name": "total_assets", "data_type": "Nullable(Float64)", "nullable": true, "comment": "资产总额"},
    {"name": "total_liabilities", "data_type": "Nullable(Float64)", "nullable": true, "comment": "负债总额"},
    {"name": "debt_asset_ratio", "data_type": "Nullable(Float64)", "nullable": true, "comment": "资产负债率(%)"},
    {"name": "current_ratio", "data_type": "Nullable(Float64)", "nullable": true, "comment": "流动比率(倍)"},
    {"name": "equity_multiplier", "data_type": "Nullable(Float64)", "nullable": true, "comment": "权益乘数"},
    {"name": "equity_ratio", "data_type": "Nullable(Float64)", "nullable": true, "comment": "产权比率"},
    
    // === 估值指标 ===
    {"name": "pe_ttm", "data_type": "Nullable(Float64)", "nullable": true, "comment": "滚动市盈率"},
    {"name": "pb_ttm", "data_type": "Nullable(Float64)", "nullable": true, "comment": "滚动市净率"},
    {"name": "total_market_cap", "data_type": "Nullable(Float64)", "nullable": true, "comment": "总市值"},
    {"name": "hksk_market_cap", "data_type": "Nullable(Float64)", "nullable": true, "comment": "港股市值"},
    
    // === 金融/保险行业特有指标 ===
    {"name": "premium_income", "data_type": "Nullable(Float64)", "nullable": true, "comment": "保费收入"},
    {"name": "net_interest_income", "data_type": "Nullable(Float64)", "nullable": true, "comment": "净利息收入"},
    {"name": "fee_commission_income", "data_type": "Nullable(Float64)", "nullable": true, "comment": "手续费及佣金收入"},
    {"name": "loan_deposit", "data_type": "Nullable(Float64)", "nullable": true, "comment": "贷款/存款"},
    {"name": "deposit_assets", "data_type": "Nullable(Float64)", "nullable": true, "comment": "存款/总资产"},
    
    // === 系统字段 ===
    {"name": "version", "data_type": "UInt32", "nullable": false, "default": "toUInt32(toUnixTimestamp(now()))", "comment": "版本号用于幂等"},
    {"name": "_ingested_at", "data_type": "DateTime", "nullable": false, "default": "now()", "comment": "数据入库时间"}
  ],
  "partition_by": "toYear(end_date)",
  "order_by": ["ts_code", "end_date", "report_type"],
  "engine": "ReplacingMergeTree",
  "engine_params": ["version"],
  "comment": "HK Financial indicators data from TuShare API"
}
```

### 2. 港股财务报表表（纵表）

**表名**: `ods_hk_balancesheet`, `ods_hk_income`, `ods_hk_cashflow`

**设计思路**：
- 采用纵表结构，每行存储一个财务科目
- 支持动态财务科目，无需预定义所有字段
- 需要 PIVOT 查询或条件聚合来获取宽表视图

**统一 Schema 定义**:

```json
{
  "table_name": "ods_hk_balancesheet",
  "table_type": "ods",
  "columns": [
    {"name": "ts_code", "data_type": "LowCardinality(String)", "nullable": false, "comment": "港股代码"},
    {"name": "name", "data_type": "String", "nullable": true, "comment": "股票名称"},
    {"name": "end_date", "data_type": "Date", "nullable": false, "comment": "报告期"},
    {"name": "ind_name", "data_type": "String", "nullable": false, "comment": "财务科目名称"},
    {"name": "ind_value", "data_type": "Nullable(Float64)", "nullable": true, "comment": "财务科目值"},
    {"name": "version", "data_type": "UInt32", "nullable": false, "default": "toUInt32(toUnixTimestamp(now()))", "comment": "版本号用于幂等"},
    {"name": "_ingested_at", "data_type": "DateTime", "nullable": false, "default": "now()", "comment": "数据入库时间"}
  ],
  "partition_by": "toYear(end_date)",
  "order_by": ["ts_code", "end_date", "ind_name"],
  "engine": "ReplacingMergeTree",
  "engine_params": ["version"],
  "comment": "HK Balance sheet data from TuShare API (EAV model)"
}
```

**ClickHouse DDL 示例**:

```sql
-- 港股资产负债表（纵表结构）
CREATE TABLE IF NOT EXISTS ods_hk_balancesheet (
    ts_code LowCardinality(String) COMMENT '港股代码',
    name String COMMENT '股票名称',
    end_date Date COMMENT '报告期',
    ind_name String COMMENT '财务科目名称',
    ind_value Nullable(Float64) COMMENT '财务科目值',
    version UInt32 DEFAULT toUInt32(toUnixTimestamp(now())) COMMENT '版本号用于幂等',
    _ingested_at DateTime DEFAULT now() COMMENT '数据入库时间'
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYear(end_date)
ORDER BY (ts_code, end_date, ind_name)
COMMENT 'HK Balance sheet data from TuShare API (EAV model)';

-- 港股利润表（纵表结构）
CREATE TABLE IF NOT EXISTS ods_hk_income (
    ts_code LowCardinality(String) COMMENT '港股代码',
    name String COMMENT '股票名称',
    end_date Date COMMENT '报告期',
    ind_name String COMMENT '财务科目名称',
    ind_value Nullable(Float64) COMMENT '财务科目值',
    version UInt32 DEFAULT toUInt32(toUnixTimestamp(now())) COMMENT '版本号用于幂等',
    _ingested_at DateTime DEFAULT now() COMMENT '数据入库时间'
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYear(end_date)
ORDER BY (ts_code, end_date, ind_name)
COMMENT 'HK Income statement data from TuShare API (EAV model)';

-- 港股现金流量表（纵表结构）
CREATE TABLE IF NOT EXISTS ods_hk_cashflow (
    ts_code LowCardinality(String) COMMENT '港股代码',
    name String COMMENT '股票名称',
    end_date Date COMMENT '报告期',
    ind_name String COMMENT '财务科目名称',
    ind_value Nullable(Float64) COMMENT '财务科目值',
    version UInt32 DEFAULT toUInt32(toUnixTimestamp(now())) COMMENT '版本号用于幂等',
    _ingested_at DateTime DEFAULT now() COMMENT '数据入库时间'
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYear(end_date)
ORDER BY (ts_code, end_date, ind_name)
COMMENT 'HK Cash flow statement data from TuShare API (EAV model)';
```

---

## Reusability Analysis

### 与 A 股财务指标的字段映射

| 港股字段 (hk_fina_indicator) | A 股字段 (fina_indicator) | 可复用 |
|------------------------------|---------------------------|--------|
| ts_code | ts_code | ✅ 类型一致 |
| end_date | end_date | ✅ 类型一致 |
| basic_eps | eps | ✅ 含义相同 |
| bps | bps | ✅ 含义相同 |
| roe_avg | roe | ✅ 含义相似 |
| roa | roa | ✅ 含义相同 |
| gross_profit_ratio | gross_profit_margin | ✅ 含义相同 |
| net_profit_ratio | net_profit_margin | ✅ 含义相同 |
| current_ratio | current_ratio | ✅ 含义相同 |
| debt_asset_ratio | debt_to_assets | ✅ 含义相同 |
| total_assets | total_assets | ✅ 含义相同 |
| total_liabilities | total_liab | ✅ 含义相同 |
| operate_income | total_revenue | ⚠️ 名称不同，含义相似 |
| holder_profit | net_profit | ⚠️ 港股特指归母利润 |
| pe_ttm | - | ❌ A 股无此字段 |
| pb_ttm | - | ❌ A 股无此字段 |

### 代码复用清单

| 组件 | 复用方式 | 说明 |
|------|---------|------|
| `BasePlugin` | 直接继承 | 插件基类，提供标准生命周期 |
| `BaseService` | 直接继承 | 服务基类，提供查询框架 |
| `schema_manager.py` | 直接使用 | Schema 解析和表创建工具 |
| `TushareExtractor` | 参考实现 | 需要新建适配港股接口 |
| `config.json` 模板 | 参考修改 | 调整调度和限频参数 |
| 前端 FinancialTable | 需要适配 | 纵表数据需要转换为宽表展示 |

---

## 纵表与横表对比

**横表（宽表）优点**：
- 查询简单，分析 SQL 直观
- 前端/报表消费成本低
- 更易做多指标对比

**横表（宽表）缺点**：
- 指标变化需 `ALTER TABLE`，维护成本高
- 不同市场科目差异导致字段冗余或缺失
- 结构固定，不利于增量扩展

**纵表（EAV）优点**：
- 指标扩展友好，新增科目无需改表
- 贴合港股接口原始结构，避免映射损失
- 适配跨市场/跨行业差异

**纵表（EAV）缺点**：
- 查询复杂，需要 PIVOT/条件聚合
- 依赖排序键与物化视图优化性能
- 前端展示需要转换逻辑

**本方案选择纵表的理由**：
- TuShare 港股三大报表以 `ind_name + ind_value` 纵表返回，直接入库最稳妥。
- 港股科目差异和变动频率高，纵表能保持可扩展性。
- 保持 A 股宽表不变，隔离改造风险。
- 后续可通过物化视图生成关键指标宽表，兼顾查询效率与灵活性。

## Query Patterns for Vertical Tables

### 问题：纵表如何高效查询？

纵表（EAV 模型）需要特殊的查询技巧来获取类似宽表的结果。

### 方案 1：条件聚合（推荐）

```sql
-- 查询某只港股的资产负债表关键指标
SELECT 
    ts_code,
    end_date,
    maxIf(ind_value, ind_name = '资产总额') AS total_assets,
    maxIf(ind_value, ind_name = '负债总额') AS total_liabilities,
    maxIf(ind_value, ind_name = '股东权益') AS shareholders_equity,
    maxIf(ind_value, ind_name = '应收帐款') AS accounts_receivable,
    maxIf(ind_value, ind_name = '存货') AS inventory
FROM ods_hk_balancesheet FINAL
WHERE ts_code = '00700.HK'
GROUP BY ts_code, end_date
ORDER BY end_date DESC
LIMIT 10;
```

### 方案 2：自连接

```sql
-- 使用自连接获取多个指标
SELECT 
    a.ts_code,
    a.end_date,
    a.ind_value AS total_assets,
    b.ind_value AS total_liabilities
FROM ods_hk_balancesheet a
JOIN ods_hk_balancesheet b 
    ON a.ts_code = b.ts_code AND a.end_date = b.end_date
WHERE a.ind_name = '资产总额' 
    AND b.ind_name = '负债总额'
    AND a.ts_code = '00700.HK';
```

### 方案 3：预聚合物化视图

```sql
-- 创建常用指标的物化视图（宽表）
CREATE MATERIALIZED VIEW mv_hk_balance_key_indicators
ENGINE = ReplacingMergeTree()
ORDER BY (ts_code, end_date)
AS SELECT
    ts_code,
    end_date,
    maxIf(ind_value, ind_name = '资产总额') AS total_assets,
    maxIf(ind_value, ind_name = '负债总额') AS total_liabilities,
    maxIf(ind_value, ind_name = '股东权益') AS shareholders_equity,
    maxIf(ind_value, ind_name = '流动资产') AS current_assets,
    maxIf(ind_value, ind_name = '流动负债') AS current_liabilities
FROM ods_hk_balancesheet
GROUP BY ts_code, end_date;
```

---

## Plugin Architecture

### 目录结构

```
src/stock_datasource/plugins/
├── tushare_hk_fina_indicator/
│   ├── __init__.py
│   ├── config.json
│   ├── schema.json
│   ├── extractor.py
│   ├── plugin.py
│   └── service.py
├── tushare_hk_balancesheet/
│   ├── __init__.py
│   ├── config.json
│   ├── schema.json
│   ├── extractor.py
│   ├── plugin.py
│   └── service.py
├── tushare_hk_income/
│   └── ... (同上)
└── tushare_hk_cashflow/
    └── ... (同上)
```

### 插件实现要点

1. **Extractor**: 调用 TuShare Pro API，处理分页和限频
2. **Plugin**: 继承 BasePlugin，实现 extract/transform/load 方法
3. **Service**: 提供纵表查询适配，支持 PIVOT 转换

### 配置示例 (config.json)

```json
{
  "enabled": true,
  "rate_limit": 120,
  "timeout": 30,
  "retry_attempts": 3,
  "description": "TuShare HK financial indicator data plugin",
  "schedule": {
    "frequency": "quarterly",
    "time": "20:00"
  },
  "parameters_schema": {
    "type": "object",
    "properties": {
      "ts_code": {"type": "string", "description": "港股代码"},
      "period": {"type": "string", "description": "报告期 YYYYMMDD"},
      "report_type": {"type": "string", "enum": ["Q1", "Q2", "Q3", "Q4"]},
      "start_date": {"type": "string"},
      "end_date": {"type": "string"}
    },
    "required": ["ts_code"]
  }
}
```

---

## Service Layer Integration

### 港股财务服务接口

```python
class HKFinancialService(BaseService):
    """港股财务数据查询服务"""
    
    async def get_fina_indicator(
        self, 
        ts_code: str, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        report_type: Optional[str] = None
    ) -> List[Dict]:
        """获取港股财务指标（宽表，直接查询）"""
        pass
    
    async def get_balancesheet(
        self,
        ts_code: str,
        period: Optional[str] = None,
        indicators: Optional[List[str]] = None
    ) -> List[Dict]:
        """获取港股资产负债表（纵表，支持 PIVOT）"""
        pass
    
    async def get_balancesheet_pivot(
        self,
        ts_code: str,
        period: Optional[str] = None,
        key_indicators: List[str] = None
    ) -> List[Dict]:
        """获取港股资产负债表（转为宽表格式）"""
        pass
```

---

## Data Flow

```
┌─────────────────┐
│  TuShare Pro    │
│  API Gateway    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Extractor     │  (API 调用, 分页, 限频)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Plugin        │  (数据转换, 校验)
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│              ClickHouse                      │
│  ┌───────────────┐  ┌───────────────────┐   │
│  │ ods_hk_fina_  │  │ ods_hk_balancesheet│   │
│  │ indicator     │  │ ods_hk_income      │   │
│  │ (宽表)        │  │ ods_hk_cashflow    │   │
│  └───────────────┘  │ (纵表)             │   │
│                     └───────────────────┘   │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  Service Layer  │  (查询适配, PIVOT)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  API / Agent    │
└─────────────────┘
```

---

## Testing Strategy

### 单元测试
- Extractor: Mock TuShare API 响应
- Plugin: 测试数据转换逻辑
- Service: 测试查询 SQL 生成

### 集成测试
- 端到端数据提取和存储
- 查询结果正确性验证

### 验证数据
- 使用已知股票（如 00700.HK 腾讯控股）验证数据准确性
- 对比 TuShare 官网数据

---

## Risk Mitigation

| 风险 | 缓解措施 |
|------|---------|
| API 积分不足 | 监控积分使用，优化查询频率 |
| 纵表查询性能 | 预聚合物化视图，缓存热点数据 |
| 财务科目变化 | 纵表结构天然支持新增科目 |
| 数据质量问题 | 添加数据校验规则，异常告警 |

---

## 港股三大报表前端展示

### 背景

后端已有完整的利润表(`/income`)、资产负债表(`/balance`)、现金流量表(`/cashflow`) API 接口，前端 API 层(`hk-report.ts`)也已封装好 `getIncome`、`getBalance`、`getCashflow` 调用方法，但 Vue 组件 `HKFinancialReportPanel.vue` 仅展示了财务指标(fina_indicator)数据，三大报表数据完全未使用。

### 改动范围

#### 1. 前端组件 `HKFinancialReportPanel.vue`

**数据加载扩展**：
- `handleSearch` 从原来的 2 个并发请求（financial + indicators）扩展为 5 个并发请求（+ income + balance + cashflow）
- 新增 `incomeData`、`balanceData`、`cashflowData` 三个响应式数据

**概览 Tab 新增卡片**：

| 卡片名称 | 数据来源 | 展示字段 |
|---------|----------|---------|
| 利润结构（最新期） | `incomeData[0]` | 营业收入、营业成本、毛利、营业利润、净利润、归母净利润 |
| 资产负债（最新期） | `balanceData[0]` | 资产总额、负债总额、股东权益、流动资产、流动负债 |
| 现金流量（最新期） | `cashflowData[0]` | 经营/投资/筹资活动现金流净额、期末现金及等价物 |

**新增「三大报表」Tab**：
- 包含 RadioGroup 子标签切换（利润表/资产负债表/现金流量表）
- 每张报表以指标为行、报告期为列的转置表格展示（`transformPivotToRows` 函数将 EAV pivot 数据转换为行列结构）
- 金额统一使用亿/万格式化（`formatAmount`）
- 负值标红

**趋势图表 Tab 新增 3 个图表**：

| 图表名称 | 图表类型 | 数据系列 |
|---------|---------|---------|
| 利润结构趋势 | 分组柱状图 | 营业收入、毛利、营业利润、净利润 |
| 资产负债结构趋势 | 分组柱状图 | 资产总额、负债总额、股东权益 |
| 现金流量趋势 | 分组柱状图 | 经营活动、投资活动、筹资活动 |

**财务指标表格扩展**：
- 新增 3 列：资产负债率(%)、流动比率、权益乘数

#### 2. 无后端/API 层变更
- `hk-report.ts` 已有 `getIncome`/`getBalance`/`getCashflow` 接口定义
- `router.py` 已有 `/income`、`/balance`、`/cashflow` 端点
- `hk_financial_report_service.py` 已有对应 service 方法
