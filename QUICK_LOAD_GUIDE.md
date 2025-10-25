# 快速加载缺失表数据

## 问题
当前数据库中以下两个表为空：
- `ods_stock_basic` - 股票基础信息表
- `ods_trade_calendar` - 交易日历表

## 解决方案

### 方案 1：使用扩展 CLI 命令（推荐）

```bash
cd /home/lzh/finance/stock_datasource

# 加载股票基础信息
python cli.py load-stock-basic --list-status L

# 加载交易日历（2025年全年）
python cli.py load-trade-calendar --start-date 20250101 --end-date 20251231 --exchange SSE
```

### 方案 2：使用 Python 脚本

```bash
cd /home/lzh/finance/stock_datasource
python load_metadata_tables.py
```

### 方案 3：直接运行插件

```bash
cd /home/lzh/finance/stock_datasource

# 加载股票基础信息
python -m stock_datasource.plugins.tushare_stock_basic.plugin --list-status L

# 加载交易日历
python -m stock_datasource.plugins.tushare_trade_calendar.plugin \
  --start-date 20250101 \
  --end-date 20251231 \
  --exchange SSE
```

## 验证结果

```bash
# 查看数据覆盖情况
python cli.py coverage --table ods_stock_basic
python cli.py coverage --table ods_trade_calendar

# 或查询数据库
python query_data_status.py
```

## 参数说明

### load-stock-basic
- `--list-status`: 股票状态
  - `L` - 上市 (Listed)
  - `D` - 退市 (Delisted)
  - `P` - 暂停 (Paused)

### load-trade-calendar
- `--start-date`: 开始日期 (YYYYMMDD 格式)
- `--end-date`: 结束日期 (YYYYMMDD 格式)
- `--exchange`: 交易所
  - `SSE` - 上海交易所 (Shanghai Stock Exchange)
  - `SZSE` - 深圳交易所 (Shenzhen Stock Exchange)

## 注意事项

1. 确保 `.env` 文件中配置了 TuShare Token
2. 确保 ClickHouse 数据库正常运行
3. 确保网络连接正常，能访问 TuShare API
4. 首次运行可能需要较长时间，请耐心等待

## 详细文档

查看 `LOAD_MISSING_TABLES.md` 了解更多信息。
