# Stock Data Source - A-Share Financial Database

一个完整的 A 股数据采集系统，使用 ClickHouse 存储、TuShare API 数据源、支持自动化编排。

## 📊 项目特性

- **完整的 A 股数据**：日线、复权因子、基础指标、涨跌停、停复牌等
- **7 个现成插件**：开箱即用的数据采集插件
- **高性能存储**：ClickHouse 列式数据库，支持 PB 级数据
- **自动化编排**：Airflow DAG 支持定时任务
- **多层数据质量**：ODS → DM/Fact → Metadata 三层架构
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
ODS Layer (原始数据，自动建表)
    ├─ ods_daily              (日线数据)
    ├─ ods_adj_factor         (复权因子)
    ├─ ods_daily_basic        (日线基础指标)
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

## 🔧 新建插件的 7 个步骤

### 1. 创建插件目录
```bash
mkdir -p src/stock_datasource/plugins/my_plugin
```

### 2. 实现 plugin.py
```python
from stock_datasource.core.base_plugin import BasePlugin
import pandas as pd

class MyPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "my_plugin"
    
    @property
    def description(self) -> str:
        return "My custom plugin"
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """从数据源获取原始数据"""
        # 实现数据提取逻辑
        return pd.DataFrame()
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """验证数据的完整性和正确性"""
        # 实现数据验证逻辑
        return True
    
    def load_data(self, data: pd.DataFrame) -> dict:
        """将清洗后的数据加载到数据库"""
        # 实现数据加载逻辑
        return {"status": "success"}
```

### 3. 实现 extractor.py
```python
# API 调用逻辑
```

### 4. 编写 config.json
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

### 5. 编写 schema.json
```json
{
  "table_name": "ods_my_table",
  "table_type": "ods",
  "columns": [
    {"name": "ts_code", "data_type": "String", "nullable": false},
    {"name": "trade_date", "data_type": "Date", "nullable": false}
  ],
  "partition_by": "toYYYYMM(trade_date)",
  "order_by": ["ts_code", "trade_date"],
  "engine": "ReplacingMergeTree"
}
```

### 6. 注册插件 (__init__.py)
```python
from .plugin import MyPlugin
__all__ = ["MyPlugin"]
```

### 7. 测试验证
```bash
# 发现插件
uv run python -m stock_datasource.cli_plugins discover

# 查看插件详情
uv run python -m stock_datasource.cli_plugins info my_plugin

# 测试数据提取
uv run python -m stock_datasource.cli_plugins test --plugin my_plugin
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
## http server与 mcp server接口自动生成
## 架构说明

### Service 层架构

项目采用**统一的 Service 层设计**，通过 `TuShareDailyService` 类统一管理所有数据查询逻辑：

```
TuShareDailyService (service.py)
    ├── 继承 BaseService
    ├── 定义查询方法（使用 @query_method 装饰器）
    └── 方法元数据（参数、描述等）
         │
         ├─→ ServiceGenerator (自动生成)
         │    ├── 生成 HTTP 路由 (FastAPI)
         │    └── 生成 MCP 工具定义
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

### 数据流向

```
客户端请求
    │
    ├─→ HTTP 请求 → HTTP Server → ServiceGenerator → TuShareDailyService → ClickHouse
    │
    └─→ MCP 请求 → MCP Server → ServiceGenerator → TuShareDailyService → ClickHouse
```

---

## MCP 接口使用

本项目提供了 MCP (Model Context Protocol) 接口来获取日线行情数据，mcp工具基于每个plugins/下面的service.py自动生成

- 启动mcp server
```bash
uv run src/stock_datasource/services/mcp_server.py
```

- mcp客户端（claude code, cursor， cline配置）
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

MCP 工具调用示例（通过 IDE 或 AI 工具）：
```python
# 工具名称：tushare_daily_get_latest_daily
# 参数：
{
  "codes": "000001.SZ",
  "limit": 10
}
```

---

## Service 实现细节

### TuShareDailyService 类结构

```python
class TuShareDailyService(BaseService):
    def __init__(self):
        super().__init__("tushare_daily")
    
    @query_method(description="...", params=[...])
    def get_daily_data(self, code: str, start_date: str, end_date: str):
        # 查询逻辑
        pass
    
    @query_method(description="...", params=[...])
    def get_latest_daily(self, codes: List[str], limit: int = 1):
        # 查询逻辑
        pass
    
    @query_method(description="...", params=[...])
    def get_daily_stats(self, code: str, start_date: str, end_date: str):
        # 查询逻辑
        pass
```

### 关键组件

1. **BaseService**：提供基础功能
   - 数据库连接管理
   - 方法元数据提取
   - 类型转换

2. **@query_method 装饰器**：标记查询方法
   - 附加描述信息
   - 定义参数元数据
   - 支持自动生成文档

3. **ServiceGenerator**：自动生成接口
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
