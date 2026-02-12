# TuShare HK Trade Calendar Plugin

## 概述
该插件用于从 TuShare 获取港股交易日历数据（hk_tradecal 接口）。

## API 信息
- **接口名称**: hk_tradecal
- **文档链接**: https://tushare.pro/document/2?doc_id=250
- **数据限量**: 单次最大返回 2000 条记录
- **积分要求**: 2000 分

## 输入参数
| 参数名 | 类型 | 必选 | 说明 |
|--------|------|------|------|
| start_date | str | N | 开始日期（如 20200101） |
| end_date | str | N | 结束日期（如 20200708） |
| is_open | str | N | 是否交易：'0' 休市，'1' 交易 |

## 输出字段
| 字段名 | 类型 | 说明 |
|--------|------|------|
| cal_date | str | 日历日期 |
| is_open | int | 是否交易（0=休市，1=交易） |
| pretrade_date | str | 上一个交易日 |

## 使用示例

### 命令行运行
```bash
# 获取默认日期范围（前后2年）的港股交易日历
python -m stock_datasource.plugins.tushare_hk_tradecal.plugin

# 指定日期范围
python -m stock_datasource.plugins.tushare_hk_tradecal.plugin \
  --start-date 20200101 --end-date 20200708

# 只获取交易日
python -m stock_datasource.plugins.tushare_hk_tradecal.plugin \
  --start-date 20200101 --end-date 20200708 --is-open 1
```

### Service 查询方法
```python
from stock_datasource.plugins.tushare_hk_tradecal import TuShareHKTradeCalService

service = TuShareHKTradeCalService()

# 获取日期范围内的交易日历
data = service.get_trade_calendar(start_date='20200101', end_date='20200708')

# 只获取交易日
data = service.get_trading_days(start_date='20200101', end_date='20200708')

# 获取下一个交易日
next_day = service.get_next_trading_day(date='20200703')

# 获取上一个交易日
prev_day = service.get_prev_trading_day(date='20200706')

# 检查某日是否为交易日
is_open = service.is_trading_day(date='20200704')

# 统计交易日数量
count = service.count_trading_days(start_date='20200101', end_date='20200708')

# 获取 N 个交易日后的日期
offset_day = service.get_offset_trading_day(date='20200703', n=5)
```

## HTTP API 调用
```bash
# 获取交易日历
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"service": "tushare_hk_tradecal", "method": "get_trade_calendar", "params": {"start_date": "20200101", "end_date": "20200708"}}'

# 获取交易日
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"service": "tushare_hk_tradecal", "method": "get_trading_days", "params": {"start_date": "20200101", "end_date": "20200708"}}'

# 检查是否为交易日
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"service": "tushare_hk_tradecal", "method": "is_trading_day", "params": {"date": "20200704"}}'
```
