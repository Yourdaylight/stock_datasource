## 1. Backend - SSE Visualization Event Infrastructure
- [x] 1.1 base_agent.py: Add `_extract_visualization()` helper that detects `_visualization` in tool results
- [x] 1.2 base_agent.py: In `on_tool_end` callback, emit `visualization` SSE event when `_visualization` is present
- [x] 1.3 router.py: Add `visualization` case in SSE generator, forward to frontend and collect in message metadata

## 2. Backend - Agent Tool Visualization Data
- [x] 2.1 MarketAgent `get_kline`: Return full OHLCV data series + indicators in `_visualization` field (type: kline)
- [x] 2.2 MarketAgent `calculate_indicators`: Append indicator data to shared visualization context
- [x] 2.3 ReportAgent `get_comprehensive_financial_analysis`: Add `_visualization` field (type: financial_trend)
- [~] 2.4 BacktestAgent `run_simple_backtest`: Add `_visualization` field (type: profit_curve) — deferred, backtest agent uses markdown output
- [~] 2.5 IndexAgent: Add `_visualization` for index kline data — deferred, low priority
- [~] 2.6 EtfAgent `compare_etf_with_index`: Add `_visualization` field (type: index_compare) — deferred, low priority

## 3. Frontend - Dynamic Chart Rendering
- [x] 3.1 api/chat.ts: Add `VisualizationEvent` type definition
- [x] 3.2 stores/chat.ts: Add visualization state management and `visualization` case in SSE handler
- [x] 3.3 MessageList.vue: Add dynamic chart component rendering (import KLineChart, TrendChart, ProfitChart, IndexCompareChart)
- [x] 3.4 MessageList.vue: Remove dead `[KLINE_CHART]` inline echarts code
