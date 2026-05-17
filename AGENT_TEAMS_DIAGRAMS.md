# Agent Teams & Orchestration: Visual Diagrams

## System Architecture Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE LAYER                        │
├───────────────┬──────────────────┬──────────────────┬───────────────┤
│               │                  │                  │               │
│  Chat View    │ Agent Management │ Orchestration    │ Sentinel View │
│  (Query)      │ (CRUD)          │ (DAG Composer)   │ (Teams)       │
│               │                  │                  │               │
└───────────────┴──────────────────┴──────────────────┴───────────────┘
                         │                 │                 │
                         ▼                 ▼                 ▼
                
┌──────────────────────────────────────────────────────────────────────┐
│                      EXECUTION ENGINE LAYER                          │
├──────────────────┬──────────────────┬──────────────────────────────┤
│                  │                  │                              │
│  AgentRuntime    │ Orchestration    │ Arena Manager                │
│  (LangGraph      │ Engine           │ (Discussion +               │
│   Supervisor)    │ (DAG Executor)   │  Backtesting)               │
│                  │                  │                              │
└──────────────────┴──────────────────┴──────────────────────────────┘
         │                  │                       │
         └──────────────────┼───────────────────────┘
                            │
┌──────────────────────────────────────────────────────────────────────┐
│                         SERVICE LAYER                               │
├──────────────┬──────────────────┬────────────────┬──────────────────┤
│              │                  │                │                  │
│ Agent Config │ Agent Registry   │ Skill Registry │ LLM Client       │
│ Service      │ (Descriptors)    │ (Tools)        │ (DeepSeek/Claude)│
│              │                  │                │                  │
└──────────────┴──────────────────┴────────────────┴──────────────────┘
              │                          │
              └──────────────┬───────────┘
                             │
┌──────────────────────────────────────────────────────────────────────┐
│                    PERSISTENCE LAYER                                │
├──────────────┬──────────────────┬────────────────┬──────────────────┤
│              │                  │                │                  │
│ ClickHouse   │ ClickHouse       │ ClickHouse     │ Redis/Memory     │
│ agent_configs│ orchestration_   │ orchestration_ │ Store            │
│              │ pipelines        │ executions     │ (Checkpoints)    │
│              │                  │                │                  │
└──────────────┴──────────────────┴────────────────┴──────────────────┘
```

---

## Agent Teams: 3-Tier Execution Flow

```
                    ┌──────────────────┐
                    │  User Input      │
                    │  Query/Task      │
                    └────────┬─────────┘
                             │
                             ▼
          ╔══════════════════════════════════════╗
          ║      TIER 1: EXECUTION LAYER         ║
          ║  (Data Collection & Monitoring)      ║
          ║                                      ║
          ║  ┌───────────┬───────────┬─────────┐ ║
          ║  │ Market    │ Index     │ ETF     │ ║
          ║  │ Agent     │ Agent     │ Agent   │ ║
          ║  └─────┬─────┴─────┬─────┴────┬────┘ ║
          ║        │           │          │      ║
          ║   Tier 1 Results:  Raw Data   │      ║
          ║   {market_data,    {indices,  │      ║
          ║    prices,         etf_data}  │      ║
          ║    volumes}                   │      ║
          ╚══════════════════════════════════════╝
                             │
                             ▼ Merged Input
          ╔══════════════════════════════════════╗
          ║      TIER 2: ANALYSIS LAYER          ║
          ║  (Processing & Filtering)            ║
          ║                                      ║
          ║  ┌──────────┬──────────┬──────────┐  ║
          ║  │ Report   │ Screener │ Backtest │  ║
          ║  │ Agent    │ Agent    │ Agent    │  ║
          ║  └────┬─────┴────┬─────┴────┬─────┘  ║
          ║       │          │          │        ║
          ║  Tier 2 Results: Analysis   │        ║
          ║  {recommendations,          │        ║
          ║   signals,                  │        ║
          ║   scores}                   │        ║
          ╚══════════════════════════════════════╝
                             │
                             ▼ Aggregated Input
          ╔══════════════════════════════════════╗
          ║      TIER 3: DECISION LAYER          ║
          ║  (Final Synthesis & Strategy)        ║
          ║                                      ║
          ║  ┌────────────────────────────────┐  ║
          ║  │  OverviewAgent / TopListAgent  │  ║
          ║  │  (LLM-based synthesis)         │  ║
          ║  └─────────────┬──────────────────┘  ║
          ║                │                     ║
          ║  Final Output: Strategic Decision    ║
          ║  {decision, reasoning, confidence}   ║
          ╚══════════════════════════════════════╝
                             │
                             ▼
                    ┌──────────────────┐
                    │  User Output     │
                    │  Report/Action   │
                    └──────────────────┘
```

**Execution Modes:**
- `hierarchical`: Tier1→Tier2→Tier3 (sequential, each tier serial)
- `parallel_then_merge`: Within-tier parallel, between-tier sequential
- `all_to_final`: All tier results → final aggregator

**Merge Strategies:**
- `llm_summarize`: LLM synthesizes recommendations
- `last_tier`: Use only final tier output
- `vote`: Consensus/voting mechanism

---

## Orchestration Pipeline: DAG Execution Model

```
         Input Node
              │
              ▼ {message: "analyze AAPL"}
         ┌─────────────┐
         │   INPUT_1   │  state["INPUT_1"] = "analyze AAPL"
         └──────┬──────┘
                │
                ├──────────────┬──────────────┐
                │              │              │
                ▼              ▼              ▼
         ┌──────────┐  ┌──────────┐  ┌──────────┐
         │ AGENT_1  │  │ AGENT_2  │  │ AGENT_3  │  (if DAG allows parallel)
         │ Market   │  │ Report   │  │ Analysis │  or sequential
         │ Agent    │  │ Agent    │  │ Agent    │
         └────┬─────┘  └────┬─────┘  └────┬─────┘
              │ output1      │ output2      │ output3
              ▼              ▼              ▼
         state["AGENT_1"] = "market: ..."
         state["AGENT_2"] = "report: ..."
         state["AGENT_3"] = "analysis: ..."
              │              │              │
              └──────┬───────┴──────┬───────┘
                     │             │
                     ▼             ▼
              ┌───────────────────────┐
              │  AGGREGATOR_1         │  Merges all upstream outputs
              │  (Merge 3 inputs)     │  state["AGG_1"] = "..."
              └──────────┬────────────┘
                         │
                         ▼
              ┌────────────────────┐
              │  OUTPUT_1          │  Collects final result
              │  (Final Output)    │  state["OUTPUT_1"] = final
              └────────────────────┘
                         │
                         ▼
                  User receives result

Topological Sort Order: [INPUT_1, AGENT_1, AGENT_2, AGENT_3, AGG_1, OUTPUT_1]
(Kahn's algorithm computes this)
```

**Node Types:**
- `input`: Receives pipeline input, passes through as-is
- `agent`: Invokes LLM with system prompt + tools
- `condition`: (Planned) Branching based on expression
- `aggregator`: Merges upstream outputs
- `output`: Collects final result

---

## Agent Runtime: LangGraph Supervisor Routing

```
                    User Query
                    "分析最近3月AAPL走势"
                          │
                          ▼
        ┌───────────────────────────────┐
        │ Middleware Chain (before)      │
        │                               │
        │ 1. Non-financial check         │ ◄─── Reject "讲个笑话"
        │ 2. Intent extraction           │ ◄─── "Analyze trend"
        │ 3. Memory injection            │ ◄─── Load conversation history
        └───────────────────┬────────────┘
                            │
                            ▼
        ╔═════════════════════════════════════╗
        ║  LangGraph Supervisor Graph         ║
        ║                                     ║
        ║  Supervisor LLM                     ║ ◄─── "User wants stock trend analysis"
        ║  ┌──────────────────────────┐       ║      "Best agent: MarketAgent"
        ║  │ Available Agents:        │       ║
        ║  │ - MarketAgent            │       ║      Decision: Route to
        ║  │ - ReportAgent            │       ║      MarketAgent
        ║  │ - HKReportAgent          │       ║
        ║  │ - BacktestAgent          │       ║
        ║  │ - ...more                │       ║
        ║  └──────────────────────────┘       ║
        ║           │                         ║
        ║           ▼ Routes to                ║
        ║  ┌─────────────────────────┐        ║
        ║  │  MarketAgent            │        ║
        ║  │  (React Agent)          │        ║
        ║  │                         │        ║
        ║  │ Tools:                  │        ║
        ║  │ - get_kline_data()      │  ◄──┐ Message:
        ║  │ - calculate_indicators()│     │ "分析AAPL 3月走势"
        ║  │ - analyze_trend()       │  ┌──┘
        ║  │ ...                     │  │
        ║  └───────────┬─────────────┘  │
        ║              │                 │
        ║              ▼                 │
        ║          Tool Calls:           │
        ║          "get_kline_data"      │
        ║          "calculate_indicators"│
        ║              │                 │
        ║              ▼ (Tool Results)  │
        ║          State Updated         │
        ║          │                     │
        ║          ▼ (Loop continues     │
        ║          or completes)         │
        ║              │                 │
        ║        Message w/ Analysis     │
        ║        ◄─ Agent Output        │
        ╚═════════════════════════════════════╝
                            │
                            ▼
        ┌───────────────────────────────┐
        │ Middleware Chain (after)       │
        │                               │
        │ 1. Cross-validation            │
        │ 2. Warning injection           │
        │ 3. Memory store commit         │
        └───────────────────┬────────────┘
                            │
                            ▼
        ╔═════════════════════════════════════╗
        ║  SSE Event Stream to Frontend       ║
        ║                                     ║
        ║  {type: "thinking", status: "..."}  ║
        ║  {type: "tool", tool: "...", ...}   ║
        ║  {type: "content", content: "..."}  ║
        ║  {type: "done", metadata: {...}}    ║
        ╚═════════════════════════════════════╝
```

---

## Data Flow: Agent Configuration

```
User UI (Agent Editor)
    │
    │ AgentConfigCreate {name, system_prompt, skills, ...}
    ▼
┌──────────────────────────────────────┐
│ /api/agents/ POST                    │
│ (agents/router.py:create_agent)      │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ AgentConfigService.create_agent()    │
│ (services/agent_config_service.py)   │
│                                      │
│ 1. Generate UUID                     │
│ 2. Serialize config to JSON          │
│ 3. Insert into agent_configs table   │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ ClickHouse                           │
│                                      │
│ INSERT INTO agent_configs (          │
│   id, user_id, name,                 │
│   system_prompt, skills,             │
│   model_config, version,             │
│   status, created_at                 │
│ ) VALUES (...)                       │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ AgentRegistry.get_agent()            │
│ (services/agent_registry.py)         │
│                                      │
│ Loads descriptor on-demand           │
│ Returns to supervisor for routing    │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ Agent available in:                  │
│ - Chat (AgentRuntime routing)        │
│ - Orchestration (pipeline nodes)     │
│ - Agent Teams (tier assignments)     │
└──────────────────────────────────────┘
```

---

## Pipeline Execution: Node-by-Node Streaming

```
Pipeline Start
    │
    ▼
SSE: {type: "pipeline_start", execution_id: "...", pipeline_id: "..."}
    │
    ├─▶ Node 1 (INPUT)
    │   │
    │   ├─ SSE: {type: "node_start", node_id: "input_1", ...}
    │   ├─ Execute: state["input_1"] = input_data["message"]
    │   └─ SSE: {type: "node_end", node_id: "input_1", output: "...", duration_ms: 10}
    │
    ├─▶ Node 2 (AGENT)
    │   │
    │   ├─ SSE: {type: "node_start", node_id: "agent_1", agent_id: "MarketAgent"}
    │   ├─ Execute: LLM call with system prompt + input
    │   │   (Upstream outputs collected: state["input_1"])
    │   │   (Built message: input from edges)
    │   │   (Called LLM, got response)
    │   └─ SSE: {type: "node_end", node_id: "agent_1", output: "...", duration_ms: 1234}
    │
    ├─▶ Node 3 (AGENT)
    │   │
    │   ├─ SSE: {type: "node_start", node_id: "agent_2", agent_id: "ReportAgent"}
    │   ├─ Execute: Collect upstream (agent_1 output), call LLM
    │   └─ SSE: {type: "node_end", node_id: "agent_2", output: "...", duration_ms: 2456}
    │
    ├─▶ Node 4 (AGGREGATOR)
    │   │
    │   ├─ Execute: Merge state["agent_1"] + state["agent_2"]
    │   └─ SSE: {type: "node_end", node_id: "agg_1", output: "merged result"}
    │
    ├─▶ Node 5 (OUTPUT)
    │   │
    │   ├─ Execute: Collect final outputs, format
    │   └─ SSE: {type: "node_end", node_id: "output_1", output: "final"}
    │
    └─▶ Pipeline Complete
        │
        └─ SSE: {type: "complete", output: "final result"}
           SSE: {type: "pipeline_end", execution_id: "...", duration_ms: 3700}
```

---

## Security & Isolation Model

```
┌─────────────────────────────────────────┐
│  User A                                 │
│  (user_id: "user-123")                  │
│                                         │
│  ├─ Agent: MyAgent (private)            │
│  │  user_id: "user-123", is_public: 0   │
│  │                                      │
│  ├─ Pipeline: MyPipeline (private)      │
│  │  user_id: "user-123", is_public: 0   │
│  │                                      │
│  └─ Pipeline: SharedPipeline (public)   │
│     user_id: "user-123", is_public: 1   │
└─────────────────────────────────────────┘
        ▼
┌─────────────────────────────────────────┐
│  User B                                 │
│  (user_id: "user-456")                  │
│                                         │
│  Can access:                            │
│  ├─ Own agents & pipelines              │
│  ├─ User A's SharedPipeline (public)    │
│  ├─ System agents (user_id: "system")   │
│  └─ NOT User A's MyAgent (private)      │
│                                         │
│  Query: WHERE                           │
│    (user_id = 'user-456'                │
│     OR user_id = 'system'               │
│     OR is_public = 1)                   │
└─────────────────────────────────────────┘

Queries in code:
- get_agent(): Filters by user_id or is_public
- list_pipelines(): Filters by user_id or is_public
- list_agents(): Filters by user_id or is_public
```

---

## Versioning in ClickHouse

```
Agent Configuration Timeline:

INSERT INTO agent_configs (id, user_id, name, version, status, updated_at)
VALUES (
  "agent-uuid",
  "user-123",
  "MarketAgent",
  1,          ◄─ First version
  "active",
  "2026-05-15 10:00:00"
)

        (User edits system_prompt)
              │
              ▼

INSERT INTO agent_configs (id, user_id, name, version, status, updated_at)
VALUES (
  "agent-uuid",
  "user-123",
  "MarketAgent",
  2,          ◄─ Version incremented
  "active",
  "2026-05-15 10:30:00"
)

        (User deletes agent)
              │
              ▼

INSERT INTO agent_configs (id, user_id, name, version, status, updated_at)
VALUES (
  "agent-uuid",
  "user-123",
  "MarketAgent",
  3,          ◄─ Version incremented
  "deleted",  ◄─ Soft delete
  "2026-05-15 11:00:00"
)

Engine: ReplacingMergeTree(updated_at)
  ▼
SELECT * FROM agent_configs FINAL
WHERE id = 'agent-uuid'
ORDER BY updated_at DESC
LIMIT 1

Result: Version 3 (deleted)
         - Can restore by inserting version 4 with status="active"
         - Full history preserved in table
```

---

## Arena vs. Orchestration: Feature Comparison

```
                    Arena System          Orchestration Pipeline
                    ──────────────        ──────────────────────

PURPOSE             Strategy competition  DAG workflow composition
                    + discussion          

TOPOLOGY            Multi-round loop      Directed Acyclic Graph

AGENTS              Fixed set per arena   User-configurable nodes

ENTRY POINT         Sentinel View         Orchestration UI
                    (Predefined)          (User-defined)

EXECUTION           Async loop            Topological sort
                    with pausing          (sequential/deterministic)

PERSISTENCE         Arena tables          Pipeline + Execution tables
                    (competition state)   (DAG + run history)

OBSERVABILITY       Thinking stream       Node-by-node events
                    (SSE)                 (SSE)

USER CONTROL        Medium                High
                    (Configurations only) (Full DAG design)

USE CASE            Strategy selection    Custom multi-step workflows
                    Stock backtesting     Research pipelines
                    Competitive analysis  Analysis chains

PARALLELISM         ✓ Within each round    ✗ Sequential (planned)
                    ✓ Background execution

STATEFUL            ✓ Extensive            ✗ Stateless nodes
                    (Scores, rankings)

PERSISTENCE         ✓ Long-term            ✗ Temporary
                    (Strategy tracking)    (90-day TTL)
```

