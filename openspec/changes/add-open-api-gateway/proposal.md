# Change: 添加开放 API 网关（Open API Gateway）

## Why
当前系统的数据查询接口仅供内部前端使用，外部用户（量化开发者、数据分析师）无法方便地查询数据。MCP Server 虽然有完善的认证体系，但使用门槛较高（需 MCP 客户端）。需要提供一套标准 HTTP 查询接口，复用已有 API Key 认证体系，让外部用户可通过 curl/Python/任何 HTTP 客户端查询数据。

## ⚠️ 开放范围严格限定

**只有 Plugin 数据查询路由可以开放给外部用户**，即通过 `ServiceGenerator` 从 `src/stock_datasource/plugins/*/service.py` 自动生成的路由（`/api/{plugin_name}/{method}`）。

### 可开放（白名单）
仅限 `ServiceGenerator.generate_http_routes()` 生成的路由，这些是纯数据库查询接口：
- `/api/stock_daily/*` — A股日线
- `/api/etf_daily/*` — ETF日线
- `/api/hk_daily/*` — 港股日线
- `/api/stock_basic/*` — 股票基本信息
- 以及其他所有 `plugins/` 下注册的数据插件

### 绝对禁止开放（黑名单）

| 类别 | 路由前缀 | 原因 |
|------|----------|------|
| **系统认证** | `/auth/*` | 登录注册、JWT令牌，暴露会导致安全灾难 |
| **AI/LLM** | `/chat/*`, `/api/workflows/*` | 对话交互、AI工作流，消耗大量 LLM 资源 |
| **管理后台** | `/datamanage/*`, `/api/cache/*`, `/api/system_logs/*` | 管理员功能，外部不可触及 |
| **用户私有数据** | `/portfolio/*`, `/memory/*`, `/user_llm_config/*`, `/mcp_api_key/*` | 用户隐私数据 |
| **前端业务模块** | `/market/*`, `/screener/*`, `/report/*`, `/index/*`, `/etf/*`, `/overview/*`, `/ths-index/*`, `/news/*`, `/hk-report/*`, `/financial-analysis/*`, `/quant/*`, `/realtime/*`, `/realtime_kline/*`, `/backtest/*`, `/arena/*` | 内含 AI 分析接口和复杂业务逻辑，非纯数据查询 |
| **策略/榜单** | `/api/strategies/*`, `/api/toplist/*` | 含 AI 报告生成和策略逻辑 |
| **统计监控** | `/mcp-usage/*`, `/token/*` | 系统内部统计 |

### 界定原则
- **技术边界清晰**: Plugin 路由由 `ServiceGenerator` 自动生成，走独立的注册路径 `_register_services()`；Module 路由通过 `_register_module_routes()` 注册，两者完全隔离
- **默认不开放**: 新注册的插件接口默认 `is_enabled=0`，需管理员手动启用
- **代码级强制**: Open API Gateway 只从 `PluginManager` 获取可用接口列表，而非扫描所有路由

## What Changes

### 安全修复（前置，已完成）
- **MODIFIED**: `cache_routes.py` — 写操作加 `get_current_user`，flush 加 `require_admin`
- **MODIFIED**: `workflow_routes.py` — 所有操作加 `get_current_user`，删除加 `require_admin`
- **MODIFIED**: `toplist_routes.py` — 所有操作加 `get_current_user`
- **MODIFIED**: `service_generator.py` — 生成的插件路由默认需要 `get_current_user`

### 开放 API 网关（新增）
- **ADDED**: 统一 API Key 认证中间件 `modules/open_api/dependencies.py` — 复用 MCP API Key (`sk-xxx`)，支持 Header/Query 两种传入方式
- **ADDED**: API 访问策略表 `api_access_policies` — 存储每个接口的开放状态、速率限制、最大返回记录数
- **ADDED**: API 用量日志表 `api_usage_log` — 统一追踪 HTTP/MCP 两端调用
- **ADDED**: 开放 API 路由 `modules/open_api/router.py` — `/api/open/v1/{plugin}/{method}` 统一入口，**仅代理 Plugin 数据查询接口**
- **ADDED**: 开放 API 管理后端 `modules/open_api/service.py` — 策略 CRUD、用量统计，**接口发现仅扫描 PluginManager 注册的插件**
- **ADDED**: 管理员配置面板 — 前端 `/admin/api-access` 页面，管理可开放接口
- **ADDED**: 自动接口文档 — `/api/open/docs` 展示可用接口及参数

## Impact
- Affected specs: `open-api-gateway` (新增)
- Affected code:
  - `src/stock_datasource/modules/open_api/` (新增)
  - `src/stock_datasource/core/service_generator.py` (已修改，加认证)
  - `src/stock_datasource/api/cache_routes.py` (已修改，加认证)
  - `src/stock_datasource/api/workflow_routes.py` (已修改，加认证)
  - `src/stock_datasource/api/toplist_routes.py` (已修改，加认证)
  - `src/stock_datasource/services/http_server.py` (注册新路由)
  - `src/stock_datasource/modules/mcp_api_key/` (复用)
  - `frontend/src/views/admin/ApiAccessView.vue` (新增)

## Technical Decisions
- **开放范围**: 仅限 Plugin 数据查询路由（`ServiceGenerator` 生成），系统/AI/管理/模块路由一律不开放
- **认证方式**: 复用 MCP API Key (`sk-xxx`)，不另造认证体系
- **路由前缀**: `/api/open/v1/` 独立命名空间，与内部路由隔离
- **权限管控**: ClickHouse `api_access_policies` 表存储策略，管理员通过面板配置
- **速率限制**: 基于 API Key 维度，滑动窗口算法（内存 + Redis）
- **用量追踪**: 复用并扩展 `mcp_tool_usage_log` 思路，新建 `api_usage_log` 表统一追踪
- **接口发现**: 从 `PluginManager.get_plugins()` 获取可开放接口，不扫描 `app.routes`
