# TuShare 港股复权行情插件 (tushare_hk_daily_adj)

## 概述
- **接口名称**: `hk_daily_adj`
- **数据来源**: TuShare Pro
- **数据限制**: 单次最大 6000 条
- **权限要求**: 120 积分

## 功能描述
获取港股复权行情数据，包含：
- 基础行情（OHLC、成交量、成交额）
- 复权因子（adj_factor）
- 股本数据（流通股本、总股本）
- 市值数据（流通市值、总市值）
- 换手率（基于总股本）

## 复权计算
```
前复权收盘价 = close × adj_factor
```
**注意**: 复权因子的历史数据可能因除权等原因被刷新，使用时请注意动态更新。

## 数据字段

| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | String | 股票代码 |
| trade_date | Date | 交易日期 |
| open | Float64 | 开盘价 |
| high | Float64 | 最高价 |
| low | Float64 | 最低价 |
| close | Float64 | 收盘价 |
| pre_close | Float64 | 昨收价 |
| change | Float64 | 涨跌额 |
| pct_change | Float64 | 涨跌幅 |
| vol | Float64 | 成交量 |
| amount | Float64 | 成交额 |
| vwap | Float64 | 平均价 |
| adj_factor | Float64 | 复权因子 |
| turnover_ratio | Float64 | 换手率(%) |
| free_share | Float64 | 流通股本 |
| total_share | Float64 | 总股本 |
| free_mv | Float64 | 流通市值 |
| total_mv | Float64 | 总市值 |

## 使用示例

### Python
```python
# 导入插件
from stock_datasource.plugins.tushare_hk_daily_adj import TuShareHKDailyAdjPlugin, TuShareHKDailyAdjService

# 运行 ETL
plugin = TuShareHKDailyAdjPlugin()
result = plugin.run(trade_date='20250110')

# 查询服务
service = TuShareHKDailyAdjService()
# 获取单只股票最新数据
latest = service.get_latest('00001.HK')
# 获取复权收盘价
adj_prices = service.get_adj_close('00001.HK', '20250101', '20250110')
# 获取市值排名
top_mv = service.get_market_value('20250110', top_n=20)
# 获取高换手股票
high_turnover = service.get_high_turnover('20250110', min_turnover=5.0)
```

### 命令行
```bash
# 获取指定日期数据
python -m stock_datasource.plugins.tushare_hk_daily_adj.plugin --date 20250110

# 获取单只股票日期范围数据
python -m stock_datasource.plugins.tushare_hk_daily_adj.plugin --ts_code 00001.HK --start_date 20250101 --end_date 20250110
```

### HTTP API
```bash
# 获取最新数据
curl "http://localhost:8000/api/tushare_hk_daily_adj/get_latest?ts_code=00001.HK"

# 获取市值排名
curl "http://localhost:8000/api/tushare_hk_daily_adj/get_market_value?trade_date=20250110&top_n=20"
```

## 依赖
- `tushare_hk_basic`: 港股列表（用于获取股票代码）

## 表结构
```sql
CREATE TABLE ods_hk_daily_adj (
    ts_code LowCardinality(String),
    trade_date Date,
    open Nullable(Float64),
    high Nullable(Float64),
    low Nullable(Float64),
    close Nullable(Float64),
    pre_close Nullable(Float64),
    change Nullable(Float64),
    pct_change Nullable(Float64),
    vol Nullable(Float64),
    amount Nullable(Float64),
    vwap Nullable(Float64),
    adj_factor Nullable(Float64),
    turnover_ratio Nullable(Float64),
    free_share Nullable(Float64),
    total_share Nullable(Float64),
    free_mv Nullable(Float64),
    total_mv Nullable(Float64),
    version UInt32 DEFAULT toUInt32(toUnixTimestamp(now())),
    _ingested_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(trade_date)
ORDER BY (ts_code, trade_date)
```
