# Change: Add chat orchestrator agent with MCP fallback

## Why
当前智能对话入口缺少统一的“协调 Agent”进行意图解析与Agent调度，且未在无可用Agent时回退到MCP工具。需要建立可复用的调度模块，先接入chat入口，后续可扩展到其它分析入口。

## What Changes
- 新增“协调 Agent”用于chat入口：负责意图识别、Agent发现与选择、调度执行与回退策略。
- 当无可用Agent时，回退到MCP工具列表进行调度执行。
- 保持前端流式输出（SSE）全量展示中间过程与结果。

## Impact
- Affected specs: `chat-orchestration` (new)
- Affected code: `src/stock_datasource/modules/chat/*`, `src/stock_datasource/agents/*`, `src/stock_datasource/services/mcp_*`, frontend chat SSE handling
