> 来源：https://tushare.pro/document/2?doc_id=79

# 接口：fina_indicator（A股财务指标数据）

**数据说明**  
获取上市公司财务指标数据，为避免服务器压力，现阶段每次请求最多返回100条记录，可通过设置日期多次请求获取更多数据。

**调取说明**  
需要至少 **2000积分** 才能调用，单次最多返回100条记录。  
如需获取某一季度全部上市公司的财务数据，请使用 `fina_indicator_vip` 接口（需5000积分）。

**权限要求**  
基础积分每分钟内可调取 500 次。

---

## 输入参数

| 名称 | 类型 | 必选 | 描述 |
|------|------|------|------|
| ts_code | str | Y | 股票代码，如 `600000.SH`（上证）或 `000001.SZ`（深证） |
| ann_date | str | N | 公告日期（格式：YYYYMMDD） |
| start_date | str | N | 报告期开始日期（格式：YYYYMMDD） |
| end_date | str | N | 报告期结束日期（格式：YYYYMMDD） |
| period | str | N | 报告期（格式：YYYYMMDD，例如 `20171231` 表示年报） |

> 注：若不指定日期参数，默认返回指定股票的全部历史财务指标。

---

## 输出参数

接口返回大量财务指标字段（完整列表近200项），以下为常用字段：

| 字段名 | 类型 | 描述 |
|--------|------|------|
| ts_code | str | TS股票代码 |
| ann_date | str | 公告日期 |
| end_date | str | 报告期 |
| eps | float | 基本每股收益 |
| dt_eps | float | 稀释每股收益 |
| roe | float | 净资产收益率 |
| roa | float | 总资产报酬率 |
| netprofit_margin | float | 销售净利率 |
| grossprofit_margin | float | 销售毛利率 |
| debt_to_assets | float | 资产负债率 |
| current_ratio | float | 流动比率 |
| quick_ratio | float | 速动比率 |
| ocfps | float | 每股经营活动现金流 |
| bps | float | 每股净资产 |
| or_yoy | float | 营业收入同比增长率 |
| q_roe | float | 单季度净资产收益率 |
| netprofit_yoy | float | 净利润同比增长率 |

> 注：完整输出字段请参考Tushare官方文档或通过API查询获取。

---

## 接口示例

```python
import tushare as ts

pro = ts.pro_api()

# 示例1：获取单只股票所有财务指标
df = pro.fina_indicator(ts_code='600000.SH')

# 示例2：指定时间范围
df = pro.fina_indicator(
    ts_code='000001.SZ',
    start_date='20200101',
    end_date='20201231'
)

# 示例3：使用query方式
df = pro.query(
    'fina_indicator',
    ts_code='600036.SH',
    period='20201231'
)

print(df.head())
```

---

## 数据样例

| ts_code   | ann_date  | end_date  | eps  | dt_eps | total_revenue_ps | revenue_ps | roe  | debt_to_assets |
|-----------|-----------|-----------|------|--------|------------------|------------|------|----------------|
| 600000.SH | 20210830  | 20210630  | 1.25 | 1.25   | 3.02            | 3.02       | 12.5 | 0.89           |
| 600000.SH | 20210428  | 20210331  | 0.60 | 0.60   | 1.45            | 1.45       | 6.2  | 0.88           |

> 注：实际返回字段数量较多，此处仅展示部分。

---

## 注意事项

- 每次请求最多返回 **100条记录**，如需更多数据请分时段多次调用
- 财务指标数据更新频率与财报披露同步（季报、半年报、年报）
- 若积分不足，请参考 [积分获取办法](https://tushare.pro/document/1?doc_id=13)

---

## 插件使用说明

### 插件参数
本插件支持以下参数：
- `ts_code` (可选): 股票代码，如 `002579.SZ`
- `start_date` (必需): 开始日期，格式 `YYYYMMDD`
- `end_date` (必需): 结束日期，格式 `YYYYMMDD`

### 存储表结构
数据存储在 `ods_fina_indicator` 表中，包含以下关键字段：
- 盈利能力指标: `roe`, `roa`, `gross_profit_margin`, `net_profit_margin`
- 每股指标: `eps`, `bps`
- 财务数据: `total_revenue`, `net_profit`, `total_assets`, `total_liab`
- 偿债能力: `current_ratio`, `quick_ratio`, `debt_to_assets`
- 运营效率: `asset_turnover`, `inventory_turnover`, `receivable_turnover`

### 查询服务
插件提供以下查询接口：
- `get_financial_indicators()` - 按股票代码和时间范围查询
- `get_latest_indicators()` - 获取最新财务指标
- `get_indicators_by_date()` - 按报告期查询所有股票
- `get_roe_trend()` - 获取 ROE 趋势数据

---

备注：本文档内容整理自 Tushare 官方接口文档，仅供参考使用。
