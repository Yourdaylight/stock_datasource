# Design: 开放 API 网关

## Context
当前系统有两个服务端口：HTTP Server (8000) 和 MCP Server (8001)。MCP 端有完善的认证 (API Key + JWT)、配额和用量追踪，但使用门槛高。HTTP 端的插件路由无认证，内部业务路由认证覆盖不完整。需要在 HTTP 端构建一套面向外部用户的开放 API 层。

### 利益相关方
- **外部用户**: 量化开发者、数据分析师 — 需要简单的 HTTP 查询接口
- **管理员**: 控制哪些接口开放、设置速率限制
- **AI 用户**: 通过 MCP 协议调用 — 已有完善支持

## ⚠️ 开放范围限定 — 核心设计约束

### 系统路由全景分类

系统中的 HTTP 路由通过三条独立路径注册：

```
http_server.py
    │
    ├── _register_services()          ← ✅ Plugin 路由（可开放）
    │   └── ServiceGenerator.generate_http_routes()
    │       └── /api/{plugin_name}/{method}
    │           └── 纯数据库查询（ClickHouse）
    │
    ├── _register_module_routes()     ← ❌ Module 路由（禁止开放）
    │   └── get_all_routers()
    │       ├── /auth/*              系统认证
    │       ├── /chat/*              AI 对话（LLM）
    │       ├── /market/*            行情分析（含 AI）
    │       ├── /screener/*          智能选股（含 AI）
    │       ├── /report/*            财报研读（含 AI）
    │       ├── /datamanage/*        数据管理（管理员）
    │       ├── /portfolio/*         持仓管理（用户私有）
    │       ├── /memory/*            用户记忆（用户私有）
    │       ├── /index/*             指数选股（含 AI）
    │       ├── /etf/*               ETF 分析（含 AI）
    │       ├── /overview/*          市场概览（含 AI）
    │       ├── /ths-index/*         板块指数
    │       ├── /news/*              新闻资讯（含 AI 情感分析）
    │       ├── /arena/*             Agent 竞技场
    │       ├── /hk-report/*         港股财报（含 AI）
    │       ├── /quant/*             量化选股
    │       ├── /realtime/*          实时分钟
    │       ├── /backtest/*          策略回测
    │       ├── /financial-analysis/* 财务分析（含 AI）
    │       ├── /mcp-usage/*         MCP 统计
    │       ├── /token/*             Token 用量
    │       ├── /user_llm_config/*   用户 LLM 配置
    │       └── /mcp_api_key/*       API Key 管理
    │
    └── 独立注册的 API 路由           ← ❌ 禁止开放
        ├── /api/strategies/*        策略管理（含 AI 生成）
        ├── /api/toplist/*           龙虎榜（含 AI 报告）
        ├── /api/workflows/*         AI 工作流（LLM）
        └── /api/cache/*             缓存管理（管理员）
```

### 为什么只开放 Plugin 路由

| 对比维度 | Plugin 路由 | Module/API 路由 |
|----------|-------------|-----------------|
| 生成方式 | `ServiceGenerator` 自动生成 | 手工编写 |
| 数据来源 | 纯 ClickHouse 查询 | ClickHouse + LLM + 外部服务 |
| AI 依赖 | ❌ 无 | ✅ 大量端点调用 LLM |
| 用户状态 | ❌ 无状态 | ✅ 依赖用户会话/配置 |
| 安全风险 | 低（只读查询） | 高（含写操作、管理功能） |
| 接口结构 | 统一（query/count/schema） | 各不相同 |
| 资源消耗 | 低（数据库查询） | 高（LLM Token 消耗） |

### 代码级强制隔离

Open API Gateway 在代码层面 **只** 通过 `PluginManager` 获取可代理的接口：

```python
# modules/open_api/router.py
from stock_datasource.plugins import PluginManager

# ✅ 只从 PluginManager 获取插件列表
available_plugins = plugin_manager.get_plugins()

# ❌ 绝对不扫描 app.routes 或 module routers
```

## Goals / Non-Goals

### Goals
- 复用现有 MCP API Key (`sk-xxx`) 体系，无需另建认证
- **仅开放 Plugin 数据查询接口，代码级隔离系统/AI/管理路由**
- 管理员可通过面板灵活控制接口开放粒度
- 统一 HTTP/MCP 两端的用量追踪
- 外部用户 curl 即可查询，零门槛

### Non-Goals
- 不构建独立的开放平台/开发者门户
- 不实现 OAuth2 / 第三方登录
- 不改变 MCP Server 现有认证流程
- 不做付费/计费系统
- **不开放任何 Module 路由**（即使其中包含纯数据查询端点，如 `/market/kline`）
- **不开放任何含 AI/LLM 调用的端点**

## Architecture

```
External User
    │
    │  curl -H "Authorization: Bearer sk-xxx"
    │  POST /api/open/v1/stock_daily/query
    ▼
┌─────────────────────────────────────────┐
│  Open API Gateway Layer                 │
│  (FastAPI Router: /api/open/v1/)        │
│                                         │
│  1. API Key 认证 (require_api_key)      │
│  2. 验证 {plugin} 在 PluginManager 中   │ ← 🔒 核心隔离点
│  3. 策略检查 (check_access)             │
│  4. 速率限制 (rate_limiter)             │
│  5. 请求转发到插件 service              │
│  6. 响应封装 + 记录限制                │
│  7. 异步写入用量日志                   │
└────────────┬────────────────────────────┘
             │
             │  只能到达 ↓
             ▼
┌─────────────────────────────────────────┐
│  Plugin Services（✅ 唯一可代理目标）    │
│  (BaseService subclasses)               │
│  stock_daily, etf_daily, hk_daily, ...  │
│  来源: plugins/*/service.py             │
└─────────────────────────────────────────┘

       ╳ 不可到达 ╳
┌─────────────────────────────────────────┐
│  Module Routes（❌ 完全隔离）            │
│  auth, chat, market, screener, report,  │
│  datamanage, portfolio, memory, ...     │
│  来源: modules/__init__.py              │
├─────────────────────────────────────────┤
│  API Routes（❌ 完全隔离）               │
│  strategies, toplist, workflows, cache  │
│  来源: api/*.py                         │
└─────────────────────────────────────────┘
```

## Decisions

### Decision 0: 开放范围仅限 Plugin 数据查询路由（最高优先级）
- **理由**: 系统路由通过三条独立路径注册，其中：
  - Plugin 路由：纯 ClickHouse 查询，无 AI 依赖，无状态，结构统一，资源消耗低
  - Module 路由：含 AI/LLM 调用（market、screener、report 等 13 个模块都有 AI 端点）、用户私有数据、管理后台
  - API 路由：含 AI 策略生成、AI 报告、管理功能
- **替代方案**: 从 Module 路由中挑选纯数据端点开放 — 维护成本高，容易遗漏 AI 端点导致资源滥用
- **结论**: 通过 `PluginManager` 获取可代理接口，代码级隔离，**绝不扫描 `app.routes` 或 module routers**

### Decision 1: 复用 MCP API Key 而非新建认证体系
- **理由**: 用户已在系统中创建 `sk-xxx` API Key，代码 (`McpApiKeyService`) 已有 hash 存储、过期检查、用量更新等完整逻辑
- **替代方案**: 新建 Open API 专用 token — 增加用户管理成本，代码重复
- **结论**: 复用 `sk-xxx`，在 `api_access_policies` 表中按 `api_path` 维度控制权限

### Decision 2: 独立路由前缀 `/api/open/v1/`
- **理由**: 与内部路由 (`/api/{plugin}/`) 隔离，可独立做版本控制、限流、日志
- **替代方案**: 在现有 `/api/{plugin}/` 上加认证 — 会影响内部前端调用流程
- **结论**: 新建独立前缀，内部路由保持用 JWT Bearer Token 认证

### Decision 3: 策略存 ClickHouse + 内存缓存
- **理由**: 与现有技术栈一致（全项目用 ClickHouse），策略变更频率低，内存缓存 5 分钟可接受
- **替代方案**: Redis 存储 — 引入额外依赖
- **结论**: ClickHouse 持久化 + dict 内存缓存（TTL 300s）

### Decision 4: 速率限制基于滑动窗口
- **理由**: 简单有效，基于 API Key + 接口维度
- **实现**: 优先使用 Redis（如已配置），否则退化为进程内 dict（单实例场景足够）
- **粒度**: 每分钟 / 每天两级限制，可按接口配置

## Database Schema

### api_access_policies
```sql
CREATE TABLE IF NOT EXISTS api_access_policies (
    policy_id String,
    api_path String,               -- e.g. 'stock_daily/query'
    api_type Enum8('http'=1, 'mcp'=2, 'both'=3),
    is_enabled UInt8 DEFAULT 0,
    rate_limit_per_min UInt32 DEFAULT 60,
    rate_limit_per_day UInt32 DEFAULT 10000,
    max_records UInt32 DEFAULT 5000,
    description String DEFAULT '',
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (api_path, api_type);
```

### api_usage_log
```sql
CREATE TABLE IF NOT EXISTS api_usage_log (
    log_id String,
    api_path String,
    api_type Enum8('http'=1, 'mcp'=2),
    user_id String DEFAULT '',
    api_key_id String DEFAULT '',
    record_count UInt32 DEFAULT 0,
    response_time_ms UInt32 DEFAULT 0,
    status_code UInt16 DEFAULT 200,
    error_message String DEFAULT '',
    client_ip String DEFAULT '',
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (api_path, created_at);
```

## Risks / Trade-offs

| Risk | Severity | Mitigation |
|------|----------|------------|
| API Key 泄露导致数据被滥用 | High | 速率限制 + 管理员可即时吊销 Key |
| 绕过 Gateway 直接调用内部路由 | High | 内部路由已加 JWT 认证（Phase 0），Open API Gateway 不暴露内部路由信息 |
| Module 路由中的 AI 端点被误纳入 | High | 代码级强制：仅通过 `PluginManager` 获取接口，不扫描全局路由 |
| 单进程内存限流不支持多实例 | Medium | 优先用 Redis；单实例部署时 dict 足够 |
| ClickHouse 策略查询延迟 | Low | 内存缓存 TTL 300s |
| 插件新增后管理员需手动开放 | Low | 默认不开放，安全优先 |

## Migration Plan
1. P0：安全修复（已完成）— 给裸奔路由加认证
2. P1：后端 Open API 模块 — 认证中间件 + 路由 + 策略管理（**接口发现仅从 PluginManager**）
3. P2：前端管理面板
4. P3：用量追踪 + 自动文档

回滚方案：删除 `modules/open_api/` 目录，去掉 `http_server.py` 中的路由注册即可，不影响已有功能。

## Open Questions
- 是否需要支持 API Key 按接口维度的细粒度权限（当前设计是全局策略 + Key 级别的配额）？
- 是否需要为开放接口提供 SDK（Python/JS）？可后续按需添加。
- 未来是否需要将 Module 路由中的纯数据查询端点（如 `/market/kline`）拆分为独立 Plugin？当前阶段保守不开放，后续可按需迁移。
