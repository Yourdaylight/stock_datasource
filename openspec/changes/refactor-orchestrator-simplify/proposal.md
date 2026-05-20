# Change: 精简 Orchestrator 为配置驱动 Harness 路径

## Why

`OrchestratorAgent` 当前保留旧 agent 扫描、AgentRuntime feature flag、Harness feature flag、MCP fallback、多 agent/arena 队列等多套执行路径，导致聊天主链路难以维护。`ConfigDrivenHarnessAgent` 已可从 DB 配置动态构建 agent，并通过 `tool_registry` 解析 skill/tool，具备成为默认路径的条件。

## What Changes

- 移除 `HARNESS_MODE_ENABLED` 与 `AGENT_RUNTIME_ENABLED` 双路径开关。
- 删除 `services/agent_runtime.py` 中间层，聊天调度直接进入 `ConfigDrivenHarnessAgent`。
- 精简 `agents/orchestrator.py`，仅保留意图分类、股票代码提取、配置驱动 agent 调度和 SSE 兼容包装。
- 删除无保留价值的废弃 agent 文件，并修正仍指向这些文件的兼容引用。
- 保留 `market_agent.py`、`report_agent.py`、`portfolio_agent.py` 的直接 import 兼容，但标记 deprecated。

## Impact

- Affected specs: `chat-orchestration`
- Affected code:
  - `src/stock_datasource/agents/orchestrator.py`
  - `src/stock_datasource/agents/config_driven_harness_agent.py`
  - `src/stock_datasource/services/agent_runtime.py`
  - deprecated files under `src/stock_datasource/agents/`
  - workflow/overview/daily-analysis references and related tests/docs
