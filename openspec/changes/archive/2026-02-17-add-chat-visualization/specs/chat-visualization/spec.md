## ADDED Requirements

### Requirement: SSE Visualization Event
The system SHALL emit an SSE event of type `visualization` when an agent tool returns structured chart data, containing the chart type, component name, title, and props sufficient to render the corresponding frontend chart component.

#### Scenario: MarketAgent returns K-line data
- **GIVEN** a user asks "分析一下贵州茅台的K线"
- **WHEN** MarketAgent's `get_kline` tool returns data
- **THEN** an SSE `visualization` event SHALL be emitted with type `kline` and props containing `data` (array of OHLCV objects)

#### Scenario: ReportAgent returns financial analysis
- **GIVEN** a user asks "分析贵州茅台的财报"
- **WHEN** ReportAgent's `get_comprehensive_financial_analysis` tool returns data
- **THEN** an SSE `visualization` event SHALL be emitted with type `financial_trend` and props containing revenue, profit, and ratio trend data

#### Scenario: BacktestAgent returns backtest results
- **GIVEN** a user asks "用MACD策略回测贵州茅台"
- **WHEN** BacktestAgent's `run_simple_backtest` tool returns data
- **THEN** an SSE `visualization` event SHALL be emitted with type `profit_curve` and props containing portfolio value time series

### Requirement: Dynamic Chart Component Rendering
The frontend MessageList SHALL render visualization events using the corresponding reusable chart component (KLineChart, TrendChart, ProfitChart, IndexCompareChart) based on the `type` field, displaying charts inline within the assistant message.

#### Scenario: K-line chart rendered in chat
- **WHEN** a `visualization` event with type `kline` is received
- **THEN** the system SHALL render the KLineChart component with the event's props data inline in the message

#### Scenario: No chart data
- **WHEN** a tool returns no `_visualization` field
- **THEN** no visualization event SHALL be emitted and the message SHALL render as text-only

### Requirement: Visualization Data Persistence
The system SHALL persist visualization data in the message metadata so that charts can be re-rendered when loading historical messages.

#### Scenario: Reload chat with charts
- **GIVEN** a message with visualization data was previously sent
- **WHEN** the user reloads the chat session
- **THEN** the charts SHALL be re-rendered from persisted metadata
