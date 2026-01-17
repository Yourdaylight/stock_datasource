## Context
智能对话入口目前直接调用既有Agent与工具链，缺少统一调度层，也未在无可用Agent时回退到MCP工具。需要新增可复用的协调Agent模块，优先调度Agents目录中的Agent，必要时回退到MCP工具。

## Goals / Non-Goals
- Goals:
  - 仅接入chat入口；模块设计可复用，便于后续扩展至其他分析入口。
  - 优先使用Agents目录下Agent进行调度，各司其职。
  - 无可用Agent时，回退调用MCP工具。
  - 保持前端SSE流输出完整呈现（思考、工具、内容、完成）。
- Non-Goals:
  - 现在就改造ETF/指数/选股等分析入口。
  - 重新设计前端对话UI或协议格式。

## Decisions
- Decision: 新增OrchestratorAgent作为统一调度入口，作为chat模块的内部依赖。
- Decision: Agent发现基于Agents目录的注册/扫描机制，生成可用Agent列表与能力描述。
- Decision: 当Orchestrator无法匹配Agent时，使用MCP客户端列出工具并进行调度执行。

## Alternatives considered
- 直接在chat路由中硬编码Agent选择逻辑：不利于复用与扩展。
- 始终使用MCP工具，不使用本地Agent：与“优先Agent”的需求冲突。

## Risks / Trade-offs
- MCP工具调度可能引入响应耗时与错误边界增加；需明确回退与错误提示。

## Migration Plan
- 第一步：引入OrchestratorAgent并接入chat入口（不影响其它入口）。
- 第二步：将现有Agent调用路径迁移到统一调度逻辑。
- 第三步：加入MCP回退调用路径。

## Test Cases (curl)
> 约定：服务运行在 `http://127.0.0.1:8000`。

### 1) 创建会话
```bash
curl -s -X POST http://127.0.0.1:8000/api/chat/session
```

### 2) Agent 调度路径（SSE）
```bash
curl -N -H "Accept: text/event-stream" -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/chat/stream \
  -d '{"session_id":"<SESSION_ID>","content":"帮我分析 600519 的走势"}'
```
**期望**：SSE 返回 `thinking/content/done` 事件；`intent` 为 `market_analysis`，`agent` 为可用的市场分析类 Agent；`done.metadata` 包含 `intent/stock_codes/tool_calls`。

### 3) MCP 回退路径（SSE）
> 前置条件：让当前请求意图找不到可用 Agent（例如临时禁用对应 Agent 注册/加载）。
```bash
curl -N -H "Accept: text/event-stream" -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/chat/stream \
  -d '{"session_id":"<SESSION_ID>","content":"请调用可用工具并返回系统能力清单"}'
```
**期望**：SSE 返回 `thinking/tool/content/done` 事件；`thinking.tool` 与 `done.metadata.tool_calls` 显示 MCP 工具调用轨迹。

## Open Questions
- Agent发现是否使用显式注册表，还是动态扫描目录（需结合现有Agent加载方式）。
- MCP回退是否需要限制工具白名单或权限策略。
