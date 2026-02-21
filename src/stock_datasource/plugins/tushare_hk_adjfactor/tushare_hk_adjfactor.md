# TuShare 港股复权因子插件 (tushare_hk_adjfactor)

## 概述
- **接口名称**: `hk_adjfactor`
- **数据来源**: TuShare Pro
- **数据限制**: 单次最大 6000 条
- **权限要求**: 开通港股日线权限后自动获取

## 功能描述
获取港股每日复权因子数据，每天滚动刷新。

## 数据字段

| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | String | 股票代码 |
| trade_date | Date | 交易日期 |
| cum_adjfactor | Float64 | 累计复权因子 |
| close_price | Float64 | 收盘价 |

## 复权计算
```
前复权价格 = 原始价格 × cum_adjfactor
```

## 使用示例

### Python
```python
from stock_datasource.plugins.tushare_hk_adjfactor import TuShareHKAdjFactorPlugin, TuShareHKAdjFactorService

# 运行 ETL
plugin = TuShareHKAdjFactorPlugin()
result = plugin.run(trade_date='20250110')

# 查询服务
service = TuShareHKAdjFactorService()
# 获取单只股票最新复权因子
latest = service.get_latest('00001.HK')
# 获取日期范围复权因子
factors = service.get_by_ts_code('00001.HK', '20250101', '20250110')
# 计算复权价格
adj_price = service.calculate_adjusted_price('00001.HK', '20250110', 40.0)
# 获取复权因子变动记录
changes = service.get_adj_factor_change('00001.HK', '20240101', '20250110')
```

### 命令行
```bash
# 获取指定日期全市场数据
python -m stock_datasource.plugins.tushare_hk_adjfactor.plugin --date 20250110

# 获取单只股票日期范围数据
python -m stock_datasource.plugins.tushare_hk_adjfactor.plugin --ts_code 00001.HK --start_date 20250101 --end_date 20250110
```

### HTTP API
```bash
# 获取最新复权因子
curl "http://localhost:8000/api/tushare_hk_adjfactor/get_latest?ts_code=00001.HK"

# 获取指定日期全市场
curl "http://localhost:8000/api/tushare_hk_adjfactor/get_by_date?trade_date=20250110"
```

## 依赖
- `tushare_hk_basic`: 港股列表

## 表结构
```sql
CREATE TABLE ods_hk_adjfactor (
    ts_code LowCardinality(String),
    trade_date Date,
    cum_adjfactor Nullable(Float64),
    close_price Nullable(Float64),
    version UInt32 DEFAULT toUInt32(toUnixTimestamp(now())),
    _ingested_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(trade_date)
ORDER BY (ts_code, trade_date)
```
