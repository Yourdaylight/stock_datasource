# Agent-to-Agent (A2A) Communication Architecture Investigation
## COMPLETE REPORT

**Investigation Status:** ✅ COMPLETED  
**Date:** 2026-05-17  
**Project:** Stock Datasource  
**Investigator:** Claude Code

---

## Quick Answer: Why is "决策" Sidebar Empty?

**ROOT CAUSE:** The chat system (System A) does NOT invoke the Arena system (System C). They are completely separate, isolated systems with no bridge between them.

- Chat routes messages → OrchestratorAgent → Specialized Agents (MarketAgent, ReportAgent, etc.)
- Chat agents emit "debug events" (thinking, tool calls), NOT decision signals
- Decision signals ONLY exist in the Arena system (BUY/SELL/HOLD voting)
- Arena is completely isolated—it only runs if explicitly created
- **NO A2A protocol exists between the systems**

---

## Architecture Overview

### Three Separate Agent Systems

```
SYSTEM A: CHAT ORCHESTRATION
├─ Location: /src/stock_datasource/agents/
├─ Entry Point: POST /chat/stream
├─ Main Components:
│  ├─ OrchestratorAgent (orchestrator.py:1477 lines)
│  ├─ Specialized Agents: MarketAgent, ReportAgent, HKReportAgent, etc.
│  ├─ LangGraphAgent base class (base_agent.py:1059 lines)
│  └─ ExecutionPlanner (execution_planner.py:186 lines)
├─ Execution Model: LLM-based intent routing + sequential with handoffs
├─ Events Emitted: debug_type = classification|routing|agent_start|tool_result|agent_end
├─ Persistence: chat_messages table
└─ SSE Output: /chat/stream

SYSTEM B: ORCHESTRATION PIPELINES (NEW - v032d83f)
├─ Location: /src/stock_datasource/services/orchestration_*.py
├─ Entry Point: POST /api/orchestrations/{id}/execute
├─ Main Components:
│  ├─ OrchestrationService (orchestration_service.py:352 lines)
│  ├─ OrchestrationEngine (orchestration_engine.py:202 lines)
│  ├─ AgentConfigService (agent_config_service.py:295+ lines)
│  └─ PipelineNode/PipelineEdge models
├─ Execution Model: DAG-based topological sort + node sequencing
├─ Events Emitted: type = node_start|node_end|node_error
├─ Persistence: orchestration_pipelines & orchestration_executions tables
└─ SSE Output: /api/orchestrations/{id}/execute

SYSTEM C: ARENA DISCUSSIONS
├─ Location: /src/stock_datasource/arena/
├─ Entry Point: GET /api/arena/{arena_id}/thinking-stream
├─ Main Components:
│  ├─ AgentDiscussionOrchestrator (discussion_orchestrator.py:451 lines)
│  ├─ ThinkingStreamProcessor (stream_processor.py:381 lines)
│  └─ ArenaAgentBase agents
├─ Execution Model: Round-based multi-agent debate/collaboration/review
├─ Events Emitted: message_type = thinking|argument|decision
├─ Special: DecisionSummary with signal (BUY/SELL/HOLD) + confidence
├─ Persistence: thinking_messages table (async)
└─ SSE Output: /api/arena/{arena_id}/thinking-stream
```

### Key Difference Table

| Aspect | System A (Chat) | System B (Orchestration) | System C (Arena) |
|--------|---|---|---|
| **Invocation** | Chat message | User creates DAG | User creates arena |
| **Agent Selection** | LLM classifies intent | Fixed DAG topology | Fixed participant list |
| **Execution** | Sequential with handoffs | Topological sort | Round-based discussion |
| **Event Format** | debug_type fields | node_type fields | message_type fields |
| **Decision Signal** | ❌ NONE | ❌ NONE | ✅ YES (isolated) |
| **Handoffs** | ✅ Within system | ❌ None (no delegation) | ❌ None |
| **A2A Protocol** | ✅ Within system only | ❌ No (each node independent) | ❌ No |
| **Cross-system Communication** | ❌ NONE | ❌ NONE | ❌ NONE |

---

## System A: Chat Orchestration (Detailed)

### File Structure
```
/src/stock_datasource/agents/
├── orchestrator.py          (1477 lines) — Main routing logic
├── base_agent.py            (1059 lines) — Base class for all agents
├── agents/
│   ├── market_agent.py      — MarketAgent (stock price, technical analysis)
│   ├── report_agent.py      — ReportAgent (stock reports for A-shares)
│   ├── hk_report_agent.py   — HKReportAgent (for Hong Kong stocks)
│   ├── ... (other specialized agents)
│   └── __init__.py          (97 lines) — Agent registration/exports
├── services/
│   ├── execution_planner.py (186 lines) — Routing config + handoff map
│   └── agent_runtime.py     (feature-flagged alternative runtime)
└── __init__.py
```

### Main Flow: User Message → Chat Response

```
1. User sends: POST /chat/stream
   Body: { session_id: "xyz", content: "分析腾讯股票的技术面" }

2. ChatRouter._stream_response() [chat/router.py:196-426]
   ├─ Line 227: service.add_message(session_id, user_id, "user", content)
   ├─ Line 249: orchestrator.execute_stream(content, context)
   └─ Yields events as SSE to frontend

3. OrchestratorAgent.execute_stream() [orchestrator.py:1134-1464]
   ├─ Line 1188: Emit {"type": "thinking", "debug_type": "classification", 
   │            "intent": "market_analysis", "stock_codes": ["0700.HK"]}
   ├─ Line 1271: Emit {"type": "thinking", "debug_type": "routing",
   │            "agent": "MarketAgent", ...}
   └─ Line 1440-1455: Call MarketAgent.execute_stream(user_message, context)

4. MarketAgent.execute_stream() [base_agent.py:681-1036]
   ├─ Line 742-750: Emit {"type": "thinking", "debug_type": "agent_start",
   │               "agent": "MarketAgent", ...}
   ├─ Line 806-815: For each tool:
   │   Emit {"type": "debug", "tool": "stock_daily_price", ...}
   │   Emit {"type": "thinking", "debug_type": "tool_result", ...}
   ├─ Line 891: Emit {"type": "content", "content": "腾讯股票..."}
   └─ Line 969-979: Emit {"type": "thinking", "debug_type": "agent_end",
                         "duration_ms": 1234, ...}

5. ChatRouter forwards all events
   ├─ Line 285-289: For each debug event:
   │   yield f"data: {json.dumps(event)}\n\n"
   └─ Line 321-328: For content events (streamed LLM response):
       yield f"data: {json.dumps({type: content, content: chunk})}\n\n"

6. ChatRouter persists to database
   ├─ Line 349-355: service.add_message(session_id, user_id, "assistant",
   │                full_response, metadata={
   │                  debug_event_count: 47,
   │                  tool_calls: ["stock_daily_price"],
   │                  visualization_count: 1,
   │                  ...
   │                })
   └─ Stores in chat_messages table (ClickHouse)

7. Frontend receives SSE stream
   ├─ Displays thinking/tool/content events as chat UI
   └─ NO "决策" sidebar populated (no decision signal emitted)
```

### Handoff Targets (Within System A Only)

```python
# /src/stock_datasource/services/execution_planner.py:62-68

AGENT_HANDOFF_MAP: dict[str, list[str]] = {
    "MarketAgent": ["ReportAgent", "HKReportAgent", "BacktestAgent"],
    "ScreenerAgent": ["MarketAgent", "ReportAgent"],
    "ReportAgent": ["BacktestAgent", "MarketAgent", "HKReportAgent"],
    "HKReportAgent": ["MarketAgent", "ReportAgent"],
    "OverviewAgent": ["MarketAgent", "IndexAgent"],
}
```

**These are NOT:**
- Arena agents
- Orchestration configurable agents
- Cross-system handoffs

---

## System B: Orchestration Pipelines (New - Post-Refactor)

### File Structure
```
/src/stock_datasource/services/
├── orchestration_service.py    (352 lines) — CRUD + persistence
├── orchestration_engine.py     (202 lines) — DAG executor

/src/stock_datasource/modules/orchestration/
├── router.py                   (134 lines) — API endpoints
└── __init__.py

/src/stock_datasource/models/
├── agent_config.py             (89 lines) — AgentConfig data model
└── orchestration.py            (123 lines) — Pipeline data model

/src/stock_datasource/modules/agent_management/
├── router.py                   (493 lines) — Agent CRUD API
└── __init__.py
```

### Data Models

```python
# Orchestration Pipeline Definition
class PipelineNode:
    id: str
    type: NodeType  # agent | input | output | condition | aggregator
    label: str
    data: dict  # {"agent_id": "uuid", "input_mapping": {...}, ...}

class PipelineEdge:
    source: str  # Source node ID
    target: str  # Target node ID

class PipelineResponse:
    nodes: list[PipelineNode]
    edges: list[PipelineEdge]
    status: PipelineStatus  # draft | active | archived | deleted

# Configurable Agent Definition
class AgentConfigResponse:
    id: str
    user_id: str
    name: str
    system_prompt: str  # Custom prompt
    skills: list[str]  # Platform tools
    user_skills: list[str]  # Personal skills
    model_config_data: ModelConfig  # temperature, max_tokens
    runtime_config: RuntimeConfig  # type: langgraph|claude|codebuddy
    status: AgentStatus  # active | archived | deleted
```

### Execution Flow

```
1. User creates pipeline via UI:
   ┌─ Node_1 (input): message
   ├─ Node_2 (agent): AgentConfig_A ("Market Analyzer")
   ├─ Node_3 (agent): AgentConfig_B ("Risk Analyzer")
   └─ Node_4 (output): final_report
   
   Edges: 1→2, 2→3, 3→4

2. User executes: POST /api/orchestrations/{id}/execute
   Body: { input_data: { message: "分析腾讯" } }

3. OrchestrationRouter.execute_pipeline() [router.py:84-123]
   ├─ Line 111: yield pipeline_start event
   ├─ Line 113-114: engine.execute(pipeline, input_data) — async generator
   └─ Line 117: yield pipeline_end event

4. OrchestrationEngine.execute() [orchestration_engine.py:24-142]
   ├─ Line 37-50: Topological sort (Kahn's algorithm)
   │   execution_order = [1, 2, 3, 4]
   ├─ For Node_1 (input):
   │   ├─ Line 63-71: state[node_1] = input_data["message"]
   │   └─ Emit: {"type": "node_end", "node_type": "input", "output": "分析腾讯"}
   │
   ├─ For Node_2 (agent):
   │   ├─ Line 76-82: Emit: {"type": "node_start", "agent_id": "..."}
   │   ├─ Line 86: _run_agent_node(node, state, ...)
   │   └─ Line 89-96: Emit: {"type": "node_end", "output": "<analysis>"}
   │
   ├─ For Node_3 (agent):
   │   ├─ (Same process with state[2] as input)
   │
   └─ For Node_4 (output):
       └─ Line 113-120: Emit: {"type": "node_end", "output": "<merged>"}

5. OrchestrationEngine._run_agent_node() [orchestration_engine.py:144-189]
   ├─ Line 158: agent_service.get_agent(agent_id)  ← From ClickHouse
   ├─ Line 163-164: upstream_outputs = _get_upstream_outputs()
   ├─ Line 178-182: client.chat(
   │     messages=[
   │       {"role": "system", "content": agent.system_prompt},
   │       {"role": "user", "content": user_message}
   │     ],
   │     temperature=agent.model_config_data.temperature,
   │     max_tokens=agent.model_config_data.max_tokens
   │   )
   └─ Line 184-186: return response.content

6. Frontend receives SSE stream
   └─ Displays node-by-node execution progress
   └─ NO integration with Chat or Arena systems
```

### ClickHouse Tables

```sql
-- /src/stock_datasource/services/orchestration_service.py:29-48
CREATE TABLE IF NOT EXISTS orchestration_pipelines (
    id String,
    user_id String,
    name String,
    description String,
    nodes String,  -- JSON array of PipelineNode
    edges String,  -- JSON array of PipelineEdge
    status Enum8('draft'=1, 'active'=2, 'archived'=3, 'deleted'=4),
    version UInt32,
    created_at DateTime,
    updated_at DateTime
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, id);

-- /src/stock_datasource/services/orchestration_service.py:50-68
CREATE TABLE IF NOT EXISTS orchestration_executions (
    id String,
    pipeline_id String,
    user_id String,
    input_data String,  -- JSON
    output_data String,  -- Final output
    status Enum8('pending'=1, 'running'=2, 'completed'=3, 'failed'=4, 'cancelled'=5),
    current_node_id String,
    node_results String,  -- JSON of node results
    started_at DateTime,
    completed_at Nullable(DateTime),
    duration_ms UInt64
) ENGINE = MergeTree()
ORDER BY (user_id, pipeline_id, started_at)
TTL started_at + INTERVAL 90 DAY;

-- /src/stock_datasource/services/agent_config_service.py:27-46
CREATE TABLE IF NOT EXISTS agent_configs (
    id String,
    user_id String,
    name String,
    system_prompt String,
    skills Array(String),
    model_config String,  -- JSON of ModelConfig
    status Enum8('active'=1, 'archived'=2, 'deleted'=3),
    version UInt32,
    created_at DateTime,
    updated_at DateTime
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, id);
```

---

## System C: Arena Discussions (Reference)

### Basic Flow
```
1. User creates Arena + selects agents + discussion mode
2. AgentDiscussionOrchestrator.run_discussion() [discussion_orchestrator.py:64-150]
3. Agents debate/collaborate/review strategies
4. DecisionSummarizer.generate_summary() produces:
   ├─ signal: "BUY" | "SELL" | "HOLD"
   ├─ confidence: 0-1
   ├─ bull_count: N agents bullish
   ├─ bear_count: N agents bearish
   └─ neutral_count: N agents neutral
5. ThinkingStreamProcessor publishes messages to SSE
6. Frontend subscribes to /api/arena/{arena_id}/thinking-stream
```

### Why Not Used in Chat

```
- Completely separate system
- Requires explicit creation + user action
- Chat flow never invokes Arena
- Arena persists in its own ThinkingStreamProcessor
- No bridge between chat_messages and thinking_messages
```

---

## Missing A2A Protocol

### What Should Exist (But Doesn't)

```
1. AGENT DISCOVERY SERVICE
   ❌ Missing:
      - Registry of all agents across all systems
      - Queries: find_agent_by_name(), find_agents_by_category()
      - Service: UnifiedAgentRegistry
   
   What exists:
      - System A agents: hardcoded in __init__.py exports
      - System B agents: in ClickHouse agent_configs table
      - System C agents: hardcoded ArenaAgentBase subclasses

2. INTER-SYSTEM HANDOFF MECHANISM
   ❌ Missing:
      - delegate_to_orchestration(system_a_agent, pipeline_template)
      - escalate_to_arena(system_a_agents, discussion_mode)
      - route_to_specialized_agent(system_b_agent_config)
   
   What exists:
      - System A → System A handoffs (MarketAgent → ReportAgent)
      - AGENT_HANDOFF_MAP in execution_planner.py

3. UNIFIED EVENT BUS
   ❌ Missing:
      - Redis pub/sub or Kafka topic per system
      - Event schema: UnifiedAgentEvent
      - Service: EventBus with publish/subscribe
   
   What exists:
      - System A events: emitted in-memory, forwarded to SSE, stored in chat_messages
      - System B events: emitted in-memory, forwarded to SSE (not persisted to DB)
      - System C events: published to ThinkingStreamProcessor, stored in thinking_messages

4. SHARED MESSAGE FORMAT
   ❌ Missing:
      - UnifiedAgentEvent schema compatible with all systems
      - Event normalization layer
      - Frontend event aggregator
   
   What exists:
      - System A: {"type": "thinking", "debug_type": "agent_start", ...}
      - System B: {"type": "node_start", "node_type": "agent", ...}
      - System C: {"type": "message", "message_type": "thinking", ...}

5. DECISION SIGNAL BRIDGE
   ❌ Missing:
      - Chat system doesn't compute decision signals
      - No link between chat_messages and decision signals
      - Frontend can't fetch decisions for chat session
   
   What exists:
      - System C only: DecisionSummary with signal + confidence
      - Only generated in Arena discussions
      - Isolated per arena_id
```

---

## Recommended Solutions

### Option 1: Embed Arena in Chat Flow (Recommended)
**Complexity:** High | **Latency Impact:** +2-3x | **Compute Cost:** +2x

**Implementation:**
1. When OrchestratorAgent selects agent(s), capture them
2. Auto-create a hidden Arena with those agents
3. Run 2-3 discussion rounds in parallel (async)
4. Capture DecisionSummary
5. Publish to chat SSE stream + link to chat message
6. Display in "决策" sidebar

**Code Changes:**
```
/src/stock_datasource/modules/chat/
├─ Create: arena_bridge.py (orchestrate chat-arena integration)
└─ Modify: router.py (add Arena creation + orchestration)

/src/stock_datasource/services/
├─ Create: chat_arena_service.py (manage ad-hoc arenas)
└─ Modify: orchestration_engine.py (accept system_a_context)

Database:
├─ Add: chat_sessions.arena_id (FK)
├─ Add: chat_messages.decision_summary_id (FK)
└─ Link: chat ↔ decisions via arena_id
```

---

### Option 2: Integrate Orchestration into Chat
**Complexity:** Moderate | **Latency Impact:** +30% | **Compute Cost:** +30%

**Implementation:**
1. OrchestratorAgent classifies intent + determines required agents
2. DynamicPipelineBuilder generates DAG from intent
3. Execute pipeline via OrchestrationEngine
4. Merge outputs + metadata
5. Present as "多轮分析" in chat

---

### Option 3: Create A2A Message Bus (Most Extensible)
**Complexity:** Very High | **Latency Impact:** Low | **Compute Cost:** +5%

**Implementation:**
1. Create UnifiedMessageBus service (Redis + ClickHouse log)
2. Define UnifiedAgentEvent schema
3. Each system publishes to bus
4. Frontend subscribes to multiple topics
5. Aggregates events for sidebar

---

## Conclusion

The stock_datasource project contains **THREE ISOLATED AGENT SYSTEMS** with no inter-communication:

1. **System A (Chat)** — LLM-based routing to specialized agents
2. **System B (Orchestration Pipelines)** — DAG-based multi-step workflows
3. **System C (Arena)** — Multi-agent discussion with decision signals

The "决策" sidebar is empty because:
- Chat never invokes Arena
- Chat doesn't compute decision signals
- No bridge exists between systems
- **No A2A protocol is implemented**

To enable "决策" in chat, implement one of the three recommended solutions above.

---

## Investigation Artifacts

Generated documents:
- `A2A_FINDINGS.txt` — Quick reference summary
- `A2A_ARCHITECTURE_ANALYSIS.md` — Detailed technical analysis
- `A2A_INVESTIGATION_COMPLETE.md` — This document

---

**Investigation Complete** ✅  
**Generated:** 2026-05-17  
**Status:** Ready for Action
