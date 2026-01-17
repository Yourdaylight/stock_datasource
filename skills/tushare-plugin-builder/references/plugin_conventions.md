# 项目插件规范 (stock_datasource)

## 路径
- 插件根目录：`/data/openresource/stock_datasource/src/stock_datasource/plugins`
- 每个插件目录：`plugins/<plugin_name>/`

## 必需文件
- `__init__.py` 导出插件类
- `plugin.py` 实现 `BasePlugin`
- `extractor.py` 包含 API 抽取逻辑，使用 `proxy_context()`
- `service.py` 实现 `BaseService` 查询方法
- `schema.json` ClickHouse 表结构
- `config.json` 插件配置

## 参考实现
- `tushare_daily` 完整流程 + service
- `tushare_index_daily` extractor 结构
- `tushare_top_list` 严格校验风格

## Service 自动发现
- 系统扫描每个插件目录的 `service.py` 自动发现 Service。
- HTTP 路由注册在 `/api/<plugin_name>/...`。
- MCP 工具从查询方法自动生成。

## SQL 安全
- Service 方法中必须使用参数化查询。
- ClickHouse 使用 `db.execute_query(query, params)`，占位符为 `%(param)s`。
- 禁止将用户输入拼接到 SQL 中。

## 代理使用
- API 调用必须用 `proxy_context()` 包裹。
- 测试时的代理设置通过 `runtime_config.json` 配置（无需修改代码）。

## Schema 指南
- 使用 `ReplacingMergeTree`，`version` 列用于幂等。
- 包含 `_ingested_at` 时间戳。
- `partition_by`：`toYYYYMM(trade_date)`。
- `order_by`：通常为 `ts_code, trade_date`。
