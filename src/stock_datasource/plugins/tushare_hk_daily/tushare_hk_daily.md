# TuShare HK Daily Plugin

## 概述
该插件用于从 TuShare 获取港股日线行情数据（hk_daily 接口）。

## API 信息
- **接口名称**: hk_daily
- **文档链接**: https://tushare.pro/document/2?doc_id=192
- **更新时间**: 每日 18:00 左右更新当日数据
- **权限限制**: 单次最大提取 5000 行记录

## 输入参数
| 参数名 | 类型 | 必选 | 说明 |
|--------|------|------|------|
| ts_code | str | N | 股票代码（如 00001.HK） |
| trade_date | str | N | 交易日期（如 20250110） |
| start_date | str | N | 开始日期（如 20250101） |
| end_date | str | N | 结束日期（如 20250110） |

## 输出字段
| 字段名 | 类型 | 说明 |
|--------|------|------|
| ts_code | str | 股票代码 |
| trade_date | str | 交易日期 |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价 |
| pre_close | float | 昨收价 |
| change | float | 涨跌额 |
| pct_chg | float | 涨跌幅(%) |
| vol | float | 成交量(股) |
| amount | float | 成交额(元) |

## 使用示例

### 命令行运行
```bash
# 获取某一日所有港股行情
python -m stock_datasource.plugins.tushare_hk_daily.plugin --date 20250110

# 获取指定股票的日期范围数据
python -m stock_datasource.plugins.tushare_hk_daily.plugin --ts_code 00001.HK --start_date 20250101 --end_date 20250110
```

### Service 查询方法
```python
from stock_datasource.plugins.tushare_hk_daily import TuShareHKDailyService

service = TuShareHKDailyService()

# 按日期查询
data = service.get_by_trade_date(trade_date='20250110')

# 按股票代码和日期范围查询
data = service.get_by_date_range(ts_code='00001.HK', start_date='20250101', end_date='20250110')

# 获取最新数据
data = service.get_latest(ts_codes=['00001.HK', '00700.HK'])

# 获取涨跌幅排行
data = service.get_top_movers(trade_date='20250110', top_n=10)
```

## HTTP API 调用
```bash
# 按交易日期查询
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"service": "tushare_hk_daily", "method": "get_by_trade_date", "params": {"trade_date": "20250110"}}'

# 按日期范围查询
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"service": "tushare_hk_daily", "method": "get_by_date_range", "params": {"ts_code": "00001.HK", "start_date": "20250101", "end_date": "20250110"}}'
```
