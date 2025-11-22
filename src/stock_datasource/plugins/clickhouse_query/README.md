# ClickHouse Query MCP Plugin

增强版ClickHouse查询MCP插件，提供表结构查看和股票数据条件过滤功能。

## 功能特性

### 1. 表结构查看工具
- `get_table_schema` - 查看表结构和字段信息
- `list_tables` - 列出所有可用表

### 2. 股票数据过滤工具
- `filter_daily_data` - 过滤ods_daily表（股票价格数据）
- `filter_daily_basic` - 过滤ods_daily_basic表（股票基本面数据）

### 3. 原始SQL查询
- `execute_raw_query` - 执行原始SQL查询

## 使用示例

### 查看表结构
```json
{
  "tool": "clickhouse_query_get_table_schema",
  "arguments": {
    "table": "ods_daily"
  }
}
```

### 列出所有表
```json
{
  "tool": "clickhouse_query_list_tables",
  "arguments": {}
}
```

### 过滤股票价格数据 (ods_daily)
```json
{
  "tool": "clickhouse_query_filter_daily_data",
  "arguments": {
    "trade_date": "20251118",
    "pct_chg_min": 5,
    "pct_chg_max": 10,
    "vol_min": 100000,
    "limit": 20,
    "order_by": "pct_chg DESC"
  }
}
```

### 过滤基本面数据 (ods_daily_basic)
```json
{
  "tool": "clickhouse_query_filter_daily_basic",
  "arguments": {
    "trade_date": "20251118",
    "pe_min": 0,
    "pe_max": 30,
    "pb_min": 0,
    "pb_max": 3,
    "dv_ratio_min": 3,
    "total_mv_min": 100000,
    "limit": 50,
    "order_by": "dv_ratio DESC"
  }
}
```

### 查询高股息率股票
```json
{
  "tool": "clickhouse_query_filter_daily_basic",
  "arguments": {
    "trade_date": "20251118",
    "dv_ratio_min": 5,
    "pe_min": 0,
    "pe_max": 50,
    "limit": 20,
    "order_by": "dv_ratio DESC"
  }
}
```

### 查询涨幅大于8%的股票
```json
{
  "tool": "clickhouse_query_filter_daily_data",
  "arguments": {
    "trade_date": "20251117",
    "pct_chg_min": 8,
    "limit": 50,
    "order_by": "pct_chg DESC"
  }
}
```

### 查询特定股票
```json
{
  "tool": "clickhouse_query_filter_daily_data",
  "arguments": {
    "ts_codes": ["000001.SZ", "000002.SZ", "600000.SH"],
    "trade_date": "20251118",
    "limit": 10
  }
}
```

## 参数说明

### filter_daily_data 参数
- `trade_date`: 交易日期 (YYYYMMDD格式)
- `ts_codes`: 股票代码列表
- `pct_chg_min/max`: 涨跌幅范围
- `close_min/max`: 收盘价范围
- `vol_min`: 最小成交量
- `amount_min`: 最小成交额
- `limit`: 返回行数限制
- `order_by`: 排序字段

### filter_daily_basic 参数
- `trade_date`: 交易日期 (YYYYMMDD格式)
- `ts_codes`: 股票代码列表
- `pe_min/max`: 市盈率范围
- `pb_min/max`: 市净率范围
- `dv_ratio_min/max`: 股息率范围
- `total_mv_min/max`: 总市值范围（单位：万元）
- `circ_mv_min/max`: 流通市值范围（单位：万元）
- `limit`: 返回行数限制
- `order_by`: 排序字段

## 常用查询场景

### 1. 寻找优质股票
```json
{
  "tool": "clickhouse_query_filter_daily_basic",
  "arguments": {
    "pe_min": 5,
    "pe_max": 20,
    "pb_min": 0.5,
    "pb_max": 2,
    "dv_ratio_min": 2,
    "total_mv_min": 500000,
    "limit": 20,
    "order_by": "dv_ratio DESC"
  }
}
```

### 2. 寻找活跃股票
```json
{
  "tool": "clickhouse_query_filter_daily_data",
  "arguments": {
    "trade_date": "20251118",
    "vol_min": 500000,
    "amount_min": 100000000,
    "pct_chg_min": 2,
    "limit": 20,
    "order_by": "amount DESC"
  }
}
```

### 3. 寻找价值低估股票
```json
{
  "tool": "clickhouse_query_filter_daily_basic",
  "arguments": {
    "pe_min": 0,
    "pe_max": 15,
    "pb_min": 0,
    "pb_max": 1,
    "total_mv_min": 1000000,
    "limit": 20,
    "order_by": "pb ASC"
  }
}
```

## 注意事项

1. 日期格式必须为YYYYMMDD（如：20251118）
2. 市值单位为万元
3. 百分比数值使用实际数值（如：5表示5%）
4. 使用适当的limit限制返回结果数量
5. 可以组合多个条件进行精确筛选