# Proposal: Add Knowledge Sync — ClickHouse 数据同步至 WeKnora 知识库

## Why

当前系统已集成 WeKnora 知识库的**查询**能力，但知识库内容为空——需要用户手动到 WeKnora 前端上传文档。这严重制约了知识库的实用性。

系统 ClickHouse 中已有丰富的已入库数据（行情、财报、指标等），需要一种**通用的、与插件解耦的方式**，将 ClickHouse 中的数据自动导入 WeKnora 知识库，实现：

1. AI 对话中可通过 RAG 检索到具体数据
2. 用户无需手动维护知识库，系统自动从已入库数据同步
3. 同步逻辑**不绑定任何具体插件**，直接基于 ClickHouse 表查询

## 核心设计原则

**与插件解耦**：同步服务直接使用 `db_client` 查询 ClickHouse 表，用户指定表名 + 筛选条件（如 ts_code、日期范围）+ 自定义 SQL，系统将查询结果转为 Markdown 导入知识库。不依赖任何插件模块。

## What Changes

### 1. 后端 — WeKnora Client 扩展 (`services/weknora_client.py`)

扩展 `WeKnoraClient`，新增知识文档管理 API：
- `create_manual_knowledge(kb_id, title, content, status="publish")` — 手工创建 Markdown 知识
- `update_manual_knowledge(knowledge_id, title, content, status)` — 更新已有知识
- `delete_knowledge(knowledge_id)` — 删除知识
- `list_knowledges(kb_id, page, page_size, keyword)` — 获取知识列表
- `get_knowledge(knowledge_id)` — 获取知识详情

### 2. 后端 — 知识同步服务 (`services/knowledge_sync_service.py`) [新增]

通用的 ClickHouse → WeKnora 同步服务，**不依赖任何插件**：

- **数据查询**：直接使用 `db_client.execute_query(sql)` 查询 ClickHouse，与 `DataExplorerService` 类似
- **表发现**：通过 `system.tables` 或已有的表发现机制列出可用表
- **Markdown 渲染**：将 DataFrame 查询结果转为可读的 Markdown 表格文档
- **同步策略**：
  - 用户指定：表名 + 筛选条件（ts_code、日期范围）或自定义 SQL
  - 每条同步记录生成唯一标题（如 `{table_name}-{ts_code}-{date_range}`），避免重复
  - 支持批量同步（多个表、多只股票）
  - 支持增量同步（仅同步新增数据）
- **文档结构**：将查询结果渲染为 Markdown 表格 + 数据摘要

### 3. 后端 — API 端点 (`modules/datamanage/router.py`)

新增知识同步管理 API：
- `POST /knowledge/sync` — 触发同步（参数：table_name、filters/sql、title_template）
- `GET /knowledge/sync/status` — 获取同步状态
- `GET /knowledge/sync/history` — 获取同步历史
- `GET /knowledge/documents` — 列出已导入的知识文档
- `DELETE /knowledge/documents/{id}` — 删除知识文档

### 4. 前端 — KnowledgeView.vue 增强

在现有知识库配置页面增加"知识同步"区域：
- 表选择器：列出所有可查询的 ClickHouse 表
- 筛选条件：ts_code（支持多选）、日期范围
- 自定义 SQL 模式：直接输入 SQL 查询
- 一键同步按钮 + 同步进度
- 已导入文档列表（分页、搜索、删除）

## Impact

- **后端改动**：扩展 `weknora_client.py`，新增 `knowledge_sync_service.py`，扩展 `router.py`
- **前端改动**：增强 `KnowledgeView.vue`
- **数据流**：ClickHouse（`db_client`）→ DataFrame → Markdown → WeKnora REST API
- **依赖**：需要 WeKnora 服务已部署且知识库已配置
- **不影响现有功能**：纯增量，不修改已有查询逻辑
- **解耦**：同步服务只依赖 `db_client` 和 `weknora_client`，不依赖任何插件

## API 细节（WeKnora 实测确认）

| WeKnora API | 方法 | 说明 |
|---|---|---|
| `/api/v1/knowledge-bases/{id}/knowledge/manual` | POST | 创建手工知识，body: `{title, content, status}` |
| `/api/v1/knowledge/manual/{id}` | PUT | 更新手工知识 |
| `/api/v1/knowledge/{id}` | GET/DELETE | 获取/删除知识 |
| `/api/v1/knowledge-bases/{id}/knowledge` | GET | 列出知识（分页） |

- `status: "publish"` 创建后自动分块+向量化，约 3-5 秒可搜索
- `status: "draft"` 创建后不处理，需手动发布
