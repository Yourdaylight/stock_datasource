# Agent Teams & Orchestration Investigation: Quick Reference

**Investigator**: Claude Opus 4.6 (1M context)  
**Date**: 2026-05-17  
**Repository**: `/root/lzh/stock_datasource`  
**Commit**: `032d83f` - "feat: Agent中心 — 可配置化Agent平台 + Agent Teams层级编排"

---

## 📋 What You Asked & What We Found

### ✅ Question 1: What is an "Agent Team" / orchestration pipeline?

**Agent Teams** are **3-tier hierarchical structures** where agents are organized by capability:
- **Tier 1 (Execution)**: Data gathering agents (MarketAgent, IndexAgent, EtfAgent)
- **Tier 2 (Analysis)**: Processing agents (ReportAgent, ScreenerAgent, BacktestAgent)
- **Tier 3 (Decision)**: Synthesis agents (OverviewAgent, TopListAgent)

**Orchestration Pipelines** are **DAG-based workflows** where:
- Nodes represent operations (agent invocations, input/output, aggregation)
- Edges represent data flow
- Execution follows topological order (Kahn's algorithm)

### ✅ Question 2: Can users create custom agent teams?

**Partially.** Users can:
- ✅ Create custom agents via UI (Agent Management)
- ✅ Create custom pipelines via visual DAG editor (Orchestration)
- ✅ Compose 3-tier hierarchies (add agents to tier 1/2/3)
- ❌ No dedicated "Agent Teams UI" (only 6 built-in teams)

**Workaround**: Pipelines with `data.tier` metadata implement teams functionally.

### ✅ Question 3: How does an Agent Team execute?

**Two pathways:**

1. **Orchestration Pipeline Path** (user-defined):
   ```
   Input → [Tier 1 Agents] → [Tier 2 Agents] → [Tier 3 Agents] → Output
   ```
   Execution modes: `hierarchical`, `parallel_then_merge`, `all_to_final`
   Merge strategies: `llm_summarize`, `last_tier`, `vote`

2. **Arena System Path** (predefined, separate):
   ```
   Discussion → Backtesting → Simulated Trading → Evaluation
   ```
   Independent from orchestration; used for strategy competition.

### ✅ Question 4: What is the relationship between orchestration and Arena?

**They are independent systems:**
- **Orchestration**: DAG-based, deterministic, user-defined, temporary (90-day TTL)
- **Arena**: Async loop, evolutionary, system-managed, persistent (strategy tracking)
- **No shared event bus** between them (both SSE-based but separate)
- Both use different execution engines and persistence models

### ✅ Question 5: Is there a unified event bus / message passing system?

**No.** Three separate event systems:
1. **AgentRuntime** (Chat) — LangGraph internal `astream_events` → SSE
2. **Orchestration Engine** — Manual SSE event generation (`node_start`, `node_end`)
3. **Arena System** — Custom `ThinkingStreamProcessor` → Redis/internal queue

**Implication**: Systems are modular but don't directly communicate. Unified layer would need to normalize all three.

---

## 📁 File Paths Summary

### Backend Core

| File | Lines | Purpose |
|------|-------|---------|
| `src/stock_datasource/models/agent_config.py` | 89 | Agent configuration schema |
| `src/stock_datasource/models/orchestration.py` | 123 | Pipeline DAG schema |
| `src/stock_datasource/services/agent_config_service.py` | 295 | Agent CRUD + ClickHouse |
| `src/stock_datasource/services/agent_runtime.py` | 758 | LangGraph Supervisor |
| `src/stock_datasource/services/orchestration_engine.py` | 202 | DAG executor |
| `src/stock_datasource/services/orchestration_service.py` | 352 | Pipeline CRUD |
| `src/stock_datasource/modules/agent_management/router.py` | 493 | Agent API routes |
| `src/stock_datasource/modules/orchestration/router.py` | 135 | Pipeline API routes |

**Total Backend**: ~2,447 lines

### Frontend UI

| File | Lines | Purpose |
|------|-------|---------|
| `frontend/src/api/agent.ts` | 143 | Agent API client |
| `frontend/src/api/orchestration.ts` | 96 | Pipeline API client |
| `frontend/src/views/agent-management/AgentList.vue` | 300 | Agent grid view |
| `frontend/src/views/agent-management/AgentEditor.vue` | 419 | Agent form |
| `frontend/src/views/orchestration/OrchestrationList.vue` | 284 | Pipeline list |
| `frontend/src/views/orchestration/OrchestrationEditor.vue` | 494 | DAG visual editor |

**Total Frontend**: ~1,736 lines

---

## 🏗️ System Architecture

```
User Interface (Vue)
  ↓
API Routes (FastAPI)
  ↓ GET/POST/PUT/DELETE
Execution Engines
  ├─ AgentRuntime (LangGraph Supervisor)
  ├─ OrchestrationEngine (Topological sort)
  └─ MultiAgentArena (Async loop)
  ↓
Shared Services
  ├─ AgentConfigService (CRUD)
  ├─ AgentRegistry (Descriptors)
  └─ LLM Client (DeepSeek/Claude)
  ↓
ClickHouse Persistence
  ├─ agent_configs
  ├─ orchestration_pipelines
  ├─ orchestration_executions
  └─ Arena tables
```

---

## 🔌 API Endpoints

### Agent Management
```
GET    /api/agents/
POST   /api/agents/
GET    /api/agents/{id}
PUT    /api/agents/{id}
DELETE /api/agents/{id}
```

### Orchestration Pipelines
```
GET    /api/orchestrations/
POST   /api/orchestrations/
GET    /api/orchestrations/{id}
PUT    /api/orchestrations/{id}
DELETE /api/orchestrations/{id}
POST   /api/orchestrations/{id}/execute          # SSE stream
GET    /api/orchestrations/{id}/executions       # History
```

---

## 💾 Data Models (Pydantic)

### Agent Configuration
```python
AgentConfigCreate {
  name: str
  system_prompt: str
  skills: list[str]                    # Platform tools
  model_config_data: {model, temperature, max_tokens}
  runtime_config: {type, command, working_dir}
  tags: list[str]
  is_public: bool
}
```

### Pipeline
```python
PipelineCreate {
  name: str
  nodes: list[PipelineNode]            # Agent, input, output, aggregator
  edges: list[PipelineEdge]            # Data connections
  input_schema: dict                   # Validation
  output_config: dict                  # Formatting
}

PipelineNode {
  id: str
  type: "agent" | "input" | "output" | "condition" | "aggregator"
  label: str
  data: dict                           # agent_id, tier, default_input, etc.
  position: {x, y}                     # UI layout
}
```

---

## 🚀 Execution Modes

### Orchestration Pipelines (3 modes)

| Mode | Behavior | Use Case |
|------|----------|----------|
| `hierarchical` | Tier1→Tier2→Tier3 all sequential | Strict layered analysis |
| `parallel_then_merge` | Within-tier parallel, between-tier seq | Efficient multi-agent |
| `all_to_final` | All results → final aggregator | Direct synthesis |

### Merge Strategies (3 strategies)

| Strategy | Behavior | Use Case |
|----------|----------|----------|
| `llm_summarize` | LLM synthesizes | Intelligent summarization |
| `last_tier` | Use final tier only | Simple top-down |
| `vote` | Consensus voting | Quorum-based decision |

---

## 📊 ClickHouse Schema

### Agent Configs Table
```sql
CREATE TABLE agent_configs (
  id String,
  user_id String,
  name String,
  system_prompt String,
  skills Array(String),
  model_config String,        -- JSON
  status Enum8(...),
  version UInt32,
  created_at DateTime,
  updated_at DateTime
) ENGINE ReplacingMergeTree(updated_at)
ORDER BY (user_id, id)
```

### Pipelines Table
```sql
CREATE TABLE orchestration_pipelines (
  id String,
  user_id String,
  name String,
  nodes String,               -- JSON
  edges String,               -- JSON
  status Enum8(...),
  version UInt32,
  created_at DateTime,
  updated_at DateTime
) ENGINE ReplacingMergeTree(updated_at)
ORDER BY (user_id, id)
```

### Executions Table
```sql
CREATE TABLE orchestration_executions (
  id String,
  pipeline_id String,
  user_id String,
  input_data String,          -- JSON
  output_data String,
  status Enum8(...),
  node_results String,        -- JSON
  started_at DateTime,
  completed_at Nullable(DateTime),
  duration_ms UInt64
) ENGINE MergeTree()
ORDER BY (user_id, pipeline_id, started_at)
TTL started_at + INTERVAL 90 DAY
```

---

## 🔒 Security Model

**User Isolation:**
- Private agents/pipelines: `user_id = "user-123"`, `is_public = 0`
- Public agents/pipelines: `user_id = "user-123"`, `is_public = 1`
- System agents: `user_id = "system"` (visible to all)

**Query Filter (applied everywhere):**
```sql
WHERE (user_id = :current_user OR user_id = 'system' OR is_public = 1)
```

---

## 📈 6 Built-in Agent Teams

1. **Sentinel Smart Stock Selection** — 哨兵智能选股
2. **Single Stock Comprehensive Checkup** — 个股全面体检
3. **Industry Deep Research** — 行业深度研究
4. **Market Trend Analysis** — 市场趋势分析
5. **Strategy Backtesting** — 策略回测
6. **Portfolio Optimization** — 组合优化

(Stored in DB with `user_id = "system"`)

---

## 🧠 10 Built-in Agents

1. **MarketAgent** — Real-time market data & trends
2. **ReportAgent** — Financial analysis & reports (A-stock)
3. **HKReportAgent** — Hong Kong stocks specific
4. **IndexAgent** — Index tracking & analysis
5. **EtfAgent** — ETF data & strategies
6. **ScreenerAgent** — Stock screening & filtering
7. **BacktestAgent** — Strategy backtesting
8. **OverviewAgent** — Market overview synthesis
9. **TopListAgent** — Top-performing stocks
10. **KnowledgeAgent** — Document/knowledge retrieval

(Stored as system agents, `user_id = "system"`)

---

## 🔄 Key Design Patterns

| Pattern | Implementation | Example |
|---------|-----------------|---------|
| **Singleton** | Getter functions | `get_agent_runtime()`, `get_orchestration_service()` |
| **Descriptor** | Agent registry | Agent metadata loaded at runtime |
| **Adapter** | Event translation | `adapt_langgraph_event_to_sse()` |
| **Repository** | ClickHouse access | `AgentConfigService.create_agent()` |
| **Middleware Chain** | Before/after hooks | Memory injection, cross-validation |

---

## ⚠️ Known Limitations

| Issue | Status | Impact |
|-------|--------|--------|
| No conditional branching | NodeType defined but not implemented | Can't do if/else in pipelines |
| No true parallelism | Sequential topological traversal | Agents run one at a time |
| No agent-to-agent messaging | Only upstream→downstream flow | Can't create bidirectional pipes |
| Teams are pipelines | Tier constraint UI-level only | No enforcement of 3-tier hierarchy |
| No versioning UI | Versions in DB but not browsable | Can't restore past versions |
| No unified event bus | Three separate systems | Harder to monitor holistically |

---

## 🚧 Planned Improvements

1. **Conditional Nodes** — Implement `NodeType.condition` for branching
2. **Parallel Execution** — Add concurrent node traversal
3. **Agent Communication** — Enable inter-agent messaging protocol
4. **Team Templates** — Save/share pipelines as reusable structures
5. **Observability Dashboard** — Real-time metrics + visualization
6. **Versioning UI** — Browse and restore pipeline versions

---

## 📚 Reference Documents

1. **AGENT_TEAMS_ARCHITECTURE.md** (this repo)
   - Comprehensive 13-section deep dive
   - File inventories
   - Detailed schemas
   - User flows

2. **AGENT_TEAMS_DIAGRAMS.md** (this repo)
   - Visual system architecture
   - 3-tier execution flow
   - DAG execution model
   - Event routing diagrams
   - Data flow and security models

3. **Source Code References**
   - `services/agent_runtime.py` — Lines 1-758
   - `services/orchestration_engine.py` — Lines 1-202
   - `modules/orchestration/router.py` — Lines 1-135
   - `models/orchestration.py` — Lines 1-123
   - Frontend: `views/orchestration/OrchestrationEditor.vue` — Lines 1-494

---

## 🎯 Quick Start Examples

### Example 1: Create a Custom Agent

```typescript
// Frontend: Agent Management → Create Agent
const agent = {
  name: "CustomAnalyst",
  description: "Analyzes custom signals",
  system_prompt: "You are a custom stock analyst...",
  skills: ["get_stock_data", "calculate_indicators"],
  model_config_data: {
    model: "DeepSeek-V4-Pro",
    temperature: 0.7,
    max_tokens: 2048
  }
}

await createAgent(agent)  // Stored in agent_configs table
```

### Example 2: Create a 2-Tier Pipeline

```typescript
// Frontend: Orchestration → New Pipeline
const pipeline = {
  name: "Market Analysis Pipeline",
  nodes: [
    {id: "input_1", type: "input", label: "Query"},
    {id: "agent_1", type: "agent", label: "Tier 1", data: {agent_id: "MarketAgent", tier: 1}},
    {id: "agent_2", type: "agent", label: "Tier 2", data: {agent_id: "ReportAgent", tier: 2}},
    {id: "output_1", type: "output", label: "Result"}
  ],
  edges: [
    {source: "input_1", target: "agent_1"},
    {source: "agent_1", target: "agent_2"},
    {source: "agent_2", target: "output_1"}
  ]
}

await createPipeline(pipeline)
```

### Example 3: Execute a Pipeline

```typescript
// Frontend: Orchestration List → Run
const response = await fetch('/api/orchestrations/{id}/execute', {
  method: 'POST',
  body: JSON.stringify({input_data: {message: "Analyze AAPL"}})
})

// Listen to SSE stream
const reader = response.body.getReader()
const decoder = new TextDecoder()
// Process events: node_start, node_end, complete
```

---

## ✅ Investigation Checklist

- [x] List all orchestration files and read main ones
- [x] Understand Agent Teams definition and structure
- [x] Explain user ability to create custom teams
- [x] Document Agent Team execution flow
- [x] Examine execution_planner.py usage
- [x] Analyze frontend API and Vue components
- [x] Investigate agent_runtime.py for Runtime system
- [x] Compare Arena system vs. orchestration
- [x] Identify event bus / message passing
- [x] Map all architectural relationships
- [x] Report file paths and design patterns

---

## 📖 How to Use This Documentation

1. **Quick Overview**: Read this file (5 min)
2. **Architecture Deep Dive**: Read `AGENT_TEAMS_ARCHITECTURE.md` (20 min)
3. **Visual Reference**: Check `AGENT_TEAMS_DIAGRAMS.md` (10 min)
4. **Source Code**: Use file paths to dig into implementation
5. **Examples**: Copy quick start snippets for reference

---

**End of Summary Document**

Generated: 2026-05-17  
Investigator: Claude Opus 4.6 (1M context)  
