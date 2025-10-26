# Stock Data Source - A-Share Financial Database

一个完整的 A 股数据采集系统，使用 ClickHouse 存储、TuShare API 数据源、支持自动化编排。

## 📊 项目特性

- **完整的 A 股数据**：日线、复权因子、基础指标、涨跌停、停复牌等
- **7 个现成插件**：开箱即用的数据采集插件
- **高性能存储**：ClickHouse 列式数据库，支持 PB 级数据
- **自动化编排**：Airflow DAG 支持定时任务
- **多层数据质量**：ODS → DM/Fact → Metadata 三层架构
- **幂等性保证**：ReplacingMergeTree 引擎确保数据一致性
- **可扩展架构**：易于添加新的数据源和插件

## 🚀 快速开始

### 前置要求

- Python 3.11+
- ClickHouse 服务器
- TuShare API Token
- uv 包管理工具

### 安装步骤

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

### 常用命令

```bash
# 发现所有插件
uv run python -m stock_datasource.cli_plugins discover

# 列出所有插件
uv run python -m stock_datasource.cli_plugins list

# 查看插件详情
uv run python -m stock_datasource.cli_plugins info tushare_daily

# 测试插件数据提取
uv run python -m stock_datasource.cli_plugins test --date 20251024

# 获取特定日期数据
uv run cli.py ingest-daily --date 20251024

# 批量回填数据
uv run cli.py backfill --start-date 20250101 --end-date 20251024

# 查看摄入状态
uv run cli.py status --date 20251024

# 运行质量检查
uv run cli.py quality-check --date 20251024

# 生成日报告
uv run cli.py report --date 20251024

# 优化表去除重复数据
uv run python -c "from src.stock_datasource.models.database import db_client; db_client.execute('OPTIMIZE TABLE ods_daily FINAL')"

# 检查重复数据情况
uv run python -c "
from src.stock_datasource.models.database import db_client
total = db_client.execute('SELECT COUNT(*) FROM ods_daily')[0][0]
unique = db_client.execute('SELECT COUNT(DISTINCT (ts_code, trade_date)) FROM ods_daily')[0][0]
print(f'总记录: {total:,}, 唯一: {unique:,}, 重复: {total-unique:,}')
"
```

## 📁 项目结构

```
stock_datasource/
├── 📄 核心文档
│   ├── README.md                      # 项目概览（本文件）
│   ├── DEVELOPMENT_GUIDE.md           # 详细开发指导
│   ├── PLUGIN_QUICK_START.md          # 新建插件快速参考
│   ├── README_SUMMARY.md              # 项目总结和导航
│   └── BASEPLUGIN_QUICK_REFERENCE.md  # BasePlugin API 参考
│
├── 🔧 核心代码
│   ├── cli.py                         # CLI 命令入口
│   ├── pyproject.toml                 # 项目配置和依赖
│   ├── uv.lock                        # 依赖锁定文件
│   └── src/stock_datasource/
│       ├── core/                      # 核心模块
│       │   ├── base_plugin.py         # BasePlugin 基类
│       │   ├── database.py            # 数据库连接
│       │   └── plugin_manager.py      # 插件管理器
│       ├── plugins/                   # 数据插件（7 个）
│       │   ├── tushare_daily/
│       │   ├── tushare_adj_factor/
│       │   ├── tushare_daily_basic/
│       │   ├── tushare_stock_basic/
│       │   ├── tushare_stk_limit/
│       │   ├── tushare_suspend_d/
│       │   └── tushare_trade_calendar/
│       └── utils/                     # 工具函数
│
├── 📊 数据目录
│   ├── data/                          # 数据存储
│   │   └── exports/                   # 导出数据
│   └── logs/                          # 运行日志
│
├── 🧪 测试目录
│   └── tests/                         # 单元测试
│
├── 🛠️ 脚本工具
│   └── scripts/
│       └── optimize_tables.py         # 表优化脚本（去重复数据）
│
├── 📚 配置文件
│   ├── .env.example                   # 环境变量示例
│   ├── .gitignore                     # Git 忽略规则
│   ├── .python-version                # Python 版本
│   └── LICENSE                        # 许可证
│
└── 📖 文档目录
    └── docs/                          # 其他文档
```

## 🏗️ 系统架构

```
TuShare API
    ↓
Plugin (Extract → Validate → Transform → Load)
    ↓
ODS Layer (原始数据，ReplacingMergeTree 幂等存储)
    ├─ ods_daily              (日线数据，按月分区)
    ├─ ods_adj_factor         (复权因子，version 去重)
    ├─ ods_daily_basic        (日线基础指标，自动合并)
    ├─ ods_stock_basic        (股票基础信息)
    ├─ ods_stk_limit          (涨跌停数据)
    ├─ ods_suspend_d          (停复牌数据)
    └─ ods_trade_calendar     (交易日历)
    ↓
DM/Fact Layer (清洗数据，稳定业务表)
    ├─ fact_daily_bar         (事实表)
    └─ dim_security           (维度表)
    ↓
Metadata Layer (审计日志)
    ├─ ingestion_logs         (摄入日志)
    ├─ quality_checks         (质量检查)
    └─ schema_evolution       (Schema 演变)
```

### 🔄 幂等性设计

**ReplacingMergeTree 引擎特性**：
- **延迟去重**：插入时允许重复，后台合并时自动去重
- **版本控制**：每条记录包含 `version` 字段（时间戳）
- **自动保留最新**：合并时保留 version 值最大的记录
- **分区优化**：按月分区 `toYYYYMM(trade_date)` 提升性能

## 📋 7 个现成插件

| 插件 | 表名 | 说明 | 参数 |
|------|------|------|------|
| `tushare_daily` | `ods_daily` | 日线数据 | `trade_date` |
| `tushare_adj_factor` | `ods_adj_factor` | 复权因子 | `trade_date` |
| `tushare_daily_basic` | `ods_daily_basic` | 日线基础指标 | `trade_date` |
| `tushare_stock_basic` | `ods_stock_basic` | 股票基础信息 | 无 |
| `tushare_stk_limit` | `ods_stk_limit` | 涨跌停数据 | `trade_date` |
| `tushare_suspend_d` | `ods_suspend_d` | 停复牌数据 | `trade_date` |
| `tushare_trade_calendar` | `ods_trade_calendar` | 交易日历 | `start_date`, `end_date` |

## 🔧 新建插件的完整步骤

### 1. 创建插件目录结构
```bash
mkdir -p src/stock_datasource/plugins/my_plugin
cd src/stock_datasource/plugins/my_plugin
touch __init__.py plugin.py extractor.py service.py config.json schema.json
```

### 2. 实现 plugin.py（数据采集）
```python
from stock_datasource.core.base_plugin import BasePlugin
import pandas as pd
from .extractor import extractor

class MyPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "my_plugin"
    
    @property
    def description(self) -> str:
        return "My custom plugin"
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """从数据源获取原始数据"""
        trade_date = kwargs.get('trade_date')
        data = extractor.extract(trade_date)
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """验证数据的完整性和正确性"""
        if data.empty:
            return False
        return True
    
    def load_data(self, data: pd.DataFrame) -> dict:
        """将清洗后的数据加载到数据库"""
        if not self.db:
            return {"status": "failed", "error": "Database not initialized"}
        
        self.db.insert_dataframe('ods_my_table', data)
        return {"status": "success", "records": len(data)}
```

### 3. 实现 extractor.py（API 调用）
```python
import pandas as pd
from stock_datasource.config.settings import settings
import tushare as ts

class Extractor:
    def __init__(self):
        self.pro = ts.pro_api(settings.TUSHARE_TOKEN)
    
    def extract(self, trade_date: str) -> pd.DataFrame:
        """从 TuShare API 获取数据"""
        data = self.pro.daily(trade_date=trade_date)
        return data

extractor = Extractor()
```

### 4. 实现 service.py（查询接口）
```python
from typing import List, Dict, Any
from stock_datasource.core.base_service import BaseService, query_method, QueryParam

class MyPluginService(BaseService):
    """Query service for my plugin data."""
    
    def __init__(self):
        super().__init__("my_plugin")
    
    @query_method(
        description="Query data by code and date range",
        params=[
            QueryParam(name="code", type="str", description="Stock code", required=True),
            QueryParam(name="start_date", type="str", description="Start date YYYYMMDD", required=True),
            QueryParam(name="end_date", type="str", description="End date YYYYMMDD", required=True),
        ]
    )
    def get_data(self, code: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Query data from database."""
        query = f"""
        SELECT * FROM ods_my_table
        WHERE ts_code = '{code}'
        AND trade_date >= '{start_date}'
        AND trade_date <= '{end_date}'
        ORDER BY trade_date ASC
        """
        df = self.db.execute_query(query)
        return df.to_dict('records')
```

### 5. 编写 config.json（配置）
```json
{
  "enabled": true,
  "rate_limit": 120,
  "timeout": 30,
  "retry_attempts": 3,
  "description": "My custom plugin",
  "parameters_schema": {
    "trade_date": {
      "type": "string",
      "format": "date",
      "required": true,
      "description": "Trade date in YYYYMMDD format"
    }
  }
}
```

### 6. 编写 schema.json（表结构）
```json
{
  "table_name": "ods_my_table",
  "table_type": "ods",
  "columns": [
    {"name": "ts_code", "data_type": "String", "nullable": false},
    {"name": "trade_date", "data_type": "Date", "nullable": false},
    {"name": "version", "data_type": "UInt64", "nullable": false},
    {"name": "_ingested_at", "data_type": "DateTime", "nullable": false}
  ],
  "partition_by": "toYYYYMM(trade_date)",
  "order_by": ["ts_code", "trade_date"],
  "engine": "ReplacingMergeTree"
}
```

### 7. 注册插件 (__init__.py)
```python
from .plugin import MyPlugin
from .service import MyPluginService

__all__ = ["MyPlugin", "MyPluginService"]
```

### 8. 测试验证
```bash
# 发现插件
uv run python -m stock_datasource.cli_plugins discover

# 查看插件详情
uv run python -m stock_datasource.cli_plugins info my_plugin

# 测试数据提取
uv run python -m stock_datasource.cli_plugins test --plugin my_plugin --date 20251024
```

## ⚠️ 新建插件的注意事项

### ✅ 必须遵守

- **实现三个必需方法**：`extract_data()`、`validate_data()`、`load_data()`
- **返回正确的类型**：`extract_data()` 必须返回 `pd.DataFrame`
- **添加系统列**：`version` 和 `_ingested_at`
- **使用 logger**：使用 `self.logger` 记录日志
- **处理异常**：捕获并处理所有异常情况

### ❌ 常见错误

- ❌ 在 `extract()` 中进行数据转换（应在 `transform()` 中）
- ❌ 忽略异常，让其传播到上层
- ❌ 跳过数据验证
- ❌ 返回 None 或其他非 DataFrame 类型
- ❌ 硬编码配置值

## 📚 文档导航

| 文档 | 用途 | 适合人群 |
|------|------|---------|
| `README.md` | 项目概览和快速开始 | 所有人 |
| `DEVELOPMENT_GUIDE.md` | 详细的开发指导 | 开发者 |
| `PLUGIN_QUICK_START.md` | 新建插件快速参考 | 新手开发者 |
| `README_SUMMARY.md` | 项目总结和导航 | 项目管理者 |
| `BASEPLUGIN_QUICK_REFERENCE.md` | BasePlugin API 参考 | API 开发者 |

## 🔐 环境配置

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TUSHARE_TOKEN` | TuShare API Token | 必需 |
| `CLICKHOUSE_HOST` | ClickHouse 服务器地址 | localhost |
| `CLICKHOUSE_PORT` | ClickHouse 服务器端口 | 9000 |
| `CLICKHOUSE_DATABASE` | ClickHouse 数据库名 | stock_datasource |
| `LOG_LEVEL` | 日志级别 | INFO |

## 📊 数据统计

- **时间范围**：2025-01-01 至 2025-10-24（195 个交易日）
- **股票数量**：~5,400 只 A 股
- **数据表**：7 个 ODS 表 + 2 个 Fact 表 + 1 个 Dim 表
- **总记录数**：~1.2 亿条（每日 ~600 万条）

## 🌐 HTTP Server 与 MCP Server 接口自动生成

### 架构说明

项目采用**统一的 Service 层设计**，通过每个插件的 `service.py` 统一管理所有数据查询逻辑：

```
plugins/tushare_daily/
├── plugin.py              (数据采集：Extract → Validate → Load)
├── extractor.py           (API 调用逻辑)
├── service.py             (查询接口：定义 @query_method)
├── config.json            (插件配置)
└── schema.json            (表结构定义)
     │
     └─→ ServiceGenerator (自动生成)
          ├── 生成 HTTP 路由 (FastAPI)
          └── 生成 MCP 工具定义
               │
               ├─→ HTTP Server (http_server.py)
               │    └── 暴露 REST API 端点
               │
               └─→ MCP Server (mcp_server.py)
                    └── 暴露 MCP 工具接口
```

**关键特性**：
- **单一数据源**：所有查询逻辑在 `service.py` 中定义一次
- **自动生成**：HTTP 路由和 MCP 工具自动从 Service 方法生成
- **元数据驱动**：通过 `@query_method` 装饰器定义参数和描述
- **代码复用**：HTTP 和 MCP 共享相同的业务逻辑
- **动态发现**：自动发现所有插件的 Service 类

### 数据流向

```
客户端请求
    │
    ├─→ HTTP 请求 → HTTP Server → ServiceGenerator → TuShareDailyService.get_daily_data() → ClickHouse
    │
    └─→ MCP 请求 → MCP Server → ServiceGenerator → TuShareDailyService.get_daily_data() → ClickHouse
```

---

## 🚀 HTTP 服务器使用

### 启动 HTTP 服务器

```bash
# 方式 1：使用 uv
uv run python -m stock_datasource.services.http_server

# 方式 2：使用 uvicorn
uvicorn stock_datasource.services.http_server:app --host 0.0.0.0 --port 8000
```

### HTTP 请求示例

```bash
# 查询特定股票的日线数据
curl -X POST http://localhost:8000/api/tushare_daily/get_daily_data \
  -H "Content-Type: application/json" \
  -d '{
    "code": "000001.SZ",
    "start_date": "20250101",
    "end_date": "20251024"
  }'

# 查询最新日线数据
curl -X POST http://localhost:8000/api/tushare_daily/get_latest_daily \
  -H "Content-Type: application/json" \
  -d '{
    "codes": ["000001.SZ", "000002.SZ"],
    "limit": 10
  }'
```

### HTTP 路由自动生成

HTTP Server 会自动为每个插件的 Service 类生成路由：
- 路由前缀：`/api/{plugin_name}`
- 方法路由：`/api/{plugin_name}/{method_name}`
- 请求方式：POST
- 请求体：JSON 格式的参数

---

## 🔌 MCP 服务器使用

MCP Server 会自动为每个插件的 Service 方法生成工具

### 启动 MCP 服务器

```bash
# 方式 1：使用 uv
uv run python -m stock_datasource.services.mcp_server

# 方式 2：直接运行
python src/stock_datasource/services/mcp_server.py
```

### MCP 客户端配置

在 Claude Code、Cursor、Cline 等 IDE 中配置 MCP 服务器：
```json
{
  "mcpServers": {
    "stock_datasource": {
      "url": "http://192.168.1.100:8001/messages",
      "transport": "streamable-http",
      "disabled": false
    }
  }
}

```


### HTTP 服务器使用

启动 HTTP 服务器：
```bash
uvicorn stock_datasource.services.http_server:app --host 0.0.0.0 --port 8000
```

HTTP 请求示例：
```bash
curl -X POST http://localhost:8000/get_latest_daily \
  -H "Content-Type: application/json" \
  -d '{"codes": "000001.SZ", "limit": 10}'
```

### MCP 服务器使用

启动 MCP 服务器：
```bash
python -m stock_datasource.services.mcp_server
```

### MCP 工具调用示例

```python
# 工具名称格式：{plugin_name}_{method_name}
# 例如：tushare_daily_get_daily_data

# 工具参数（JSON 格式）：
{
  "code": "000001.SZ",
  "start_date": "20250101",
  "end_date": "20251024"
}
```

---

## 📋 Service 实现细节

### Service 类结构

每个插件的 `service.py` 都遵循以下结构：

```python
from stock_datasource.core.base_service import BaseService, query_method, QueryParam
from typing import List, Dict, Any

class TuShareDailyService(BaseService):
    """Query service for TuShare daily stock data."""
    
    def __init__(self):
        super().__init__("tushare_daily")
    
    @query_method(
        description="Query daily stock data by code and date range",
        params=[
            QueryParam(name="code", type="str", description="Stock code", required=True),
            QueryParam(name="start_date", type="str", description="Start date YYYYMMDD", required=True),
            QueryParam(name="end_date", type="str", description="End date YYYYMMDD", required=True),
        ]
    )
    def get_daily_data(self, code: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Query daily data from database."""
        query = f"""
        SELECT * FROM ods_daily
        WHERE ts_code = '{code}'
        AND trade_date >= '{start_date}'
        AND trade_date <= '{end_date}'
        ORDER BY trade_date ASC
        """
        df = self.db.execute_query(query)
        return df.to_dict('records')
    
    @query_method(
        description="Query latest daily data for multiple stocks",
        params=[
            QueryParam(name="codes", type="list", description="List of stock codes", required=True),
            QueryParam(name="limit", type="int", description="Number of latest records", required=False, default=1),
        ]
    )
    def get_latest_daily(self, codes: List[str], limit: int = 1) -> List[Dict[str, Any]]:
        """Query latest daily data."""
        # 实现查询逻辑
        pass
```

### 关键组件

1. **BaseService**：提供基础功能
   - 数据库连接管理（`self.db`）
   - 方法元数据提取（`get_query_methods()`）
   - 类型转换（`python_type_to_json_schema()`）

2. **@query_method 装饰器**：标记查询方法
   - 附加描述信息（`description`）
   - 定义参数元数据（`params`）
   - 支持自动生成文档和接口

3. **QueryParam 数据类**：定义参数元数据
   - 参数名称、类型、描述
   - 是否必需、默认值

4. **ServiceGenerator**：自动生成接口
   - 从 Service 方法生成 HTTP 路由
   - 从 Service 方法生成 MCP 工具
   - 动态创建请求/响应模型



## 🧪 测试

```bash
# 运行所有测试
uv run pytest tests/

# 运行特定测试
uv run pytest tests/test_plugins.py

# 生成覆盖率报告
uv run pytest --cov=src tests/
```

## 🐛 常见问题

### Q: 插件未被发现
**A**: 检查 `__init__.py` 是否导出了插件类

### Q: Schema 加载失败
**A**: 检查 `schema.json` 是否存在且格式正确

### Q: 参数定义为空
**A**: 检查 `config.json` 中是否有 `parameters_schema` 字段

### Q: 导入错误
**A**: 确保使用 `uv run` 而不是直接 `python`

### Q: 数据库中存在重复数据
**A**: 这是 ReplacingMergeTree 引擎的正常行为，参见下方"重复数据处理"章节

---

## 🔄 重复数据处理

### 问题说明

由于使用 ClickHouse 的 `ReplacingMergeTree` 引擎，系统采用**延迟去重**机制：
- ✅ **幂等性保证**：相同数据多次插入不会影响最终结果
- ⚠️ **延迟去重**：重复数据在后台合并前会暂时存在
- 🔧 **version 字段**：通过时间戳版本号确保保留最新数据

### 立即解决重复数据

#### 1. 手动优化单个表
```bash
# 优化 ods_daily 表
uv run python -c "
from src.stock_datasource.models.database import db_client
db_client.execute('OPTIMIZE TABLE ods_daily FINAL')
print('✅ ods_daily 表优化完成')
"
```

#### 2. 使用专用优化脚本（推荐）
```bash
# 检查所有表的重复数据状态
uv run python scripts/optimize_tables.py --check

# 优化所有 ODS 表
uv run python scripts/optimize_tables.py --all

# 优化指定表
uv run python scripts/optimize_tables.py --table ods_daily

# 详细输出模式
uv run python scripts/optimize_tables.py --all --verbose
```

#### 3. 批量优化所有 ODS 表（手动）
```bash
# 优化所有表
uv run python -c "
from src.stock_datasource.models.database import db_client

tables = ['ods_daily', 'ods_adj_factor', 'ods_daily_basic', 
          'ods_stk_limit', 'ods_suspend_d', 'ods_trade_calendar']

for table in tables:
    try:
        print(f'优化 {table}...')
        db_client.execute(f'OPTIMIZE TABLE {table} FINAL')
        print(f'✅ {table} 优化完成')
    except Exception as e:
        print(f'❌ {table} 优化失败: {e}')
"
```

#### 3. 检查重复数据情况
```bash
# 检查重复数据统计
uv run python -c "
from src.stock_datasource.models.database import db_client

table = 'ods_daily'  # 可替换为其他表名
total = db_client.execute(f'SELECT COUNT(*) FROM {table}')[0][0]
unique = db_client.execute(f'SELECT COUNT(DISTINCT (ts_code, trade_date)) FROM {table}')[0][0]

print(f'表: {table}')
print(f'总记录数: {total:,}')
print(f'唯一记录数: {unique:,}')
print(f'重复记录数: {total - unique:,}')
print(f'重复率: {((total - unique) / total * 100):.2f}%' if total > 0 else '0%')
"
```

### 查询时确保无重复

对于需要确保无重复数据的查询，使用 `FINAL` 关键字：

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

### 预防重复数据的最佳实践

#### 1. 定期自动优化
在 Airflow DAG 中添加优化任务：
```python
# 每日数据摄入完成后执行
optimize_task = BashOperator(
    task_id='optimize_tables',
    bash_command='''
    uv run python -c "
    from src.stock_datasource.models.database import db_client
    db_client.execute('OPTIMIZE TABLE ods_daily FINAL')
    "
    ''',
    dag=dag
)
```

#### 2. 监控重复率
```bash
# 添加到日常监控脚本
uv run cli.py report --date 20251025 --check-duplicates
```

#### 3. 调整 ClickHouse 配置
在 `config.xml` 中优化合并策略：
```xml
<merge_tree>
    <parts_to_delay_insert>150</parts_to_delay_insert>
    <parts_to_throw_insert>300</parts_to_throw_insert>
    <max_delay_to_insert>1</max_delay_to_insert>
</merge_tree>
```

### 技术原理

**ReplacingMergeTree 工作机制**：
1. **插入阶段**：数据直接插入，允许重复
2. **合并阶段**：后台自动合并分片时，根据 `ORDER BY` 键去重
3. **版本选择**：保留 `version` 字段值最大的记录
4. **查询优化**：使用 `FINAL` 或 `argMax` 函数确保结果唯一

**幂等性保证**：
- 相同的 `(ts_code, trade_date)` 组合被视为同一条记录
- 每次插入都会生成新的 `version`（时间戳）
- 系统自动保留最新版本的数据

## 📞 获取帮助

- **快速问题** → 查看 `PLUGIN_QUICK_START.md`
- **详细指导** → 查看 `DEVELOPMENT_GUIDE.md`
- **API 参考** → 查看 `BASEPLUGIN_QUICK_REFERENCE.md`
- **项目总结** → 查看 `README_SUMMARY.md`

## 📄 许可证

本项目采用 MIT 许可证 - 详见 LICENSE 文件

## 🤝 贡献

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## ✨ 项目状态

✅ **生产就绪** - 所有核心文档和代码已完成，可以开始新建插件和后续开发！
