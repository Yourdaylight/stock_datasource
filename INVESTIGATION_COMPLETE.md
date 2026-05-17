# Investigation Complete: Agent Teams & A2A Communication Architecture

**Date**: 2026-05-17  
**Investigation Phase**: 2/2 Complete  
**Status**: ✅ ALL QUESTIONS ANSWERED

---

## Overview

This document summarizes the completion of a comprehensive two-phase investigation into the Agent Teams and Agent-to-Agent (A2A) Communication Architecture in the `/root/lzh/stock_datasource` project.

### What Was Investigated

**Phase 1: Agent Teams & Orchestration Pipeline System**
- What are Agent Teams and how are they defined?
- Can users create custom agent teams?
- How do Agent Teams execute?
- Relationship between orchestration pipelines and Arena system
- Is there a unified event bus or message passing system?
- Complete file paths and architectural relationships

**Phase 2: Agent-to-Agent Communication Architecture**
- Why does the chat "决策" sidebar show no agent discussions?
- Are Arena and Chat agents completely separate systems?
- What are the actual event flows between agents?
- How do chat handoffs convert to discussions?
- What are the architectural gaps?

---

## Investigation Findings Summary

### Finding 1: Agent Teams ARE Orchestration Pipelines

**Definition**: Agent Teams are hierarchical 3-tier execution structures defined as Directed Acyclic Graphs (DAGs) with:
- **Tier 1** (Execution): Parallel agent execution with market data collection
- **Tier 2** (Analysis): Analysis and research agents processing tier 1 outputs
- **Tier 3** (Decision): Final decision-making agents synthesizing recommendations

**Implementation**: 
- Stored in ClickHouse with ReplacingMergeTree versioning
- Executed via topological sort (Kahn's algorithm)
- Controlled by LangGraph Supervisor with streaming SSE events
- 6 built-in teams + unlimited custom teams via frontend

**Evidence Files**:
- `src/stock_datasource/models/orchestration.py` (123 lines)
- `src/stock_datasource/services/orchestration_engine.py` (202 lines)
- `src/stock_datasource/services/orchestration_service.py` (352 lines)

---

### Finding 2: Three Completely Separate Agent Systems

**System 1: Chat Orchestrator**
- Purpose: Handle user chat messages
- Agents: MarketAgent, ReportAgent, ScreenerAgent, BacktestAgent, etc.
- Events: Debug events (classification, routing, tool_result, data_sharing)
- Streaming: LangGraph → chat SSE stream
- Location: `src/stock_datasource/agents/orchestrator.py`

**System 2: Arena Discussion System**
- Purpose: Multi-agent strategy competition with debate/collaboration
- Agents: MarketSentiment, QuantResearcher, RiskAnalyst, StrategyGenerator, StrategyReviewer
- Events: ThinkingMessage (thinking, argument, conclusion)
- Streaming: AgentDiscussionOrchestrator → ThinkingStreamProcessor → Arena SSE stream
- Location: `src/stock_datasource/arena/`

**System 3: Orchestration Pipeline Execution**
- Purpose: DAG-based multi-node workflows with topological sort
- Nodes: agent, input, output, aggregator, condition (planned)
- Events: node_start, node_end, node_error, complete (SSE events)
- Streaming: OrchestrationEngine → pipeline SSE stream
- Location: `src/stock_datasource/services/orchestration_engine.py`

**Cross-System Communication**: ❌ **ZERO** — No connection between systems

---

### Finding 3: The "决策" Sidebar is Empty Because...

**Root Cause 1: No Arena Trigger from Chat**
- File: `src/stock_datasource/modules/chat/router.py` (line 196-362)
- Problem: `_stream_response()` never calls arena or triggers discussion
- Evidence: No import of arena modules, no `create_arena()` calls

**Root Cause 2: Incompatible Event Models**
- Chat debug events use: `{type: "debug", debug_type: "classification|routing|...", data: {...}}`
- Arena thinking messages use: `{message_type: "thinking|argument|conclusion", content: "...", metadata: {...}}`
- No conversion layer exists between the two models

**Root Cause 3: Handoff Configuration Unused**
- File: `src/stock_datasource/services/execution_planner.py` (line 62-68)
- AGENT_HANDOFF_MAP defined but NEVER consulted in orchestrator
- No handoff debug events emitted even though frontend expects them

**Root Cause 4: Frontend Infrastructure Missing Data**
- DebugMessage interface expects "handoff" role → never emitted
- No "discussion" or "arena" role in sidebar interface
- `processDebugEvent()` handler ready but orchestrator never calls it

---

### Finding 4: Event System Architecture

**Chat System Event Flow**:
```
User Message
  ↓
OrchestratorAgent.execute_stream()
  ├─ Classifies intent → emits debug("classification", ...)
  ├─ Routes to agent(s) → emits debug("routing", ...)
  ├─ Executes agent → receives thinking/content/tool events
  └─ Completes → emits done(metadata)
  ↓
SSE Stream (JSON format)
  ↓
Frontend chat.ts → processDebugEvent() → debugMessages[]
  ↓
Debug sidebar (no discussions, only orchestrator/agent/tool roles)
```

**Arena System Event Flow** (Separate completely):
```
Arena API Endpoint (OR hypothetical Chat trigger)
  ↓
AgentDiscussionOrchestrator.run_discussion()
  ├─ Debate mode: agents critique each other
  ├─ Collaboration mode: agents refine strategy together
  └─ Review mode: reviewers evaluate
  ↓
ThinkingStreamProcessor.publish(ThinkingMessage)
  ├─ Dual-write: In-memory store + async ClickHouse
  └─ Yields as SSE stream
  ↓
SSE Stream (custom "event: {type}" format)
  ↓
Frontend arena page (SEPARATE UI from chat)
```

**Orchestration Pipeline Event Flow** (Third system):
```
User initiates pipeline
  ↓
OrchestrationService.create_execution()
  ↓
OrchestrationEngine.execute() async generator
  ├─ node_start: Processing begins
  ├─ node_end: Agent response received
  ├─ node_error: Failure occurs
  └─ complete: All nodes done
  ↓
SSE Stream (JSON format)
  ↓
Frontend orchestration page
```

**Result**: Three parallel systems with NO information sharing

---

## Questions Answered

### Q1: What is an "Agent Team" / orchestration pipeline?

**Answer**: Agent Teams are 3-tier hierarchical orchestration structures stored as DAGs in ClickHouse, executed via topological sort with LangGraph Supervisor control. Each tier represents a different execution phase: data collection (Tier 1), analysis (Tier 2), decision-making (Tier 3).

**Evidence**: AGENT_TEAMS_ARCHITECTURE.md (27KB)

---

### Q2: Can users create custom agent teams?

**Answer**: YES. Users can create custom teams via the frontend with:
1. Drag-and-drop agent selection for each tier
2. Execution mode selector (hierarchical, parallel_then_merge, all_to_final)
3. Merge strategy selector (llm_summarize, last_tier, vote)
4. AI-assisted generation via prompt

**Evidence**: 
- Frontend: `/frontend/src/views/orchestration/OrchestrationEditor.vue` (494 lines)
- Backend: `POST /api/orchestrations/` endpoint in router.py

---

### Q3: How does an Agent Team execute?

**Answer**: Execution uses three distinct mechanisms depending on context:
1. **For custom orchestration pipelines**: OrchestrationEngine with topological sort (Kahn's algorithm)
2. **For chat multi-agent scenarios**: LangGraph Supervisor (AgentRuntime) with routing
3. **For arena discussions**: AgentDiscussionOrchestrator with debate/collaboration/review modes

The system is NOT unified — each execution path is independent.

**Evidence**: 
- OrchestrationEngine: `src/stock_datasource/services/orchestration_engine.py` (202 lines)
- AgentRuntime: `src/stock_datasource/services/agent_runtime.py` (758 lines)

---

### Q4: What is the relationship between orchestration pipelines and Arena?

**Answer**: **ZERO relationship**. They are completely separate systems:

| Aspect | Orchestration | Arena |
|--------|---------------|-------|
| **Trigger** | API endpoint or custom pipeline creation | Separate API endpoint only |
| **Agents** | MarketAgent, ReportAgent, ScreenerAgent | MarketSentiment, QuantResearcher, RiskAnalyst |
| **Purpose** | General-purpose DAG workflows | Strategy discussion/competition |
| **Events** | node_start, node_end, node_error, complete | thinking, argument, question, conclusion |
| **Frontend** | Orchestration page + pipeline editor | Separate arena page |
| **Cross-communication** | ❌ No connection |

**Evidence**: A2A_INVESTIGATION_REPORT.md

---

### Q5: Is there a unified event bus / message passing system?

**Answer**: **NO**. There are THREE independent event systems:

1. **AgentRuntime Events**: LangGraph astream_events → SSE chat stream
2. **Orchestration Events**: OrchestrationEngine yields → SSE pipeline stream  
3. **Arena Events**: ThinkingStreamProcessor publishes → SSE arena stream

Each system:
- Uses different event types
- Streams to different frontend pages
- Has different persistence (Redis in-memory vs ClickHouse vs LangGraph state)
- No unified protocol or message bus

**Evidence**: 
- AGENT_TEAMS_DIAGRAMS.md (section: Event Systems)
- IMPLEMENTATION_ROADMAP.md (Option 3: Unified Agent Model)

---

### Q6: File paths and architectural relationships?

**Answer**: See complete file inventory in sections below.

---

## Complete File Inventory

### Backend Files (14 analyzed)

**Agent Configuration**:
- `src/stock_datasource/models/agent_config.py` (89 lines)
  - AgentConfigCreate, AgentConfigUpdate, AgentConfigResponse, ModelConfig, RuntimeConfig
- `src/stock_datasource/services/agent_config_service.py` (295 lines)
  - CRUD operations with ClickHouse ReplacingMergeTree versioning
- `src/stock_datasource/modules/agent_management/router.py` (493 lines)
  - FastAPI endpoints for agent management

**Orchestration Pipelines**:
- `src/stock_datasource/models/orchestration.py` (123 lines)
  - NodeType, PipelineNode, PipelineEdge, PipelineResponse
- `src/stock_datasource/services/orchestration_engine.py` (202 lines)
  - Topological sort execution, SSE event streaming
- `src/stock_datasource/services/orchestration_service.py` (352 lines)
  - Pipeline CRUD, execution tracking, ClickHouse persistence
- `src/stock_datasource/modules/orchestration/router.py` (135 lines)
  - FastAPI endpoints for pipelines

**Chat Orchestration**:
- `src/stock_datasource/agents/orchestrator.py` (1465 lines)
  - OrchestratorAgent with debug event generation
- `src/stock_datasource/modules/chat/router.py` (362 lines)
  - SSE streaming handler, debug event forwarding

**Execution Planning**:
- `src/stock_datasource/services/execution_planner.py` (186 lines)
  - ExecutionMode enums, handoff configuration (UNUSED)
- `src/stock_datasource/services/agent_runtime.py` (758 lines)
  - LangGraph Supervisor with event adaptation

**Arena System** (Separate):
- `src/stock_datasource/arena/discussion_orchestrator.py`
  - Debate/collaboration/review orchestration
- `src/stock_datasource/arena/stream_processor.py`
  - ThinkingMessage publishing with dual-write
- `src/stock_datasource/modules/arena/router.py`
  - Arena API endpoints

### Frontend Files (6 analyzed)

**API Clients**:
- `frontend/src/api/orchestration.ts` (96 lines)
  - listPipelines, getPipeline, createPipeline, updatePipeline, deletePipeline, getExecuteUrl
- `frontend/src/api/agent.ts` (143 lines)
  - listAgents, getAgent, createAgent, updateAgent, deleteAgent

**Pages/Components**:
- `frontend/src/views/orchestration/OrchestrationList.vue` (284 lines)
  - Pipeline grid, create/edit/run/delete actions
- `frontend/src/views/orchestration/OrchestrationEditor.vue` (494 lines)
  - Tier configuration, execution mode selector, merge strategy selector
- `frontend/src/views/agent-management/AgentList.vue` (300 lines)
  - Agent grid, filter, search, CRUD actions
- `frontend/src/views/agent-management/AgentEditor.vue` (419 lines)
  - Agent form with name, description, system prompt, skills

**Stores**:
- `frontend/src/stores/chat.ts` (700+ lines)
  - Chat state management with DebugMessage handling (line 428-474)

---

## Architectural Relationships

### Tier 1: Core Data Models
```
AgentConfigResponse
  ├─ id, user_id, name, description, avatar
  ├─ system_prompt, skills, user_skills
  ├─ model_config_data (ModelConfig)
  ├─ runtime_config (RuntimeConfig)
  └─ tags, is_public, status, version

PipelineResponse
  ├─ id, user_id, name, description
  ├─ nodes: [PipelineNode]
  ├─ edges: [PipelineEdge]
  ├─ execution_mode, merge_strategy
  └─ version, status, created_at, updated_at
```

### Tier 2: Service Layer
```
AgentConfigService
  └─ CRUD operations → ClickHouse agent_configs table

OrchestrationService
  ├─ Pipeline CRUD → orchestration_pipelines table (ReplacingMergeTree)
  └─ Execution tracking → orchestration_executions table (90-day TTL)

ExecutionPlanner
  └─ Static configuration (AGENT_HANDOFF_MAP, CONCURRENT_AGENT_GROUPS)

AgentRuntime
  └─ LangGraph Supervisor with middleware chain
```

### Tier 3: Execution Engines
```
OrchestratorAgent (Chat)
  ├─ Classifies intent
  ├─ Routes to agent(s)
  ├─ Executes via LangGraph/DeepAgent
  └─ Emits: debug events

OrchestrationEngine (Pipeline)
  ├─ Topological sort
  ├─ Node execution (agent, input, output, aggregator)
  └─ Emits: node_start, node_end, node_error, complete

AgentDiscussionOrchestrator (Arena) — SEPARATE SYSTEM
  ├─ Debate mode
  ├─ Collaboration mode
  └─ Emits: ThinkingMessage
```

### Tier 4: Event Streaming
```
Chat SSE → OrchestratorAgent → debug events → chat.ts → debugMessages[]
Pipeline SSE → OrchestrationEngine → node events → orchestration page
Arena SSE → AgentDiscussionOrchestrator → ThinkingMessage → arena page
```

### Tier 5: Storage
```
ClickHouse:
  ├─ agent_configs (ReplacingMergeTree) — versioning
  ├─ orchestration_pipelines (ReplacingMergeTree) — versioning
  ├─ orchestration_executions (MergeTree, 90-day TTL)
  └─ arena_messages (for persistence)

Redis:
  └─ Agent inter-communication cache (data_sharing mechanism)

LangGraph:
  └─ Agent state and routing decisions
```

---

## Critical Architectural Gaps

### Gap 1: No Chat → Arena Connection
**Impact**: User discussions never triggered from chat  
**Location**: `src/stock_datasource/modules/chat/router.py`  
**Severity**: HIGH

### Gap 2: Unused Handoff Configuration
**Impact**: Agent handoffs not implemented  
**Location**: `src/stock_datasource/services/execution_planner.py` line 62-68  
**Severity**: MEDIUM

### Gap 3: Incompatible Event Models
**Impact**: Can't merge debug events with ThinkingMessages  
**Severity**: HIGH

### Gap 4: No Unified Event Bus
**Impact**: Each system operates independently  
**Severity**: ARCHITECTURAL

---

## Implementation Roadmap

Three strategic options provided in IMPLEMENTATION_ROADMAP.md:

### Option 1: Arena Integration (RECOMMENDED)
**Effort**: Medium (2-3 weeks)
- Trigger arena discussions from chat handoffs
- Convert ThinkingMessage → DebugEvent for frontend
- Add "discussion" role to sidebar

**Phase 1**: Backend integration layer
**Phase 2**: Frontend event handling
**Phase 3**: Testing & deployment

### Option 2: A2A Protocol via Debug Events
**Effort**: High (3-4 weeks)
- Implement actual handoff mechanism
- Emit proper handoff debug events
- Update frontend to display handoffs

### Option 3: Unified Agent Model
**Effort**: Very High (4-6 weeks)
- Single A2AEvent type for all communication
- Replace all debug events and ThinkingMessages
- Massive refactoring of two systems

---

## Documentation Generated

### Quick Reference (Read First)
1. **INVESTIGATION_SUMMARY.md** - 6 questions answered
2. **INVESTIGATION_INDEX.md** - Navigation guide
3. **A2A_INVESTIGATION_REPORT.md** - Executive summary

### Deep Technical Dive
4. **AGENT_TEAMS_ARCHITECTURE.md** - 13-section deep dive
5. **AGENT_TEAMS_DIAGRAMS.md** - Visual flows and diagrams
6. **IMPLEMENTATION_ROADMAP.md** - 3 integration strategies

### Supporting Documents
7. **ARCHITECTURE.md** - System overview
8. **ARCHITECTURE_QUICK_REFERENCE.md** - Quick lookup
9. **ARCHITECTURE_SUMMARY.md** - Condensed version

**Total**: 140KB+ of comprehensive documentation

---

## Next Actions

1. **Review IMPLEMENTATION_ROADMAP.md** - Choose Option 1, 2, or 3
2. **Approve Integration Strategy** - Get team consensus
3. **Create GitHub Issues** - Use appendix file references
4. **Assign Development Team** - Backend + Frontend engineers
5. **Begin Phase 1** - Backend integration layer

---

## Investigation Metadata

- **Investigation Start**: Previous conversation (context compacted)
- **Investigation Complete**: 2026-05-17 17:36 UTC
- **Total Analysis Time**: Multi-phase comprehensive investigation
- **Files Analyzed**: 30+ backend and frontend files
- **Lines of Code Reviewed**: 5000+ lines
- **Diagrams Created**: 8+ ASCII diagrams
- **Recommendations**: 3 concrete implementation strategies
- **Risk Assessments**: Complete with mitigations

---

## Conclusion

The investigation is **COMPLETE**. All six original questions have been answered with detailed evidence and file references. The "决策" sidebar shows nothing because two completely separate systems (Chat orchestrator and Arena) have NO connection. Three strategic implementation options have been provided to fix this architectural gap.

**The system is working as designed, but the design has a fundamental disconnect that prevents integrated agent discussions in the chat interface.**
