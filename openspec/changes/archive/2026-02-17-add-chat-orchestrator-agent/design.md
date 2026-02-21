## Context
智能对话入口目前直接调用既有Agent与工具链，缺少统一调度层，也未在无可用Agent时回退到MCP工具。需要新增可复用的协调Agent模块，优先调度Agents目录中的Agent，必要时回退到MCP工具。

## Goals / Non-Goals
- Goals:
  - 仅接入chat入口；模块设计可复用，便于后续扩展至其他分析入口。
  - 优先使用Agents目录下Agent进行调度，各司其职。
  - 无可用Agent时，回退调用MCP工具。
  - 保持前端SSE流输出完整呈现（思考、工具、内容、完成）。
  - **Agent与API数据源保持一致，确保对话分析结果与页面展示一致。**
  - **集成Langfuse追踪，记录用户会话和LLM调用。**
- Non-Goals:
  - 现在就改造ETF/指数/选股等分析入口。
  - 重新设计前端对话UI或协议格式。

## Decisions
- Decision: 新增OrchestratorAgent作为统一调度入口，作为chat模块的内部依赖。
- Decision: Agent发现基于Agents目录的注册/扫描机制，生成可用Agent列表与能力描述。
- Decision: 当Orchestrator无法匹配Agent时，使用MCP客户端列出工具并进行调度执行。
- **Decision: Portfolio Agent使用与API相同的PortfolioService获取持仓数据，确保数据一致性。**
- **Decision: user_positions表添加user_id字段，支持多用户持仓隔离。**
- **Decision: Langfuse 3.x集成通过环境变量配置，用户上下文通过LangChain config metadata传递。**

## Alternatives considered
- 直接在chat路由中硬编码Agent选择逻辑：不利于复用与扩展。
- 始终使用MCP工具，不使用本地Agent：与"优先Agent"的需求冲突。
- **Agent使用独立的EnhancedPortfolioService：会导致数据与API不一致，已弃用。**
- **Langfuse 2.x API方式传递密钥：Langfuse 3.x不再支持，需使用环境变量。**

## Risks / Trade-offs
- MCP工具调度可能引入响应耗时与错误边界增加；需明确回退与错误提示。
- **数据库表结构变更需要兼容性处理，service层需检测字段是否存在。**

## Implementation Details

### 1. 数据库变更
```sql
-- user_positions 表添加 user_id 字段
ALTER TABLE user_positions ADD COLUMN user_id String DEFAULT 'default_user'
```

### 2. 服务层数据一致性
```python
# portfolio_agent.py - 使用统一的 PortfolioService
from stock_datasource.modules.portfolio.service import get_portfolio_service
service = get_portfolio_service()
positions = await service.get_positions(user_id=_current_user_id)
```

### 3. Langfuse 3.x 集成
```python
# base_agent.py - 通过 config metadata 传递用户上下文
config = {
    "metadata": {
        "langfuse_user_id": user_id,
        "langfuse_session_id": session_id,
        "langfuse_tags": [agent_name],
    }
}
```

环境变量配置：
```env
LANGFUSE_HOST=http://host.docker.internal:3000
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_ENABLED=true
```

## Migration Plan
- 第一步：引入OrchestratorAgent并接入chat入口（不影响其它入口）。
- 第二步：将现有Agent调用路径迁移到统一调度逻辑。
- 第三步：加入MCP回退调用路径。
- **第四步：数据库user_positions表添加user_id字段。**
- **第五步：Portfolio Agent改用PortfolioService保持数据一致性。**
- **第六步：集成Langfuse 3.x进行LLM调用追踪。**

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

### 4) 持仓分析（数据一致性验证）
```bash
curl -N -H "Accept: text/event-stream" -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/chat/stream \
  -d '{"session_id":"<SESSION_ID>","content":"查看我的持仓"}'
```
**期望**：返回的持仓数据与 `/api/portfolio/positions` 接口一致。

### 5) Langfuse 追踪验证
```bash
# 验证 Langfuse traces
curl -s 'http://localhost:3000/api/public/traces?limit=3' \
  -u 'pk-xxx:sk-xxx' | jq '.data[] | {name, userId, sessionId}'
```
**期望**：Langfuse Dashboard 中可见带有 userId 和 sessionId 的 trace 记录。

## Open Questions
- Agent发现是否使用显式注册表，还是动态扫描目录（需结合现有Agent加载方式）。
- MCP回退是否需要限制工具白名单或权限策略。
- **Langfuse数据保留策略与清理机制待定。**
