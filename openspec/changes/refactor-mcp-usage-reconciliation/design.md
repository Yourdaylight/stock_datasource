## Context

The MCP data service already persists every successful tool invocation in `mcp_tool_usage_log` and exposes `/usage/summary`. `nps_enhanced` currently has quota purchase and entitlement models, but its usage accounting path assumes the data service will push increments back through `usage-report`.

## Goals / Non-Goals

- Goals:
  - Decouple MCP query latency and success from `nps_enhanced` availability.
  - Make quota accounting idempotent by reconciling against aggregated usage totals.
  - Reuse existing node configuration and bearer authentication.
- Non-Goals:
  - Removing the legacy `usage-report` endpoint from `nps_enhanced`.
  - Introducing a new cursor or ledger model for incremental reconciliation.

## Decisions

- Decision: `stock_datasource` remains the source of truth for raw usage rows.
  - Rationale: it already logs successful tool calls locally before any external reporting.
- Decision: `nps_enhanced` will periodically fetch `/usage/summary?username=...&since=<starts_at>` for each active entitlement.
  - Rationale: using `starts_at` makes reconciliation idempotent because the returned `total_records` represents the full entitlement window.
- Decision: reconciliation overwrites `quota_used` instead of incrementing it.
  - Rationale: overwrite semantics eliminate double-deduction risk after retries or scheduler restarts.
- Decision: authentication for `/usage/summary` uses node-level `mcp_policy_bearer` first, then existing global MCP bearer config.
  - Rationale: avoids adding a second secret just for reconciliation.

## Risks / Trade-offs

- Reconciliation is eventually consistent rather than immediate.
  - Mitigation: run the scheduler on a short interval and preserve local quota checks inside `stock_datasource`.
- A bad node URL or bearer leaves usage stale for that entitlement.
  - Mitigation: record scheduler failures and continue processing other entitlements.
- Full-window aggregation may become expensive for very long entitlements.
  - Mitigation: start with the simpler idempotent implementation; add cursor-based narrowing only if the query cost becomes material.

## Migration Plan

1. Deploy `stock_datasource` with push reporting removed but `/usage/summary` retained.
2. Deploy `nps_enhanced` with reconciliation enabled.
3. Let the first scheduler pass overwrite `quota_used` from the authoritative summary.

## Open Questions

- Whether the scheduler should later persist a dedicated reconciliation timestamp for observability, even if not needed for correctness.