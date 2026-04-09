# Change: Run MCP from the backend container

## Why
当前部署把 HTTP API (`backend`) 和 MCP Server (`mcp`) 拆成两个容器，但业务上它们共享同一套代码、同一组插件发现逻辑、同一份数据库与认证配置。继续拆分会带来额外的服务发现、端口和运维复杂度，而且与你要求的运行形态冲突。

## What Changes
- Remove the dedicated `mcp` container from Docker Compose application deployment.
- Run both backend HTTP API and MCP server processes inside the backend container.
- Preserve MCP protocol compatibility for existing clients, including the streamable HTTP `/messages` endpoint and legacy endpoint normalization.
- Keep separate external ports for backend API and MCP access while removing cross-container MCP service discovery.
- Update backend-side MCP fallback calls to target the backend container-local MCP endpoint instead of the `stock-mcp` service hostname.
- Update deployment and verification documentation to describe the single-container runtime topology.

## Impact
- Affected specs: `chat-orchestration`, `mcp-runtime-topology`
- Affected code:
  - `src/stock_datasource/services/http_server.py`
  - `src/stock_datasource/services/mcp_server.py`
  - `src/stock_datasource/services/mcp_client.py`
  - `docker-compose.yml`
  - `docker-compose.dev.yml`
  - verification scripts and README deployment docs