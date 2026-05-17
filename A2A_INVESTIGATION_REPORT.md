# Agent-to-Agent (A2A) Communication Architecture Investigation

## Executive Summary

The investigation reveals a **fundamental architectural disconnect** between two completely separate agent systems:

1. **Arena System** (`src/stock_datasource/arena/`) - Designed for multi-agent strategy discussions with SSE streaming
2. **Chat Orchestrator** (`src/stock_datasource/agents/orchestrator.py`) - Handles chat messages with the Orchestrator pattern

**Finding**: The chat page's "决策" (Decision) sidebar shows NO agent discussions because:
- The Chat orchestrator emits **debug events** (classification, routing, agent_start, agent_end, tool_result, handoff) — NOT arena-style ThinkingMessages
- Arena discussions are a completely separate subsystem that is **never triggered** from chat messages
- There is NO mechanism to convert chat agent handoffs into arena discussions
- The two systems use completely different event models and have no cross-system communication

---

## System Architecture

### 1. Chat System (Active in Chat Page)

**Location**: `src/stock_datasource/agents/orchestrator.py`

**Flow**:
```
User Message (chat page)
  ↓
OrchestratorAgent.execute_stream()
  ↓
Emits: thinking, content, tool, debug, visualization, done
  ↓
Chat Router (`modules/chat/router.py`)
  ↓
SSE Stream to Frontend
```

**Debug Event Types** (Line 69-79 in orchestrator.py):
```python
def _make_debug_event(self, debug_type: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "debug",
        "debug_type": debug_type,  # classification, routing, agent_start, agent_end, tool_result, handoff
        "agent": "OrchestratorAgent",
        "timestamp": time.time(),
        "data": data,
    }
```

**Debug Event Flow**:
- **classification**: Line 1188-1197 — intent and agent selection
- **routing**: Line 1271-1279, 1339-1347 — agent routing decisions
- **agent_start/agent_end**: Not explicitly emitted by orchestrator (delegated to sub-agents)
- **tool_result**: Collected by sub-agents, forwarded via orchestrator (Line 286-305 in chat/router.py)
- **data_sharing**: Line 486-498 — inter-agent data sharing via Redis cache
- **handoff**: NOT IMPLEMENTED in orchestrator (defined in execution_planner.py Line 62-68 but never used in orchestrator)

**Frontend Sidebar Integration** (frontend/src/stores/chat.ts):
```typescript
// Line 428-474: processDebugEvent
// Processes debug events and converts them to DebugMessage for sidebar display
// BUT: No discussion/arena event handling — only orchestrator/agent/tool/handoff roles
```

---

### 2. Arena System (NOT Triggered from Chat)

**Location**: `src/stock_datasource/arena/`

**Flow**:
```
Arena API endpoint (`modules/arena/router.py`)
  ↓
create_arena() / run_competition()
  ↓
AgentDiscussionOrchestrator.run_discussion()
  ↓
Emits: ThinkingMessage via ThinkingStreamProcessor
  ↓
SSE Stream to frontend/arena page (separate)
```

**ThinkingMessage Model** (arena/models.py):
```python
class MessageType(str, Enum):
    THINKING = "thinking"
    ARGUMENT = "argument"
    QUESTION = "question"
    ANSWER = "answer"
    CONCLUSION = "conclusion"
    SYSTEM = "system"
    ERROR = "error"

class ThinkingMessage:
    id: str
    arena_id: str
    agent_id: str
    agent_role: str
    round_id: str
    message_type: MessageType  # ← Different from debug_type!
    content: str
    metadata: dict
```

**Discussion Orchestration** (arena/discussion_orchestrator.py):
- Line 64-163: `run_discussion()` — executes multi-agent discussions
- Line 165-201: `_run_debate()` — agents critique each other
- Line 226-264: `_run_collaboration()` — agents collaborate
- Line 266-314: `_run_review()` — designated reviewers evaluate
- Line 316-358: `_generate_decision_summary()` — produces buy/sell/hold signals

**Stream Processor** (arena/stream_processor.py):
- Line 146-197: `publish()` — publishes ThinkingMessage with dual-write:
  1. In-memory store (for real-time SSE)
  2. ClickHouse (for persistence) — async, non-blocking
- Line 286-341: `stream()` — yields messages as they arrive

---

## Why "决策" Sidebar Shows Nothing

### Root Cause 1: No Connection from Chat to Arena

**File**: `src/stock_datasource/modules/chat/router.py` (Line 196-362)

```python
async def _stream_response(session_id: str, content: str, current_user: dict):
    # ...
    orchestrator = get_orchestrator()
    context = {
        "session_id": session_id,
        "user_id": user_id,
        "history": service.get_session_history(session_id)[-10:],
    }

    async def generate():
        # Streams debug events, content, tool calls, visualizations
        # BUT: Never triggers arena or discussion
        async for event in orchestrator.execute_stream(content, context):
            # Yields: thinking, content, tool, debug, visualization, done
            # NO: discussion, arena, ThinkingMessage events
```

**Critical Missing Code**: There is NO call to:
- `create_arena()` when user wants "agent discussion"
- `AgentDiscussionOrchestrator.run_discussion()`
- Arena-mode routing or detection

### Root Cause 2: No A2A Handoff Implementation

**File**: `src/stock_datasource/services/execution_planner.py` (Line 62-68)

```python
AGENT_HANDOFF_MAP: dict[str, list[str]] = {
    "MarketAgent": ["ReportAgent", "HKReportAgent", "BacktestAgent"],
    "ScreenerAgent": ["MarketAgent", "ReportAgent"],
    "ReportAgent": ["BacktestAgent", "MarketAgent", "HKReportAgent"],
    "HKReportAgent": ["MarketAgent", "ReportAgent"],
    "OverviewAgent": ["MarketAgent", "IndexAgent"],
}
```

**Status**: These handoff targets are DEFINED but:
- NOT used in orchestrator (checked at line 376 only for reference, never executed)
- NO handoff debug events emitted from orchestrator (line 440 in chat.ts checks for role='handoff', but orchestrator never emits it)
- NO conversion to arena-style discussion messages

### Root Cause 3: Frontend Never Renders Arena Events

**File**: `frontend/src/stores/chat.ts` (Line 75-88, 428-474)

```typescript
interface DebugMessage {
  id: string
  debugType: DebugEvent['debug_type']  // classification, routing, agent_start, agent_end, tool_result, handoff
  agent: string
  timestamp: number
  data: DebugEvent['data']
  targetAgent?: string
  parentAgent?: string
  laneId?: string
  role: 'orchestrator' | 'agent' | 'tool' | 'system' | 'handoff'  // ← No 'discussion' role!
}
```

The frontend's `DebugMessage` interface has:
- **orchestrator role**: For classification/routing events
- **agent role**: For agent_start/agent_end (not emitted)
- **tool role**: For tool_result events
- **handoff role**: For handoff events (never emitted)
- **system role**: For data_sharing (emitted but not displayed as discussion)

**Missing**: No concept of "discussion" or "arena" in the debug sidebar data structure.

---

## Current Event Flow Analysis

### Chat Message → Orchestrator → Frontend

```
User sends message in chat:
  ↓
OrchestratorAgent.execute_stream()
  ├─ Classifies intent + selects agent
  │  └─ Emits: debug("classification", {intent, agent, rationale})
  │
  ├─ Builds execution plan (possibly multi-agent)
  │  └─ Emits: debug("routing", {from_agent, to_agent, is_parallel, plan})
  │
  ├─ Executes agent(s)
  │  └─ Agent emits: thinking, content, tool (NOT debug events)
  │
  └─ Completes
     └─ Emits: done({metadata})

Frontend chat.ts receives:
  ├─ thinking events → updates currentAgent, currentStatus, currentTool
  ├─ content events → builds streamingContent
  ├─ tool events → records tool calls
  ├─ debug events → processDebugEvent() → adds to debugMessages[]
  │  (only shows orchestrator/agent/tool/handoff roles, NO discussion)
  └─ done → finalizes message
```

**Key Missing Piece**: NO "discussion" or "arena" event type exists in this flow!

---

## Why Handoff Doesn't Produce Discussion Events

### Location: `src/stock_datasource/services/execution_planner.py`

**Line 62-68**: AGENT_HANDOFF_MAP defined but:
1. Never consulted in orchestrator
2. Never triggers arena creation
3. Never produces handoff debug events
4. No connection between handoff and discussion

### What SHOULD Happen (Not Implemented):

```python
# Hypothetical implementation that doesn't exist:
if agent_complete and can_handoff_to(next_agent):
    # 1. Emit handoff debug event (PARTIALLY IMPLEMENTED)
    yield {
        "type": "debug",
        "debug_type": "handoff",
        "data": {
            "from_agent": agent_name,
            "to_agent": next_agent,
            "reason": "..."
        }
    }
    
    # 2. Transfer shared context (PARTIALLY IMPLEMENTED)
    self._share_data_to_next_agent(session_id, agent_name, next_agent, data)
    
    # 3. MISSING: Trigger arena discussion for multi-agent coordination
    # arena_orchestrator.run_discussion(
    #     strategies=[...],
    #     mode=DiscussionMode.DEBATE,
    #     market_context={...}
    # )
    # This code does NOT exist!
```

---

## Data Flow Mapping

### Chat System Data Flow

```
OrchestratorAgent._make_debug_event()
  ↓
debug_event = {
  "type": "debug",
  "debug_type": "classification|routing|agent_start|agent_end|tool_result|handoff|data_sharing",
  "agent": "OrchestratorAgent",
  "timestamp": time.time(),
  "data": {...}
}
  ↓
Chat Router._stream_response() yield handler
  ↓
JSON SSE format: "data: {json}\n\n"
  ↓
Frontend EventSource listener
  ↓
chat.ts processDebugEvent(event as DebugEvent)
  ↓
debugMessages.value.push({
  debugType, agent, timestamp, data, role, targetAgent, laneId
})
  ↓
Frontend renders debug sidebar with lanes
```

### Arena System Data Flow

```
AgentDiscussionOrchestrator.run_discussion()
  ↓
agent.critique_strategy() / agent.refine_strategy()
  ↓
stream_processor.publish(
  agent_id, agent_role, content,
  message_type=MessageType.ARGUMENT,
  round_id, metadata
)
  ↓
ThinkingMessage = {
  id, arena_id, agent_id, agent_role, round_id,
  message_type: "argument|thinking|conclusion",
  content, metadata
}
  ↓
In-memory store + async ClickHouse write
  ↓
StreamingResponse yields via generate_sse_stream()
  ↓
JSON SSE format: "event: {message_type}\ndata: {json}\n\n"
  ↓
frontend/arena page (separate from chat page)
```

---

## File Reference Summary

### Chat System Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/stock_datasource/agents/orchestrator.py` | 69-79 | Debug event maker |
| `src/stock_datasource/agents/orchestrator.py` | 1134-1465 | execute_stream() with debug events |
| `src/stock_datasource/modules/chat/router.py` | 177-362 | SSE streaming handler |
| `src/stock_datasource/modules/chat/router.py` | 285-305 | Debug event forwarding |
| `frontend/src/stores/chat.ts` | 75-88 | DebugMessage interface |
| `frontend/src/stores/chat.ts` | 428-474 | processDebugEvent() |

### Arena System Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/stock_datasource/arena/discussion_orchestrator.py` | 64-163 | run_discussion() |
| `src/stock_datasource/arena/stream_processor.py` | 146-197 | publish() with dual-write |
| `src/stock_datasource/arena/stream_processor.py` | 286-341 | stream() generator |
| `src/stock_datasource/modules/arena/router.py` | 1-100+ | Arena API endpoints |

### Handoff/Routing Configuration

| File | Lines | Purpose |
|------|-------|---------|
| `src/stock_datasource/services/execution_planner.py` | 52-68 | CONCURRENT_AGENT_GROUPS, AGENT_HANDOFF_MAP |
| `src/stock_datasource/agents/orchestrator.py` | 367-376 | _get_handoff_targets() (defined but unused) |

---

## Questions Answered

### Q1: Are the Arena agents and Chat agents completely separate systems with NO connection?

**Answer: YES**

- Arena agents (arena/agents/) are specialized for discussion/debate: MarketSentiment, QuantResearcher, RiskAnalyst, StrategyGenerator, StrategyReviewer
- Chat agents (agents/) are specialized for user queries: MarketAgent, ReportAgent, ScreenerAgent, etc.
- **Zero cross-system communication** — Arena is never instantiated from chat flow
- Arena is a standalone subsystem accessed via separate API endpoints

### Q2: Does the Chat orchestrator produce debug events that show agent discussions/handoffs?

**Answer: PARTIALLY**

- Debug events ARE emitted: classification, routing, tool_result, data_sharing
- Handoff debug events are NOT emitted (even though DebugMessage interface expects them)
- These debug events are NOT meant to represent "discussions" — they're just routing metadata
- Frontend receives them but doesn't correlate them with actual multi-agent collaboration

### Q3: Is there any mechanism for chat agents to produce arena-style ThinkingMessages?

**Answer: NO**

- Chat agents use LangGraph/DeepAgent framework with standard output (response, success, metadata)
- Arena agents use ThinkingStreamProcessor to emit ThinkingMessage with dual-write
- No conversion layer exists between chat debug events and arena ThinkingMessage
- Orchestrator never calls `ThinkingStreamProcessor.publish()`

### Q4: What does the debug event flow look like?

**Answer**:

**Chat Debug Event Types & Lines**:
1. **classification** (Line 1188): intent, selected_agent, rationale, available_agents
2. **routing** (Line 1271, 1339): from_agent, to_agent, is_parallel, plan
3. **tool_result** (Line 120-126 in agent_runtime.py): tool name, result_summary
4. **data_sharing** (Line 486): from_agent, to_agent, data_summary, success
5. **agent_start** (NOT EMITTED in orchestrator)
6. **agent_end** (NOT EMITTED in orchestrator)
7. **handoff** (NOT EMITTED even though defined in line 440 of chat.ts)

**Arena ThinkingMessage Types**:
1. THINKING: Agent's reasoning
2. ARGUMENT: Critique/challenge in debate mode
3. QUESTION: Question to other agents
4. ANSWER: Response to question
5. CONCLUSION: Final conclusion
6. SYSTEM: System messages
7. ERROR: Error messages

These are COMPLETELY DIFFERENT event systems!

---

## Recommendations for Fixing

### Option 1: Connect Chat to Arena (Recommended for "Discussion" Feature)

**To enable the "决策" sidebar to show agent discussions:**

1. **Detect when multi-agent handoff is needed** (orchestrator.py, line 1259-1332):
   ```python
   if len(plan) > 1 and should_run_discussion:
       # Create arena with agents in plan
       arena = create_arena(...)
       async for discussion_event in arena_orchestrator.run_discussion():
           yield convert_thinking_message_to_debug_event(discussion_event)
   ```

2. **Convert ThinkingMessage → DebugMessage in frontend**:
   ```typescript
   // Add "discussion" role to DebugMessage
   role: 'orchestrator' | 'agent' | 'tool' | 'system' | 'handoff' | 'discussion'
   ```

3. **Add UI rendering for discussion events** in sidebar

### Option 2: Emit Handoff Debug Events

**To show actual A2A communication in debug sidebar:**

1. **Emit handoff debug events in orchestrator.py**:
   ```python
   # In _execute_with_mcp_stream(), around line 768-1016
   yield self._make_debug_event("handoff", {
       "from_agent": current_agent,
       "to_agent": next_agent,
       "reason": "..."
   })
   ```

2. **Implement actual handoff in orchestrator** (not just pass-through)

3. **Frontend already supports displaying handoff events** (line 440 in chat.ts)

### Option 3: Unify Event Systems

**To have a single A2A protocol:**

1. Replace both debug events and ThinkingMessage with unified A2AEvent:
   ```python
   class A2AEvent(BaseModel):
       type: Literal["discussion", "handoff", "debug"]
       from_agent: str
       to_agent: str
       message_type: str
       content: str
       metadata: dict
   ```

2. Make all agents emit A2AEvent
3. Frontend renders all A2A interactions in a unified way

---

## Conclusion

The "决策" sidebar shows nothing because:

1. **No Arena Trigger**: Chat orchestrator never creates or invokes arena discussions
2. **Different Event Models**: Debug events ≠ ThinkingMessages — they're incompatible
3. **Missing Handoff Implementation**: Handoff targets are defined but never used or emitted
4. **Incomplete Instrumentation**: Frontend expects handoff/discussion events that are never generated

**The two systems are architecturally separate and require explicit integration to show discussions in the chat sidebar.**

