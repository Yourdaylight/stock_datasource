# ClickHouse Query Plugin 使用指南

这是一个通用的ClickHouse查询MCP插件，支持灵活的条件查询。

## 功能特性

1. **条件查询** - 支持多种查询条件格式
2. **原生SQL查询** - 支持执行原始SQL语句
3. **表结构查询** - 获取表结构和统计信息
4. **表列表** - 列出数据库中的所有表

## 使用方法

### 1. 条件查询

```python
# 基本查询
result = service.query_with_conditions(
    table="ods_daily_basic",
    conditions={"trade_date": "20241201"}
)

# 多条件查询
result = service.query_with_conditions(
    table="ods_daily_basic",
    conditions={
        "trade_date": "20241201",
        "total_mv": {"min": 100000, "max": 1000000}
    }
)

# IN查询
result = service.query_with_conditions(
    table="ods_daily_basic",
    conditions={
        "ts_code": ["000001.SZ", "000002.SZ", "600000.SH"]
    }
)

# 模糊查询
result = service.query_with_conditions(
    table="ods_daily_basic",
    conditions={
        "ts_code": {"like": "000%"},
        "total_mv": {"min": 500000}
    }
)

# 指定列和排序
result = service.query_with_conditions(
    table="ods_daily_basic",
    columns=["ts_code", "trade_date", "close", "total_mv"],
    conditions={"trade_date": "20241201"},
    order_by="total_mv DESC",
    limit=100
)
```

### 2. 原生SQL查询

```python
# 简单查询
result = service.execute_raw_query(
    "SELECT * FROM ods_daily_basic WHERE trade_date = %s LIMIT 10",
    ["20241201"]
)

# 复杂查询
result = service.execute_raw_query("""
    SELECT 
        ts_code,
        AVG(close) as avg_close,
        MAX(close) as max_close,
        MIN(close) as min_close
    FROM ods_daily_basic 
    WHERE trade_date >= %s AND trade_date <= %s
    GROUP BY ts_code
    ORDER BY avg_close DESC
    LIMIT 20
""", ["20241201", "20241231"])
```

### 3. 获取表结构

```python
# 获取表结构
schema = service.get_table_schema("ods_daily_basic")

# 列出所有表
tables = service.list_tables()

# 列出指定数据库的表
tables = service.list_tables("stock_db")

# 获取表统计信息
stats = service.get_table_stats("ods_daily_basic")
```

## 条件查询格式说明

### 基本条件
```python
{"column": "value"}  # 等于: column = 'value'
```

### 范围条件
```python
{"column": {"min": 100, "max": 1000}}  # column >= 100 AND column <= 1000
{"column": {"min": 100}}               # column >= 100
{"column": {"max": 1000}}              # column <= 1000
```

### 列表条件
```python
{"column": ["value1", "value2", "value3"]}  # column IN ('value1', 'value2', 'value3')
```

### 模糊条件
```python
{"column": {"like": "pattern%"}}   # column LIKE 'pattern%'
{"column": {"like": "%pattern"}}   # column LIKE '%pattern'
{"column": {"like": "%pattern%"}}  # column LIKE '%pattern%'
```

### 不等于条件
```python
{"column": {"ne": "value"}}  # column != 'value'
```

### 等于条件（显式）
```python
{"column": {"eq": "value"}}  # column = 'value'
```

## MCP工具调用示例

### query_with_conditions
```json
{
  "table": "ods_daily_basic",
  "conditions": {
    "trade_date": "20241201",
    "total_mv": {"min": 500000, "max": 2000000},
    "turnover_rate": {"min": 5, "max": 10}
  },
  "columns": ["ts_code", "close", "total_mv", "turnover_rate"],
  "order_by": "total_mv DESC",
  "limit": 50
}
```

### execute_raw_query
```json
{
  "sql": "SELECT ts_code, AVG(close) as avg_close FROM ods_daily_basic WHERE trade_date >= %s GROUP BY ts_code ORDER BY avg_close DESC LIMIT 10",
  "params": ["20241201"]
}
```

### get_table_schema
```json
{
  "table": "ods_daily_basic"
}
```

### list_tables
```json
{
  "database": "stock_db"
}
```

### get_table_stats
```json
{
  "table": "ods_daily_basic"
}
```

## 注意事项

1. **SQL注入防护** - 所有条件查询都使用参数化查询，防止SQL注入
2. **性能考虑** - 大表查询建议添加适当的LIMIT条件
3. **数据类型** - 日期时间字段会自动转换为ISO格式字符串
4. **NULL值处理** - 数据库NULL值会转换为Python的None

## 错误处理

插件会自动处理以下错误情况：
- 表不存在
- 列名错误
- SQL语法错误
- 参数类型错误
- 数据库连接错误

错误信息会包含在返回结果中，便于调试。