# Change: Refactor MCP usage accounting to pull reconciliation

## Why

`stock_datasource` currently pushes usage deltas to `nps_enhanced` after each successful MCP tool call. That makes quota accounting depend on the management service being reachable in the request path, and it couples query success to an external callback that is not required to serve data.

## What Changes

- Remove active usage push reporting from `stock_datasource` MCP tool execution.
- Keep `stock_datasource` as the source of truth for raw MCP usage logs and `/usage/summary` aggregation.
- Add a periodic reconciliation job in `nps_enhanced` that pulls `/usage/summary` for active entitlements and overwrites `quota_used` with the aggregated total.
- Reuse the existing MCP bearer configuration for `/usage/summary` authentication.

## Impact

- Affected specs: `mcp-usage-accounting`
- Affected code: `src/stock_datasource/services/mcp_server.py`, Docker env/config for MCP service, `nps_enhanced` MCP quota scheduler and related tests