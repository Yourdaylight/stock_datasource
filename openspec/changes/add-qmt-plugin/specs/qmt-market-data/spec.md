## ADDED Requirements

### Requirement: QMT gateway configuration

The system SHALL support QMT market data access through a configurable gateway endpoint rather than requiring `xtquant` inside the main service process.

#### Scenario: Configure remote QMT gateway
- **GIVEN** an operator sets `QMT_ENABLED=true` and `QMT_GATEWAY_URL` to a remote QMT gateway URL
- **WHEN** the system initializes QMT market data access
- **THEN** it uses the configured gateway URL for QMT requests
- **AND** it does not import `xtquant` in the main service process

#### Scenario: Configure localhost QMT gateway
- **GIVEN** an operator runs QMT gateway on the same machine
- **WHEN** `QMT_GATEWAY_URL` is set to a localhost URL
- **THEN** QMT market data requests use the localhost gateway

#### Scenario: QMT gateway unavailable
- **GIVEN** QMT is selected as a data source
- **AND** the configured QMT gateway is unavailable
- **WHEN** the user starts a QMT-backed sync or realtime collection
- **THEN** the system fails gracefully with an actionable error message
- **AND** no partial invalid data is loaded

### Requirement: Historical market data provider selection

The system SHALL support QMT as a selectable provider for historical market data in logical行情 plugins.

#### Scenario: Use default provider
- **GIVEN** a historical行情 plugin has `data_source = "tushare"` as its default
- **WHEN** the user runs the plugin without a per-sync data-source override
- **THEN** the plugin uses the default TuShare provider

#### Scenario: Use QMT provider override
- **GIVEN** a historical行情 plugin supports providers `tushare` and `qmt`
- **WHEN** the user triggers sync with `data_source = "qmt"`
- **THEN** the plugin fetches historical data from the QMT provider
- **AND** the plugin name remains the logical plugin name rather than a QMT-specific plugin name

#### Scenario: Reject unsupported provider
- **GIVEN** a plugin supports only `tushare`
- **WHEN** the user triggers sync with `data_source = "qmt"`
- **THEN** the system rejects the request with a validation error
- **AND** no sync task is created

### Requirement: Historical data normalization

The system SHALL normalize QMT historical data into each logical plugin's canonical schema before validation and load.

#### Scenario: Normalize daily bars
- **GIVEN** QMT returns daily bar data for an A-share symbol
- **WHEN** the daily行情 plugin processes the response
- **THEN** the data is normalized to include `ts_code`, `trade_date`, `open`, `high`, `low`, `close`, `vol`, and `amount`
- **AND** plugin validation runs against those canonical fields

#### Scenario: Normalize minute bars
- **GIVEN** QMT returns minute bar data for an A-share symbol
- **WHEN** the minute行情 plugin processes the response
- **THEN** the data is normalized to include `ts_code`, `trade_time`, `freq`, `open`, `high`, `low`, `close`, `vol`, and `amount`
- **AND** plugin validation runs against those canonical fields

#### Scenario: Track QMT source
- **GIVEN** QMT data is written through a shared logical plugin table
- **WHEN** the target table supports source metadata
- **THEN** rows include `source = "qmt"`
- **AND** if the table cannot safely store `source`, the sync task or logs record QMT as the provider

### Requirement: Data-source selection UI

The system SHALL let users select a data source for plugins that support multiple market-data providers.

#### Scenario: Show provider selector for multi-source plugin
- **GIVEN** a plugin supports `tushare` and `qmt`
- **WHEN** the user opens the manual sync dialog
- **THEN** the UI shows a data-source selector with `tushare` and `qmt`
- **AND** the selector defaults to the plugin's configured default provider

#### Scenario: Hide provider selector for single-source plugin
- **GIVEN** a plugin supports only one provider
- **WHEN** the user opens the manual sync dialog
- **THEN** the UI does not show a data-source selector

#### Scenario: Persist default provider
- **GIVEN** a plugin supports multiple providers
- **WHEN** the user changes the plugin default data source in the configuration UI
- **THEN** future sync dialogs default to the selected provider
- **AND** existing users who do not change the setting retain the current default behavior

### Requirement: QMT realtime market data

The system SHALL collect QMT realtime market data through the QMT gateway and expose it through cache-first service APIs.

#### Scenario: Collect realtime quote
- **GIVEN** QMT realtime collection is enabled
- **WHEN** the collector requests realtime quotes from the gateway
- **THEN** quotes are normalized to the system realtime shape
- **AND** the latest quote is written to the realtime cache

#### Scenario: Persist realtime quote
- **GIVEN** realtime ClickHouse persistence is enabled
- **WHEN** normalized QMT realtime quotes are collected
- **THEN** the sink writes them to ClickHouse in batches

#### Scenario: Query latest realtime quote
- **GIVEN** a latest QMT realtime quote exists in cache
- **WHEN** a service consumer requests the latest quote for that symbol
- **THEN** the service returns the cached quote before falling back to ClickHouse

### Requirement: QMT trading remains out of scope

The system SHALL NOT perform live QMT order operations as part of this market data change.

#### Scenario: No live order submission
- **WHEN** QMT market data features are used
- **THEN** the system does not call live order submit or cancel APIs
- **AND** account, position, order, and trade callback support is left for a separate future change
