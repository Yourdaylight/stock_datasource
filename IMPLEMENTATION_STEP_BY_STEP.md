# Step-by-Step Implementation Guide: Arena-Chat Integration

**Status**: Phase 1 (Foundation) - STARTED  
**Last Updated**: 2026-05-17  
**Implementation Path**: Option 1 - Embed Arena in Chat Flow

---

## Quick Start

This guide walks through implementing Arena-Chat integration to enable the "决策" sidebar.

### What Gets Built
- **ChatArenaAdapter** service (new file)
- **session-arena mapping** in ClickHouse
- **Integration points** in orchestrator.py and chat router
- **Event conversion** from Arena to Chat format

### Timeline
- Phase 1 (Foundation): 1-2 days ✅ **IN PROGRESS**
- Phase 2 (Integration): 1-2 days
- Phase 3 (Frontend): 1 day
- Phase 4 (Testing): 2-3 days

---

## Phase 1: Foundation (IN PROGRESS)

### Step 1.1: Create ChatArenaAdapter Service ✅ DONE

**File**: `/src/stock_datasource/services/chat_arena_adapter.py`

**Status**: Created and ready

**Key Components**:
- `ChatArenaAdapter` class with 4 main methods
- Singleton pattern with `get_chat_arena_adapter()`
- ClickHouse table schema for session-arena mapping
- Event converter for DecisionSummary

**Verify**:
```bash
ls -l /root/lzh/stock_datasource/src/stock_datasource/services/chat_arena_adapter.py
# Should show ~400 lines
```

### Step 1.2: Create ClickHouse Table (Manual)

**SQL Command** (run in ClickHouse client):
```sql
CREATE TABLE IF NOT EXISTS chat_session_arenas (
    session_id String,
    arena_id String,
    user_id String,
    stock_codes Array(String),
    agents_in_discussion Array(String),
    discussion_mode String,
    created_at DateTime,
    decision_summary_id String DEFAULT '',
) ENGINE = MergeTree()
ORDER BY (user_id, session_id)
```

**Or** run through adapter initialization (automatic):
```python
from stock_datasource.services.chat_arena_adapter import get_chat_arena_adapter
adapter = get_chat_arena_adapter()  # Creates table if not exists
```

### Step 1.3: Test Adapter Import

**File**: Create temporary test file
```bash
cat > /tmp/test_adapter.py << 'EOF'
import asyncio
import sys
sys.path.insert(0, '/root/lzh/stock_datasource/src')

from stock_datasource.services.chat_arena_adapter import get_chat_arena_adapter

async def test():
    adapter = get_chat_arena_adapter()
    print(f"✅ ChatArenaAdapter initialized successfully")
    print(f"   Cache: {adapter._arena_cache}")

asyncio.run(test())
EOF

python /tmp/test_adapter.py
```

**Expected Output**:
```
✅ ChatArenaAdapter initialized successfully
   Cache: {}
```

### Step 1.4: Verify Arena Models Import

**Verify** Arena models are importable:
```bash
python3 -c "
import sys
sys.path.insert(0, '/root/lzh/stock_datasource/src')
from stock_datasource.arena.models import Arena, ArenaStrategy, DiscussionMode
print('✅ Arena models import successfully')
"
```

---

## Phase 2: Integration (NEXT)

### Step 2.1: Modify Chat Router

**File**: `/src/stock_datasource/modules/chat/router.py`

**Location**: Line ~196-230 in `_stream_response()` function

**Change 1**: Extract session_id from function parameters

Current (line 196):
```python
async def _stream_response(session_id: str, content: str, current_user: dict):
```

Context building (line ~220-237):
```python
context = {
    "session_id": session_id,  # ← ALREADY THERE
    "user_id": user_id,
    "history": service.get_session_history(session_id)[-10:],
}
```

**Status**: ✅ Already has session_id in context

### Step 2.2: Modify Orchestrator

**File**: `/src/stock_datasource/agents/orchestrator.py`

**Location**: Line ~1334 (multi-agent plan trigger)

**Changes Needed**:

1. **Add import** (line ~15):
```python
from stock_datasource.services.chat_arena_adapter import get_chat_arena_adapter
```

2. **Add arena initialization** (after line 1335):
```python
        logger.info(f"Streaming via multi-agent plan: {plan}")
        is_parallel = self._can_run_concurrently(plan)

        # NEW: Create Arena discussion in parallel if multi-agent plan
        adapter = None
        arena_task = None
        
        if len(plan) > 1:
            try:
                adapter = get_chat_arena_adapter()
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
                logger.info(f"Started parallel arena discussion: {arena_id}")
            except Exception as e:
                logger.warning(f"Failed to create Arena for chat session: {e}")
                # Continue without Arena - non-blocking
```

3. **Collect arena events** (after line 1440-1450, after all sub-agents complete):
```python
        # NEW: Collect Arena discussion events
        if arena_task:
            try:
                async for arena_event in arena_task:
                    yield arena_event
            except Exception as e:
                logger.warning(f"Error collecting arena events: {e}")
```

### Step 2.3: Manual Integration Test

**Create test file** `/tmp/test_integration.py`:
```python
import asyncio
import sys
sys.path.insert(0, '/root/lzh/stock_datasource/src')

from stock_datasource.services.chat_arena_adapter import get_chat_arena_adapter

async def test():
    adapter = get_chat_arena_adapter()
    
    # Simulate arena creation
    try:
        arena_id = await adapter.create_arena_for_chat_session(
            session_id="test_sess_001",
            user_id="test_user_001",
            stock_codes=["000001", "000002"],
            agents_in_plan=["MarketAgent", "ReportAgent"],
            market_context={"date": "2026-05-17"}
        )
        print(f"✅ Arena created: {arena_id}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

result = asyncio.run(test())
sys.exit(0 if result else 1)
```

**Run test**:
```bash
cd /root/lzh/stock_datasource && python /tmp/test_integration.py
```

---

## Phase 3: Frontend Integration (READY)

### Step 3.1: Chat Sidebar Event Handler

**File**: `/frontend/src/api/chat.ts` (or wherever handlers are)

**Location**: Event switch statement (around line 440)

**Add cases** for arena events:
```typescript
case "decision_summary":
    // Add to sidebar
    event_log.push({
        type: "decision_summary",
        signal: event.metadata?.signal || "NONE",
        confidence: event.metadata?.confidence || 0,
        bull: event.metadata?.bull_count || 0,
        bear: event.metadata?.bear_count || 0,
        neutral: event.metadata?.neutral_count || 0,
    });
    break;

case "arena_error":
    console.warn("Arena discussion error:", event.content);
    break;
```

### Step 3.2: Decision Summary Sidebar Display

**New Endpoint**: `GET /chat/session/{session_id}/decision-summary`

**Add to chat router** (chat/router.py, after line 175):
```python
@router.get("/session/{session_id}/decision-summary")
async def get_session_decision_summary(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get decision summary for chat session sidebar."""
    try:
        adapter = get_chat_arena_adapter()
        summary = await adapter.get_decision_summary_for_session(session_id)
        if summary:
            return summary
        return {"signal": "NONE", "confidence": 0, "message": "No decision yet"}
    except Exception as e:
        logger.error(f"Failed to get decision summary: {e}")
        return {"signal": "ERROR", "confidence": 0, "error": str(e)}
```

---

## Phase 4: Testing & Validation

### Step 4.1: Unit Tests

**Create file**: `/tests/test_chat_arena_adapter.py`

```python
import pytest
import asyncio
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_create_arena_for_chat_session():
    from stock_datasource.services.chat_arena_adapter import ChatArenaAdapter
    
    adapter = ChatArenaAdapter()
    arena_id = await adapter.create_arena_for_chat_session(
        session_id="test_sess",
        user_id="test_user",
        stock_codes=["000001"],
        agents_in_plan=["MarketAgent"],
        market_context={},
    )
    
    assert arena_id.startswith("a_test_sess")
    assert arena_id in adapter._arena_cache


@pytest.mark.asyncio
async def test_get_decision_summary_no_data():
    adapter = ChatArenaAdapter()
    
    # Should return None when no mapping exists
    result = await adapter.get_decision_summary_for_session("nonexistent")
    assert result is None
```

**Run tests**:
```bash
pytest tests/test_chat_arena_adapter.py -v
```

### Step 4.2: E2E Test: Multi-Agent Chat

**Manual Test Scenario**:

1. Start app
2. Send multi-agent chat message:
   ```
   "分析一下000001和000002的技术面和基本面特点，帮我综合对比"
   ```
   This should trigger: MarketAgent + ReportAgent

3. Observe in browser DevTools:
   - SSE events with type="debug", debug_type="decision_summary"
   - Sidebar shows decision signal if Arena completes

4. Verify database:
   ```bash
   clickhouse-client -q "SELECT * FROM chat_session_arenas LIMIT 1"
   ```

### Step 4.3: Load Testing

**Test concurrent multi-agent chats**:
```bash
# Simulate 5 concurrent multi-agent chat sessions
for i in {1..5}; do
    curl -X POST http://localhost:8000/chat/stream \
        -H "Authorization: Bearer token" \
        -d "分析000001" &
done
wait
```

Monitor:
- CPU/Memory usage (Arena should not exceed 30% additional)
- Response latency (should be <10s for chat)
- Arena discussion completion time (should be <30s)

---

## Rollout Checklist

- [ ] ChatArenaAdapter created and tested
- [ ] Orchestrator integration complete
- [ ] Chat router endpoint added
- [ ] Frontend event handler implemented
- [ ] ClickHouse table created
- [ ] Unit tests passing
- [ ] E2E test: multi-agent chat works
- [ ] Load testing: <30% CPU overhead
- [ ] Documentation updated
- [ ] Code review approved
- [ ] Staging deployment successful
- [ ] Production rollout scheduled

---

## Rollback Plan

If issues occur:

1. **Chat breaks**: Disable Arena in orchestrator (set `if len(plan) > 1` to `if False`)
2. **Performance degradation**: Limit to top 10% of users with feature flag
3. **Database issues**: Truncate chat_session_arenas table
4. **Revert code**: `git revert <commit_hash>`

---

## Expected Results

After complete implementation:

✅ **Before**: Chat "决策" sidebar always empty
❌ Multi-agent messages: No discussion shown

✅ **After**: Chat "决策" sidebar shows discussions
✅ Multi-agent messages: Decision signals appear
✅ Debate points visible in sidebar
✅ BUY/SELL/HOLD signals with confidence %

---

## Troubleshooting

### Issue: "Arena {id} not found in cache"
**Solution**: Arena must be created before calling run_discussion_and_collect_signals()

### Issue: "No arena mapping found for session"
**Solution**: Ensure ClickHouse table exists and insert succeeded

### Issue: "Failed to generate decision summary"
**Solution**: Arena agents may be failing - check orchestrator logs

### Issue: Chat latency increased by 5+ seconds
**Solution**: Run Arena in background without blocking chat response

