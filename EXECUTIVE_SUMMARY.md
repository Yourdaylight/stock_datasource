# "决策" Sidebar Issue: Executive Summary

**Date**: 2026-05-17  
**Status**: Investigation Complete | Ready for Implementation Decision  
**Issue**: Chat page's "决策" (Decision) sidebar shows no agent discussions

---

## The Problem

Users expect to see **multi-agent discussions and decisions** in the "决策" sidebar when asking strategy-related questions, but the sidebar remains empty.

**Why?** Two agent systems exist in parallel with **zero integration**:

1. **Arena System** ✅ Can run multi-agent discussions  
2. **Chat System** ✅ Routes messages to agents  
3. **Connection** ❌ Missing

---

## Impact

| Business Impact | Technical Impact |
|-----------------|------------------|
| Users can't see agent reasoning | Architecture has wasted Arena investment |
| No decision confidence signals | Duplicate event systems (debug vs thinking) |
| Reduced trust in recommendations | Technical debt from separation |
| Feature incomplete | Maintenance burden of two models |

---

## Root Cause (Technical)

Three things are missing:

```
1. No Trigger
   └─ Chat orchestrator never creates or invokes arena discussions

2. Incompatible Events
   └─ Chat emits "debug events"
   └─ Arena emits "thinking messages"
   └─ Frontend can't display both

3. Frontend Unfinished
   └─ Sidebar infrastructure exists
   └─ Missing "discussion" event role
   └─ No rendering logic for discussions
```

---

## Business Value of Fix

| Benefit | Value |
|---------|-------|
| **Transparency** | Users see agent reasoning → more trust |
| **Confidence Signals** | Buy/sell/hold with confidence scores → better decisions |
| **Market Analysis** | Multiple agents debate strategy → better insights |
| **Competitive Edge** | Multi-agent discussions → unique value proposition |
| **Infrastructure Reuse** | Leverage Arena investment → ROI on existing system |

---

## Solution Overview

**Connect Chat → Arena with Event Bridge**

```
User: "Should I buy AAPL?"
  │
  ├─ OrchestratorAgent routes to: [MarketAgent, ReportAgent, BacktestAgent]
  │
  ├─ If multi-agent → Trigger Arena Discussion
  │  ├─ MarketAgent: "Trend looks bullish, RSI 62"
  │  ├─ ReportAgent: "Fundamentals weak, earnings miss"
  │  └─ BacktestAgent: "Strategy returns 12% historically"
  │
  ├─ Decision Summary: "HOLD (60% confidence)"
  │  ├─ Bull: 2 agents
  │  ├─ Bear: 1 agent
  │  └─ Neutral: 0 agents
  │
  └─ Sidebar shows entire discussion with decision
```

---

## Implementation Options

### Option 1: Arena Integration ⭐ **RECOMMENDED**

**Approach**: Connect chat flow to arena discussions  
**Complexity**: Medium  
**Timeline**: 6-7 weeks  
**Cost**: ~2-3 engineers  

**Pros**:
- ✅ Leverages battle-tested Arena system
- ✅ Reuses infrastructure investment
- ✅ Provides rich decision signals
- ✅ Clean separation of concerns

**Cons**:
- Need event adapter layer
- Integration testing required

---

### Option 2: Simple A2A Protocol

**Approach**: Emit handoff events showing agent-to-agent routing  
**Complexity**: Low  
**Timeline**: 1-2 weeks  
**Cost**: ~1 engineer  

**Pros**:
- ✅ Quicker implementation
- ✅ Simpler code
- ✅ Shows A2A routing

**Cons**:
- Doesn't show discussions
- Limited metadata
- Doesn't use Arena

---

### Option 3: Unified Agent Model

**Approach**: Refactor both systems to use single event model  
**Complexity**: High  
**Timeline**: 6-8 weeks  
**Cost**: ~3-4 engineers  

**Pros**:
- ✅ Clean long-term architecture

**Cons**:
- Highest risk
- Most complex
- Longest timeline

---

## Recommendation: Option 1

**Why Option 1 (Arena Integration)?**

1. **Business**: Maximizes value from existing Arena investment
2. **Technical**: Clean architecture with clear separation
3. **Timeline**: Moderate complexity, 6-7 weeks
4. **Risk**: Medium, mitigated with feature flags and testing
5. **Scalability**: Foundation for future discussion features

**Financial**: Best ROI on engineering effort

---

## Implementation Timeline

```
Week 1-2:  Event adaptation + setup
Week 3-4:  Backend arena integration
Week 5-6:  Frontend rendering + styling
Week 7:    Testing, QA, deployment

Total: 6-7 weeks
Team: 2-3 engineers (backend + frontend)
```

### Rollout Strategy

```
Week 7:    Internal testing (feature flag OFF)
Week 8:    Beta to 10% users (feature flag ON)
Week 9:    Full rollout (feature flag ON)
Week 10+:  Monitor, optimize, gather feedback
```

---

## Risk & Mitigation

| Risk | Mitigation |
|------|-----------|
| Arena integration breaks chat | Comprehensive integration tests + feature flag |
| SSE performance issues | Load testing + event batching |
| Event model conflicts | Adapter layer + schema validation |
| User confusion | Documentation + UI tooltips |

**Confidence Level**: ✅ High (80%+)

---

## Success Metrics

After implementation, we should see:

✅ **Engagement**: 40%+ increase in "decide with discussion" scenarios  
✅ **Performance**: SSE latency < 500ms for discussion events  
✅ **Stability**: Zero regression in chat functionality  
✅ **User Satisfaction**: Positive feedback on decision transparency  
✅ **Data**: Discussion rounds being saved for analysis  

---

## Decision Required

**Question**: Should we proceed with Option 1 (Arena Integration)?

**Prerequisite Approvals**:
1. ☐ Product/Business stakeholder approval
2. ☐ Technical lead sign-off
3. ☐ Engineering capacity confirmed
4. ☐ Timeline accepted

**Next Steps Upon Approval**:
1. Create GitHub issues (one per phase)
2. Schedule kickoff meeting
3. Assign engineers
4. Set Sprint milestones

---

## Appendix: Current System Status

| Component | Status | Notes |
|-----------|--------|-------|
| Chat Orchestrator | ✅ Fully operational | Produces debug events correctly |
| Arena Discussion Engine | ✅ Fully operational | Can run 3 modes (debate/collab/review) |
| Frontend SSE Handler | ✅ Ready | EventSource + processDebugEvent working |
| LangGraph Supervisor | ✅ Feature-complete | New runtime system ready |
| Agent Registry | ✅ Operational | Agent management working |
| Orchestration Pipelines | ✅ Operational | DAG execution functional |

**Missing**: Integration layer connecting chat → arena

---

## Questions?

- **Technical Details**: See `A2A_INVESTIGATION_REPORT.md` (500+ lines)
- **Architecture Diagrams**: See `AGENT_TEAMS_DIAGRAMS.md`
- **Implementation Details**: See `IMPLEMENTATION_ROADMAP.md`
- **Code References**: Line-by-line analysis in investigation report

