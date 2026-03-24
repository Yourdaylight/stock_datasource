# Tasks: 开放 API 网关

## 0. 安全修复（前置）
- [x] 0.1 `cache_routes.py` 写操作加 `get_current_user`，flush 加 `require_admin`
- [x] 0.2 `workflow_routes.py` 所有操作加 `get_current_user`，删除加 `require_admin`
- [x] 0.3 `toplist_routes.py` 所有操作加 `get_current_user`
- [x] 0.4 `service_generator.py` 生成的插件路由默认需要 `get_current_user`

## 0.5 接口开放范围界定（前置，已完成）
- [x] 0.5.1 全面梳理系统三条路由注册路径（Plugin / Module / API）
- [x] 0.5.2 分析所有 Module 路由，标记含 AI/LLM 的端点
- [x] 0.5.3 确认开放范围：仅 `ServiceGenerator` 生成的 Plugin 路由
- [x] 0.5.4 更新 proposal/design/spec 文档，明确白名单和黑名单

## 1. 数据库层
- [x] 1.1 创建 `api_access_policies` 表 schema（接口开放策略）
- [x] 1.2 创建 `api_usage_log` 表 schema（统一调用日志）
- [x] 1.3 在 `http_server.py` lifespan 中确保表自动创建

## 2. 统一 API Key 认证中间件
- [x] 2.1 创建 `modules/open_api/__init__.py`
- [x] 2.2 创建 `modules/open_api/dependencies.py`（复用 MCP API Key 验证）
- [x] 2.3 支持 Header `Authorization: Bearer sk-xxx` 和 Query `?api_key=sk-xxx` 两种传入
- [x] 2.4 添加速率限制中间件（滑动窗口，基于 API Key 维度）

## 3. 开放 API 路由
- [x] 3.1 创建 `modules/open_api/router.py`（`/api/open/v1/{plugin}/{method}` 统一入口）
- [x] 3.2 实现请求参数透传到插件 service 方法
- [x] 3.3 实现响应格式统一封装（status, data, message, pagination）
- [x] 3.4 实现 `max_records` 限制（按策略表配置截断返回）

## 4. 访问策略管理
- [x] 4.1 创建 `modules/open_api/service.py`（策略 CRUD）
- [x] 4.2 实现策略缓存（避免每次请求查 ClickHouse）
- [x] 4.3 实现接口自动发现（**仅从 PluginManager 获取**可用接口列表，禁止扫描全局路由）
- [x] 4.4 创建管理 API 路由（`/api/open-api-admin/*`，需 `require_admin`）

## 5. 用量追踪
- [x] 5.1 实现调用日志异步写入 `api_usage_log` 表
- [x] 5.2 实现用量统计查询（按 API Key / 接口 / 时间段）
- [x] 5.3 在管理 API 中暴露用量统计接口

## 6. 前端管理面板
- [x] 6.1 创建 `ApiAccessView.vue`（管理员页面）
- [x] 6.2 实现接口列表展示（自动发现 + 开关控制）
- [x] 6.3 实现速率限制、最大记录数等参数配置
- [x] 6.4 实现调用日志和统计图表
- [x] 6.5 在前端路由注册 `/api-access`（`requiresAdmin`）

## 7. 接口文档自动生成
- [x] 7.1 实现 `GET /api/open/docs`（返回可用接口列表及参数说明）
- [x] 7.2 为每个开放接口生成示例 curl 命令
