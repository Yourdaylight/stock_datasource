# TuShare THS Index Plugin

## 概述

本插件用于获取同花顺板块指数元数据（指数列表），包括概念指数、行业指数、地域指数等。

## 数据来源

- **API**: `ths_index`
- **文档**: https://tushare.pro/document/2?doc_id=259
- **权限要求**: 6000积分
- **数据版权**: 同花顺

## 表结构

| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | String | 指数代码 |
| name | String | 指数名称 |
| count | Int32 | 成分股个数 |
| exchange | String | 交易所 (A/HK/US) |
| list_date | Date | 上市日期 |
| type | String | 指数类型 |

### 指数类型说明

| 代码 | 含义 |
|------|------|
| N | 概念指数 |
| I | 行业指数 |
| R | 地域指数 |
| S | 同花顺特色指数 |
| ST | 同花顺风格指数 |
| TH | 同花顺主题指数 |
| BB | 同花顺宽基指数 |

## 使用方式

### ETL 数据拉取

```bash
# 拉取全部指数数据
python -m stock_datasource.plugins.tushare_ths_index.plugin

# 按交易所筛选
python -m stock_datasource.plugins.tushare_ths_index.plugin --exchange A

# 按类型筛选
python -m stock_datasource.plugins.tushare_ths_index.plugin --type N
```

### Service 查询

```python
from stock_datasource.plugins.tushare_ths_index import TuShareTHSIndexService

service = TuShareTHSIndexService()

# 查询所有 A 股概念指数
indices = service.get_ths_index_list(exchange="A", index_type="N")

# 根据代码查询
index = service.get_ths_index_by_code("885001.TI")

# 按名称搜索
results = service.search_ths_index_by_name("新能源")

# 统计信息
stats = service.get_ths_index_stats()
```

### HTTP API

```bash
# 查询指数列表
curl -X POST "http://localhost:8000/api/tushare_ths_index/get_ths_index_list" \
  -H "Content-Type: application/json" \
  -d '{"exchange": "A", "index_type": "N", "limit": 100}'

# 按代码查询
curl -X POST "http://localhost:8000/api/tushare_ths_index/get_ths_index_by_code" \
  -H "Content-Type: application/json" \
  -d '{"ts_code": "885001.TI"}'

# 按名称搜索
curl -X POST "http://localhost:8000/api/tushare_ths_index/search_ths_index_by_name" \
  -H "Content-Type: application/json" \
  -d '{"keyword": "新能源", "limit": 50}'
```

## 更新频率

建议每周更新一次，因为指数元数据变化较少。
