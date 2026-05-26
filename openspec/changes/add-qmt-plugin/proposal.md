# Change: Add QMT market data integration

## Why

Users need QMT as a selectable data source for local/near-realtime market data and future live trading workflows. Historical data should reuse the existing logical plugin model instead of creating source-specific QMT plugins, so users can switch providers such as TuShare and QMT without changing the business-facing plugin entry point.

## What Changes

- Add QMT gateway configuration for remote QMT/xtquant access, with localhost supported for same-machine deployments.
- Add QMT as a historical market-data provider for logical行情 plugins, using provider routing and field normalization to the existing canonical plugin schemas.
- Add UI/API support for selecting default and per-sync data sources for plugins that support multiple providers.
- Add QMT realtime market data collection through a dedicated realtime module that uses cache-first serving and optional ClickHouse persistence.
- Document future live trading boundaries for QMT broker/account/order integration, without implementing real order submission in this change.

## Impact

- Affected specs: `qmt-market-data`
- Affected backend code:
  - `src/stock_datasource/config/settings.py`
  - `src/stock_datasource/modules/qmt_gateway/`
  - `src/stock_datasource/core/data_sources/` or equivalent provider abstraction
  - `src/stock_datasource/data_sources/qmt/`
  - selected historical market plugins such as `tushare_daily` and `tushare_stk_mins`
  - `src/stock_datasource/modules/datamanage/` schemas/service/router
  - `src/stock_datasource/modules/qmt_realtime/`
- Affected frontend code:
  - `frontend/src/api/datamanage.ts`
  - `frontend/src/views/datamanage/components/SyncDialog.vue`
  - plugin detail/config UI in `frontend/src/views/datamanage/`
- Dependencies:
  - The main project does not hard-depend on `xtquant`.
  - QMT/xtquant runs behind a configured QMT gateway on a trading workstation or localhost.
