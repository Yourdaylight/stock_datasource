---
name: tushare-plugin-builder
description: This skill should be used when the user provides a Tushare API document URL and asks to generate a full plugin in this codebase, including extractor, schema, config, query service, and agent/MCP/http usage with testable curl examples.
---

## 目的
将 Tushare 文档 URL 转换为本仓库的生产级插件，包含数据抽取、ClickHouse 表结构、查询服务，以及可测试的 `curl` 示例。

## 何时使用
- 用户提供 Tushare 文档 URL 或页面内容，要求生成插件。
- 用户需要基于某个 Tushare 接口生成插件 + 入库 + service + Agent/MCP 调用。
- **验证已有插件**：用户要求检查某个插件是否符合规范。

## 工作流程

### 1) 收集必要输入
- 确保用户提供了 Tushare 文档 URL。若无法访问，请求截图或复制的文档内容。
- 若未指定插件名，询问用户。使用 snake_case 命名，与现有 `tushare_*` 插件保持一致。

### 2) 从文档提取 API 规格
- 解析接口名称、输入参数、输出字段、使用说明（频率限制、分页、数据量限制）。
- 记录字段命名差异（如 `pct_change` vs `pct_chg`）及所需转换。

### 3) 规划插件结构（参考 `references/plugin_conventions.md`）
- 目录：`src/stock_datasource/plugins/<plugin_name>/`
- 文件：`__init__.py`、`plugin.py`、`extractor.py`、`service.py`、`schema.json`、`config.json`、`<plugin_name>.md`
- 以现有 `tushare_*` 插件为模板。

### 4) 实现 extractor
- 使用 `tushare` SDK，API 调用需用 `proxy_context()` 包裹。
- 实现频率限制、超时、重试（tenacity）。
- 根据 API 特性支持 `trade_date` 或 `start_date`/`end_date`。

### 5) 实现 plugin
- 实现 `extract_data`、`validate_data`、`transform_data`、`load_data`。
- 插入前添加 `version` 和 `_ingested_at` 列。
- 转换数值类型，`trade_date` 转为 `Date`。

#### 插件分类与角色
必须实现以下方法指定插件的分类和角色：

```python
from stock_datasource.core.base_plugin import PluginCategory, PluginRole

def get_category(self) -> PluginCategory:
    """插件分类 - 按市场划分"""
    return PluginCategory.CN_STOCK  # 或 HK_STOCK, INDEX, ETF_FUND, SYSTEM

def get_role(self) -> PluginRole:
    """插件角色"""
    return PluginRole.PRIMARY  # 或 BASIC, DERIVED, AUXILIARY
```

**分类说明**：
- `CN_STOCK`: A股相关数据
- `HK_STOCK`: 港股相关数据
- `INDEX`: 指数相关数据
- `ETF_FUND`: ETF/基金相关数据
- `SYSTEM`: 系统数据（如交易日历）

**角色说明**：
- `PRIMARY`: 主数据（如 daily 行情）
- `BASIC`: 基础数据（如 stock_basic）
- `DERIVED`: 衍生数据（如复权因子）
- `AUXILIARY`: 辅助数据（如指数权重）

#### 依赖配置
在 `plugin.py` 中实现依赖方法（**不是在 config.json 中配置**）：

```python
def get_dependencies(self) -> List[str]:
    """必须依赖 - 这些插件的数据必须存在才能运行当前插件。
    
    例如：tushare_daily 依赖 tushare_stock_basic 提供股票代码列表。
    """
    return ["tushare_stock_basic"]

def get_optional_dependencies(self) -> List[str]:
    """可选依赖 - 同步主插件时默认会同步这些依赖，用户可选择禁用。
    
    例如：tushare_daily 可选同步 tushare_adj_factor 复权因子。
    """
    return ["tushare_adj_factor"]
```

**依赖规则**：
- 必须依赖：在运行当前插件前，会检查依赖插件表中是否有数据
- 可选依赖：前端展示时会显示可勾选的关联插件，默认勾选

### 6) 实现 service 查询
- 至少提供一个日期范围查询和一个最新数据查询。
- **必须使用参数化查询**（禁止字符串拼接）。
- 返回 JSON 可序列化结构。

### 7) 定义 schema/config
- `schema.json`：使用 `ReplacingMergeTree`，`partition_by` 为 `toYYYYMM(trade_date)`，`order_by` 为主键。
- `config.json`：包含完整的插件配置。

#### config.json 完整结构
```json
{
  "enabled": true,
  "rate_limit": 120,
  "timeout": 30,
  "retry_attempts": 3,
  "description": "插件描述",
  "schedule": {
    "frequency": "daily",
    "time": "18:00",
    "day_of_week": "monday"
  },
  "parameters": {
    "max_empty_days": 5,
    "validate_prices": true
  },
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

**字段说明**：
| 字段 | 必需 | 说明 |
|------|------|------|
| `enabled` | 是 | 是否启用插件 |
| `rate_limit` | 是 | API 调用频率限制（次/分钟） |
| `timeout` | 是 | 请求超时时间（秒） |
| `retry_attempts` | 是 | 重试次数 |
| `description` | 是 | 插件描述 |
| `schedule` | 否 | 调度配置 |
| `schedule.frequency` | 否 | 调度频率：`daily` 或 `weekly`，默认 `daily` |
| `schedule.time` | 否 | 执行时间，格式 `HH:MM`，默认 `18:00` |
| `schedule.day_of_week` | 否 | 仅 `weekly` 时有效，如 `monday` |
| `parameters` | 否 | 插件特定参数 |
| `parameters_schema` | 是 | 参数 schema，用于验证和前端展示 |

**注意**：依赖配置（`dependencies`、`optional_dependencies`）**不在 config.json 中定义**，而是通过 `plugin.py` 中的 `get_dependencies()` 和 `get_optional_dependencies()` 方法实现。

### 8) 创建 ClickHouse 表
- 根据 `schema.json` 生成 `CREATE TABLE` SQL。
- **使用脚本**：
  ```bash
  # 仅生成 SQL
  python .codebuddy/skills/tushare-plugin-builder/scripts/generate_create_table_sql.py \
    src/stock_datasource/plugins/<plugin_name>/schema.json

  # 生成并执行
  python .codebuddy/skills/tushare-plugin-builder/scripts/generate_create_table_sql.py \
    src/stock_datasource/plugins/<plugin_name>/schema.json --execute
  ```

### 9) 验证数据库连接
- 执行前先验证 ClickHouse 连接是否正常：
  ```bash
  # 测试连接
  python .codebuddy/skills/tushare-plugin-builder/scripts/verify_clickhouse_connection.py

  # 列出所有表
  python .codebuddy/skills/tushare-plugin-builder/scripts/verify_clickhouse_connection.py --list

  # 验证指定表是否存在
  python .codebuddy/skills/tushare-plugin-builder/scripts/verify_clickhouse_connection.py --table <table_name>
  ```

### 10) 运行数据拉取测试
- 执行插件拉取并存储样本数据（如某一交易日）。
- 代理配置：运行前确保 `runtime_config.json` 中代理设置正确。
- **使用脚本**：
  ```bash
  # 运行插件并验证
  python .codebuddy/skills/tushare-plugin-builder/scripts/run_plugin_test.py \
    <plugin_name> --date 20250110 --verify
  ```
- 或使用模块方式：
  ```bash
  python -m stock_datasource.plugins.<plugin_name>.plugin --date 20250110
  ```

### 11) 验证 ClickHouse 数据
- 查询 ClickHouse 确认数据已存储：
  ```bash
  # 使用脚本验证
  python .codebuddy/skills/tushare-plugin-builder/scripts/verify_clickhouse_connection.py \
    --table <table_name> --date 20250110
  ```
- 或手动查询：
  ```sql
  SELECT count(*), min(trade_date), max(trade_date)
  FROM <table_name>
  WHERE trade_date = '2025-01-10';
  ```

### 12) 测试 HTTP 服务端点
- 若未运行，启动 HTTP 服务：`python -m stock_datasource.services.http_server`
- **使用脚本**：
  ```bash
  # 列出所有 API 路由
  python .codebuddy/skills/tushare-plugin-builder/scripts/verify_service_http.py --list

  # 测试指定服务方法
  python .codebuddy/skills/tushare-plugin-builder/scripts/verify_service_http.py \
    --service <service_name> \
    --method get_by_date_range \
    --params '{"ts_code":"XXX","start_date":"20250101","end_date":"20250110"}'

  # 仅生成 curl 命令
  python .codebuddy/skills/tushare-plugin-builder/scripts/verify_service_http.py \
    --service <service_name> --method get_latest --params '{}' --curl
  ```

### 13) 测试 MCP 工具可用性
- 若未运行，启动 MCP 服务：`python -m stock_datasource.services.mcp_server`
- **使用脚本**：
  ```bash
  # 列出所有 MCP 工具
  python .codebuddy/skills/tushare-plugin-builder/scripts/verify_mcp_tool.py --list

  # 搜索相关工具
  python .codebuddy/skills/tushare-plugin-builder/scripts/verify_mcp_tool.py --pattern <service_name>

  # 验证指定工具
  python .codebuddy/skills/tushare-plugin-builder/scripts/verify_mcp_tool.py --tool <tool_name>
  ```

### 14) 测试 Agent 集成
- 向 Orchestrator 发送自然语言查询，应调用新插件的 service。
- 示例提问："查询 XXX 指数最近一周的行情数据"
- 验证：
  - Agent 正确识别意图并选择工具。
  - 工具调用从 ClickHouse 返回数据。
  - 响应格式化后返回给用户。

### 15) 验证集成点
- Service 自动发现，无需额外手动注册。
- MCP/HTTP 端点按生成的路由工作。

## 验证脚本说明

本 skill 提供以下验证脚本（位于 `scripts/` 目录）：

| 脚本 | 用途 |
|------|------|
| `validate_plugin.py` | **综合验证插件是否符合规范** |
| `verify_clickhouse_connection.py` | 测试数据库连接、列出表、验证数据 |
| `generate_create_table_sql.py` | 根据 schema.json 生成建表 SQL |
| `run_plugin_test.py` | 运行插件 ETL 并验证入库 |
| `verify_service_http.py` | 测试 HTTP 服务端点 |
| `verify_mcp_tool.py` | 验证 MCP 工具注册状态 |

---

## 插件验证流程

当用户要求验证已有插件（无论是自己编写还是生成的），执行以下步骤：

### 1) 运行综合验证脚本
```bash
# 验证单个插件
python .codebuddy/skills/tushare-plugin-builder/scripts/validate_plugin.py <plugin_name>

# 显示所有检查详情
python .codebuddy/skills/tushare-plugin-builder/scripts/validate_plugin.py <plugin_name> --verbose

# 列出所有可用插件
python .codebuddy/skills/tushare-plugin-builder/scripts/validate_plugin.py --list

# 验证所有插件
python .codebuddy/skills/tushare-plugin-builder/scripts/validate_plugin.py --all
```

### 2) 验证检查项

`validate_plugin.py` 会自动检查以下内容：

**文件结构检查：**
- [ ] `__init__.py` 存在且导出 Plugin/Service 类
- [ ] `plugin.py` 存在且继承 BasePlugin
- [ ] `extractor.py` 存在且使用 proxy_context
- [ ] `service.py` 存在且继承 BaseService
- [ ] `schema.json` 存在且包含必需字段
- [ ] `config.json` 存在且包含必需配置

**代码规范检查：**
- [ ] plugin.py 实现了 extract/validate/transform/load 方法
- [ ] plugin.py 添加了 version 和 _ingested_at 系统列
- [ ] plugin.py 实现了 get_category() 返回正确的 PluginCategory
- [ ] plugin.py 实现了 get_role() 返回正确的 PluginRole
- [ ] plugin.py 实现了 get_dependencies()（返回空列表或依赖插件名）
- [ ] plugin.py 实现了 get_optional_dependencies()（如有可选依赖）
- [ ] extractor.py 使用了重试逻辑（tenacity）
- [ ] service.py 使用参数化 SQL（无 SQL 注入风险）
- [ ] service.py 包含查询方法（get_*/query_*/fetch_*）

**Schema 规范检查：**
- [ ] 包含 table_name、columns、engine、order_by
- [ ] 使用 ReplacingMergeTree 引擎
- [ ] 包含 version 和 _ingested_at 系统列
- [ ] 设置了分区策略（partition_by）

**运行时检查：**
- [ ] 模块可正常导入
- [ ] 数据库表已创建
- [ ] 表中有数据（如已运行过 ETL）

### 3) 处理验证结果

根据验证结果采取行动：

**✅ 通过**：插件符合规范，可进行下一步测试。

**⚠️ 警告**：插件可运行但存在潜在问题，建议修复：
- 缺少重试逻辑 → 添加 tenacity 装饰器
- 未检测到参数化查询 → 检查 SQL 是否使用 `%(param)s`
- 表为空 → 运行数据拉取测试

**❌ 失败**：插件存在严重问题，必须修复：
- SQL 注入风险 → 改用参数化查询
- 缺少必需文件 → 补充缺失文件
- 未使用 proxy_context → API 调用将失败
- 缺少系统列 → 在 schema.json 和 plugin.py 中添加

### 4) 端到端验证

通过基础检查后，执行完整测试流程：

```bash
# 1. 验证数据库连接
python .codebuddy/skills/tushare-plugin-builder/scripts/verify_clickhouse_connection.py

# 2. 建表（如果表不存在）
python .codebuddy/skills/tushare-plugin-builder/scripts/generate_create_table_sql.py \
  src/stock_datasource/plugins/<plugin_name>/schema.json --execute

# 3. 运行 ETL 并验证入库
python .codebuddy/skills/tushare-plugin-builder/scripts/run_plugin_test.py \
  <plugin_name> --date 20250110 --verify

# 4. 测试 HTTP 服务
python .codebuddy/skills/tushare-plugin-builder/scripts/verify_service_http.py \
  --service <service_name> --method get_latest --params '{}'

# 5. 测试 MCP 工具
python .codebuddy/skills/tushare-plugin-builder/scripts/verify_mcp_tool.py \
  --pattern <service_name>
```

---

## 输出检查清单
- [ ] 插件目录已创建，包含所有必需文件。
- [ ] Extractor 使用 `proxy_context()` 和 `tushare` SDK。
- [ ] Plugin 实现了 `get_category()` 和 `get_role()` 方法。
- [ ] Plugin 实现了 `get_dependencies()` 和 `get_optional_dependencies()` 方法。
- [ ] Service 使用参数化 SQL。
- [ ] Schema 匹配 Tushare 输出字段。
- [ ] Config 包含频率限制、schedule 和参数 schema。
- [ ] ClickHouse 表已创建，数据已入库。
- [ ] 通过 SQL 查询验证 ClickHouse 中有数据。
- [ ] HTTP 服务端点已通过 curl 测试。
- [ ] MCP 工具已注册且可调用。
- [ ] Agent 可通过自然语言查询调用该服务。
