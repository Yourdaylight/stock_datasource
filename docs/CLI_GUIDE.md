# CLI 命令行使用指南

本文档介绍 A股赛博操盘手 的命令行工具使用方法。

## 前置要求

- Python 3.11+
- ClickHouse 服务器
- TuShare API Token
- uv 包管理工具

## 安装步骤

1. **克隆仓库**
```bash
git clone <repository-url>
cd stock_datasource
```

2. **安装依赖**
```bash
uv sync
```

3. **配置环境**
```bash
cp .env.example .env
# 编辑 .env 文件，填入 TuShare Token 和 ClickHouse 配置
```

4. **初始化数据库**
```bash
uv run cli.py init-db
```

## 常用命令

### 数据库初始化

```bash
# 初始化所有表
uv run cli.py init-db

# 初始化特定表
uv run cli.py init-db --table ods_daily
```

### 插件管理

```bash
# 发现所有插件
uv run python -m stock_datasource.cli_plugins discover

# 列出所有插件
uv run python -m stock_datasource.cli_plugins list

# 查看插件详情
uv run python -m stock_datasource.cli_plugins info tushare_daily

# 测试插件数据提取
uv run python -m stock_datasource.cli_plugins test --date 20251024
```

### 数据采集

```bash
# 获取特定日期数据
uv run cli.py ingest-daily --date 20251024

# 批量回填数据
uv run cli.py backfill --start-date 20250101 --end-date 20251024

# 加载股票基础信息
uv run cli.py load-stock-basic

# 加载交易日历
uv run cli.py load-trade-calendar --start-date 20250101 --end-date 20251231
```

### 数据质量

```bash
# 查看摄入状态
uv run cli.py status --date 20251024

# 运行质量检查
uv run cli.py quality-check --date 20251024

# 生成日报告
uv run cli.py report --date 20251024

# 检查数据覆盖率
uv run cli.py coverage --table ods_daily
```

### 数据优化

```bash
# 优化表去除重复数据
uv run python -c "from src.stock_datasource.models.database import db_client; db_client.execute('OPTIMIZE TABLE ods_daily FINAL')"

# 检查重复数据情况
uv run python -c "
from src.stock_datasource.models.database import db_client
total = db_client.execute('SELECT COUNT(*) FROM ods_daily')[0][0]
unique = db_client.execute('SELECT COUNT(DISTINCT (ts_code, trade_date)) FROM ods_daily')[0][0]
print(f'总记录: {total:,}, 唯一: {unique:,}, 重复: {total-unique:,}')
"

# 使用专用优化脚本
uv run python scripts/optimize_tables.py --check
uv run python scripts/optimize_tables.py --all
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TUSHARE_TOKEN` | TuShare API Token | 必需 |
| `CLICKHOUSE_HOST` | ClickHouse 服务器地址 | localhost |
| `CLICKHOUSE_PORT` | ClickHouse 服务器端口 | 9000 |
| `CLICKHOUSE_DATABASE` | ClickHouse 数据库名 | stock_datasource |
| `LOG_LEVEL` | 日志级别 | INFO |
| `OPENAI_API_KEY` | OpenAI API Key（AI 功能必需） | - |
| `OPENAI_BASE_URL` | OpenAI API 地址 | https://api.openai.com/v1 |
| `OPENAI_MODEL` | 使用的模型 | gpt-4 |

## 7 个现成插件

| 插件 | 表名 | 说明 | 参数 |
|------|------|------|------|
| `tushare_daily` | `ods_daily` | 日线数据 | `trade_date` |
| `tushare_adj_factor` | `ods_adj_factor` | 复权因子 | `trade_date` |
| `tushare_daily_basic` | `ods_daily_basic` | 日线基础指标 | `trade_date` |
| `tushare_stock_basic` | `ods_stock_basic` | 股票基础信息 | 无 |
| `tushare_stk_limit` | `ods_stk_limit` | 涨跌停数据 | `trade_date` |
| `tushare_suspend_d` | `ods_suspend_d` | 停复牌数据 | `trade_date` |
| `tushare_trade_calendar` | `ods_trade_calendar` | 交易日历 | `start_date`, `end_date` |

## 重复数据处理

由于使用 ClickHouse 的 `ReplacingMergeTree` 引擎，系统采用延迟去重机制：

### 立即去重

```bash
# 手动优化单个表
uv run python -c "
from src.stock_datasource.models.database import db_client
db_client.execute('OPTIMIZE TABLE ods_daily FINAL')
print('✅ ods_daily 表优化完成')
"

# 批量优化所有 ODS 表
uv run python -c "
from src.stock_datasource.models.database import db_client
tables = ['ods_daily', 'ods_adj_factor', 'ods_daily_basic', 
          'ods_stk_limit', 'ods_suspend_d', 'ods_trade_calendar']
for table in tables:
    db_client.execute(f'OPTIMIZE TABLE {table} FINAL')
    print(f'✅ {table} 优化完成')
"
```

### 查询时确保无重复

```sql
-- 查询时自动去重
SELECT * FROM ods_daily FINAL 
WHERE trade_date = '20251025'
AND ts_code = '000001.SZ'

-- 聚合查询（推荐，性能更好）
SELECT ts_code, trade_date, 
       argMax(close, version) as close,
       argMax(vol, version) as vol
FROM ods_daily 
WHERE trade_date = '20251025'
GROUP BY ts_code, trade_date
```

## 常见问题

### Q: 插件未被发现
**A**: 检查 `__init__.py` 是否导出了插件类

### Q: Schema 加载失败
**A**: 检查 `schema.json` 是否存在且格式正确

### Q: 参数定义为空
**A**: 检查 `config.json` 中是否有 `parameters_schema` 字段

### Q: 导入错误
**A**: 确保使用 `uv run` 而不是直接 `python`

### Q: 数据库中存在重复数据
**A**: 这是 ReplacingMergeTree 引擎的正常行为，使用 `OPTIMIZE TABLE ... FINAL` 命令去重
