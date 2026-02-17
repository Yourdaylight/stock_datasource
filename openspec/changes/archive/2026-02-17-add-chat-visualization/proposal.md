# Change: Add Chat Visualization with Reusable Chart Components

## Why
智能对话中的量化分析结果（K线、技术指标、财报趋势、回测收益曲线等）目前只有纯文字输出，缺失可视化展示。前端已有 6 个成熟的图表组件（KLineChart、TrendChart、ProfitChart 等），但未被聊天界面复用。现有的 `[KLINE_CHART]` 标记机制是死代码——后端 Agent 从不生成该标记。

## What Changes
- 新增 SSE `visualization` 事件类型，工具调用后自动携带结构化图表数据
- 后端 Agent 工具层（MarketAgent、ReportAgent、BacktestAgent、IndexAgent、EtfAgent）在返回数据时同步生成 visualization payload
- 前端 MessageList 新增动态组件渲染逻辑，收到 visualization 事件后渲染对应的已有图表组件
- 移除不可达的 `[KLINE_CHART]` 内联 echarts 死代码

## Impact
- Affected specs: chat-visualization (new)
- Affected code:
  - Backend: `agents/base_agent.py`, `agents/market_agent.py`, `agents/report_agent.py`, `agents/backtest_agent.py`, `agents/index_agent.py`, `agents/etf_agent.py`, `modules/chat/router.py`
  - Frontend: `api/chat.ts`, `stores/chat.ts`, `views/chat/components/MessageList.vue`
  - Reused: `components/charts/KLineChart.vue`, `components/report/TrendChart.vue`, `components/ProfitChart.vue`, `components/market/IndexCompareChart.vue`
