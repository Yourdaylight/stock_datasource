> 来源：https://tushare.pro/document/2?doc_id=25

# 接口：daily_basic

**更新时间**  
交易日每日 15:00 ～ 17:00 之间。

**描述**  
获取全部股票每日重要的基本面指标，可用于选股分析、报表展示等。  
单次请求最大返回 6000 条数据，可按日线循环提取全部历史。

**积分**  
至少 2000 积分才可以调取，5000 积分无总量限制。  
具体请参阅积分获取办法。

---

## 输入参数

| 名称 | 类型 | 必选 | 描述 |
|------|------|------|------|
| ts_code | str | Y | 股票代码（二选一） |
| trade_date | str | N | 交易日期（二选一） |
| start_date | str | N | 开始日期 (YYYYMMDD) |
| end_date | str | N | 结束日期 (YYYYMMDD) |

> 注：日期格式统一为 `YYYYMMDD`，例如：`20181010`。

---

## 输出参数

| 名称 | 类型 | 描述 |
|------|------|------|
| ts_code | str | TS股票代码 |
| trade_date | str | 交易日期 |
| close | float | 当日收盘价 |
| turnover_rate | float | 换手率（%） |
| turnover_rate_f | float | 换手率（自由流通股） |
| volume_ratio | float | 量比 |
| pe | float | 市盈率（总市值/净利润，亏损的PE为空） |
| pe_ttm | float | 市盈率（TTM，亏损的PE为空） |
| pb | float | 市净率（总市值/净资产） |
| ps | float | 市销率 |
| ps_ttm | float | 市销率（TTM） |
| dv_ratio | float | 股息率（%） |
| dv_ttm | float | 股息率（TTM）（%） |
| total_share | float | 总股本（万股） |
| float_share | float | 流通股本（万股） |
| free_share | float | 自由流通股本（万股） |
| total_mv | float | 总市值（万元） |
| circ_mv | float | 流通市值（万元） |

---

## 接口示例

```python
import tushare as ts

pro = ts.pro_api()

# 获取每日基本面指标
df = pro.daily_basic(
    ts_code='',
    trade_date='20180726',
    fields='ts_code,trade_date,turnover_rate,volume_ratio,pe,pb'
)
```

或：

```python
df = pro.query(
    'daily_basic',
    ts_code='',
    trade_date='20180726',
    fields='ts_code,trade_date,turnover_rate,volume_ratio,pe,pb'
)
```

---

## 数据样例

| ts_code | trade_date | turnover_rate | volume_ratio | pe | pb |
|----------|-------------|----------------|---------------|-----------|-----------|
| 600230.SH | 20180726 | 2.4584 | 0.72 | 8.6928 | 3.7203 |
| 600237.SH | 20180726 | 1.4737 | 0.88 | 166.4001 | 1.8868 |
| 002465.SZ | 20180726 | 0.7489 | 0.72 | 71.8943 | 2.6391 |
| 300732.SZ | 20180726 | 6.7083 | 0.77 | 21.8101 | 3.2513 |
| 600007.SH | 20180726 | 0.0381 | 0.61 | 23.7696 | 2.3774 |
| 300068.SZ | 20180726 | 1.4583 | 0.52 | 27.8166 | 1.7549 |

---

备注：本文档内容整理自 Tushare 官方接口文档，仅供参考使用。
