# QMT market data integration tasks

## 1. OpenSpec

- [ ] 1.1 Create proposal, design, tasks, and spec delta files.
- [ ] 1.2 Validate with `openspec validate add-qmt-plugin --strict`.
- [ ] 1.3 Get proposal approval before production implementation.

## 2. QMT gateway client

- [ ] 2.1 Add QMT gateway settings.
- [ ] 2.2 Implement QMT gateway client health check and request helpers.
- [ ] 2.3 Implement typed errors for unavailable gateway, timeout, auth failure, and malformed response.
- [ ] 2.4 Add tests for gateway client behavior using controlled HTTP responses.

## 3. Historical provider integration

- [ ] 3.1 Add lightweight historical provider abstraction and provider resolution.
- [ ] 3.2 Implement QMT historical provider using QMT gateway client.
- [ ] 3.3 Implement QMT daily and minute normalizers to canonical plugin schemas.
- [ ] 3.4 Add `data_source` and `available_data_sources` config support for selected行情 plugins.
- [ ] 3.5 Route `tushare_daily` to TuShare or QMT based on per-run override or default config.
- [ ] 3.6 Route `tushare_stk_mins` to TuShare or QMT based on per-run override or default config.
- [ ] 3.7 Validate QMT historical writes against real ClickHouse data where QMT gateway is available.

## 4. Data-source selection UI/API

- [ ] 4.1 Extend backend plugin info/config schemas with `data_source` and `available_data_sources`.
- [ ] 4.2 Extend sync request schema with optional `data_source`.
- [ ] 4.3 Pass selected data source into sync task execution and plugin run parameters.
- [ ] 4.4 Add frontend API types for data-source fields.
- [ ] 4.5 Add data-source selector to sync dialog for multi-provider plugins.
- [ ] 4.6 Add plugin default data-source display/configuration in plugin detail/config UI.

## 5. Realtime QMT data

- [ ] 5.1 Implement QMT realtime collector and normalizer.
- [ ] 5.2 Implement realtime cache store and service queries.
- [ ] 5.3 Implement ClickHouse sink for realtime QMT records.
- [ ] 5.4 Add router only if the existing UI/API needs direct QMT realtime endpoints.
- [ ] 5.5 Add realtime tests and a QMT-enabled smoke test path.

## 6. Verification

- [ ] 6.1 Run OpenSpec validation.
- [ ] 6.2 Run targeted backend tests for provider routing, normalization, datamanage API, and QMT gateway client.
- [ ] 6.3 Run targeted frontend checks for the data-source selector.
- [ ] 6.4 Run real DB validation for historical QMT ingestion on a QMT-enabled environment.
- [ ] 6.5 Confirm no live trading APIs are called in this change.
