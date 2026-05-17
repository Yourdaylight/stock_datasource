# Quick Start: Investigation Guide & Documentation Index

**Investigation Status**: ✅ COMPLETE  
**Date**: 2026-05-17  
**Questions Answered**: 6/6 ✅

---

## TL;DR Summary

### What Were You Investigating?

Two interconnected problems in the Agent Teams and orchestration system:

1. **Agent Teams Architecture**: How are they defined? How do they work? Can users create custom ones?
2. **A2A Communication Gap**: Why does the chat "决策" sidebar show NO agent discussions?

### Key Findings (The Punch Line)

1. **Agent Teams ARE orchestration pipelines** → 3-tier DAGs executed via topological sort with LangGraph Supervisor
2. **Chat and Arena are COMPLETELY SEPARATE SYSTEMS** → Zero cross-communication (this is why sidebar is empty)
3. **Handoff configuration exists but is NEVER USED** → A2A communication incomplete
4. **Three different event systems** → Not unified, each goes to different frontend page

---

## Where to Read First

### 🟢 If you have 5 minutes:
Read this page (you're here) and check the **Key Findings** section above.

### 🟡 If you have 15 minutes:
Read: **INVESTIGATION_COMPLETE.md** (this project's root directory)
- All 6 questions answered
- Quick reference tables
- File inventory with line numbers

### 🔵 If you have 30 minutes:
Read in order:
1. **A2A_INVESTIGATION_REPORT.md** - Why "决策" sidebar is empty
2. **IMPLEMENTATION_ROADMAP.md** - 3 options to fix it

### 🟣 If you have 1+ hours (Deep Dive):
Read in order:
1. **INVESTIGATION_SUMMARY.md** - Quick reference
2. **AGENT_TEAMS_ARCHITECTURE.md** - 13-section deep dive (27KB)
3. **AGENT_TEAMS_DIAGRAMS.md** - Visual flows and comparisons
4. **IMPLEMENTATION_ROADMAP.md** - Strategic options

---

## The Six Questions (With Quick Answers)

### Q1: What is an "Agent Team"?
**Answer**: 3-tier hierarchical DAG structure (Tier 1: Execution, Tier 2: Analysis, Tier 3: Decision)  
**File**: `src/stock_datasource/services/orchestration_engine.py` (202 lines)  
**Frontend**: `/frontend/src/views/orchestration/OrchestrationEditor.vue` (494 lines)

### Q2: Can users create custom agent teams?
**Answer**: YES, via frontend with drag-drop tier configuration  
**File**: OrchestrationEditor.vue (shown above)  
**Endpoint**: `POST /api/orchestrations/`

### Q3: How do Agent Teams execute?
**Answer**: Topological sort (Kahn's algorithm) → LangGraph Supervisor streams events via SSE  
**File**: `src/stock_datasource/services/orchestration_engine.py`  
**Storage**: ClickHouse orchestration_pipelines (ReplacingMergeTree)

### Q4: Relationship between orchestration and Arena?
**Answer**: **ZERO** — Completely separate systems  
**Chat System**: `src/stock_datasource/agents/orchestrator.py` (1465 lines)  
**Arena System**: `src/stock_datasource/arena/discussion_orchestrator.py`

### Q5: Unified event bus?
**Answer**: **NO** — 3 independent systems:
1. AgentRuntime (LangGraph) → SSE chat stream
2. Orchestration (OrchestrationEngine) → SSE pipeline stream
3. Arena (ThinkingStreamProcessor) → SSE arena stream

### Q6: File paths and relationships?
**Answer**: See complete inventory in INVESTIGATION_COMPLETE.md

---

## Why "决策" Sidebar is Empty

### The Root Cause (In Plain English)

You have two agent systems:
- **Chat Orchestrator**: Handles user messages, emits debug events
- **Arena Discussion**: Handles multi-agent debates, emits thinking messages

These systems are **completely isolated**. When the chat orchestrator routes to multiple agents, it does NOT trigger the arena system. So the sidebar remains empty.

### What's Missing (4 Root Causes)

1. ❌ **No Arena Trigger**: `src/stock_datasource/modules/chat/router.py` line 196-362 never calls arena
2. ❌ **Incompatible Events**: Debug events ≠ ThinkingMessages (different JSON structure)
3. ❌ **Unused Handoff Config**: `src/stock_datasource/services/execution_planner.py` defines AGENT_HANDOFF_MAP but never uses it
4. ❌ **Missing Frontend Data**: Frontend expects "discussion" role in sidebar but orchestrator never emits it

### The Fix (3 Options)

**Option 1 (RECOMMENDED)**: Arena Integration
- Trigger arena discussions from chat handoffs
- Effort: 2-3 weeks
- Files to modify: 3 backend + 2 frontend

**Option 2**: A2A Protocol via Debug Events  
- Implement actual handoff mechanism
- Effort: 3-4 weeks
- Files to modify: 2 backend + 1 frontend

**Option 3**: Unified Agent Model
- Single event type for all A2A communication
- Effort: 4-6 weeks
- Files to modify: Most backend files

See **IMPLEMENTATION_ROADMAP.md** for detailed implementation phases.

---

## File Inventory (At a Glance)

### Critical Backend Files

| File | Purpose | Lines |
|------|---------|-------|
| `agents/orchestrator.py` | Chat orchestrator with debug events | 1465 |
| `services/orchestration_engine.py` | DAG execution engine (topological sort) | 202 |
| `services/agent_runtime.py` | LangGraph Supervisor | 758 |
| `services/orchestration_service.py` | Pipeline CRUD + ClickHouse | 352 |
| `arena/discussion_orchestrator.py` | Multi-agent debate/collaboration | ~200 |

### Critical Frontend Files

| File | Purpose | Lines |
|------|---------|-------|
| `views/orchestration/OrchestrationEditor.vue` | Pipeline visual editor | 494 |
| `views/agent-management/AgentList.vue` | Agent management UI | 300 |
| `stores/chat.ts` | Chat state + debug event handler | 700+ |

---

## Event Flow Comparison

### Chat System Event Flow
```
User Message
  ↓
OrchestratorAgent.execute_stream()
  └─ emits: debug("classification"), debug("routing"), tool, done
  ↓
Frontend debugMessages[] (sidebar)
  └─ roles: orchestrator, agent, tool (NOT: discussion)
```

### Arena System Event Flow
```
Arena API call (SEPARATE from chat)
  ↓
AgentDiscussionOrchestrator.run_discussion()
  └─ emits: ThinkingMessage(type=thinking|argument|conclusion)
  ↓
Arena page (DIFFERENT UI from chat)
```

**Key Point**: These are completely separate pipelines with different event types, different frontends, different storage.

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────┐
│                  AGENT SYSTEMS OVERVIEW                  │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  1. CHAT SYSTEM                 2. ARENA SYSTEM          │
│  ├─ OrchestratorAgent           ├─ AgentDiscussionOrch.  │
│  ├─ Debug events               ├─ ThinkingMessage        │
│  ├─ LangGraph routing          ├─ Debate/Collaboration  │
│  └─ Chat SSE stream            └─ Arena SSE stream       │
│                                                           │
│  3. ORCHESTRATION SYSTEM                                 │
│  ├─ OrchestrationEngine                                  │
│  ├─ Topological sort (Kahn's)                            │
│  └─ Pipeline SSE stream                                  │
│                                                           │
│  CONNECTION BETWEEN SYSTEMS: ❌ NONE                     │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

---

## ClickHouse Storage Model

### Tables Created

1. **agent_configs** (ReplacingMergeTree)
   - Versioning enabled
   - Fields: id, user_id, name, system_prompt, skills, model_config, tags, is_public, status, version
   - User isolation: WHERE (user_id = current_user OR user_id = 'system' OR is_public = 1)

2. **orchestration_pipelines** (ReplacingMergeTree)
   - Versioning enabled
   - Fields: id, user_id, name, nodes, edges, execution_mode, merge_strategy, version
   - Soft-delete via status = 'deleted'

3. **orchestration_executions** (MergeTree)
   - TTL: 90 days
   - Fields: execution_id, pipeline_id, start_time, status, result
   - No user isolation (internal use)

---

## Documentation Files Generated

### Tier 1: Start Here
- **QUICK_START_INVESTIGATION_GUIDE.md** (this file)
- **INVESTIGATION_COMPLETE.md** - Comprehensive summary
- **INVESTIGATION_SUMMARY.md** - Quick reference with checkmarks

### Tier 2: Deep Analysis
- **AGENT_TEAMS_ARCHITECTURE.md** - 13-section detailed dive
- **AGENT_TEAMS_DIAGRAMS.md** - Visual flows and system diagrams
- **A2A_INVESTIGATION_REPORT.md** - Root cause analysis

### Tier 3: Implementation
- **IMPLEMENTATION_ROADMAP.md** - 3 strategic options with phases
- **ARCHITECTURE.md** - System overview
- **ARCHITECTURE_QUICK_REFERENCE.md** - Quick lookup tables

---

## Next Steps (For You)

### If you're an ARCHITECT:
1. Read: **IMPLEMENTATION_ROADMAP.md**
2. Choose: Option 1, 2, or 3
3. Approve: Timeline and effort estimate
4. Create: GitHub issues from appendix file list

### If you're a BACKEND ENGINEER:
1. Read: **AGENT_TEAMS_ARCHITECTURE.md** (sections 7-9)
2. Review: `src/stock_datasource/agents/orchestrator.py` (line 1259-1332)
3. Review: `src/stock_datasource/modules/chat/router.py` (line 196-362)
4. Implement: Phase 1 backend integration layer

### If you're a FRONTEND ENGINEER:
1. Read: **A2A_INVESTIGATION_REPORT.md** (sections 4-5)
2. Review: `frontend/src/stores/chat.ts` (line 428-474)
3. Review: `frontend/src/views/orchestration/OrchestrationEditor.vue`
4. Implement: Phase 2 event handler + sidebar display

### If you're a PRODUCT MANAGER:
1. Read: **INVESTIGATION_COMPLETE.md** (sections 2-4)
2. Understand: The three strategic options (Option 1 recommended)
3. Plan: 2-3 week sprint for Option 1
4. Decide: Which option fits your roadmap

---

## Key Statistics

- **Total Investigation Time**: Multi-phase comprehensive analysis
- **Files Analyzed**: 30+ backend and frontend files
- **Lines of Code Reviewed**: 5,000+ lines
- **Diagrams Created**: 8+ ASCII flow diagrams
- **Documentation Generated**: 10 markdown files (140KB+)
- **Root Causes Identified**: 4 specific architectural gaps
- **Implementation Options**: 3 strategic approaches with effort estimates
- **All Questions Answered**: 6/6 ✅

---

## Important Takeaways

1. **Agent Teams ARE working as designed** — they're 3-tier DAGs with proper execution
2. **The "决策" sidebar is empty BY DESIGN** — Chat and Arena are separate systems
3. **This is NOT a bug, it's an ARCHITECTURAL CHOICE** — but one that could be improved
4. **Three clear paths to integrate** them, each with different trade-offs
5. **Option 1 is recommended** for best ROI (2-3 weeks, medium effort)

---

## Questions About the Investigation?

- **What do the build numbers mean?** See AGENT_TEAMS_ARCHITECTURE.md section 11
- **What's the execution mode selection for?** See IMPLEMENTATION_ROADMAP.md Option 1 Phase 1
- **How does user isolation work?** See INVESTIGATION_COMPLETE.md "Complete File Inventory"
- **Where's the code for handoffs?** See A2A_INVESTIGATION_REPORT.md section "Why Handoff Doesn't Produce Discussion Events"
- **Can I run a pipeline and arena at the same time?** Yes, they're separate (see section "Why "决策" Sidebar is Empty")

---

## Reference

**Investigation Documentation Location**: `/root/lzh/stock_datasource/`

**Key Files**:
- ✅ INVESTIGATION_COMPLETE.md (main findings)
- ✅ AGENT_TEAMS_ARCHITECTURE.md (deep dive)
- ✅ A2A_INVESTIGATION_REPORT.md (root cause analysis)
- ✅ IMPLEMENTATION_ROADMAP.md (fix strategy)
- ✅ INVESTIGATION_SUMMARY.md (quick reference)

**Start Reading**: Pick a file above based on your role and available time.
