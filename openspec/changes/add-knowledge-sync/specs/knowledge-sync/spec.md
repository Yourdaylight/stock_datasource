# Capability: Knowledge Sync — ClickHouse 数据同步至知识库

## ADDED Requirements

### REQ-KSYNC-001: 通用数据查询与 Markdown 生成

系统应能从 ClickHouse 任意已入库的表中查询数据，并将结果转换为可读的 Markdown 文档。同步逻辑不依赖任何具体插件，直接使用 `db_client` 查询。

#### Scenario: 从 ods_income_statement 表生成财报文档
- Given ClickHouse 中 `ods_income_statement` 表存在 600519.SH 的 20240930 数据
- When 系统对该表执行查询 `SELECT * FROM ods_income_statement WHERE ts_code='600519.SH' AND end_date='20240930'`
- Then 将查询结果转为 Markdown 表格文档
- And 文档标题格式为 `{table_name}-{ts_code}-{date_range}`

#### Scenario: 通过自定义 SQL 生成知识文档
- Given 用户输入自定义 SQL `SELECT ts_code, trade_date, close, vol FROM ods_daily WHERE ts_code='600519.SH' ORDER BY trade_date DESC LIMIT 30`
- When 系统执行该 SQL 并渲染结果
- Then 将结果转为 Markdown 表格文档并导入 WeKnora 知识库

### REQ-KSYNC-002: 批量同步至 WeKnora

系统应能将生成的 Markdown 文档批量导入到 WeKnora 知识库。

#### Scenario: 批量同步指定表的数据
- Given WeKnora 服务已配置且可连接
- And 用户指定了表名 `ods_income_statement`、股票列表 [600519.SH, 000858.SZ] 和日期范围
- When 用户触发知识同步
- Then 系统为每只股票查询数据并生成 Markdown 文档，通过 WeKnora manual knowledge API 导入
- And 同步完成后用户可在 AI 对话中通过知识库搜索到相关内容

#### Scenario: 增量同步避免重复
- Given WeKnora 知识库中已存在标题为 `ods_income_statement-600519.SH-20240930` 的文档
- When 用户再次触发包含该数据的同步
- Then 系统应更新已有文档内容而非创建重复文档

### REQ-KSYNC-003: 同步管理 API

系统应提供 REST API 来管理知识同步。

#### Scenario: 通过 API 触发同步
- Given 用户已认证且为管理员
- When 用户调用 `POST /api/datamanage/knowledge/sync` 并提供 table_name 和筛选条件
- Then 系统启动异步同步任务并返回任务状态

#### Scenario: 查看已导入文档
- Given WeKnora 中存在已导入的知识文档
- When 用户调用 `GET /api/datamanage/knowledge/documents`
- Then 返回分页的文档列表，包含标题、创建时间、状态等

### REQ-KSYNC-004: 前端知识同步界面

知识库页面应提供知识同步功能区域。

#### Scenario: 用户通过界面触发同步
- Given 用户在知识库页面的"知识同步"区域
- When 用户选择 ClickHouse 表、输入筛选条件或自定义 SQL，点击"开始同步"
- Then 系统触发同步并显示同步进度
- And 完成后刷新已导入文档列表
