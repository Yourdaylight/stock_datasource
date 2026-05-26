# Design: QMT market data integration

## Context

The project uses `BasePlugin` for data plugins and has existing source-specific implementations such as TuShare and AKShare. Some existing work already points toward logical plugins with replaceable sources, for example `tushare_hk_daily` keeps the business-facing plugin name while `config.json` sets `data_source = "yfinance"` and maps yfinance fields back to TuShare-compatible columns.

QMT introduces two distinct needs:

1. Historical market data should behave like another provider for existing logical行情 plugins.
2. Realtime data should use a long-running collector/cache/sink flow, consistent with existing realtime modules rather than the batch plugin pipeline.

## Goals / Non-Goals

### Goals

- Configure QMT gateway access for remote trading-machine deployments and localhost deployments.
- Route selected historical行情 plugins to `tushare` or `qmt` through a data-source provider abstraction.
- Normalize QMT historical data to each plugin's canonical schema before validation and loading.
- Let users select default provider and per-sync provider in the data management UI.
- Provide QMT realtime quote/snapshot collection with cache-first reads and optional ClickHouse persistence.
- Keep QMT live trading as a documented future boundary.

### Non-Goals

- Do not submit, cancel, or persist live broker orders.
- Do not make `xtquant` a hard dependency of the main Linux service.
- Do not create a source-specific `qmt_history_kline` logical plugin unless a future spec defines it as a separate business capability.
- Do not refactor every existing plugin into a full provider registry in this milestone.

## Decisions

### 1. Remote gateway first

QMT access is mediated by a configured gateway:

```text
QMT/xtquant workstation -> QMT Gateway -> stock_datasource QmtGatewayClient
```

Settings:

```python
QMT_ENABLED: bool = False
QMT_GATEWAY_URL: str = "http://localhost:58610"
QMT_GATEWAY_TIMEOUT: int = 10
QMT_GATEWAY_TOKEN: str = ""
QMT_HISTORY_DEFAULT_PERIOD: str = "1d"
QMT_REALTIME_ENABLED: bool = False
QMT_REALTIME_MARKETS: str = "a_stock,etf,index"
```

The gateway token is runtime configuration only and must not be stored in plugin `config.json`.

### 2. Historical data provider routing

Historical data uses a small provider abstraction:

```text
HistoricalDataProvider.extract(params) -> DataFrame in source-native shape
normalizer.normalize(data) -> DataFrame in plugin canonical shape
```

Initial provider support is intentionally narrow:

- `tushare_daily`: `data_source = "tushare" | "qmt"`
- `tushare_stk_mins`: `data_source = "tushare" | "qmt"`

The plugin remains the business entry point. Provider selection can come from:

1. per-sync request override: `data_source`
2. persisted plugin default: `config.data_source` or runtime override
3. plugin default provider

Canonical daily fields:

```text
ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount, version, _ingested_at
```

Canonical minute fields:

```text
ts_code, trade_time, freq, open, high, low, close, vol, amount, version, _ingested_at
```

If a target table can safely add a `source` column, store `source = "qmt"`. If table compatibility prevents that, record the provider in task metadata/logs and document the limitation.

### 3. UI and API provider selection

Current sync flow only passes `plugin_name`. This change adds provider selection without breaking existing behavior.

Backend additions:

- `PluginConfig.data_source: str | None`
- `PluginConfig.available_data_sources: list[str]`
- `PluginInfo.data_source: str | None`
- `PluginInfo.available_data_sources: list[str]`
- `TriggerSyncRequest.data_source: str | None`

Frontend additions:

- Plugin detail/config UI shows default data source for multi-provider plugins.
- Sync dialog shows a "本次数据源" selector only when `available_data_sources.length > 1`.
- If the user does not choose a provider, backend uses the configured default.

### 4. Realtime data module

Realtime QMT data uses module/service style:

```text
src/stock_datasource/modules/qmt_realtime/
├── collector.py
├── service.py
├── sync_service.py
├── cache_store.py
└── router.py (if API exposure is needed)
```

Flow:

```text
QMT Gateway -> QmtGatewayClient -> collector -> normalizer -> cache -> ClickHouse sink -> service/router
```

Realtime fields include latest price, bid/ask levels when available, volume, amount, timestamp, market, and code.

### 5. Future live trading seam

Future live trading should be a separate OpenSpec change and should introduce explicit modules for:

- broker connection
- account/balance query
- position sync
- order submit/cancel
- order/trade callbacks
- risk checks
- order/account persistence

This change must not call QMT live trading APIs.

## Risks

- QMT gateway response shapes may vary by local implementation. Mitigation: keep gateway client and normalizers isolated and test normalization independently.
- Existing ODS schemas may not accept a `source` column without migration impact. Mitigation: add the column only where safe; otherwise persist source in task metadata/logs.
- UI provider selection can confuse users if shown everywhere. Mitigation: only show the selector for plugins with multiple supported providers.
