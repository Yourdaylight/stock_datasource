# TuShare HK Basic Plugin

## 概述
该插件用于从 TuShare 获取港股列表基础信息（hk_basic 接口）。

## API 信息
- **接口名称**: hk_basic
- **文档链接**: https://tushare.pro/document/2?doc_id=191
- **权限要求**: 2000 积分
- **数据范围**: 单次可提取全部在交易的港股列表数据

## 输入参数
| 参数名 | 类型 | 必选 | 说明 |
|--------|------|------|------|
| ts_code | str | N | TS代码（如 00001.HK） |
| list_status | str | N | 上市状态：L上市(默认)/D退市/P暂停上市 |

## 输出字段
| 字段名 | 类型 | 说明 |
|--------|------|------|
| ts_code | str | TS代码 |
| name | str | 股票简称 |
| fullname | str | 公司全称 |
| enname | str | 英文名称 |
| cn_spell | str | 拼音 |
| market | str | 市场类别 |
| list_status | str | 上市状态 |
| list_date | str | 上市日期 |
| delist_date | str | 退市日期 |
| trade_unit | float | 交易单位 |
| isin | str | ISIN代码 |
| curr_type | str | 货币代码 |

## 使用示例

### 命令行运行
```bash
# 获取所有上市港股
python -m stock_datasource.plugins.tushare_hk_basic.plugin

# 获取指定股票信息
python -m stock_datasource.plugins.tushare_hk_basic.plugin --ts-code 00001.HK

# 获取退市股票
python -m stock_datasource.plugins.tushare_hk_basic.plugin --list-status D

# 获取所有状态的股票（L+D+P）
python -m stock_datasource.plugins.tushare_hk_basic.plugin --all
```

### Service 查询方法
```python
from stock_datasource.plugins.tushare_hk_basic import TuShareHKBasicService

service = TuShareHKBasicService()

# 获取单只股票信息
info = service.get_by_ts_code('00001.HK')

# 获取上市股票列表
stocks = service.get_stock_list(list_status='L')

# 搜索股票
results = service.search('腾讯')

# 获取统计信息
stats = service.get_statistics()

# 获取最近上市股票
recent = service.get_recent_ipo(days=30)

# 获取所有股票代码
codes = service.get_all_ts_codes()
```

## HTTP API 调用
```bash
# 获取单只股票信息
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"service": "tushare_hk_basic", "method": "get_by_ts_code", "params": {"ts_code": "00001.HK"}}'

# 搜索股票
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"service": "tushare_hk_basic", "method": "search", "params": {"keyword": "腾讯"}}'

# 获取统计信息
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"service": "tushare_hk_basic", "method": "get_statistics", "params": {}}'
```
