# A2A Communication & Agent Orchestration: Implementation Roadmap

**Date**: 2026-05-17  
**Status**: Investigation Complete | Planning Implementation Phase  
**Prepared by**: Claude Code Investigation Team

---

## Table of Contents

1. [Investigation Summary](#investigation-summary)
2. [Current State Assessment](#current-state-assessment)
3. [Root Cause Analysis](#root-cause-analysis)
4. [Decision Point: Integration Strategy](#decision-point-integration-strategy)
5. [Option 1: Arena Integration (Recommended)](#option-1-arena-integration-recommended)
6. [Option 2: A2A Protocol via Debug Events](#option-2-a2a-protocol-via-debug-events)
7. [Option 3: Unified Agent Model](#option-3-unified-agent-model)
8. [Implementation Phases](#implementation-phases)
9. [Risk Assessment & Mitigation](#risk-assessment--mitigation)

---

## Investigation Summary

### Background

The user reported that the chat page's **"决策" (Decision) sidebar** shows NO agent discussions despite the system having:
- **Arena System**: Multi-agent discussion with debate, collaboration, and review modes
- **Chat Orchestrator**: OrchestratorAgent routing to sub-agents
- **Two separate SSE streaming systems** with incompatible event models

### Key Findings

**✗ Architecture Problem**: The Arena and Chat systems are **completely isolated**

| Aspect | Arena System | Chat System | Integration |
|--------|-------------|------------|-------------|
| **Trigger** | API endpoint only | Chat message | ❌ None |
| **Agents** | MarketSentiment, QuantResearcher, RiskAnalyst, etc. | MarketAgent, ReportAgent, ScreenerAgent, etc. | ❌ Different types |
| **Event Model** | ThinkingMessage (thinking, argument, conclusion) | DebugEvent (classification, routing, tool_result) | ❌ Incompatible |
| **Streaming** | ThinkingStreamProcessor + ClickHouse | OrchestratorAgent + LangGraph | ❌ Different pipelines |
| **Frontend** | Arena page (separate) | Chat page (has sidebar) | ❌ No data flow |

**✗ Handoff Configuration Problem**: Defined but never used

```
File: src/stock_datasource/services/execution_planner.py
Line: 62-68

AGENT_HANDOFF_MAP = {
    "MarketAgent": ["ReportAgent", "HKReportAgent", "BacktestAgent"],
    "ScreenerAgent": ["MarketAgent", "ReportAgent"],
    ...
}

Status: DEFINED but NEVER CONSULTED in orchestrator
```

**✗ Frontend Infrastructure Problem**: Ready but missing data

- DebugMessage interface expects handoff events → **never emitted**
- No "discussion" or "arena" role in sidebar → **can't display discussions**
- processDebugEvent() handler exists → **but orchestrator never calls it**

---

## Current State Assessment

### What's Working

| Component | Status | Evidence |
|-----------|--------|----------|
| **OrchestratorAgent** | ✅ Fully functional | Produces debug events, routes agents, handles streaming |
| **LangGraph Supervisor** | ✅ Feature-complete | New AgentRuntime with event adaptation ready |
| **Arena Discussion Engine** | ✅ Fully functional | Can run debate/collaboration/review modes |
| **Frontend SSE Handler** | ✅ Ready | EventSource listener + processDebugEvent |
| **Agent Registry** | ✅ Operational | Descriptors + CRUD endpoints |
| **Orchestration Pipelines** | ✅ Operational | DAG execution engine with topological sort |

### What's Missing

| Gap | Impact | Complexity |
|-----|--------|-----------|
| **No Arena trigger from Chat** | "决策" shows nothing | Medium |
| **Incompatible event models** | Can't merge debug + thinking messages | Medium |
| **No handoff implementation** | A2A communication incomplete | High |
| **Frontend missing "discussion" role** | Can't display multi-agent discussions | Low |

---

## Root Cause Analysis

### Why "决策" Sidebar is Empty

**Root Cause #1: No Connection**
- File: `src/stock_datasource/modules/chat/router.py` (line 196-362)
- Problem: `_stream_response()` never creates arena or triggers discussion
- Evidence: No import of arena modules, no arena API calls, no arena context

**Root Cause #2: Incompatible Events**
- File: Chat emits debug events, Arena emits ThinkingMessages
- Problem: Frontend expects debug role, not discussion role
- Evidence: DebugMessage interface line 75-88 has no discussion/arena option

**Root Cause #3: Handoff Config Unused**
- File: `src/stock_datasource/services/execution_planner.py` (line 62-68)
- Problem: AGENT_HANDOFF_MAP defined but orchestrator never calls get_handoff_targets()
- Evidence: grep shows no usage of get_handoff_targets() in orchestrator

**Root Cause #4: Debug Events Incomplete**
- File: `src/stock_datasource/agents/orchestrator.py`
- Problem: handoff debug event never emitted (Line 440 in chat.ts expects it)
- Evidence: _make_debug_event() is called, but never with debug_type="handoff"

---

## Decision Point: Integration Strategy

### Three Implementation Options

| Option | Approach | Pros | Cons | Timeline |
|--------|----------|------|------|----------|
| **Option 1: Arena Integration** | Connect chat → arena for multi-agent discussions | Most complete, separate concerns, reuses arena | Moderate complexity, event translation needed | 3-4 weeks |
| **Option 2: A2A Protocol** | Emit handoff events, show discussions in debug sidebar | Simpler code, reuses existing sidebar, debug events work | Less flexible, discussion model limited to handoffs only | 1-2 weeks |
| **Option 3: Unified Agent** | New AgentModel merging chat+arena events | Long-term architecture improvement, most unified | Highest complexity, refactor both systems | 6-8 weeks |

### Recommendation

**Implement Option 1 (Arena Integration)** because:

1. ✅ Leverages existing Arena system (battle-tested)
2. ✅ Separates discussion orchestration from main chat flow
3. ✅ Provides richer decision metadata (buy/sell/hold signals)
4. ✅ Matches business model (multi-agent discussions create value)
5. ✅ Can be implemented incrementally

---

## Option 1: Arena Integration (Recommended)

### Architecture: Chat → Arena Bridge

```
User Query
  │
  ├─ (1) OrchestratorAgent.execute_stream()
  │      └─ Emits: classification, routing, tool_result events
  │
  ├─ (2) Detect Multi-Agent Scenario
  │      └─ If len(plan) > 1 and user_wants_discussion:
  │         └─ Trigger Arena
  │
  └─ (3) AgentDiscussionOrchestrator.run_discussion()
         ├─ Creates Arena
         ├─ Runs agents through discussion
         ├─ Emits: ThinkingMessages (argument, conclusion)
         └─ Generates DecisionSummary (signal, confidence)

Frontend receives:
  ├─ debug events (classification, routing) → Main chat
  ├─ thinking events (argument, conclusion) → "决策" sidebar
  └─ done → Finalize
```

### Implementation Steps

#### Phase 1: Event Adaptation (1 week)

**Step 1.1: Add "discussion" role to frontend**

File: `frontend/src/stores/chat.ts` (line 75-88)

```typescript
interface DebugMessage {
  id: string
  debugType: DebugEvent['debug_type']
  agent: string
  timestamp: number
  data: DebugEvent['data']
  role: 'orchestrator' | 'agent' | 'tool' | 'system' | 'handoff' | 'discussion'  // ← ADD
  targetAgent?: string
  parentAgent?: string
  laneId?: string
}
```

**Step 1.2: Extend processDebugEvent() to handle thinking messages**

File: `frontend/src/stores/chat.ts` (line 428-474)

```typescript
processDebugEvent(event: DebugEvent | ThinkingMessage) {
  if (event.type === 'thinking_message') {
    // New handling for arena events
    const message: DebugMessage = {
      id: event.id,
      debugType: event.message_type,  // "argument", "conclusion", etc.
      agent: event.agent_id,
      timestamp: event.created_at,
      data: event.content,
      role: 'discussion',  // ← NEW
      targetAgent: event.metadata.target_strategy_id,
      laneId: event.round_id
    }
    this.debugMessages.value.push(message)
  } else {
    // Existing debug event handling
  }
}
```

#### Phase 2: Arena Trigger Logic (1.5 weeks)

**Step 2.1: Add arena trigger condition to orchestrator**

File: `src/stock_datasource/agents/orchestrator.py` (around line 1259-1332)

```python
async def execute_stream(self, user_query: str, context: dict):
    # ... existing classification logic ...
    
    plan = self._build_execution_plan(intent, selected_agent)
    
    # NEW: Check if multi-agent discussion is warranted
    if len(plan) > 1 and self._should_run_discussion(intent, context):
        # Trigger arena discussion
        async for arena_event in self._run_arena_discussion(plan, context):
            yield arena_event
    
    # ... existing execution logic ...
```

**Step 2.2: Implement _should_run_discussion()**

```python
def _should_run_discussion(self, intent: str, context: dict) -> bool:
    """Determine if multi-agent discussion is needed."""
    keywords = {
        'discuss', 'debate', 'compare', 'evaluate',
        '讨论', '对比', '评估', '分析', '决策'
    }
    return any(kw in intent.lower() for kw in keywords)
```

**Step 2.3: Implement _run_arena_discussion()**

```python
async def _run_arena_discussion(self, plan: list[str], context: dict):
    """Bridge to arena discussion system."""
    from stock_datasource.arena.discussion_orchestrator import (
        AgentDiscussionOrchestrator
    )
    from stock_datasource.arena.models import DiscussionMode, ArenaStrategy
    
    # Create mock strategies from chat agents
    strategies = [
        ArenaStrategy(
            id=f"strategy_{agent}",
            agent_id=agent,
            name=f"{agent} Analysis",
            symbols=context.get('stock_codes', [])
        )
        for agent in plan
    ]
    
    # Create minimal arena
    arena = Arena(
        id=context['session_id'],
        user_id=context['user_id'],
        strategies=strategies,
        config=ArenaConfig(agents=plan)
    )
    
    orchestrator = AgentDiscussionOrchestrator(arena)
    
    # Run discussion and forward events
    discussion_round = await orchestrator.run_discussion(
        strategies=strategies,
        mode=DiscussionMode.DEBATE,
        market_context=context.get('market_data')
    )
    
    # Yield decision summary as SSE event
    if discussion_round.conclusions:
        yield {
            'type': 'thinking_message',
            'message_type': 'conclusion',
            'agent_id': 'OrchestratorAgent',
            'agent_role': 'Coordinator',
            'round_id': discussion_round.id,
            'content': discussion_round.conclusions,
            'metadata': {
                'decision_summary': discussion_round.conclusions.get('_decision_summary')
            }
        }
```

#### Phase 3: Event Streaming (1 week)

**Step 3.1: Adapt Arena events to SSE format**

File: `src/stock_datasource/modules/chat/router.py` (line 250-305)

```python
async def _stream_response(session_id: str, content: str, current_user: dict):
    # ... existing code ...
    
    async def generate():
        # ... existing streaming ...
        
        # NEW: Forward arena discussion events
        if should_run_discussion:
            async for arena_event in orchestrator.get_discussion_stream():
                # Convert ThinkingMessage → SSE format
                sse_event = {
                    'type': arena_event.message_type,  # 'argument', 'conclusion', etc.
                    'agent': arena_event.agent_id,
                    'round_id': arena_event.round_id,
                    'content': arena_event.content,
                    'timestamp': time.time(),
                    'metadata': arena_event.metadata
                }
                yield f"data: {json.dumps(sse_event)}\n\n"
```

#### Phase 4: Frontend Rendering (1 week)

**Step 4.1: Add discussion lane rendering**

File: `frontend/src/components/ChatDebugSidebar.vue`

```vue
<template>
  <div class="debug-sidebar">
    <div v-for="lane in debugLanes" :key="lane.laneId" class="lane">
      <h4>{{ lane.title }}</h4>
      
      <!-- NEW: Discussion lane -->
      <div v-if="lane.role === 'discussion'" class="discussion-lane">
        <div v-for="msg in lane.messages" :key="msg.id" class="discussion-msg">
          <span class="agent">{{ msg.agent }}:</span>
          <span class="argument">{{ msg.data }}</span>
        </div>
      </div>
      
      <!-- Existing debug lanes -->
      <div v-else-if="lane.role === 'orchestrator'" class="debug-lane">
        <!-- Existing code -->
      </div>
    </div>
  </div>
</template>
```

---

## Option 2: A2A Protocol via Debug Events

### Simpler Alternative (1-2 weeks)

**Approach**: Emit handoff debug events instead of triggering arena

```python
# In orchestrator.py: Emit handoff events for each agent transition

if len(plan) > 1:
    for i in range(len(plan) - 1):
        from_agent = plan[i]
        to_agent = plan[i + 1]
        
        yield self._make_debug_event("handoff", {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "reason": f"Passing results from {from_agent} to {to_agent}",
            "shared_context": {...}
        })
```

**Pros**:
- Simpler implementation (no arena integration)
- Reuses existing frontend debug sidebar
- Shows A2A communication clearly

**Cons**:
- Doesn't leverage arena's discussion features
- Limited metadata (no decision signals)
- Just shows routing, not actual discussion

---

## Option 3: Unified Agent Model

### Long-term Architecture (6-8 weeks)

Create unified `A2AEvent` model:

```python
class A2AEvent(BaseModel):
    type: Literal["discussion", "handoff", "debug"]
    from_agent: str
    to_agent: str
    message_type: str
    content: str
    metadata: dict
    timestamp: float
    round_id: str
```

Replace both debug events and ThinkingMessages with A2AEvent.

**Pros**:
- Single event model for everything
- Easier frontend rendering
- Cleaner architecture long-term

**Cons**:
- Requires refactoring both chat and arena systems
- Higher risk of breaking existing functionality
- Longer timeline

---

## Implementation Phases

### Phase 1: Setup (1-2 days)
- [ ] Create feature flag: `ENABLE_ARENA_DISCUSSION` (env var)
- [ ] Set up logging for arena integration events
- [ ] Create integration test fixtures

### Phase 2: Backend (2 weeks)
- [ ] Implement arena trigger in orchestrator
- [ ] Add multi-agent detection logic
- [ ] Create event adapter functions
- [ ] Add strategy creation from chat agents
- [ ] Wire arena events into SSE stream

### Phase 3: Frontend (1.5 weeks)
- [ ] Add "discussion" role to DebugMessage
- [ ] Extend processDebugEvent() handler
- [ ] Create discussion lane component
- [ ] Add decision summary display
- [ ] Style and polish

### Phase 4: Testing & QA (1.5 weeks)
- [ ] Unit tests for arena trigger
- [ ] Integration tests: chat → arena → frontend
- [ ] UI/UX testing with users
- [ ] Performance testing (SSE load)
- [ ] Bug fixes and refinement

### Phase 5: Deployment (1 week)
- [ ] Gradual rollout with feature flag
- [ ] Monitor error logs
- [ ] Performance metrics
- [ ] User feedback loop

**Total Timeline**: 6-7 weeks

---

## Risk Assessment & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Arena integration breaks chat | Medium | High | Comprehensive integration tests, feature flag |
| Performance degradation (SSE) | Low | High | Load testing, event batching |
| Event model incompatibility | Low | Medium | Create adapter layer, validate schema |
| Frontend rendering issues | Low | Medium | Incremental rollout, UI testing |
| User confusion (new UI) | Medium | Low | Documentation, UI tooltips, training |

### Rollout Strategy

1. **Phase 1 (Week 1-2)**: Internal testing with feature flag OFF
2. **Phase 2 (Week 3)**: Beta release to 10% of users with feature flag ON
3. **Phase 3 (Week 4)**: Full rollout with feature flag ON for all users
4. **Phase 4 (Week 5+)**: Monitor, refine, optimize

---

## Success Criteria

✅ "决策" sidebar shows multi-agent discussions when discussing strategies  
✅ Decision signals (buy/sell/hold) appear in sidebar  
✅ Each agent's argument/contribution is visible  
✅ SSE latency < 500ms for discussion events  
✅ No regression in existing chat functionality  
✅ Frontend handles 10+ discussion rounds without lag  

---

## Next Steps

1. **Approve Implementation Strategy**: Choose Option 1, 2, or 3
2. **Create GitHub Issues**: One per phase with acceptance criteria
3. **Assign Development Team**: Backend + Frontend engineers
4. **Set Milestones**: Week-by-week deliverables
5. **Kickoff Meeting**: Align on architecture and timelines

---

## Appendix: File Reference

### Backend Files to Modify

| File | Change | Lines |
|------|--------|-------|
| `src/stock_datasource/agents/orchestrator.py` | Add arena trigger logic | 1259-1332 |
| `src/stock_datasource/modules/chat/router.py` | Forward arena events | 196-362 |
| `src/stock_datasource/services/execution_planner.py` | Implement handoff (if Option 2) | 62-68 |

### Frontend Files to Modify

| File | Change | Lines |
|------|--------|-------|
| `frontend/src/stores/chat.ts` | Add discussion role, extend handler | 75-88, 428-474 |
| `frontend/src/components/ChatDebugSidebar.vue` | Add discussion lane | All |

### New Files to Create

| File | Purpose |
|------|---------|
| `src/stock_datasource/services/arena_bridge.py` | Chat → Arena adapter |
| `frontend/src/components/DiscussionLane.vue` | Discussion display component |
| `tests/integration/test_chat_arena_integration.py` | Integration tests |

