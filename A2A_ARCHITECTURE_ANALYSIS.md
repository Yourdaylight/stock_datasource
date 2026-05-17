# Agent-to-Agent (A2A) Communication Architecture Analysis
## Stock Datasource Project

**Investigation Date:** 2026-05-17  
**Focus:** Why chat page's "决策" (decisions) sidebar shows no agent discussions  
**Key Finding:** Two separate, unconnected agent systems exist in parallel

---

## Executive Summary

The stock_datasource project was recently restructured (commit `032d83f`) to introduce a **configurable Agent platform + Agent Teams hierarchical orchestration** system. This analysis reveals that:

1. **Two Completely Separate Agent Systems** exist with NO inter-communication:
   - **Chat System** (`/src/stock_datasource/agents/`) — OrchestratorAgent routes to specialized agents
   - **Orchestration System** (`/src/stock_datasource/services/orchestration_*.py`) — New pipeline-based agent execution
   - **Arena System** (`/src/stock_datasource/arena/`) — Multi-agent discussion discussions (separate)

2. **The Chat "决策" Sidebar is Empty Because:**
   - Chat messages route to OrchestratorAgent, which dispatches to MarketAgent, ReportAgent, etc.
   - These agents emit `debug_type: agent_start, tool_result, agent_end` events
   - The chat router forwards these events to the frontend as SSE
   - **NO connection exists to the Arena system's ThinkingStreamProcessor**
   - **NO connection exists to the Orchestration pipelines system**
   - The sidebar cannot show "decisions" because they're not published anywhere it can find them

3. **The Architecture After Recent Refactor:**
   - Agent Management (`/src/stock_datasource/modules/agent_management/`) — CRUD for configurable agents
   - Orchestration Engine (`/src/stock_datasource/services/orchestration_engine.py`) — DAG executor for pipelines
   - Orchestration Service (`/src/stock_datasource/services/orchestration_service.py`) — ClickHouse persistence
   - These are completely isolated from the existing Chat → OrchestratorAgent pipeline

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (Chat Page)                              │
│  ┌──────────────────────┐          ┌────────────────────────────────────┐  │
│  │  Chat Input Form     │          │  "决策" (Decisions) Sidebar [EMPTY] │  │
│  └──────────────────────┘          └────────────────────────────────────┘  │
│         │ POST /chat/stream               ^ (Expected: Agent discussions)   │
└─────────┼────────────────────────────────┼───────────────────────────────┘
          │                                │
          │                                │
          v                                │ (Missing Connection!)
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BACKEND SYSTEM A: CHAT ORCHESTRATION                      │
│                         (/src/stock_datasource/agents/)                      │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ ChatRouter._stream_response() [chat/router.py:196-426]              │  │
│  │  • Calls orchestrator.execute_stream(message, context)              │  │
│  │  • Receives SSE debug events: classification, routing               │  │
│  │  • Forwards to frontend as SSE: agent_start, tool_result, agent_end │  │
│  │  • Persists with debug_event_count to database                      │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│         ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ OrchestratorAgent.execute_stream() [agents/orchestrator.py:1134]    │  │
│  │  • LLM classifies user intent → "market_analysis", "screening", ... │  │
│  │  • Selects appropriate agent → MarketAgent, ScreenerAgent, ...      │  │
│  │  • May call multiple agents in sequence/parallel via routing        │  │
│  │  • Emits events:                                                     │  │
│  │    - type=thinking, debug_type=classification (intent detected)     │  │
│  │    - type=thinking, debug_type=routing (agent selected)             │  │
│  │    - type=debug (tool calls)                                        │  │
│  │    - type=content (response text)                                   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│         ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ Specialized Agents (LangGraphAgent base)                             │  │
│  │  • MarketAgent, ReportAgent, HKReportAgent, etc.                    │  │
│  │  • execute_stream() → emits agent_start, tool_result, agent_end     │  │
│  │  • Each tool call → visualization extraction                        │  │
│  │  • No connection to Arena or Orchestration systems                  │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  [HANDOFF TARGETS: Within this system only!]                               │
│   MarketAgent → ReportAgent | HKReportAgent | BacktestAgent               │
│   ScreenerAgent → MarketAgent | ReportAgent                               │
│   (Defined in ExecutionPlanner.AGENT_HANDOFF_MAP)                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│        BACKEND SYSTEM B: ORCHESTRATION PIPELINES (NEW - v032d83f)            │
│        (/src/stock_datasource/services/ + /modules/orchestration/)          │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ OrchestrationRouter.execute_pipeline() [modules/orchestration/]    │  │
│  │  • User creates DAG-based pipeline with PipelineNodes              │  │
│  │  • Each node type: input, agent, output, condition, aggregator     │  │
│  │  • Returns SSE stream of node execution                            │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│         ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ OrchestrationEngine.execute() [services/orchestration_engine.py]   │  │
│  │  • Topological sort of DAG (Kahn's algorithm)                      │  │
│  │  • For each agent node:                                            │  │
│  │    - Load AgentConfig from ClickHouse                             │  │
│  │    - Build system prompt + skills                                  │  │
│  │    - Call LLM client with user message + system prompt             │  │
│  │    - Emit: node_start, node_end/node_error                        │  │
│  │  • No specialized agents, no handoff mechanism                     │  │
│  │  • No connection to Chat system or Arena                          │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│         ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ AgentConfigService.get_agent() [services/agent_config_service.py]  │  │
│  │  • Fetches AgentConfigResponse from ClickHouse (agent_configs)     │  │
│  │  • Contains: system_prompt, skills, model_config, runtime_config   │  │
│  │  • Each call is independent (no agent composition)                 │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  [PERSISTENCE: ClickHouse Tables]                                          │
│   • orchestration_pipelines (nodes, edges, DAG definition)                 │
│   • orchestration_executions (execution history + node_results)           │
│   • agent_configs (configurable agents + system prompts)                   │
│                                                                              │
│  [NO HANDOFF MECHANISM: Each node is independent]                          │
│   Unlike System A, there's no routing logic between agents.                │
│   Data flows through pipeline edges: node_output → next_node_input         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│              BACKEND SYSTEM C: ARENA (Separate - Pre-existing)               │
│              (/src/stock_datasource/arena/)                                  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ Arena API (/api/arena/{arena_id}/thinking-stream)                   │  │
│  │  • Separate SSE endpoint for discussion subscribers                 │  │
│  │  • Returns ThinkingMessages from arena-specific store              │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│         ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ ThinkingStreamProcessor (per arena_id)                              │  │
│  │  • In-memory MessageStore per arena                                │  │
│  │  • Async publishes to ClickHouse (non-blocking)                   │  │
│  │  • No connection to Chat or Orchestration systems                 │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  [ISOLATED SUBSCRIBERS]                                                     │
│   Arena users must explicitly create an Arena and subscribe to its stream.  │
│   Chat page does not have an associated Arena instance.                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

[CRITICAL GAP: No connection between System A (Chat) and System B (Orchestration)]
[MISSING: No bridge to publish Chat events to Orchestration or vice versa]
```

---

## System A: Chat Orchestration (Existing)

### Key Files

| File | Lines | Purpose |
|------|-------|---------|
| `/src/stock_datasource/agents/orchestrator.py` | 1477 | OrchestratorAgent main logic — LLM-based intent routing |
| `/src/stock_datasource/agents/base_agent.py` | 1059 | LangGraphAgent base — streaming with debug events |
| `/src/stock_datasource/modules/chat/router.py` | 427 | Chat API router — SSE streaming |
| `/src/stock_datasource/services/execution_planner.py` | 186 | Config: agent routing, concurrency, handoffs (within-system only) |

### Event Flow: Chat Message → Agent Routing

```
1. User sends: POST /chat/stream
   └─ Payload: { session_id, content: "分析腾讯股票" }

2. ChatRouter._stream_response() [router.py:196]
   └─ Calls: orchestrator.execute_stream(content, context)

3. OrchestratorAgent._classify_with_llm() [orchestrator.py:147-240]
   └─ LLM determines intent: "market_analysis"
   └─ Emit: type=thinking, debug_type=classification, intent="market_analysis"

4. OrchestratorAgent._build_multi_agent_plan() [orchestrator.py:288-361]
   └─ Select agent: MarketAgent (from ExecutionPlanner.expand_agent_list)
   └─ Emit: type=thinking, debug_type=routing, agent="MarketAgent"

5. MarketAgent.execute_stream() [base_agent.py:681-1036]
   └─ Emit: type=thinking, debug_type=agent_start, agent="MarketAgent"
   └─ For each tool: Emit: type=debug, tool="stock_daily_price"
   └─ For tool result: Emit: type=debug, debug_type=tool_result
   └─ Emit: type=content, content="<markdown response>"
   └─ Emit: type=thinking, debug_type=agent_end, duration_ms=1234

6. ChatRouter forwards all events as SSE to frontend
   └─ Emit each event: f"data: {json.dumps(event)}\n\n"

7. ChatRouter persists to database
   └─ add_message(session_id, user_id, "assistant", response, metadata={
       debug_event_count: N,
       tool_calls: ["stock_daily_price", ...],
       tool_errors: [...],
       visualization_count: M
     })
```

### Debug Event Types Emitted in System A

| Event Type | Debug Type | Emitted By | Line | Purpose |
|-----------|-----------|-----------|------|---------|
| thinking | classification | OrchestratorAgent | 1188 | User intent detected (intent, stock_codes extracted) |
| thinking | routing | OrchestratorAgent | 1271 | Agent selected for routing |
| thinking | agent_start | LangGraphAgent | 742 | Agent execution begins |
| debug | tool | LangGraphAgent | 806 | Tool call with args |
| thinking | tool_result | LangGraphAgent | 806 | Tool result received |
| thinking | agent_end | LangGraphAgent | 969 | Agent execution complete (duration_ms, success status) |
| content | — | LangGraphAgent | 891 | Text chunk from LLM |
| visualization | — | LangGraphAgent | 635-679 | Extracted viz from tool output |
| done | — | ChatRouter | 361 | Stream complete with metadata |

### No A2A Connection in System A

**Critical Finding:** The `ExecutionPlanner.AGENT_HANDOFF_MAP` defines handoffs ONLY within specialized agents:

```python
# Line 62-68: /src/stock_datasource/services/execution_planner.py
AGENT_HANDOFF_MAP: dict[str, list[str]] = {
    "MarketAgent": ["ReportAgent", "HKReportAgent", "BacktestAgent"],
    "ScreenerAgent": ["MarketAgent", "ReportAgent"],
    "ReportAgent": ["BacktestAgent", "MarketAgent", "HKReportAgent"],
    "HKReportAgent": ["MarketAgent", "ReportAgent"],
    "OverviewAgent": ["MarketAgent", "IndexAgent"],
}
```

**These targets are specialized agents within the SAME system, not:**
- Arena agents (ArenaAgentBase)
- Orchestration configurable agents (AgentConfig)
- External systems

---

## System B: Orchestration Pipelines (New - Post-Refactor)

### Key Files

| File | Lines | Purpose |
|------|-------|---------|
| `/src/stock_datasource/services/orchestration_service.py` | 352 | CRUD for pipelines + executions (ClickHouse) |
| `/src/stock_datasource/services/orchestration_engine.py` | 202 | DAG executor — topological sort, node sequencing |
| `/src/stock_datasource/services/agent_config_service.py` | 295+ | CRUD for configurable agents (ClickHouse) |
| `/src/stock_datasource/modules/orchestration/router.py` | 134 | Pipeline API: create, edit, execute (SSE) |
| `/src/stock_datasource/models/orchestration.py` | 123 | Pydantic models: PipelineNode, PipelineEdge, ExecutionStatus |
| `/src/stock_datasource/models/agent_config.py` | 89 | Pydantic models: AgentConfigCreate, RuntimeConfig |

### Data Model: Orchestration Pipeline

```python
# /src/stock_datasource/models/orchestration.py

class PipelineNode:
    id: str
    type: NodeType  # agent | input | output | condition | aggregator
    label: str
    data: dict      # For agent: { agent_id, input_mapping, default_input }

class PipelineEdge:
    source: str     # Source node ID
    target: str     # Target node ID
    label: str

class PipelineResponse:
    id: str
    user_id: str
    name: str
    nodes: list[PipelineNode]
    edges: list[PipelineEdge]
    status: PipelineStatus  # draft | active | archived | deleted
    version: int
    created_at: datetime
    updated_at: datetime
```

### Data Model: Configurable Agent

```python
# /src/stock_datasource/models/agent_config.py

class AgentConfigResponse:
    id: str
    user_id: str
    name: str
    system_prompt: str              # ← Custom system prompt
    skills: list[str]               # Platform tools (MCP)
    user_skills: list[str]          # User's personal Skills
    model_config_data: ModelConfig   # temperature, max_tokens
    runtime_config: RuntimeConfig    # type: langgraph | claude | codebuddy
    status: AgentStatus              # active | archived | deleted
    version: int
    created_at: datetime
    updated_at: datetime
```

### Event Flow: Pipeline Execution

```
1. User creates pipeline via /api/orchestrations/:
   ┌─ Node_1 (input): message
   ├─ Node_2 (agent): MarketAnalyzer (AgentConfig_A)
   ├─ Node_3 (agent): RiskAnalyzer (AgentConfig_B)
   └─ Node_4 (output): final_report
   
   Edges: 1→2, 2→3, 3→4

2. User executes: POST /api/orchestrations/{id}/execute
   └─ Payload: { input_data: { message: "分析腾讯" } }

3. OrchestrationRouter.execute_pipeline() [router.py:84-123]
   └─ Calls: engine.execute(pipeline, input_data)

4. OrchestrationEngine.execute() [orchestration_engine.py:24-142]
   └─ Topological sort: [1, 2, 3, 4]
   └─ For Node_1 (input):
      └─ state[node_1] = input_data["message"]
      └─ Emit: type=node_end, node_type=input, output="分析腾讯"
   
   └─ For Node_2 (agent):
      └─ Emit: type=node_start, node_type=agent, agent_id=AgentConfig_A
      └─ Load AgentConfig_A from ClickHouse
      └─ Call LLM with: system_prompt + state[node_1]
      └─ Emit: type=node_end, node_type=agent, output="<analysis>"
   
   └─ For Node_3 (agent):
      └─ (Same, but with state[node_2] as input)
   
   └─ For Node_4 (output):
      └─ Emit: type=node_end, node_type=output, output="<merged>"

5. OrchestrationRouter yields SSE stream
   └─ Each event: f"data: {json.dumps(event)}\n\n"

6. Service logs execution (not persisted to DB in real-time)
   └─ complete_execution() merely logs, doesn't insert
```

### Event Types Emitted in System B

| Event Type | Node Type | Emitted By | Purpose |
|-----------|-----------|-----------|---------|
| pipeline_start | — | router | Pipeline execution begins |
| node_start | agent/input/output/etc. | engine | Node execution begins |
| node_end | agent/input/output/etc. | engine | Node completed successfully |
| node_error | agent/input/output/etc. | engine | Node failed with error |
| complete | — | engine | Pipeline completed |
| error | — | router | Execution failed (exception) |

### No Connection to System A or Arena

**Key Differences from System A:**

1. **No Intent Routing** — Orchestration uses fixed DAG topology, not LLM-based routing
2. **No Specialized Agents** — Uses generic AgentConfig (any system prompt + skills)
3. **No Tool Calls** — Agents only call LLM, not tools (no MCP invocation)
4. **No Handoffs** — Data flows through edges, not agent-to-agent delegation
5. **No A2A Protocol** — Each agent node is independent; no cross-system messaging

**System B is fundamentally a different execution model** — pipeline orchestration, not chat-based routing.

---

## System C: Arena (Separate)

### Key Files

| File | Lines | Purpose |
|------|-------|---------|
| `/src/stock_datasource/arena/discussion_orchestrator.py` | 451 | Multi-agent discussion coordinator (debate/collab/review) |
| `/src/stock_datasource/arena/stream_processor.py` | 381 | ThinkingStreamProcessor — in-memory pub/sub + ClickHouse |
| `/src/stock_datasource/modules/arena/router.py` | 500+ | Arena API: thinking-stream (SSE) |

### Arena Event Flow

```
Arena is only invoked if explicitly created and run.
Chat page does NOT have an associated Arena instance.

For reference:
1. User creates Arena with debate mode + N agents
2. AgentDiscussionOrchestrator runs rounds
3. For each round: agents critique strategies
4. ThinkingStreamProcessor publishes messages via SSE
5. Frontend subscribes to /api/arena/{arena_id}/thinking-stream

This is completely independent from Chat system.
```

---

## Why Chat "决策" (Decisions) Sidebar is Empty

### Problem Statement

The chat page's "决策" sidebar is designed to show:
- Agent discussions
- Decision signals (BUY/SELL/HOLD)
- Voting/consensus from multiple agents

But it always appears empty.

### Root Cause Analysis

| Root Cause | Evidence | Impact |
|-----------|----------|--------|
| **No Arena in Chat Flow** | Chat → OrchestratorAgent → Specialized Agents. No Arena created. | Decisions aren't published to Arena's ThinkingStreamProcessor |
| **Chat Events ≠ Arena Events** | Chat emits `debug_type` events; Arena expects `ThinkingMessage` with agent discussions | Events can't be cross-published |
| **Orchestration System Isolated** | New pipeline system not integrated into chat flow | No multi-agent consensus in chat |
| **No SSE Bridge** | Three separate SSE endpoints: /chat/stream, /api/orchestrations/{id}/execute, /api/arena/{id}/thinking-stream | Frontend can't aggregate signals |
| **No Message Bus** | Each system stores events in different places (chat_messages, orchestration_executions, arena ThinkingMessages) | No unified decision signal |

### Architectural Mismatch

```
What exists:
  Chat page → OrchestratorAgent.execute_stream()
             └─ Emits debug events (classification, routing, agent_start, ...)
             └─ Frontend displays as "工具调用" (tool calls) / "思考过程" (thinking)
             └─ NOT designed to produce "decisions" / "voting"

What's needed for "决策":
  1. Multi-agent discussion (Arena model)
  2. Strategy comparison (debate/collaboration)
  3. Decision summarization (DecisionSummary with signal + confidence)
  4. Signal aggregation (BUY/SELL/HOLD voting)
  └─ This only exists in the Arena system

The Problem:
  • Chat uses OrchestratorAgent + Specialized Agents (routing-based)
  • Arena uses ArenaAgentBase + DecisionSummarizer (discussion-based)
  • Orchestration uses AgentConfig + OrchestrationEngine (DAG-based)
  • They are THREE SEPARATE EXECUTION MODELS WITH NO BRIDGE
```

---

## Missing A2A Protocol

### What Is Missing

1. **No Agent Discovery Service**
   - Specialized agents (MarketAgent, ReportAgent) are hardcoded in `/src/stock_datasource/agents/__init__.py`
   - ConfigurableAgents (AgentConfig) are user-created and stored in ClickHouse
   - No registry to find agents across systems

2. **No Handoff Mechanism Between Systems**
   - Within System A (Chat): MarketAgent can handoff to ReportAgent via ExecutionPlanner
   - Between Systems: NO way for Chat → Orchestration or Chat → Arena
   - No `delegate_to_orchestration()` or `escalate_to_arena()` function

3. **No Shared Message Format**
   - System A emits: `{"type": "thinking", "debug_type": "agent_start", "agent": "MarketAgent", ...}`
   - System B emits: `{"type": "node_start", "node_type": "agent", "agent_id": "uuid", ...}`
   - System C emits: `{"type": "message", "message_type": "thinking", "agent_id": "...", ...}`
   - Frontend can't normalize/aggregate

4. **No Unified Event Bus**
   - System A: Events held in memory + chat_messages table
   - System B: Events held in memory + orchestration_executions table
   - System C: Events held in ThinkingStreamProcessor + thinking_messages table
   - No publish/subscribe across systems

5. **No Decision Signal Bridge**
   - System C (Arena) computes: `DecisionSummary(signal="BUY", confidence=0.85, bull_count=3, ...)`
   - System A (Chat) has no parallel logic
   - Frontend has no way to fetch decision signals from chat-initiated discussions

---

## Code Evidence

### System A: Chat Debug Events

```python
# /src/stock_datasource/agents/orchestrator.py:1188
yield {"type": "thinking", "debug_type": "classification", "intent": "market_analysis"}

# Line 1271
yield {"type": "thinking", "debug_type": "routing", "agent": "MarketAgent"}

# /src/stock_datasource/agents/base_agent.py:742
yield {"type": "thinking", "debug_type": "agent_start", "agent": self.agent_id}

# Line 806
yield {"type": "debug", "debug_type": "tool_result", "tool": tool_name}
```

### System B: Orchestration Events

```python
# /src/stock_datasource/services/orchestration_engine.py:76-82
yield {
    "type": "node_start",
    "node_id": node_id,
    "node_type": "agent",
    "agent_id": agent_id,
}

# Line 89-96
yield {
    "type": "node_end",
    "node_id": node_id,
    "node_type": "agent",
    "output": output[:2000],
    "duration_ms": duration_ms,
}
```

### System C: Arena Events

```python
# /src/stock_datasource/arena/stream_processor.py:195-197
await self.publish_system(
    f"## 决策信号: {decision_summary.signal.upper()}",
    metadata={...}
)
```

**These are THREE DIFFERENT EVENT FORMATS.** There is no A2A protocol.

---

## How to Resolve (Recommended Solutions)

### Option 1: Embed Arena in Chat Flow (Comprehensive)

**Goal:** When user sends chat message, also run a parallel Arena discussion to generate decisions.

**Implementation:**
1. After OrchestratorAgent routes to agents, capture the selected agent(s)
2. Create an Ad-hoc Arena with those agents as participants
3. Run 2-3 discussion rounds (debate/collaboration)
4. Collect DecisionSummary with signal + confidence
5. Publish decision to chat session for sidebar display
6. Link chat message to Arena round in database

**Changes Needed:**
- `/src/stock_datasource/modules/chat/router.py`: Add Arena creation + orchestration
- `/src/stock_datasource/services/`: Create `ChatArenaService` to manage ad-hoc arenas
- Database: Add `chat_sessions.arena_id` foreign key

**Pros:** Full "决策" sidebar with discussions, agent debates, voting  
**Cons:** 2-3x latency (Arena rounds take time), doubles compute cost

---

### Option 2: Integrate Orchestration Pipelines into Chat (Moderate)

**Goal:** When user message requires multi-step analysis, auto-generate and execute an orchestration pipeline.

**Implementation:**
1. OrchestratorAgent classifies intent + determines required agents
2. DynamicPipelineBuilder creates DAG: Input → [Agent_1, Agent_2, ...] → Aggregator → Output
3. Execute pipeline via OrchestrationEngine
4. Collect outputs + metadata + node results
5. Present as "多轮分析" (multi-round analysis) in chat

**Changes Needed:**
- `/src/stock_datasource/agents/orchestrator.py`: Add pipeline generation
- `/src/stock_datasource/services/`: Create `DynamicPipelineBuilder`
- `/src/stock_datasource/modules/chat/`: Add pipeline execution SSE forwarding

**Pros:** Structured multi-step analysis, clearer dependencies  
**Cons:** Different UI paradigm (pipeline vs. chat), frontend refactor needed

---

### Option 3: Create A2A Message Bus (Architectural)

**Goal:** Unified event bus so any system can publish/subscribe to agent decisions.

**Implementation:**
1. Create `MessageBus` service (Redis pub/sub or in-memory + ClickHouse log)
2. Define `UnifiedAgentEvent` schema compatible with all three systems
3. Each system publishes to bus:
   - System A: `/topic/chat/{session_id}/agent_events`
   - System B: `/topic/orchestration/{execution_id}/node_events`
   - System C: `/topic/arena/{arena_id}/thinking_events`
4. Chat frontend subscribes to both `/topic/chat/{session_id}/*` and `/topic/orchestration/*` (if linked)
5. Decision signal published to `/topic/chat/{session_id}/decision`

**Changes Needed:**
- New `/src/stock_datasource/services/message_bus.py`
- Update ChatRouter, OrchestrationEngine, ArenaOrchestrator to publish to bus
- Frontend: Multi-topic subscription logic

**Pros:** Future-proof, decoupled, extensible  
**Cons:** Most complex, requires architectural refactor

---

## Key Metrics & Configuration

### System A Limits
- Max concurrent agents: 3 (ExecutionPlanner.CONCURRENT_AGENT_GROUPS)
- Handoff targets per agent: 1-3 (ExecutionPlanner.AGENT_HANDOFF_MAP)

### System B Limits
- DAG nodes per pipeline: 50+ (no hard limit)
- Agent configuration options: ModelConfig (temperature, max_tokens), RuntimeConfig (type, env_vars)

### System C Limits
- Discussion rounds: User-defined
- Agents per discussion: User-defined

---

## Summary Table

| Aspect | System A (Chat) | System B (Orchestration) | System C (Arena) |
|--------|-----------------|--------------------------|------------------|
| **Invocation** | Chat message sent | User creates + executes pipeline | User creates + runs arena |
| **Agent Selection** | LLM-based intent routing | Fixed DAG topology | Fixed participant list |
| **Execution Model** | Sequential with handoffs | Topological sort (DAG) | Round-based discussion |
| **Events** | debug_type: classification, routing, agent_start, tool_result, agent_end | type: node_start, node_end, node_error | message_type: thinking, argument, decision |
| **Persistence** | chat_messages table | orchestration_executions table | thinking_messages table |
| **SSE Endpoint** | /chat/stream | /api/orchestrations/{id}/execute | /api/arena/{id}/thinking-stream |
| **Decision Signal** | ❌ None | ❌ None | ✅ DecisionSummary (signal, confidence) |
| **A2A Connection** | ✅ Within-system (MarketAgent ↔ ReportAgent) | ❌ No handoffs | ❌ No cross-system |
| **Can Produce "决策"?** | ❌ No | ❌ No | ✅ Yes (but isolated) |

---

## Conclusion

The stock_datasource project currently has **THREE ISOLATED AGENT SYSTEMS** that do not communicate with each other:

1. **Chat System (System A)** — Specializes in LLM-based intent routing + tool calls
2. **Orchestration Pipelines (System B)** — Specializes in DAG-based multi-step workflows
3. **Arena Discussions (System C)** — Specializes in multi-agent debates + decision signals

The "决策" (decisions) sidebar in the chat page is empty because:
- Chat doesn't invoke Arena
- Chat doesn't produce decision signals
- Chat doesn't have an associated discussion
- No bridge exists to integrate decisions from other systems

**To enable "决策" in chat:**
- Choose one of the three resolution options above
- Implement the necessary integration layer
- Update frontend to consume unified decision signals

**Recommendation:** Option 1 (Embed Arena in Chat Flow) provides the best UX, but requires architectural refactor. Option 3 (A2A Message Bus) is most flexible for future expansion.

