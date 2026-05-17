# Stock DataSource: Agent Teams & Orchestration Pipeline Investigation

**Date**: 2026-05-17  
**Commit**: `032d83f` - "feat: Agent中心 — 可配置化Agent平台 + Agent Teams层级编排"  
**Status**: Complete architectural investigation

---

## Executive Summary

The system has undergone a major refactoring from hardcoded agents to a **fully configurable Agent platform** with a **hierarchical Agent Teams orchestration system**. The system now supports:

1. **Configurable Agent Platform**: 10 built-in agents + user-created agents with isolated namespaces
2. **Agent Teams (3-tier Hierarchy)**: Execution → Analysis → Decision layers with 6 built-in teams
3. **Orchestration Pipeline DAG**: Visual editor for composing custom agent workflows
4. **Dual Execution Paths**: 
   - Traditional **Arena Discussion System** (separate from orchestration)
   - New **Agent Runtime + LangGraph Supervisor** (unified multi-agent control plane)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      USER INTERFACE (Vue)                       │
├──────────────────┬──────────────────┬────────────────┬──────────┤
│ Chat View        │ Agent Management │ Orchestration  │ Sentinel │
│ (AgentRuntime)   │ (CRUD Agents)    │ (DAG Composer) │ (Arena)  │
└──────────────────┴──────────────────┴────────────────┴──────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────┐
│  AgentRuntime    │ │Orchestration │ │Arena Manager │
│  (LangGraph)     │ │  Engine      │ │              │
│                  │ │ (DAG Exec)   │ │              │
└──────────────────┘ └──────────────┘ └──────────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────┐
│ Agent Registry   │ │ Agent Config │ │    LLM       │
│ (Descriptors)    │ │ Service      │ │  (DeepSeek/  │
│                  │ │ (CRUD)       │ │   Claude)    │
└──────────────────┘ └──────────────┘ └──────────────┘
```

---

## 1. Agent Teams & Hierarchical Orchestration

### Definition: What is an "Agent Team"?

An **Agent Team** is a **3-tier hierarchical orchestration structure** where agents are organized by capability level:

```yaml
Agent Team Structure:
├─ Tier 1 (Execution Layer) — 执行层
│  └─ Agents: Raw data gathering, monitoring, real-time feeds
│     Examples: MarketAgent, IndexAgent
│
├─ Tier 2 (Analysis Layer) — 分析层  
│  └─ Agents: Data processing, filtering, analysis, recommendations
│     Examples: ReportAgent, ScreenerAgent, BacktestAgent
│
└─ Tier 3 (Decision Layer) — 决策层
   └─ Agents: Final synthesis, strategic decisions, output generation
      Examples: OverviewAgent, TopListAgent
```

### 6 Built-in Teams (System-managed)

From commit diff, these are created as presets:

1. **Sentinel Smart Stock Selection** — 哨兵智能选股
2. **Single Stock Comprehensive Checkup** — 个股全面体检
3. **Industry Deep Research** — 行业深度研究
4. **Market Trend Analysis** — 市场趋势分析
5. **Strategy Backtesting** — 策略回测
6. **Portfolio Optimization** — 组合优化

### How Agent Teams Execute

**Execution Flow** (from `OrchestrationEditor.vue` + `orchestration_engine.py`):

```
User Input (Query)
  │
  ▼
┌─────────────────────┐
│ Tier 1 Agents       │  <- All run in parallel (if marked "parallel_within_tier")
│ (Execution Layer)   │     or sequentially (if "hierarchical")
└──────────────────┬──┘
                   │
                   ▼ Tier 1 Results (Collected)
┌─────────────────────┐
│ Tier 2 Agents       │  <- Process upstream outputs
│ (Analysis Layer)    │     Apply merge_strategy (aggregation logic)
└──────────────────┬──┘
                   │
                   ▼ Tier 2 Results (Summarized)
┌─────────────────────┐
│ Tier 3 Agents       │  <- Final decision layer
│ (Decision Layer)    │     LLM-based synthesis
└──────────────────┬──┘
                   │
                   ▼ Final Output
               User Output
```

**Execution Modes** (from `OrchestrationEditor.vue` line 52-56):

```typescript
executionMode:
  - "hierarchical"         — Tier1→Tier2→Tier3 sequential, each tier sequential
  - "parallel_then_merge"  — Within-tier parallel, between-tier sequential
  - "all_to_final"         — All tier results sent directly to final aggregator

mergeStrategy:
  - "llm_summarize"        — LLM-based synthesis (default)
  - "last_tier"            — Use only highest tier output
  - "vote"                 — Voting/consensus
```

---

## 2. Orchestration Pipelines (DAG-based)

### Definition: What is an Orchestration Pipeline?

An **Orchestration Pipeline** is a **Directed Acyclic Graph (DAG)** of nodes and edges where:

- **Nodes** represent operations (agents, input, output, conditions, aggregators)
- **Edges** represent data flow
- **Execution** follows topological order (Kahn's algorithm)

### File Paths - Orchestration System

**Backend Models & Services:**
```
src/stock_datasource/
├─ models/
│  └─ orchestration.py               # Pydantic models (PipelineNode, PipelineEdge, etc.)
├─ modules/orchestration/
│  ├─ __init__.py
│  └─ router.py                      # FastAPI routes (/api/orchestrations/**)
├─ services/
│  ├─ orchestration_service.py       # CRUD ops + ClickHouse persistence
│  ├─ orchestration_engine.py        # DAG execution engine (topological sort)
│  └─ execution_planner.py           # Agent routing + concurrency config (legacy)
```

**Frontend UI & API:**
```
frontend/src/
├─ api/
│  └─ orchestration.ts               # API client (TypeScript)
└─ views/orchestration/
   ├─ OrchestrationList.vue          # List view (pipeline cards)
   └─ OrchestrationEditor.vue        # Visual DAG editor
```

### Pipeline Node Types

```python
# From models/orchestration.py
class NodeType(str, Enum):
    agent = "agent"           # Invokes an agent with system prompt + tools
    input = "input"           # Receives pipeline input
    output = "output"         # Collects results from upstream
    condition = "condition"   # (Planned) Conditional branching
    aggregator = "aggregator" # Merges upstream outputs
```

### Pipeline Schema (Pydantic)

```python
# models/orchestration.py (lines 20-140)

class PipelineNode:
    id: str
    type: NodeType
    label: str
    position: dict  # UI layout {x, y}
    data: dict      # Node-specific config
    # agent: data.agent_id, data.input_mapping
    # condition: data.condition_expression
    # aggregator: data.merge_strategy

class PipelineEdge:
    id: str
    source: str      # source node ID
    target: str      # target node ID
    source_handle: str = "output"
    target_handle: str = "input"
    label: str = ""

class PipelineResponse:
    id: str
    user_id: str
    name: str
    description: str
    nodes: list[PipelineNode]
    edges: list[PipelineEdge]
    input_schema: dict       # Input validation schema
    output_config: dict      # Output formatting
    tags: list[str]
    is_public: bool
    status: "draft" | "active" | "archived" | "deleted"
    version: int
    created_at: datetime
    updated_at: datetime
```

### How Pipelines Execute

**Engine** (`orchestration_engine.py` lines 17-142):

1. **Topological Sort** (Kahn's algorithm) — Compute execution order
2. **State Dict** — Stores output of each node
3. **Sequential Traversal** — Process nodes in topological order
4. **SSE Streaming** — Emit events for each node: `node_start` → `node_end` → `complete`

**Example Flow:**
```
Input Node → Agent Node1 → Agent Node2 → Aggregator → Output Node
   (pass input) → (LLM call) → (LLM call)  (merge results) (finalize)
```

**Backend Routes** (`modules/orchestration/router.py`):

```python
GET    /api/orchestrations/              # List pipelines
POST   /api/orchestrations/              # Create pipeline
GET    /api/orchestrations/{id}          # Get pipeline
PUT    /api/orchestrations/{id}          # Update pipeline
DELETE /api/orchestrations/{id}          # Delete pipeline (soft)

POST   /api/orchestrations/{id}/execute  # Execute (SSE stream)
GET    /api/orchestrations/{id}/executions  # List past executions
```

---

## 3. Agent Platform: Configurable Agents

### File Paths - Agent Management

**Backend Models & Services:**
```
src/stock_datasource/
├─ models/
│  └─ agent_config.py                # Pydantic models (AgentConfigCreate, etc.)
├─ modules/agent_management/
│  ├─ __init__.py
│  └─ router.py                      # FastAPI routes (/api/agents/**)
├─ services/
│  ├─ agent_config_service.py        # CRUD + ClickHouse persistence
│  ├─ agent_registry.py              # Runtime descriptor registry
│  ├─ agent_runtime.py               # LangGraph Supervisor
│  └─ agent_registrations.py         # (Deprecated) stub
```

**Frontend UI & API:**
```
frontend/src/
├─ api/
│  └─ agent.ts                       # API client (TypeScript)
└─ views/agent-management/
   ├─ AgentList.vue                  # Grid view (agent cards, search, filter)
   ├─ AgentEditor.vue                # Form to create/edit agents
   └─ RuntimeManagement.vue          # Runtime selection (LangGraph/CLI)
```

### Agent Configuration Schema

```python
# models/agent_config.py

class ModelConfig:
    model: str = "DeepSeek-V4-Pro"
    temperature: float = 0.7
    max_tokens: int = 4096
    min_tokens: int = 0

class RuntimeConfig:
    type: str  # "langgraph" | "claude" | "codebuddy"
    command: str  # CLI path (for external runtimes)
    working_dir: str
    env_vars: dict

class AgentConfigResponse:
    id: str
    user_id: str
    name: str
    description: str
    avatar: str              # Emoji
    system_prompt: str       # Agent's instructions
    skills: list[str]        # Platform tools (from SkillRegistry)
    user_skills: list[str]   # User-defined tools
    model_config_data: ModelConfig
    runtime_config: RuntimeConfig
    tags: list[str]
    is_public: bool
    status: "active" | "archived" | "deleted"
    version: int
    created_at: datetime
    updated_at: datetime
```

### Agent Lifecycle

**Creation:**
1. User creates agent via `AgentEditor.vue`
2. Backend stores config in `agent_configs` ClickHouse table
3. Agent assigned UUID, version=1, status=active
4. Created agents isolated to `user_id` namespace (unless `is_public=true`)

**Use:**
1. Agent listed in `AgentRegistry` (descriptor pattern)
2. Can be used in:
   - **Orchestration Pipelines** (as agent nodes)
   - **Agent Teams** (added to tier)
   - **Chat** (via AgentRuntime supervisor)

**10 Built-in (System) Agents:**
- MarketAgent, ReportAgent, HKReportAgent
- IndexAgent, EtfAgent, ScreenerAgent
- BacktestAgent, OverviewAgent, TopListAgent
- KnowledgeAgent (+ ChatAgent for fallback)
- User ID = "system" (visible globally)

---

## 4. Agent Runtime: LangGraph Supervisor

### What is AgentRuntime?

**AgentRuntime** is the **unified control plane** for multi-agent execution powered by **LangGraph Supervisor**:

- **Replaces** hardcoded agent orchestration logic
- **Uses** LangGraph's native `create_supervisor()` + `create_react_agent()`
- **Handles** routing, handoff, state management, checkpointing
- **Streams** events via `astream_events(version="v2")`
- **Integrates** with memory store, middleware chain, observability

### File Path: Agent Runtime

```
src/stock_datasource/
└─ services/
   ├─ agent_runtime.py               # AgentRuntime class (230+ lines)
   ├─ execution_planner.py           # Config data (CONCURRENT_AGENT_GROUPS, etc.)
   └─ agent_registry.py              # Registry + descriptor pattern
```

### Execution Path: Chat Query

```
User Query (Chat)
  │
  ▼
AgentRuntime.execute_stream_sse()
  │
  ├─ Middleware chain: before() — filter non-financial queries, inject memory
  │
  ├─ LangGraph Supervisor Graph
  │  │
  │  ├─ Supervisor LLM: "Understand intent, route to best agent"
  │  │  └─ Available agents from registry
  │  │
  │  └─ Sub-Agents (LangGraph react agents)
  │     ├─ MarketAgent (tools, system prompt)
  │     ├─ ReportAgent (tools, system prompt)
  │     └─ ... (more agents)
  │
  ├─ Stream LangGraph events → SSE format conversion
  │  (on_chat_model_stream → {type: "content", content: "..."}
  │   on_tool_start → {type: "tool", tool: "...", args: {...}}
  │   on_tool_end → {type: "debug", debug_type: "tool_result", ...}
  │
  └─ Middleware chain: after() — cross-validation, warnings, memory store
        │
        ▼
    SSE Event Stream to Frontend
```

### Observability Metrics (Task 5.2)

From `agent_runtime.py` lines 233-237:

```python
self._cold_start_ms: float  # Supervisor build time
self._classification_count: int  # Routing decisions
self._concurrent_failures: int  # Failures during parallel execution
self._total_invocations: int  # Total calls
```

Exposed via `/stats` property (lines 723-737).

---

## 5. Relationship Between Systems

### Arena vs. Orchestration

| Aspect | Arena System | Orchestration Pipelines |
|--------|-------------|------------------------|
| **Purpose** | Multi-agent strategy competition & discussion | DAG-based workflow composition |
| **Model** | Graph-based (discussion rounds, backtesting, trading) | DAG (topological execution) |
| **Entry Point** | Sentinel View (pre-configured) | OrchestrationEditor (user-defined) |
| **Execution** | `MultiAgentArena` (async loop) | `OrchestrationEngine` (topological sort) |
| **Observability** | Real-time thinking stream (SSE) | Node-by-node progress (SSE) |
| **Persistence** | Arena tables in ClickHouse | Pipeline + Execution tables |
| **User Control** | Limited (configurations only) | Full (visual DAG editor) |

### Agent Runtime vs. Orchestration

| Aspect | AgentRuntime | Orchestration |
|--------|-------------|--------------|
| **Coordinator** | LangGraph Supervisor (LLM-based routing) | Kahn's topological sort (deterministic) |
| **Entry Point** | Chat (user query) | OrchestrationList (manual run) |
| **Agent Selection** | Dynamic (Supervisor LLM decides) | Static (user configures DAG) |
| **Execution Model** | Parallel + handoff (LangGraph native) | Sequential (per topological order) |
| **State** | MessagesState (conversation history) | Node dict (node output cache) |

### Agent Teams vs. Orchestration

| Aspect | Agent Teams | Orchestration |
|--------|-------------|--------------|
| **Hierarchy** | 3-tier (fixed structure) | Arbitrary DAG (flexible) |
| **UI** | Tier picker + drag-to-move | Visual canvas editor |
| **Execution** | Hierarchical merging strategy | Topological traversal |
| **Use Case** | Predefined team structures | Custom workflows |

---

## 6. Event Bus & Message Passing

### Is there a unified event bus?

**Answer**: NO — Systems are **modular but separate**:

1. **AgentRuntime** — LangGraph internal event stream (`astream_events`)
   - Converted to SSE format by `adapt_langgraph_event_to_sse()`
   - No shared event bus

2. **Orchestration Engine** — Manual SSE event generation
   - Yields dicts: `{type: "node_start", ...}`, `{type: "node_end", ...}`
   - No shared event bus

3. **Arena System** — Custom `ThinkingStreamProcessor`
   - Publishes to Redis Streams or internal queue
   - Separate from above

**Implication**: 
- Each system has its own **async event stream protocol**
- They can coexist but **don't directly communicate**
- Unified access layer would need to normalize events from all three

### SSE Event Format

**Orchestration Pipeline Events:**
```json
{
  "type": "node_start",
  "node_id": "agent_1",
  "node_type": "agent",
  "label": "Market Analysis",
  "agent_id": "MarketAgent"
}
```

```json
{
  "type": "node_end",
  "node_id": "agent_1",
  "output": "... (truncated to 2000 chars)",
  "duration_ms": 1234
}
```

```json
{
  "type": "complete",
  "output": "... (final output)"
}
```

**AgentRuntime (LangGraph) Events:**
```json
{
  "type": "thinking",
  "agent": "AgentRuntime",
  "status": "正在理解您的需求...",
  "intent": "",
  "stock_codes": []
}
```

```json
{
  "type": "content",
  "content": "..."
}
```

```json
{
  "type": "tool",
  "tool": "get_stock_data",
  "args": {...},
  "status": "调用工具: get_stock_data"
}
```

---

## 7. Data Persistence

### ClickHouse Tables

**Agent Configs:**
```sql
CREATE TABLE agent_configs (
    id String,
    user_id String,
    name String,
    description String,
    avatar String,
    system_prompt String,
    skills Array(String),
    model_config String,  -- JSON
    tags Array(String),
    is_public UInt8,
    status Enum8('active'=1, 'archived'=2, 'deleted'=3),
    version UInt32,
    created_at DateTime,
    updated_at DateTime
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, id)
```

**Orchestration Pipelines:**
```sql
CREATE TABLE orchestration_pipelines (
    id String,
    user_id String,
    name String,
    description String,
    nodes String,           -- JSON list
    edges String,           -- JSON list
    input_schema String,    -- JSON
    output_config String,   -- JSON
    tags Array(String),
    is_public UInt8,
    status Enum8('draft'=1, 'active'=2, 'archived'=3, 'deleted'=4),
    version UInt32,
    created_at DateTime,
    updated_at DateTime
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, id)
```

**Orchestration Executions:**
```sql
CREATE TABLE orchestration_executions (
    id String,
    pipeline_id String,
    user_id String,
    input_data String,      -- JSON
    output_data String,     -- JSON/text
    status Enum8('pending'=1, 'running'=2, 'completed'=3, 'failed'=4, 'cancelled'=5),
    current_node_id String,
    node_results String,    -- JSON
    error_message String,
    started_at DateTime,
    completed_at Nullable(DateTime),
    duration_ms UInt64
) ENGINE = MergeTree()
ORDER BY (user_id, pipeline_id, started_at)
TTL started_at + INTERVAL 90 DAY
```

**Note**: `ReplacingMergeTree(updated_at)` used for pipelines/agents to enable **versioning**.

---

## 8. User Flows

### Flow 1: Create & Run a Custom Agent

```
1. Go to Agent Management → Create Agent
2. Fill: Name, Description, System Prompt, Skills, Model Config
3. Save (stored in agent_configs)
4. Use in orchestration or chat
```

### Flow 2: Create & Run Orchestration Pipeline

```
1. Go to Orchestration → New Pipeline
2. Drag agents, input, output nodes onto canvas
3. Connect edges (data flow)
4. Configure execution mode + merge strategy
5. Save (stored in orchestration_pipelines)
6. Click "Run Team" → Input data → Stream results
```

### Flow 3: Use Predefined Agent Team

```
1. Chat → Select a predefined team (e.g., "Sentinel Stock Selection")
2. System loads team config as orchestration pipeline
3. Executes with 3-tier hierarchy + merge strategy
4. Results streamed back to chat
```

### Flow 4: Chat with AgentRuntime Supervisor

```
1. User types query in chat
2. Middleware filters (non-financial check, memory injection)
3. AgentRuntime supervisor routes to best agent(s)
4. Sub-agents execute in parallel or sequence
5. LangGraph handles state, handoff, streaming
6. Results streamed to frontend as SSE
```

---

## 9. Capabilities & Limitations

### Can Users Create Custom Agent Teams?

**Short Answer**: **Partially**

- ✅ Create custom agents in Agent Management
- ✅ Create custom orchestration pipelines (DAG-based)
- ✅ Compose multi-tier hierarchies via `OrchestrationEditor.vue`
- ❌ No "Agent Teams" UI (only 6 built-in)
- 🟡 Teams are implemented as **pipelines with tier metadata** (`data.tier = 1|2|3`)

**Workaround**: Use OrchestrationEditor to manually:
1. Add agent nodes with `data.tier=1`, `data.tier=2`, `data.tier=3`
2. Configure execution_mode ("hierarchical" or "parallel_then_merge")
3. Set merge_strategy ("llm_summarize", "last_tier", or "vote")
4. Save as custom pipeline

### Current Limitations

1. **No conditional branching** — `NodeType.condition` defined but not implemented
2. **No true parallel execution** — Orchestration engine is sequential
3. **No agent-to-agent communication** — Only upstream→downstream data flow
4. **Teams are pipelines** — 3-tier constraint is UI-level, not enforced backend
5. **No versioning UI** — Versions in DB but no history browser
6. **Limited observability** — Node metrics only; no per-tool latency tracking

---

## 10. File Inventory Summary

### Backend (Complete)

```
src/stock_datasource/
├── models/
│   ├── agent_config.py (89 lines)
│   └── orchestration.py (123 lines)
├── modules/
│   ├── agent_management/
│   │   ├── __init__.py
│   │   └── router.py (493 lines)
│   └── orchestration/
│       ├── __init__.py
│       └── router.py (135 lines)
└── services/
    ├── agent_config_service.py (295 lines)
    ├── agent_registry.py (examined)
    ├── agent_runtime.py (758 lines)
    ├── execution_planner.py (186 lines)
    ├── orchestration_engine.py (202 lines)
    └── orchestration_service.py (352 lines)
```

**Total**: ~3,000 lines of new code

### Frontend (Complete)

```
frontend/src/
├── api/
│   ├── agent.ts (143 lines)
│   └── orchestration.ts (96 lines)
└── views/
    ├── agent-management/
    │   ├── AgentEditor.vue (419 lines)
    │   ├── AgentList.vue (300 lines)
    │   └── RuntimeManagement.vue (111 lines)
    └── orchestration/
        ├── OrchestrationEditor.vue (494 lines)
        └── OrchestrationList.vue (284 lines)
```

**Total**: ~1,847 lines of Vue/TypeScript

### Tests

```
tests/
└── test_agent_runtime.py (examined setup only)
```

---

## 11. Architectural Insights

### Design Patterns

1. **Singleton Pattern**: 
   - `get_agent_runtime()`, `get_orchestration_service()`, `get_agent_config_service()`

2. **Descriptor Pattern** (agent_registry.py):
   - Agents defined declaratively, loaded at runtime
   - Enables dynamic registration without code changes

3. **Adapter Pattern**:
   - `adapt_langgraph_event_to_sse()` — Bridges LangGraph events to legacy SSE format

4. **Repository Pattern**:
   - ClickHouse as data layer (agent_configs, orchestration_pipelines, orchestration_executions)

5. **Middleware Chain Pattern**:
   - `build_default_middleware_chain()` — Before/after hooks for cross-cutting concerns

### Scalability Considerations

1. **Concurrency**: LangGraph Supervisor handles parallel agents natively; orchestration is sequential
2. **Persistence**: ClickHouse TTL policies (90-day retention for executions)
3. **Versioning**: ReplacingMergeTree enables soft-deletes + version history
4. **Memory**: MemorySaver (in-memory) for checkpoints; can swap for distributed store

### Security Model

- **Namespace Isolation**: User IDs isolate agent/pipeline visibility
- **Public Sharing**: `is_public` flag allows opt-in sharing
- **System Agents**: Special `user_id="system"` for built-in agents
- **Runtime Config**: Agents can specify runtime type (CLI paths validated?)

---

## 12. Next Steps & Recommendations

### Feature Roadmap (from comments)

1. **Conditional Nodes** — `NodeType.condition` skeleton exists; implement branch logic
2. **Parallel Execution** — Orchestration engine currently sequential; add concurrent node execution
3. **Agent Communication Protocol** — Enable agent-to-agent messaging
4. **Team Templates** — Save/share orchestration pipelines as reusable team templates
5. **Observability Dashboard** — Real-time metrics for running pipelines/teams
6. **Versioning UI** — Browse and restore previous pipeline versions

### Known TODOs

- Task 4.3: SubAgentEnvelope integration ✓ (in agent_runtime.py)
- Task 5.2: Observability metrics ✓ (cold_start_ms, classification_count, etc.)
- Memory Store + Middleware Chain ✓ (integrated, feature-flagged)

---

## 13. Conclusion

The system has successfully evolved into a **flexible, user-centric multi-agent orchestration platform**:

- **Configurable Agents** replace hardcoded implementations
- **Orchestration Pipelines** provide DAG-based workflow composition
- **Agent Teams** add semantic 3-tier hierarchy with predefined templates
- **LangGraph Supervisor** provides unified control plane for chat interactions
- **Arena System** remains separate for strategy competition use cases

The architecture is **modular, extensible, and production-ready** for building complex multi-agent financial analysis workflows.

---

**Generated**: 2026-05-17  
**Investigator**: Claude Opus 4.6 (1M context)
