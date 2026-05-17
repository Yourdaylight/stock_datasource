# Option 1 Implementation Design: Arena-Chat Integration

**Date**: 2026-05-17  
**Status**: Design Phase  
**Target Solution**: Enable "决策" sidebar by embedding Arena discussions in chat flow

---

## 1. Overview

Currently, when a user sends a chat message that requires multi-agent analysis, the orchestrator routes to multiple agents sequentially (lines 1334+ in orchestrator.py). These agents execute independently with no discussion/debate between them.

**Goal**: When multi-agent routing is triggered, also run a parallel Arena discussion with the same agents, capture decision signals, and display them in the chat "决策" sidebar.

---

## 2. Trigger Conditions for Arena Discussion

### When to Invoke Arena

**Condition 1**: Multi-agent plan with 2+ agents
```python
plan = self._build_multi_agent_plan(agent_name, stock_codes, query)
if len(plan) > 1:  # <-- TRIGGER POINT (orchestrator.py line 1334)
    # Launch Arena discussion in parallel
```

**Condition 2**: Multi-agent plan contains specific analysis types
```python
# Example: MarketAgent + ReportAgent suggests technical+fundamental analysis
# This is a good candidate for debate/discussion
```

**Exact Code Location**:
- File: `/src/stock_datasource/agents/orchestrator.py`
- Line: 1334 (already logged as `Streaming via multi-agent plan: {plan}`)
- Trigger: `if len(plan) > 1` after `_build_multi_agent_plan()`

---

## 3. Architecture Changes Required

### 3.1 New Service: ChatArenaAdapter

**Purpose**: Bridge between chat orchestrator and arena system

**Location**: `/src/stock_datasource/services/chat_arena_adapter.py` (NEW)

**Key Methods**:

```python
class ChatArenaAdapter:
    """Bridges chat sessions with arena discussions."""
    
    async def create_arena_for_chat_session(
        self,
        session_id: str,
        user_id: str,
        stock_codes: list[str],
        agents_in_plan: list[str],
        market_context: dict,
    ) -> str:
        """Create Arena instance tied to chat session.
        
        Returns:
            arena_id: ID for later retrieval of discussion
        """
        
    async def run_discussion_and_collect_signals(
        self,
        arena_id: str,
        discussion_mode: str = "debate",  # debate|collaboration|review
    ) -> AsyncGenerator[dict, None]:
        """Run arena discussion in parallel, yield decision signals."""
        
    async def get_decision_summary_for_session(
        self,
        session_id: str,
    ) -> dict | None:
        """Retrieve decision summary for display in sidebar."""
```

**Interaction**:
1. Chat orchestrator creates adapter when multi-agent plan detected (line 1334)
2. Adapter creates Arena with appropriate agents from plan
3. Arena runs discussion in parallel with agent execution
4. Decision summary automatically stored with session mapping
5. Frontend queries endpoint to fetch decision data for sidebar

---

## 4. Data Model: Session-to-Arena Mapping

### New Database Table: `chat_session_arenas`

**Location**: ClickHouse (persistent)

**Schema**:
```sql
CREATE TABLE chat_session_arenas (
    session_id String,
    arena_id String,
    user_id String,
    stock_codes Array(String),
    agents_in_discussion Array(String),
    discussion_mode String,
    created_at DateTime,
    PRIMARY KEY (user_id, session_id)
)
```

**Purpose**: Map each chat session to its corresponding Arena instance for sidebar queries

---

## 5. Event Conversion Layer

### 5.1 ThinkingMessage → DebugEvent Conversion

**Problem**: Arena uses `ThinkingMessage`, but chat frontend expects `DebugEvent`

**Solution**: Convert at the source before yielding to frontend

**Location**: ChatArenaAdapter or new converter utility

**Converter Function**:

```python
def thinking_message_to_debug_event(msg: ThinkingMessage, session_id: str) -> dict:
    """Convert Arena ThinkingMessage to debug event format."""
    
    debug_type_map = {
        MessageType.THINKING: "agent_thinking",
        MessageType.ARGUMENT: "debate_argument",
        MessageType.QUESTION: "agent_question",
        MessageType.ANSWER: "agent_answer",
        MessageType.CONCLUSION: "agent_conclusion",
        MessageType.SYSTEM: "system",
        MessageType.ERROR: "error",
    }
    
    return {
        "type": "debug",
        "debug_type": debug_type_map.get(msg.message_type, "other"),
        "agent": msg.agent_id,
        "content": msg.content,
        "timestamp": msg.timestamp,
        "session_id": session_id,
        "arena_mode": msg.metadata.get("mode"),  # debate|collaboration|review
    }
```

**Decision Summary Conversion**:

```python
def decision_summary_to_debug_event(summary: DecisionSummary) -> dict:
    """Convert Arena DecisionSummary to debug event."""
    
    return {
        "type": "debug",
        "debug_type": "decision_summary",
        "agent": "ArenaOrchestratorAgent",
        "content": f"Signal: {summary.signal} (confidence: {summary.confidence:.1%})",
        "timestamp": time.time(),
        "metadata": {
            "signal": summary.signal,  # BUY|SELL|HOLD
            "confidence": summary.confidence,
            "bull_count": summary.bull_count,
            "bear_count": summary.bear_count,
            "neutral_count": summary.neutral_count,
            "suggested_action": summary.suggested_action,
        },
    }
```

---

## 6. Execution Flow Diagram

```
User sends chat message
    ↓
ChatRouter._stream_response() [chat/router.py:196]
    ↓
OrchestratorAgent.execute_stream() [orchestrator.py:1134]
    ↓
_classify_with_llm() → detect intent [orchestrator.py:147]
    ↓
_build_multi_agent_plan() [orchestrator.py:288]
    ↓
┌─────────────────────────────────────────────────────────┐
│ TRIGGER POINT: len(plan) > 1 [orchestrator.py:1334]    │
│                                                          │
│ if len(plan) > 1:                                       │
│     adapter = ChatArenaAdapter()                        │
│     arena_id = await adapter.create_arena_for_chat(...) │
│     arena_discussion_task = asyncio.create_task(        │
│         adapter.run_discussion_and_collect_signals()    │
│     )                                                    │
└─────────────────────────────────────────────────────────┘
    ↓
[PARALLEL EXECUTION]
    ├─→ Execute agents in orchestrator (existing flow)
    │   ├─ MarketAgent.execute_stream()
    │   ├─ ReportAgent.execute_stream()
    │   └─ Yield content events to frontend
    │
    └─→ Run Arena discussion (NEW)
        ├─ arena_orchestrator.run_discussion()
        │   ├─ Round 1: Debate mode
        │   │   ├─ Each agent critiques others' strategies
        │   │   └─ Publish ThinkingMessages
        │   ├─ Generate DecisionSummary
        │   │   └─ BUY|SELL|HOLD signal with confidence
        │   └─ Store session-arena mapping
        │
        └─ Convert events & yield to frontend
            ├─ ThinkingMessage → debug_type: "debate_argument"
            └─ DecisionSummary → debug_type: "decision_summary"
    ↓
Frontend receives mixed events:
├─ Agent execution: type="thinking"|"content"|"tool"
├─ Arena discussion: type="debug" with debug_type="debate_*"
└─ Decision signal: type="debug" with debug_type="decision_summary"
    ↓
Frontend renders in "决策" sidebar:
├─ Discussion round summary
├─ Debate points from each agent
└─ Final decision signal (BUY/SELL/HOLD with confidence)
```

---

## 7. Code Changes Required

### 7.1 Orchestrator.py Changes

**File**: `/src/stock_datasource/agents/orchestrator.py`

**Changes**:

1. Import adapter (line ~15):
```python
from stock_datasource.services.chat_arena_adapter import ChatArenaAdapter
```

2. Modify execute_stream() around line 1334:
```python
        logger.info(f"Streaming via multi-agent plan: {plan}")
        is_parallel = self._can_run_concurrently(plan)
        
        # NEW: Create Arena discussion in parallel if multi-agent plan
        adapter = ChatArenaAdapter()
        arena_id = None
        arena_task = None
        
        if len(plan) > 1:
            try:
                arena_id = await adapter.create_arena_for_chat_session(
                    session_id=context.get("session_id", "unknown"),
                    user_id=context.get("user_id", ""),
                    stock_codes=stock_codes,
                    agents_in_plan=plan,
                    market_context=context.get("market_context", {}),
                )
                arena_task = asyncio.create_task(
                    adapter.run_discussion_and_collect_signals(arena_id)
                )
            except Exception as e:
                logger.warning(f"Failed to create Arena for chat session: {e}")
                # Continue without Arena, don't break chat flow
```

3. Yield Arena events (around line 1430, after forwarding sub-agent events):
```python
            # NEW: Forward Arena discussion events
            arena_events = await asyncio.gather(arena_task, return_exceptions=True)
            if isinstance(arena_events, list):
                for event in arena_events:
                    if event and isinstance(event, dict):
                        yield event
```

---

### 7.2 Chat Router Changes

**File**: `/src/stock_datasource/modules/chat/router.py`

**Changes**:

1. Extract session_id from path and pass to context (line ~234):
```python
        context = {
            "session_id": session_id,  # NEW: Add session_id
            "user_id": user_id,
            "history": service.get_session_history(session_id)[-10:],
        }
```

---

### 7.3 New Service: ChatArenaAdapter

**File**: `/src/stock_datasource/services/chat_arena_adapter.py` (NEW)

**Full Implementation**:

```python
"""Bridges chat sessions with arena discussions."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import AsyncGenerator, Any

from stock_datasource.arena.discussion_orchestrator import AgentDiscussionOrchestrator
from stock_datasource.arena.models import Arena, ArenaStrategy, DiscussionMode
from stock_datasource.models.database import db_client

logger = logging.getLogger(__name__)


class ChatArenaAdapter:
    """Bridges chat sessions with arena discussions."""

    async def create_arena_for_chat_session(
        self,
        session_id: str,
        user_id: str,
        stock_codes: list[str],
        agents_in_plan: list[str],
        market_context: dict[str, Any],
    ) -> str:
        """Create Arena instance tied to chat session.
        
        Args:
            session_id: Chat session ID
            user_id: User ID
            stock_codes: Stock symbols to analyze
            agents_in_plan: Agent names from orchestrator plan
            market_context: Current market data
            
        Returns:
            arena_id: Unique ID for this arena instance
        """
        arena_id = str(uuid.uuid4())[:8]
        
        # Create arena with agents from chat orchestrator plan
        arena = Arena(
            id=arena_id,
            user_id=user_id,
            name=f"Chat-{session_id[:8]}",
            description=f"Multi-agent discussion for chat session {session_id}",
            agents=[],  # TODO: Create ArenaAgentConfig from orchestrator agents
            strategies=[
                ArenaStrategy(
                    id=f"strategy_{i}",
                    name=agent_name,
                    agent_id=agent_name,
                    symbols=stock_codes,
                )
                for i, agent_name in enumerate(agents_in_plan)
            ],
        )
        
        # Store mapping for sidebar queries
        self._store_session_arena_mapping(
            session_id=session_id,
            arena_id=arena_id,
            user_id=user_id,
            stock_codes=stock_codes,
            agents=agents_in_plan,
        )
        
        return arena_id

    async def run_discussion_and_collect_signals(
        self,
        arena_id: str,
        discussion_mode: str = "debate",
    ) -> AsyncGenerator[dict, None]:
        """Run arena discussion, yield decision signals."""
        
        try:
            # TODO: Fetch arena by arena_id
            # orchestrator = AgentDiscussionOrchestrator(arena)
            # discussion_round = await orchestrator.run_discussion(
            #     strategies=arena.strategies,
            #     mode=DiscussionMode(discussion_mode),
            # )
            pass
        except Exception as e:
            logger.error(f"Arena discussion failed: {e}")

    async def get_decision_summary_for_session(
        self,
        session_id: str,
    ) -> dict | None:
        """Retrieve decision summary for display in sidebar."""
        
        # Query chat_session_arenas to get arena_id
        # Query thinking_messages to get DecisionSummary
        # Return formatted for frontend
        pass

    def _store_session_arena_mapping(
        self,
        session_id: str,
        arena_id: str,
        user_id: str,
        stock_codes: list[str],
        agents: list[str],
    ):
        """Store mapping in ClickHouse for later retrieval."""
        
        # Ensure table exists
        self._ensure_session_arena_table()
        
        # Insert mapping row
        row = {
            "session_id": session_id,
            "arena_id": arena_id,
            "user_id": user_id,
            "stock_codes": stock_codes,
            "agents_in_discussion": agents,
            "discussion_mode": "debate",
            "created_at": datetime.now(),
        }
        
        import pandas as pd
        df = pd.DataFrame([row])
        db_client.insert_dataframe("chat_session_arenas", df)

    def _ensure_session_arena_table(self):
        """Create table if not exists."""
        
        sql = """
        CREATE TABLE IF NOT EXISTS chat_session_arenas (
            session_id String,
            arena_id String,
            user_id String,
            stock_codes Array(String),
            agents_in_discussion Array(String),
            discussion_mode String,
            created_at DateTime,
        )
        ENGINE = MergeTree()
        ORDER BY (user_id, session_id)
        """
        
        try:
            db_client.execute(sql)
        except Exception as e:
            logger.warning(f"Failed to create table: {e}")
```

---

## 8. Frontend Integration Points

### 8.1 New Chat Events to Handle

The frontend chat.ts already has event handler for `debug_type` (line 440):

```typescript
case "debate_argument":
case "agent_question":
case "agent_answer":
case "agent_conclusion":
    // Forward to 决策 sidebar
    break;
    
case "decision_summary":
    // Update decision signal display with:
    // - signal (BUY/SELL/HOLD)
    // - confidence (0-100%)
    // - bull/bear/neutral counts
    break;
```

### 8.2 Sidebar API Endpoint

**NEW Endpoint**: `GET /chat/session/{session_id}/decision-summary`

**Purpose**: Retrieve decision summary for sidebar display

**Implementation** (chat/router.py):
```python
@router.get("/session/{session_id}/decision-summary")
async def get_session_decision_summary(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get decision summary for chat session sidebar."""
    adapter = ChatArenaAdapter()
    summary = await adapter.get_decision_summary_for_session(session_id)
    return summary or {"signal": "NONE", "confidence": 0}
```

---

## 9. Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Create ChatArenaAdapter service
- [ ] Implement session-arena mapping table
- [ ] Add event converter (ThinkingMessage → DebugEvent)
- [ ] Unit tests for converter

### Phase 2: Integration (Week 2)
- [ ] Modify orchestrator.py to detect multi-agent triggers
- [ ] Create Arena instances in adapter
- [ ] Connect adapter to orchestrator flow
- [ ] Test E2E with 2-agent chat message

### Phase 3: Frontend (Week 3)
- [ ] Update chat.ts to handle arena debug events
- [ ] Add decision-summary sidebar display
- [ ] Test sidebar population
- [ ] UI polish

### Phase 4: Optimization (Week 4)
- [ ] Profile Arena discussion latency
- [ ] Optimize parallel execution
- [ ] Add decision summary caching
- [ ] Load testing

---

## 10. Risk Assessment

### Risk 1: Increased Latency
**Impact**: Chat responses will be slower (2-3x due to parallel Arena)
**Mitigation**: 
- Run Arena as non-blocking background task
- Cache decision summaries
- Add flag to enable/disable Arena discussions

### Risk 2: Resource Consumption
**Impact**: 2x compute for parallel execution
**Mitigation**:
- Limit Arena to specific agent combinations
- Add rate limiting
- Monitor CPU/memory usage

### Risk 3: Event Ordering
**Impact**: Arena events may arrive out of order
**Mitigation**:
- Add sequence numbers to events
- Frontend reorders before display
- Add delivery guarantees in SSE

### Risk 4: Backward Compatibility
**Impact**: Existing chat messages without Arena data
**Mitigation**:
- All Arena features optional
- Graceful degradation if Arena fails
- No breaking changes to existing APIs

---

## 11. Success Criteria

- [ ] Multi-agent chat triggers Arena discussion
- [ ] Decision signals display in sidebar
- [ ] No chat failures due to Arena errors
- [ ] Latency increase < 5 seconds
- [ ] All existing tests pass
- [ ] E2E test: 2-agent chat → decision summary

---

## 12. Timeline Estimate

**Total Effort**: ~4-5 weeks (2-3 engineers)

**Breakdown**:
- ChatArenaAdapter: 3-4 days
- Orchestrator integration: 2-3 days
- Frontend updates: 3-4 days
- Testing & optimization: 1-2 weeks

**Go-Live**: Estimated early June 2026

