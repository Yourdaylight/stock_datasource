# 数据库设置指南

本文档介绍如何为 A股赛博操盘手 系统设置数据库。

## 📋 前提条件

1. **ClickHouse 数据库**已安装并运行
2. **环境变量**已正确配置（参考 `.env.example`）
3. **Python 依赖**已安装（`uv install`）

## 🚀 快速初始化

### 方法1：自动初始化（推荐）

系统启动时会自动检查并创建必要的数据库表：

```bash
# 启动 HTTP 服务器（会自动初始化表）
uv run python -m stock_datasource.services.http_server
```

### 方法2：手动初始化

使用 CLI 命令手动初始化所有表：

```bash
# 初始化所有表（插件表 + 元数据表 + 业务表）
uv run python cli.py init-db

# 初始化特定表
uv run python cli.py init-db --table user_positions
uv run python cli.py init-db --table portfolio_analysis
```

### 方法3：仅初始化 Portfolio 表

如果只需要初始化持仓管理相关表：

```bash
uv run python -c "
from stock_datasource.modules.portfolio.init import init_portfolio_tables
init_portfolio_tables()
"
```

## 📊 数据库表结构

### 1. 用户持仓表 (`user_positions`)

存储用户的股票持仓信息：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | String | 唯一标识符 |
| `ts_code` | LowCardinality(String) | 股票代码 (如 600519.SH) |
| `stock_name` | String | 股票名称 |
| `quantity` | UInt32 | 持股数量 |
| `cost_price` | Decimal(10,3) | 成本价 |
| `buy_date` | Date | 买入日期 |
| `current_price` | Nullable(Decimal(10,3)) | 当前价格 |
| `market_value` | Nullable(Decimal(15,2)) | 市值 |
| `profit_loss` | Nullable(Decimal(15,2)) | 盈亏金额 |
| `profit_rate` | Nullable(Decimal(8,4)) | 收益率(%) |
| `notes` | Nullable(String) | 备注 |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |

**引擎**: `ReplacingMergeTree(updated_at)`  
**分区**: `toYYYYMM(buy_date)`  
**排序**: `(ts_code, buy_date, id)`

### 2. 投资组合分析表 (`portfolio_analysis`)

存储 AI 生成的投资组合分析：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | String | 唯一标识符 |
| `analysis_date` | Date | 分析日期 |
| `analysis_summary` | Nullable(String) | 分析摘要 |
| `stock_analyses` | Nullable(String) | 个股分析 (JSON) |
| `risk_alerts` | Nullable(String) | 风险提示 (JSON) |
| `recommendations` | Nullable(String) | 投资建议 (JSON) |
| `created_at` | DateTime | 创建时间 |

**引擎**: `ReplacingMergeTree(created_at)`  
**分区**: `toYYYYMM(analysis_date)`  
**排序**: `(analysis_date, id)`

## 🔧 验证安装

检查表是否正确创建：

```bash
# 检查表是否存在
uv run python -c "
from stock_datasource.models.database import db_client
print('user_positions 表存在:', db_client.table_exists('user_positions'))
print('portfolio_analysis 表存在:', db_client.table_exists('portfolio_analysis'))
"

# 查看表结构
uv run python -c "
from stock_datasource.models.database import db_client
schema = db_client.get_table_schema('user_positions')
for col in schema:
    print(f'{col[\"column_name\"]}: {col[\"data_type\"]}')
"
```

## 🐛 故障排除

### 问题1：表不存在错误

```
DB::Exception: Unknown table expression identifier 'user_positions'
```

**解决方案**：
1. 检查 ClickHouse 连接配置
2. 手动运行初始化命令：`uv run python cli.py init-db`
3. 检查数据库权限

### 问题2：连接失败

**解决方案**：
1. 确认 ClickHouse 服务正在运行
2. 检查环境变量配置：
   ```bash
   echo $CLICKHOUSE_HOST
   echo $CLICKHOUSE_PORT
   echo $CLICKHOUSE_DATABASE
   ```
3. 测试连接：
   ```bash
   uv run python -c "
   from stock_datasource.models.database import db_client
   result = db_client.execute('SELECT 1')
   print('连接成功:', result)
   "
   ```

### 问题3：权限不足

**解决方案**：
1. 确保 ClickHouse 用户有创建表的权限
2. 检查数据库用户配置

## 📈 性能优化

### 分区策略

- **用户持仓表**: 按买入日期月份分区 (`toYYYYMM(buy_date)`)
- **分析表**: 按分析日期月份分区 (`toYYYYMM(analysis_date)`)

### 索引优化

- 主要查询字段已包含在 `ORDER BY` 中
- 使用 `LowCardinality` 优化股票代码存储
- `ReplacingMergeTree` 自动处理数据更新

### 数据清理

ClickHouse 会自动合并和清理重复数据，无需手动维护。

## 🔄 数据迁移

如果需要从其他系统迁移数据：

```bash
# 导出现有数据
uv run python -c "
from stock_datasource.modules.portfolio.service import get_portfolio_service
import json

service = get_portfolio_service()
positions = await service.get_positions()
data = [p.__dict__ for p in positions]

with open('portfolio_backup.json', 'w') as f:
    json.dump(data, f, indent=2, default=str)
"

# 导入数据（根据需要修改）
# ... 导入逻辑 ...
```

## 📞 支持

如果遇到问题，请：

1. 查看日志文件中的详细错误信息
2. 确认系统环境配置正确
3. 参考 [DEVELOPMENT_GUIDE.md](./DEVELOPMENT_GUIDE.md) 获取更多技术细节