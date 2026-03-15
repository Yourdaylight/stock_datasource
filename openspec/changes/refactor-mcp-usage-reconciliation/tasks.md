## 1. Implementation

- [x] 1.1 Add a periodic reconciliation scheduler in `nps_enhanced` for active MCP entitlements.
- [x] 1.2 Fetch `/usage/summary` from the configured MCP node and overwrite `quota_used` with the returned aggregate.
- [x] 1.3 Remove `stock_datasource` usage push reporting from MCP tool execution while keeping local usage logging and `/usage/summary`.
- [x] 1.4 Remove unused push-reporting Docker configuration from `stock_datasource`.
- [x] 1.5 Add targeted tests for reconciliation helpers and quota update behavior.