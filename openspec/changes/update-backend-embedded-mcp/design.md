## Context
当前系统存在两个运行中的 FastAPI 服务：
- `http_server.py` 提供主业务 API
- `mcp_server.py` 提供 MCP streamable-http / SSE 接口

两者都运行在相同代码仓库和相同镜像之上，但 Compose 层把它们拆成了 `stock-backend` 与 `stock-mcp` 两个容器。最近的 MCP fallback 故障已经暴露出该拆分引入的额外复杂度：容器内默认 URL、服务名、端口路径和文档都需要保持同步。

## Goals / Non-Goals
- Goals:
  - 让 MCP 不再作为独立容器部署
  - 保持 backend API 与 MCP server 继续使用独立进程和独立监听端口
  - 保持现有 MCP 协议能力与认证逻辑不回退
  - 尽量不改变外部客户端使用方式，尤其是 `/messages` 协议入口
  - 让 backend 内部 MCP fallback 不再依赖 `stock-mcp` 服务发现
- Non-Goals:
  - 不重写 MCP 协议实现
  - 不改变 MCP 工具注册和权限模型
  - 不在本次变更中重构插件发现机制

## Decisions
- Decision: backend 容器内同时运行两个进程，一个负责主 HTTP API，一个负责 MCP server。
  - Why: 这样满足“mcp 必须放在 backend 里面”的约束，同时保留现有 `mcp_server.py` 的独立应用边界，避免一次性把两套 FastAPI app、中间件、healthcheck 和初始化逻辑强行合并。

- Decision: backend 容器对外继续保留两个端口映射，业务 API 和 MCP 分别暴露。
  - Why: 这能最大限度保持当前外部接入方式不变。客户端仍然使用 MCP 专用端口，前端/API 仍然使用业务端口，但部署层面只有一个应用容器。

- Decision: 保留 MCP 路径语义，不把 MCP 端点改到业务 API 前缀下。
  - Why: 现有 MCP 客户端和外部集成已经使用 `/messages`、`/sse`、`/info`、`/usage/summary`。如果直接改成 `/api/mcp/*`，会产生不必要的兼容性断裂。

- Decision: backend 容器内的 MCP 进程监听本地 `8001`，HTTP API 进程继续监听业务端口。
  - Why: 这保留了现有 MCP server 的运行方式和健康检查方式，只把进程承载位置从独立容器迁移到 backend 容器。

- Decision: backend 内部默认 MCP URL 改为容器本地地址，而不是 Docker 服务名 `stock-mcp`。
  - Why: 合并后不应该再依赖跨容器服务发现。

## Risks / Trade-offs
- backend 容器需要有一个可靠的进程管理方案，否则任一子进程退出都可能导致容器状态与实际可用性不一致。
- 健康检查需要从“单进程单端口”调整为覆盖 HTTP API 和 MCP 两个子进程，避免只检查到其中一个。
- 日志输出需要区分 backend API 与 MCP server，避免两个进程混在一起难以排查。

## Migration Plan
1. 为 backend 容器增加进程启动器，同时拉起 HTTP API 进程和 MCP server 进程。
2. 更新 `docker-compose.yml` / `docker-compose.dev.yml`，移除独立 `mcp` 服务，把 `8001` 端口映射到 backend 容器。
3. 更新 `MCPClient` 默认地址解析与 backend 内部 fallback 路径。
4. 更新 backend 容器 healthcheck / 日志策略，确保两条进程链路都可观测。
5. 更新 README 与验证脚本，说明 MCP 已改为 backend 容器内进程。
6. 验证：
   - `http://localhost:8001/messages` 可正常握手
   - backend 内 chat MCP fallback 正常调用
   - 不再需要 `stock-mcp` 容器

## Open Questions
- backend 容器内采用什么进程管理方式最合适：简易 shell 启动器、`supervisord`，还是项目内自带的 Python launcher？本提案先不锁死实现，只要求具备可重启与可观测性。