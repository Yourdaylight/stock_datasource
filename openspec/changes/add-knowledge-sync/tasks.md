# Tasks: Add Knowledge Sync

## Phase 1: WeKnora Client 扩展

- [ ] 1.1 在 `WeKnoraClient` 中新增 `create_manual_knowledge()` 方法
- [ ] 1.2 新增 `update_manual_knowledge()` 方法
- [ ] 1.3 新增 `delete_knowledge()` 方法
- [ ] 1.4 新增 `list_knowledges()` 方法
- [ ] 1.5 新增 `get_knowledge()` 方法

## Phase 2: 知识同步服务（与插件解耦）

- [ ] 2.1 创建 `services/knowledge_sync_service.py` 骨架
- [ ] 2.2 实现通用表查询（直接使用 `db_client` 查询 ClickHouse，不依赖插件）
- [ ] 2.3 实现 Markdown 渲染引擎（DataFrame → Markdown 表格 + 数据摘要）
- [ ] 2.4 实现批量同步逻辑（按表名+筛选条件遍历，防重复）
- [ ] 2.5 实现同步状态跟踪和历史记录

## Phase 3: 后端 API

- [ ] 3.1 添加 `POST /knowledge/sync` 端点（触发同步，参数：table_name、filters/sql）
- [ ] 3.2 添加 `GET /knowledge/sync/status` 端点
- [ ] 3.3 添加 `GET /knowledge/sync/history` 端点
- [ ] 3.4 添加 `GET /knowledge/documents` 端点（列出已导入知识）
- [ ] 3.5 添加 `DELETE /knowledge/documents/{id}` 端点

## Phase 4: 前端增强

- [ ] 4.1 在 KnowledgeView.vue 添加"知识同步"区域
- [ ] 4.2 实现同步表单（表选择器、筛选条件、自定义 SQL）
- [ ] 4.3 实现已导入文档列表（分页、搜索、删除）
- [ ] 4.4 实现同步进度和历史展示
- [ ] 4.5 添加前端 API 调用函数

## Phase 5: 集成验证

- [ ] 5.1 端到端测试：触发同步 → WeKnora 知识创建 → 搜索验证
- [ ] 5.2 Docker 环境验证
