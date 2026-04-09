## 1. Implementation
- [x] 1.1 Add a backend-container process launcher that starts both the HTTP API process and the MCP server process.
- [x] 1.2 Update Compose deployment to remove the dedicated `mcp` service and map the MCP port to the backend container.
- [x] 1.3 Update `mcp_client.py` and backend MCP fallback defaults to target the backend-container-local MCP endpoint.
- [x] 1.4 Update backend container health checks and logging to cover both processes.
- [x] 1.5 Update verification scripts and docs that still refer to a standalone MCP container or `/mcp` endpoint.

## 2. Validation
- [x] 2.1 Verify the backend container serves MCP handshake and tool listing successfully on the MCP port.
- [x] 2.2 Verify chat MCP fallback works with the embedded endpoint.
- [x] 2.3 Verify Docker deployment no longer starts a `stock-mcp` container.