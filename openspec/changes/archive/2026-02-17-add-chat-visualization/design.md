## Context
智能对话平台的 Agent 通过工具调用获取大量结构化金融数据（K线、指标、财报、回测结果），但当前只由 LLM 转为文字描述输出。平台前端已有 6 个成熟的 ECharts 图表组件分别用于股票详情、指数对比、财报趋势等页面，但聊天界面未复用。

## Goals / Non-Goals
- Goals:
  - 工具调用自动触发可视化，不依赖 LLM 生成图表标记
  - 复用已有的 KLineChart、TrendChart、ProfitChart、IndexCompareChart 组件
  - 保持 SSE 流式协议向后兼容
- Non-Goals:
  - 不改变 Agent 路由、编排逻辑
  - 不新建图表组件（全部复用已有的）
  - 不改变 LLM 的文字分析输出

## Decisions

### Decision 1: SSE visualization 事件（而非 LLM 嵌入标记）
让工具函数返回数据时同步生成 visualization payload，通过 SSE `visualization` 事件发送到前端。
- 优势：100% 可靠，不依赖 LLM 格式遵从性
- 替代方案：让 LLM 在回复中嵌入 `[KLINE_CHART]` JSON — 不可靠，且与 COMMON_OUTPUT_RULES 矛盾

### Decision 2: 工具层生成 visualization 数据
在各 Agent 的工具函数（如 `get_kline`、`get_comprehensive_financial_analysis`）中，返回值增加 `_visualization` 字段。base_agent 的 `on_tool_end` 回调检测此字段并发射 visualization SSE 事件。
- 优势：逻辑内聚，每个工具自决定是否需要可视化和用哪个组件
- 替代方案：在 Orchestrator 层统一判断 — 过于耦合，难以扩展

### Decision 3: 组件映射表
前端使用组件名到实际组件的静态映射，支持以下图表类型：

| type | component | 数据来源 Agent/Tool |
|------|-----------|-------------------|
| kline | KLineChart | MarketAgent/get_kline, IndexAgent/get_kline |
| financial_trend | TrendChart | ReportAgent/get_comprehensive_financial_analysis |
| profit_curve | ProfitChart | BacktestAgent/run_simple_backtest |
| index_compare | IndexCompareChart | EtfAgent/compare_etf_with_index |

### Decision 4: visualization payload 格式
```json
{
  "type": "kline",
  "title": "贵州茅台(600519) 近60日K线",
  "props": {
    "data": [{"date":"2024-01-02","open":1800,"high":1820,"low":1790,"close":1810,"volume":50000}],
    "indicators": {"MA5": [...]},
    "selectedIndicators": ["MA5","MA20","MACD"]
  }
}
```

## Risks / Trade-offs
- 工具函数返回数据量增加（完整日线数据而非摘要）→ 通过限制默认天数（60天）和不压缩 `_visualization` 字段缓解
- SSE 单条 visualization 事件可能较大（~50KB）→ 可接受，远小于图片

## Open Questions
- 无
