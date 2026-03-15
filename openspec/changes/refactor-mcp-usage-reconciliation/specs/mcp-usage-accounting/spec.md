## ADDED Requirements

### Requirement: MCP quota usage reconciliation

The system SHALL reconcile MCP quota usage by polling aggregated usage from the MCP data service instead of relying on per-call push callbacks.

#### Scenario: Active entitlement is reconciled from usage summary

- **GIVEN** a user has an active MCP entitlement bound to a node
- **AND** the node has a reachable MCP server URL
- **AND** the MCP server returns `total_records = 1200` for `/usage/summary` since the entitlement `starts_at`
- **WHEN** the reconciliation scheduler runs
- **THEN** the system sets that entitlement's `quota_used` to `1200`

#### Scenario: One node fails without stopping the whole pass

- **GIVEN** multiple active MCP entitlements exist
- **AND** one node returns an authentication or network error for `/usage/summary`
- **WHEN** the reconciliation scheduler runs
- **THEN** the system records a failed item for that entitlement
- **AND** it continues reconciling the remaining entitlements

### Requirement: MCP data service usage logging remains local-first

The system SHALL record MCP tool usage locally in `stock_datasource` without requiring a synchronous callback to the quota service.

#### Scenario: Tool call succeeds while management service is unavailable

- **GIVEN** an authenticated MCP tool call returns records successfully
- **AND** `nps_enhanced` is unreachable
- **WHEN** `stock_datasource` finishes the tool call
- **THEN** it still writes the local MCP usage log entry
- **AND** it does not fail the request because a push callback could not be sent