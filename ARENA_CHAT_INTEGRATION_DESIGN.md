# Arena-Chat Integration Design (Option 1)

**Status**: Design Phase  
**Date**: 2026-05-17  
**Target Timeline**: 3-4 weeks implementation

## Executive Summary

This document details the implementation design for **Option 1: Arena Integration** from the A2A Communication investigation. The goal is to enable the chat page's "决策" (Decision) sidebar to display multi-agent discussions by creating a bridge between the Chat orchestrator and Arena system.

**Key Design Decision**: Rather than modifying core orchestrator execution, we'll create a **ChatArenaAdapter** service that:
1. Detects multi-agent scenarios after orchestrator builds its plan
2. Conditionally triggers Arena discussion based on user intent keywords
3. Converts ThinkingMessages ↔ DebugEvents for unified frontend consumption
4. Integrates Arena events into the existing SSE stream

---

## Architecture Overview

### Current State (Before Integration)

```
User Chat Message
  ↓
OrchestratorAgent.execute_stream()
  ├─ Classification (emits debug event)
  ├─ Routing (emits debug event)
  └─ Multi-Agent Execution (parallel agents via asyncio queue)
       ├─ MarketAgent.execute_stream() → thinking, content, done
       ├─ ReportAgent.execute_stream() → thinking, content, done
       └─ ScreenerAgent.execute_stream() → thinking, content, done
  ↓
Chat Router._stream_response()
  └─ Yields: thinking, content, tool, debug, visualization, done
  ↓
Frontend Chat Page (main) + Debug Sidebar
  └─ No discussion/arena events = empty "决策" sidebar
```

### New State (After Integration)

```
User Chat Message
  ↓
OrchestratorAgent.execute_stream()
  ├─ Classification (emits debug event)
  ├─ Routing (emits debug event)
  └─ Multi-Agent Execution
       ├─ Agents execute & collect responses
       └─ [NEW] Trigger ChatArenaAdapter if multi-agent scenario
            ├─ Create temporary Arena with agents from plan
            ├─ Run AgentDiscussionOrchestrator.run_discussion()
            ├─ Convert ThinkingMessages → DebugEvents (role='discussion')
            └─ Yield as part of main orchestrator stream
  ↓
Chat Router._stream_response()
  └─ Yields: thinking, content, tool, debug, visualization, [discussion events], done
  ↓
Frontend Chat Page
  ├─ Main chat stream (thinking, content, tool, debug)
  ├─ Debug Sidebar - discussion lane (NEW)
  │   └─ Shows: MarketAgent argument, QuantResearcher critique, decision summary
  └─ Full experience without page navigation
```

---

## Detailed Component Design

### 1. Trigger Condition Logic

**Location**: `src/stock_datasource/services/chat_arena_trigger.py` (NEW)

**Purpose**: Determine when to invoke Arena discussion

```python
class ChatArenaTriggerId:
    """Conditions for triggering Arena discussion from chat context."""
    
    @staticmethod
    def should_run_discussion(
        plan: list[str],
        intent: str,
        user_query: str,
        context: dict
    ) -> bool:
        """
        Determine if a multi-agent discussion should be triggered.
        
        Args:
            plan: List of agents selected by orchestrator
            intent: Classified intent (e.g., "stock_analysis")
            user_query: Original user message
            context: Execution context with session_id, user_id, etc.
        
        Returns:
            True if discussion should be triggered, False otherwise
        """
        # Condition 1: Must be multi-agent scenario
        if len(plan) <= 1:
            return False
        
        # Condition 2: Check for explicit discussion keywords
        discussion_keywords = {
            # English
            'discuss', 'debate', 'compare', 'evaluate', 'analyze',
            'opinion', 'perspective', 'pros', 'cons', 'decision',
            'should', 'recommend', 'suggest', 'which', 'better',
            # Chinese
            '讨论', '对比', '评估', '分析', '决策', '意见', '观点',
            '优缺点', '哪个', '更好', '建议', '推荐', '应该',
            '是否', '如何'
        }
        query_lower = user_query.lower()
        has_discussion_keyword = any(
            kw in query_lower for kw in discussion_keywords
        )
        
        # Condition 3: Intent should be analyzable (not pure data retrieval)
        non_discussion_intents = {
            'price_lookup', 'quick_quote', 'chart_fetch', 'data_query'
        }
        if intent in non_discussion_intents:
            return False
        
        # Discussion intents that benefit from multi-agent analysis
        discussion_intents = {
            'stock_analysis', 'investment_decision', 'market_analysis',
            'comparison', 'risk_assessment', 'strategy_evaluation'
        }
        
        return has_discussion_keyword or intent in discussion_intents
    
    @staticmethod
    def should_use_debate_mode(intent: str) -> bool:
        """Decide between DEBATE, COLLABORATION, or REVIEW mode."""
        if intent in ['investment_decision', 'comparison', 'risk_assessment']:
            return True  # Use DEBATE mode for conflicting perspectives
        return False  # Use COLLABORATION for most cases
```

**Rationale**:
- Opt-in based on user intent, not forced on all queries
- Avoids arena overhead for simple lookups
- User gets discussion experience for strategic questions

---

### 2. Event Conversion Layer

**Location**: `src/stock_datasource/services/arena_event_adapter.py` (NEW)

**Purpose**: Bidirectional conversion between ThinkingMessage and DebugEvent

```python
from dataclasses import dataclass, asdict
from typing import TypedDict
import time

class ThinkingMessageDict(TypedDict, total=False):
    """Arena's ThinkingMessage structure."""
    id: str
    arena_id: str
    agent_id: str
    agent_role: str
    round_id: str
    message_type: str  # "thinking", "argument", "question", "answer", "conclusion"
    content: str
    metadata: dict
    created_at: float

class DebugEventDict(TypedDict, total=False):
    """Chat's DebugEvent structure."""
    type: str  # "debug"
    debug_type: str  # "classification", "routing", "tool_result", "data_sharing", "handoff", "discussion"
    agent: str
    timestamp: float
    data: dict
    role: str  # "orchestrator", "agent", "tool", "system", "handoff", "discussion"
    targetAgent: str
    parentAgent: str
    laneId: str

class ArenaEventAdapter:
    """Adapts Arena ThinkingMessage to/from Chat DebugEvent."""
    
    @staticmethod
    def thinking_message_to_debug_event(
        thinking_msg: ThinkingMessageDict,
        session_id: str
    ) -> DebugEventDict:
        """
        Convert Arena ThinkingMessage → Chat DebugEvent
        
        Frontend expects: {type: "debug", debug_type: "...", role: "discussion", ...}
        """
        return {
            "type": "debug",
            "debug_type": "discussion",  # New debug_type for discussions
            "agent": thinking_msg.get("agent_id", "OrchestratorAgent"),
            "timestamp": thinking_msg.get("created_at", time.time()),
            "data": {
                "message_id": thinking_msg.get("id"),
                "round_id": thinking_msg.get("round_id"),
                "message_type": thinking_msg.get("message_type"),
                # "thinking" → line-by-line reasoning
                # "argument" → critique/challenge during debate
                # "conclusion" → final decision summary
                "content": thinking_msg.get("content"),
                "agent_role": thinking_msg.get("agent_role"),
                # Additional context for sidebar rendering
                "metadata": thinking_msg.get("metadata", {})
            },
            "role": "discussion",
            "targetAgent": thinking_msg.get("agent_id"),
            "laneId": thinking_msg.get("round_id"),  # Group by discussion round
            # These map to debug sidebar's lane concept
        }
    
    @staticmethod
    def batch_thinking_messages_to_debug_events(
        thinking_messages: list[ThinkingMessageDict],
        session_id: str
    ) -> list[DebugEventDict]:
        """Convert multiple ThinkingMessages at once."""
        return [
            ArenaEventAdapter.thinking_message_to_debug_event(msg, session_id)
            for msg in thinking_messages
        ]
    
    @staticmethod
    def extract_decision_summary(
        conclusion_message: ThinkingMessageDict
    ) -> dict:
        """
        Extract actionable decision from conclusion message.
        
        Returns: {signal: "buy"|"sell"|"hold", confidence: 0.0-1.0, rationale: "..."}
        """
        content = conclusion_message.get("content", "")
        metadata = conclusion_message.get("metadata", {})
        
        # Parse decision signals from conclusion
        signal = "neutral"
        if any(word in content.lower() for word in ['buy', '买入', '建议买', '强烈推荐']):
            signal = "buy"
        elif any(word in content.lower() for word in ['sell', '卖出', '建议卖', '减仓', '规避']):
            signal = "sell"
        elif any(word in content.lower() for word in ['hold', '持有', '观望', '不变']):
            signal = "hold"
        
        return {
            "signal": signal,
            "confidence": metadata.get("confidence", 0.5),
            "rationale": content,
            "timestamp": conclusion_message.get("created_at", time.time())
        }
```

**Integration Point**: Frontend's `processDebugEvent()` will recognize `debug_type === "discussion"` and route to discussion lane.

---

### 3. ChatArenaAdapter Service

**Location**: `src/stock_datasource/services/chat_arena_adapter.py` (NEW)

**Purpose**: Main orchestrator for integrating arena into chat flow

```python
import asyncio
import logging
from typing import AsyncGenerator

from stock_datasource.arena.discussion_orchestrator import (
    AgentDiscussionOrchestrator
)
from stock_datasource.arena.models import Arena, DiscussionMode, ArenaStrategy
from stock_datasource.services.arena_event_adapter import ArenaEventAdapter

logger = logging.getLogger(__name__)

class ChatArenaAdapter:
    """
    Bridge between Chat orchestration and Arena discussion system.
    
    Usage:
        adapter = ChatArenaAdapter()
        async for event in adapter.run_discussion(
            plan=["MarketAgent", "ReportAgent"],
            intent="investment_decision",
            context={"session_id": "...", "user_id": "..."}
        ):
            yield event  # Yields DebugEvent with role='discussion'
    """
    
    def __init__(self):
        self.orchestrator = AgentDiscussionOrchestrator()
    
    async def run_discussion(
        self,
        plan: list[str],
        intent: str,
        context: dict,
        user_query: str = ""
    ) -> AsyncGenerator[dict, None]:
        """
        Run arena discussion for multi-agent plan.
        
        Args:
            plan: List of agent names from orchestrator
            intent: Classified intent
            context: {session_id, user_id, history, market_data, stock_codes}
            user_query: Original user message
        
        Yields:
            DebugEvent dicts with role='discussion' for SSE streaming
        """
        logger.info(f"[ChatArenaAdapter] Starting discussion for plan: {plan}")
        
        try:
            # Step 1: Create strategies from chat agents
            strategies = self._create_strategies_from_agents(
                plan,
                context.get("stock_codes", []),
                context.get("session_id", "unknown")
            )
            
            # Step 2: Create minimal Arena object
            arena = self._create_arena(
                session_id=context.get("session_id", "unknown"),
                user_id=context.get("user_id", "unknown"),
                strategies=strategies,
                intent=intent
            )
            
            # Step 3: Decide discussion mode
            mode = self._select_discussion_mode(intent)
            
            logger.info(f"[ChatArenaAdapter] Created arena with {len(strategies)} strategies, mode={mode}")
            
            # Step 4: Run discussion and stream events
            async for thinking_msg in self.orchestrator.run_discussion(
                arena=arena,
                strategies=strategies,
                mode=mode
            ):
                # Convert to DebugEvent for frontend
                debug_event = ArenaEventAdapter.thinking_message_to_debug_event(
                    thinking_msg,
                    session_id=context.get("session_id", "")
                )
                yield debug_event
                
                # Log for debugging
                logger.debug(
                    f"[ChatArenaAdapter] Yielding discussion event: "
                    f"agent={debug_event['agent']}, type={debug_event['data']['message_type']}"
                )
            
            logger.info(f"[ChatArenaAdapter] Discussion completed")
            
        except Exception as e:
            logger.error(f"[ChatArenaAdapter] Discussion failed: {e}", exc_info=True)
            # Don't crash the stream, just skip the discussion
            yield {
                "type": "debug",
                "debug_type": "discussion",
                "agent": "ChatArenaAdapter",
                "timestamp": time.time(),
                "data": {
                    "message_type": "error",
                    "content": f"Arena discussion failed: {str(e)[:100]}"
                },
                "role": "discussion"
            }
    
    def _create_strategies_from_agents(
        self,
        agent_names: list[str],
        stock_codes: list[str],
        session_id: str
    ) -> list[ArenaStrategy]:
        """Create ArenaStrategy objects for each agent in the plan."""
        strategies = []
        for agent_name in agent_names:
            strategy = ArenaStrategy(
                id=f"strategy_{agent_name}_{session_id}",
                agent_id=agent_name,
                name=f"{agent_name} Analysis",
                symbols=stock_codes if stock_codes else ["GENERIC"],
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            strategies.append(strategy)
        return strategies
    
    def _create_arena(
        self,
        session_id: str,
        user_id: str,
        strategies: list[ArenaStrategy],
        intent: str
    ) -> Arena:
        """Create a minimal Arena object for discussion."""
        arena = Arena(
            id=f"arena_{session_id}",
            user_id=user_id,
            name=f"Chat Discussion: {intent}",
            strategies=strategies,
            config=ArenaConfig(
                agents=[s.agent_id for s in strategies],
                max_rounds=3,  # Limit rounds for chat context
                mode="auto"  # Will be overridden by run_discussion mode param
            ),
            status="running",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        return arena
    
    def _select_discussion_mode(self, intent: str) -> DiscussionMode:
        """Choose debate, collaboration, or review based on intent."""
        if intent in ['investment_decision', 'comparison', 'risk_assessment']:
            return DiscussionMode.DEBATE  # Agents critique each other
        elif intent in ['strategy_evaluation', 'portfolio_analysis']:
            return DiscussionMode.REVIEW  # Designated reviewer evaluates
        else:
            return DiscussionMode.COLLABORATION  # Agents work together
```

---

### 4. Orchestrator Integration Point

**Location**: `src/stock_datasource/agents/orchestrator.py` (MODIFY)

**Change**: After multi-agent execution completes, optionally trigger arena discussion.

```python
# Around line 1441 - after all agents complete but before yielding done event

# NEW: Check if we should run arena discussion
if len(plan) > 1 and ChatArenaTriggerId.should_run_discussion(
    plan, intent, query, context
):
    logger.info(f"[Orchestrator] Triggering arena discussion for plan: {plan}")
    
    # Import adapter (at top of file add to imports)
    from stock_datasource.services.chat_arena_adapter import ChatArenaAdapter
    
    adapter = ChatArenaAdapter()
    
    try:
        async for discussion_event in adapter.run_discussion(
            plan=plan,
            intent=intent,
            context=context,
            user_query=query
        ):
            # Yield discussion events as part of main stream
            yield discussion_event
            
    except Exception as e:
        logger.error(f"[Orchestrator] Arena discussion failed: {e}")
        # Continue without discussion - don't break main flow
```

**Placement Logic**:
- After multi-agent execution (line ~1441)
- Before final `yield {"type": "done", ...}` (line ~1452)
- Inside the main `async def generate():` function in orchestrator.execute_stream()

---

### 5. Chat Router Integration

**Location**: `src/stock_datasource/modules/chat/router.py` (MODIFY)

**Change**: Already handles debug events, but add explicit discussion event handling

```python
# In _stream_response() function, around line 285-289 where debug events are handled

elif event_type == "debug":
    debug_type = event.get("debug_type")
    
    # Existing: Forward all debug events
    debug_events.append(event)
    debug_data = json.dumps(event, ensure_ascii=False)
    yield f"data: {debug_data}\n\n"
    
    # NEW: Track discussion events separately for metrics
    if debug_type == "discussion":
        logger.info(
            f"[Chat] Discussion event received: "
            f"message_type={event.get('data', {}).get('message_type')}, "
            f"agent={event.get('agent')}"
        )
```

No code changes needed - existing debug event handling is sufficient!

---

### 6. Frontend Changes

**Location**: `frontend/src/stores/chat.ts` (MODIFY)

**Change**: Add discussion role to DebugMessage interface and rendering

```typescript
// Line 75-88: Update DebugMessage interface
interface DebugMessage {
  id: string
  debugType: DebugEvent['debug_type'] | 'discussion'  // ADD 'discussion'
  agent: string
  timestamp: number
  data: DebugEvent['data']
  role: 'orchestrator' | 'agent' | 'tool' | 'system' | 'handoff' | 'discussion'  // ADD 'discussion'
  targetAgent?: string
  parentAgent?: string
  laneId?: string
}

// Line 428-474: Update processDebugEvent() handler
processDebugEvent(event: DebugEvent | ThinkingMessage) {
  const debug_type = event.debug_type || event.type;
  
  if (debug_type === 'discussion' || (event.type === 'debug' && event.data?.message_type)) {
    // NEW: Handle discussion events
    const message: DebugMessage = {
      id: event.data?.message_id || `disc_${Date.now()}`,
      debugType: 'discussion',
      agent: event.agent,
      timestamp: event.timestamp || Date.now(),
      data: event.data,
      role: 'discussion',
      targetAgent: event.targetAgent,
      laneId: event.laneId,  // Group by discussion round
    }
    this.debugMessages.value.push(message)
  } else {
    // Existing debug event handling
    const message: DebugMessage = {
      id: `${event.debug_type}_${Date.now()}`,
      debugType: event.debug_type,
      agent: event.agent,
      timestamp: event.timestamp,
      data: event.data,
      role: this._mapDebugTypeToRole(event.debug_type),
      targetAgent: event.data?.to_agent,
      parentAgent: event.data?.from_agent,
      laneId: `lane_${event.agent}`,
    }
    this.debugMessages.value.push(message)
  }
}

// NEW helper method
_mapDebugTypeToRole(debugType: string): 'orchestrator' | 'agent' | 'tool' | 'system' | 'handoff' {
  switch (debugType) {
    case 'classification': return 'orchestrator'
    case 'routing': return 'orchestrator'
    case 'tool_result': return 'tool'
    case 'data_sharing': return 'system'
    case 'handoff': return 'handoff'
    default: return 'system'
  }
}
```

**Location**: `frontend/src/components/ChatDebugSidebar.vue` (MODIFY)

**Change**: Add rendering for discussion lane

```vue
<template>
  <div class="debug-sidebar">
    <!-- Existing lanes (orchestrator, tool, handoff) -->
    <div v-for="lane in debugLanes" :key="lane.laneId" class="lane">
      <!-- Existing rendering for non-discussion lanes -->
      <div v-if="lane.role !== 'discussion'" class="debug-lane">
        <!-- ... existing code ... -->
      </div>
      
      <!-- NEW: Discussion lane rendering -->
      <div v-else-if="lane.role === 'discussion'" class="discussion-lane">
        <div class="lane-header">
          <span class="lane-title">🎯 决策讨论</span>
          <span class="lane-subtitle">Round {{ lane.laneId }}</span>
        </div>
        <div v-for="msg in lane.messages" :key="msg.id" class="discussion-message">
          <div class="msg-header">
            <span class="agent-badge">{{ msg.agent }}</span>
            <span class="msg-type-badge" :class="msg.data.message_type">
              {{ msg.data.message_type }}
            </span>
          </div>
          <div class="msg-content">{{ msg.data.content }}</div>
          <div v-if="msg.data.metadata?.signal" class="decision-signal">
            📊 {{ msg.data.metadata.signal.toUpperCase() }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.discussion-lane {
  padding: 12px;
  background: linear-gradient(135deg, #f0f8ff 0%, #e6f7ff 100%);
  border-left: 3px solid #0052d9;
  border-radius: 4px;
  margin-bottom: 8px;
}

.lane-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-weight: 600;
  font-size: 14px;
}

.discussion-message {
  margin-bottom: 12px;
  padding: 8px;
  background: white;
  border-radius: 4px;
  font-size: 13px;
}

.msg-header {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
}

.agent-badge {
  background: #0052d9;
  color: white;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 12px;
  font-weight: 600;
}

.msg-type-badge {
  font-size: 11px;
  padding: 2px 4px;
  border-radius: 3px;
  background: #fafafa;
  color: #595959;
}

.msg-type-badge.argument {
  background: #fff7d6;
  color: #d46b08;
}

.msg-type-badge.conclusion {
  background: #d9f0ff;
  color: #0052d9;
}

.msg-content {
  color: #262b30;
  line-height: 1.5;
  margin-bottom: 4px;
  font-size: 13px;
}

.decision-signal {
  font-size: 12px;
  font-weight: 600;
  color: #0052d9;
  padding-top: 4px;
  border-top: 1px solid #e7e7e7;
  margin-top: 4px;
}
</style>
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Create `chat_arena_trigger.py` with trigger logic
- [ ] Create `arena_event_adapter.py` with conversion functions
- [ ] Create `chat_arena_adapter.py` with main orchestration
- [ ] Unit tests for trigger conditions and conversions
- [ ] Feature flag: `ENABLE_ARENA_CHAT_INTEGRATION` (env var, default OFF)

### Phase 2: Backend Integration (Week 2)
- [ ] Integrate ChatArenaAdapter into orchestrator.py
- [ ] Update chat router for explicit logging
- [ ] Integration tests: plan → arena → debug events
- [ ] Test error handling (arena failure doesn't break chat)

### Phase 3: Frontend Integration (Week 2-3)
- [ ] Update chat.ts DebugMessage interface
- [ ] Extend processDebugEvent() handler
- [ ] Update ChatDebugSidebar component
- [ ] Add discussion lane CSS styling
- [ ] UI testing with dev tools

### Phase 4: Testing & Refinement (Week 3-4)
- [ ] End-to-end tests: chat message → discussion display
- [ ] Performance testing (Arena discussions under 3 seconds)
- [ ] User testing with sample queries
- [ ] Bug fixes and polish
- [ ] Documentation updates

---

## Data Flow with Line Numbers

### Request Flow

```
User: "我应该买入这支股票吗？" (Should I buy this stock?)
  ↓
POST /api/chat/sessions/{session_id}/messages
  ↓
chat/router.py:196 _stream_response(session_id, content, current_user)
  ├─ service.add_message(session_id, user_id, "user", content)
  ├─ orchestrator = get_orchestrator()
  └─ async def generate():
       └─ orchestrator.py:1134 orchestrator.execute_stream(content, context)
           ├─ Line 1167-1178: Intent classification
           │  └─ Emit: debug("classification", {intent: "investment_decision", ...})
           │
           ├─ Line 1188-1197: Select agent(s)
           │  └─ plan = ["MarketAgent", "ReportAgent", "RiskAnalyst"]
           │
           ├─ Line 1259-1332: Single agent OR
           │  Line 1334-1450: Multi-agent execution
           │
           ├─ Line 1437-1450: [NEW] Check for discussion trigger
           │  ├─ ChatArenaTriggerId.should_run_discussion(plan, intent, query, context)
           │  │  └─ Checks: len(plan) > 1 ✓, has_keyword("买入") ✓, intent="investment_decision" ✓
           │  │  └─ Returns: True
           │  │
           │  └─ adapter.run_discussion(plan, intent, context)
           │     ├─ arena_event_adapter.py: Create strategies from agents
           │     ├─ chat_arena_adapter.py: Run discussion with DEBATE mode
           │     ├─ arena/discussion_orchestrator.py:64 run_discussion()
           │     ├─ Arena runs agents through critique rounds
           │     ├─ Yields: ThinkingMessage (argument, conclusion, etc.)
           │     │
           │     └─ For each ThinkingMessage:
           │        ├─ arena_event_adapter.py: Convert to DebugEvent
           │        │  ├─ debug_type: "discussion"
           │        │  ├─ role: "discussion"
           │        │  └─ data: {message_type, content, ...}
           │        │
           │        └─ orchestrator.py: Yield DebugEvent
           │
           ├─ Line 1452: Emit: done({metadata, tool_calls, ...})
           │
           └─ chat/router.py:249 yield event through generate()
              ├─ event_type="debug" → Line 285-289
              │  └─ json.dumps(event) + SSE format
              │
              └─ EventSource (frontend) → processDebugEvent()
                 └─ debug_type="discussion" → DebugMessage with role="discussion"

Frontend Chat Page renders:
  ├─ Main chat: thinking states + content
  ├─ Debug Sidebar:
  │  ├─ Orchestrator lane: classification, routing
  │  ├─ Tool lane: tool calls
  │  └─ Discussion lane (NEW): market analysis, risk perspective, decision
  └─ Done ✓
```

---

## Success Criteria

✅ Chat message triggers multi-agent discussion when appropriate  
✅ "决策" sidebar shows discussion events with correct role='discussion'  
✅ Each agent's argument/conclusion displays in separate lane  
✅ Discussion completes without breaking main chat flow  
✅ SSE latency remains < 500ms for discussion events  
✅ No regression in existing chat functionality  
✅ Error handling: arena failure doesn't crash chat stream  
✅ Feature flag allows gradual rollout  

---

## Configuration & Deployment

### Environment Variables

```bash
# .env or docker-compose.yml
ENABLE_ARENA_CHAT_INTEGRATION=true  # Feature flag
ARENA_MAX_ROUNDS=3                  # Limit discussion rounds for chat context
ARENA_DISCUSSION_TIMEOUT=30         # Timeout in seconds
ARENA_MODE_DEFAULT=collaboration    # debate | collaboration | review
```

### Feature Flag Usage

```python
# In orchestrator.py
import os
ARENA_ENABLED = os.getenv("ENABLE_ARENA_CHAT_INTEGRATION", "false").lower() == "true"

if ARENA_ENABLED and len(plan) > 1 and ChatArenaTriggerId.should_run_discussion(...):
    # Run discussion
    ...
```

### Monitoring

**Metrics to track**:
- `arena_discussion_count` - discussions triggered per hour
- `arena_discussion_duration` - time to complete discussion (p50, p95, p99)
- `arena_discussion_success_rate` - % not erroring
- `arena_event_count` - events yielded to frontend
- `chat_sse_latency_with_arena` - SSE performance impact

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Arena integration slows chat | Medium | High | Timeout (30s), async execution, feature flag |
| Event conversion bugs | Low | Medium | Unit tests for all conversions, type safety |
| Frontend rendering issues | Low | Medium | Incremental CSS, testing with sample data |
| User confusion (new UI) | Medium | Low | Tooltips, documentation, clear labeling |
| Discussion irrelevant to query | Medium | Low | Better trigger heuristics, user feedback |
| Performance degradation | Low | High | Load testing, ClickHouse async write, pagination |

---

## Appendix: File Summary

### New Files to Create
- `src/stock_datasource/services/chat_arena_trigger.py` (150 lines)
- `src/stock_datasource/services/arena_event_adapter.py` (200 lines)
- `src/stock_datasource/services/chat_arena_adapter.py` (250 lines)
- Tests: `tests/unit/test_chat_arena_*` (300 lines)

### Files to Modify
- `src/stock_datasource/agents/orchestrator.py` (+50 lines at line ~1437)
- `src/stock_datasource/modules/chat/router.py` (+10 lines at line ~285)
- `frontend/src/stores/chat.ts` (+30 lines around line 428)
- `frontend/src/components/ChatDebugSidebar.vue` (+80 lines for discussion lane)

### Total Effort
- Backend: ~600 lines of new code
- Frontend: ~110 lines of modifications
- Tests: ~300 lines
- **Total**: ~1,000 lines of code

---

## Next Steps

1. **Approve Design**: Confirm architectural approach and timeline
2. **Create Issues**: One per phase in GitHub
3. **Set Up Feature Flag**: Add env var and conditional logic
4. **Begin Phase 1**: Create foundation services and tests
5. **Code Review Checkpoints**: After each phase

