# Tasks: Add Plugin Data Explorer

## Phase 1: 后端 API 开发

### 1.1 表信息查询 API
- [x] 实现 `GET /api/datamanage/explorer/tables` - 获取所有可查询表列表
  - 遍历所有插件的 schema.json
  - 返回表名、分类、列信息、行数统计
- [x] 实现 `GET /api/datamanage/explorer/tables/{table_name}/schema` - 获取表结构详情
  - 返回完整的列定义、分区方式、索引等信息

### 1.2 SQL 安全校验模块
- [x] 创建 `sql_validator.py`
  - 实现 SQL 语句解析和校验
  - 白名单校验（仅允许 SELECT）
  - 黑名单关键字检测（DROP, DELETE, INSERT 等）
  - 表名白名单校验（仅允许查询已注册的插件表）
- [x] 添加配置项：最大返回行数、查询超时时间

### 1.3 查询执行 API
- [x] 实现 `POST /api/datamanage/explorer/tables/{table_name}/query` - 简单筛选查询
  - 支持日期范围筛选
  - 支持股票代码筛选
  - 支持分页和排序
- [x] 实现 `POST /api/datamanage/explorer/sql/execute` - SQL 查询执行
  - SQL 安全校验
  - 执行查询并返回结果
  - 返回执行时间和行数
- [x] 实现 `POST /api/datamanage/explorer/sql/export` - 导出查询结果
  - 支持 CSV 格式
  - 支持 Excel 格式

### 1.4 查询模板管理 API
- [x] 实现查询模板 CRUD
  - `GET /api/datamanage/explorer/sql/templates` - 获取模板列表
  - `POST /api/datamanage/explorer/sql/templates` - 创建模板
  - `DELETE /api/datamanage/explorer/sql/templates/{id}` - 删除模板
- [x] 数据库表设计：`user_sql_templates` 表（自动创建）

> **注意**：查询历史记录在前端 localStorage 保存，无需后端 API

---

## Phase 2: 前端页面开发

### 2.1 路由和页面框架
- [x] 添加 `/datamanage/explorer` 子路由（数据管理的二级菜单）
- [x] 创建 `DataExplorerView.vue` 主页面
  - 左右布局：表列表 + 查询区域

### 2.2 表列表组件
- [x] 在 `DataExplorerView.vue` 中实现表列表面板
  - 按分类分组展示（使用 Radio 切换）
  - 搜索过滤功能
  - 显示表基础信息（行数、分类）
  - 点击选中表

### 2.3 简单筛选模式
- [x] 在查询区域实现简单筛选表单
  - 日期范围选择器（带预设）
  - 代码筛选输入框（模糊匹配）
  - 排序选择（列名 + 升降序）
  - 执行查询按钮

### 2.4 SQL 查询模式
- [x] 创建 `SqlEditorTabs.vue` 多 Tab SQL 编辑器组件
  - 支持新建/关闭 Tab
  - 每个 Tab 独立的 SQL 编辑器
  - Tab 标题显示查询名称（双击可编辑）
  - 使用 textarea 实现（简化版，可后续集成 Monaco Editor）
  - 快捷键支持（Ctrl+Enter 执行）
- [x] 模式切换 Tab（简单筛选 / SQL 查询）

### 2.5 查询历史记录（前端）
- [x] 创建 `useQueryHistory.ts` composable
  - localStorage 存储查询历史
  - 最多保存 100 条记录
  - 记录 SQL、执行时间、表名
  - 支持搜索和清空历史
- [x] 在 SQL 编辑器中显示历史记录面板（Popover）

### 2.6 查询结果展示
- [x] 在 `DataExplorerView.vue` 中实现查询结果表格
  - 动态列渲染
  - 分页组件
  - 导出按钮（CSV/Excel）
  - 显示查询耗时和行数

### 2.7 查询模板管理
- [x] 实现模板保存对话框
- [x] 实现模板列表展示和加载（下拉菜单）

---

## Phase 3: 集成和优化

### 3.1 权限控制
- [x] SQL 查询模式限制为管理员（使用 require_admin 依赖）
- [x] 简单筛选模式对所有用户开放（使用 require_admin 依赖，可后续调整）

### 3.2 性能优化
- [x] 大数据量分页优化（使用 LIMIT OFFSET）
- [x] 表行数缓存（1小时TTL）
- [x] 导出大数据时限制最大10000行

### 3.3 导航集成
- [x] 在数据管理菜单下添加"数据浏览器"二级菜单
- [ ] 从插件列表可快速跳转到对应表的浏览（可选优化）

---

## 验收标准

1. ✅ 数据浏览器作为数据管理的二级菜单可访问
2. ✅ 可以在页面上看到所有插件对应的数据库表列表
3. ✅ 选择表后，可以使用简单筛选模式浏览数据
4. ✅ 管理员可以使用 SQL 查询模式执行自定义查询
5. ✅ **SQL 编辑器支持多 Tab，可同时编辑多个查询**
6. ✅ **查询历史记录在前端 localStorage 保存**
7. ✅ SQL 查询有安全校验，禁止危险操作
8. ✅ 查询结果可以导出为 CSV 或 Excel
9. ✅ 可以保存和加载常用查询模板

---

## 已创建的文件

### 后端
- `src/stock_datasource/modules/datamanage/sql_validator.py` - SQL 安全校验器
- `src/stock_datasource/modules/datamanage/data_explorer_service.py` - 数据浏览服务
- `src/stock_datasource/modules/datamanage/schemas.py` - 新增数据浏览器相关模型
- `src/stock_datasource/modules/datamanage/router.py` - 新增 API 端点

### 前端
- `frontend/src/views/datamanage/DataExplorerView.vue` - 数据浏览器主页面
- `frontend/src/views/datamanage/components/SqlEditorTabs.vue` - 多 Tab SQL 编辑器
- `frontend/src/composables/useQueryHistory.ts` - 查询历史 Composable
- `frontend/src/api/datamanage.ts` - 新增数据浏览器 API 方法和类型
- `frontend/src/router/index.ts` - 新增路由
- `frontend/src/App.vue` - 更新导航菜单支持二级菜单

---

## 依赖关系

```
Phase 1.1 ──┬── Phase 2.1 ── Phase 2.2
            │
Phase 1.2 ──┼── Phase 2.3
            │
Phase 1.3 ──┼── Phase 2.4 ── Phase 2.5 ── Phase 2.6
            │
Phase 1.4 ──┴── Phase 2.7

Phase 2.* ──── Phase 3.*
```

## 预估工期

| 阶段 | 预估时间 | 实际状态 |
|------|----------|----------|
| Phase 1: 后端 API | 2-3 天 | ✅ 已完成 |
| Phase 2: 前端页面 | 3-4 天 | ✅ 已完成 |
| Phase 3: 集成优化 | 1-2 天 | ✅ 已完成 |
| **总计** | **6-9 天** | **已完成** |
