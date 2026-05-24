# Chat Agent Decision Trace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Chat conversation show both Orchestrator routing decisions and per-Agent team decision logic in the multi-agent decision panel.

**Architecture:** Add a normalized `decision_trace` debug event that can represent scheduling, team-agent reasoning, and final summaries. Preserve existing `classification`, `routing`, `discussion_argument`, and `decision_summary` events for compatibility. Frontend Chat keeps an active team selection and sends optional team fields with every message.

**Tech Stack:** FastAPI/Pydantic/Python SSE backend; Vue 3 + Pinia + TypeScript frontend; real configured database validation where backend team/pipeline data is involved.

---

## Files

- Modify: `src/stock_datasource/modules/chat/schemas.py` — add optional `team_id` and `team_name` to `SendMessageRequest`.
- Modify: `src/stock_datasource/modules/chat/router.py` — pass team fields into orchestrator context and persist/stream `decision_trace` debug events.
- Modify: `src/stock_datasource/agents/orchestrator.py` — emit normalized `decision_trace` for routing and delegate to team execution when `team_id` exists.
- Modify: `src/stock_datasource/agents/config_driven_harness_agent.py` — emit `decision_trace` for each config-driven Agent summary without exposing hidden chain-of-thought.
- Modify: `frontend/src/api/chat.ts` — extend request/event typings and pass optional team data in streaming request body.
- Modify: `frontend/src/stores/chat.ts` — add active team state; include team in `sendMessage`; categorize `decision_trace`; derive final decision state from `team_summary`.
- Modify: `frontend/src/views/chat/ChatView.vue` — team picker sets active team instead of sending a prompt; show active team chip; pass selection through store.
- Modify: `frontend/src/views/chat/components/AgentDiscussionSidebar.vue` — render scheduler, per-agent cards, final summary, and legacy discussion events.
- Test: add/extend Python tests under `tests/` for schema/context/event behavior.
- Test: frontend verification via `npm run build` because no frontend unit test runner is configured.

## Task 1: Backend request and context plumbing

- [ ] **Step 1: Write failing backend schema/router test**

Add a Python test that constructs `SendMessageRequest(session_id='s', content='c', team_id='team-1', team_name='价值投研团队')` and asserts those fields are accepted. If router-level testing is practical without mocks, verify `_stream_response` context receives team fields using the real service/session setup already used by chat tests.

- [ ] **Step 2: Run targeted test and verify RED**

Run: `pytest tests/test_chat_decision_trace.py -q`

Expected: failure because `team_id`/`team_name` are not defined on `SendMessageRequest`.

- [ ] **Step 3: Implement minimal schema/router plumbing**

Add optional fields to `SendMessageRequest`; in `_stream_response`, include `team_id` and `team_name` in `context` only when present. For GET stream keep defaults as `None`.

- [ ] **Step 4: Run targeted test and verify GREEN**

Run: `pytest tests/test_chat_decision_trace.py -q`

Expected: schema/context test passes.

## Task 2: Normalize Orchestrator decision trace

- [ ] **Step 1: Write failing orchestrator event test**

Add a test that drives `OrchestratorAgent.execute_stream()` far enough to inspect emitted debug events and asserts one event has `debug_type == 'decision_trace'`, `data.stage == 'orchestrator'`, and includes `intent`, `rationale`, `selected_agent` or `selected_team`.

- [ ] **Step 2: Run targeted test and verify RED**

Run: `pytest tests/test_chat_decision_trace.py -q`

Expected: failure because only `classification`/`routing` exist.

- [ ] **Step 3: Emit `decision_trace` from Orchestrator**

After classification, emit a debug event with:

```python
self._make_debug_event(
    "decision_trace",
    {
        "stage": "orchestrator",
        "title": "调度决策",
        "intent": intent,
        "selected_agent": agent_name,
        "selected_team": context.get("team_name"),
        "rationale": rationale,
        "stock_codes": stock_codes,
        "available_agents": [agent["name"] for agent in available_agents],
    },
)
```

- [ ] **Step 4: Run targeted test and verify GREEN**

Run: `pytest tests/test_chat_decision_trace.py -q`

Expected: new event exists and legacy events remain.

## Task 3: Per-Agent decision trace event

- [ ] **Step 1: Write failing Agent stream test**

Add a test that executes a `ConfigDrivenHarnessAgent` path already supported by existing test setup and asserts an `agent_start` remains plus a `decision_trace` with `stage == 'team_agent'` or `stage == 'agent'` appears.

- [ ] **Step 2: Run targeted test and verify RED**

Run: `pytest tests/test_chat_decision_trace.py -q`

Expected: failure because config-driven agent emits no normalized decision trace.

- [ ] **Step 3: Implement minimal Agent decision trace**

Emit a `decision_trace` debug event after `agent_start` using safe summary fields only:

```python
yield self._make_debug_event(
    "decision_trace",
    {
        "stage": "team_agent" if context.get("team_id") else "agent",
        "title": self.config.name,
        "agent": self.config.name,
        "role": self.config.description,
        "rationale": "已接收任务并开始基于配置技能分析",
        "key_points": [f"可用工具 {len(tool_names)} 个"],
        "direction": "neutral",
        "confidence": None,
    },
)
```

Do not expose hidden reasoning; use concise decision rationale and observable evidence.

- [ ] **Step 4: Run targeted test and verify GREEN**

Run: `pytest tests/test_chat_decision_trace.py -q`

Expected: per-agent normalized event appears.

## Task 4: Frontend typings and store state

- [ ] **Step 1: Type-check RED**

Reference `team_id`, `team_name`, and `decision_trace` in store code/tests by adding typings first; run `npm run build` from `frontend/` and expect TypeScript errors until implementation is complete.

- [ ] **Step 2: Implement API typings**

In `frontend/src/api/chat.ts`, add optional team fields to `SendMessageRequest`, include them in `streamMessagePost`, and extend `DebugEvent.debug_type` with `decision_trace`. Add data fields: `stage`, `title`, `key_points`, `direction`, `confidence`, `selected_team`, `signal`, vote counts, and `suggested_action`.

- [ ] **Step 3: Implement store active team**

In `frontend/src/stores/chat.ts`, add `activeTeamId`, `activeTeamName`, `setActiveTeam(team)`, `clearActiveTeam()`. In `sendMessage`, pass active team fields to `chatApi.streamMessagePost`. Treat `decision_trace` as role `discussion`. If `data.stage === 'team_summary'`, update `decisionSummary`.

- [ ] **Step 4: Run frontend type-check/build**

Run: `cd /root/lzh/stock_datasource/frontend && npm run build`

Expected: build passes after implementation.

## Task 5: Chat UI and decision panel

- [ ] **Step 1: Update team picker behavior**

In `ChatView.vue`, change `handleTeamChat(team)` to call `chatStore.setActiveTeam(team)` and close the panel. Do not send the synthetic prompt. Add an active-team chip near the input controls with a clear action.

- [ ] **Step 2: Update decision sidebar rendering**

In `AgentDiscussionSidebar.vue`, compute:

- scheduler traces: `decision_trace` with `stage === 'orchestrator'`
- agent traces: `decision_trace` with `stage === 'team_agent' || stage === 'agent'`
- summary traces: `decision_trace` with `stage === 'team_summary'`
- legacy arguments: `discussion_argument`

Render scheduler section, per-agent cards, and final summary while preserving empty state.

- [ ] **Step 3: Build verification**

Run: `cd /root/lzh/stock_datasource/frontend && npm run build`

Expected: build passes.

## Task 6: Real integration validation

- [ ] **Step 1: Backend targeted tests**

Run: `pytest tests/test_chat_decision_trace.py -q`

Expected: all targeted tests pass.

- [ ] **Step 2: Existing related tests**

Run: `pytest tests/test_agent_config_seed.py tests/test_user_scoped_features.py -q`

Expected: passes against configured project data/database; do not rely on mocked validation as final proof.

- [ ] **Step 3: Frontend production build**

Run: `cd /root/lzh/stock_datasource/frontend && npm run build`

Expected: Vue type-check and Vite build pass.

- [ ] **Step 4: Manual experience check**

Start the app using existing project commands if available, choose a team in Chat, send a stock-analysis prompt, and verify the right panel shows: 调度决策, Agent 决策流, 最终汇总/legacy summary. If live LLM/database services are unavailable, report the exact blocker and the tests/build evidence.

## Self-review

- Spec coverage: scheduler, team-agent traces, final summary, compatibility, errors, and tests are represented.
- Placeholder scan: no TBD/TODO placeholders; code snippets define exact event shapes.
- Type consistency: backend `team_id`/`team_name`, frontend `decision_trace`, and `stage` names match across tasks.
- Commit policy: no git commits in this plan because the user did not explicitly request commits.
