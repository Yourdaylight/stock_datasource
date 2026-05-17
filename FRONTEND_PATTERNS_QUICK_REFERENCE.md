# Frontend Patterns - Quick Reference Guide

## Route Architecture

### Entry Points
```
/                   → /chat (default redirect)
/login              → Public (no auth)
/market, /research  → Public (no auth)
/chat               → Chat interface [AUTH]
/quant/*            → Quant system [AUTH + PRO]
/agents, /orchestration → Agent management [AUTH]
```

### Tier Control
```
requiresAuth: true        → Login required
requiresTier: 'pro'      → Pro or admin user only
requiresAdmin: true      → Admin only
```

---

## Layout Patterns

### Global Structure (App.vue)
```
┌─ Sidebar Navigation (fixed left) ──┬─ Main Content ──────┐
│  - Nested menu items                │  - Header (title)   │
│  - Tier visibility filter           │  - Router view      │
│  - ~200px width                     │  - Page content     │
└─────────────────────────────────────┴─────────────────────┘
```

### Chat View Structure (3-column flex)
```
┌─ Sessions      ─┬─ Main Chat ─────────────┬─ Debug Sidebar ─┐
│  (collapsed)    │  - Header               │  (toggle)       │
│  - 280px when   │  - Tabs (Chat/Akinator) │  - 360px        │
│    expanded     │  - Messages             │  - Timeline     │
│                 │  - Input + Teams        │  - Debug msgs   │
└─────────────────┴─────────────────────────┴─────────────────┘
```

### Analysis Page Structure (Quant example)
```
┌────────────────────────────────────────────────┐
│ Card 1: Pipeline Progress (4 stages)           │
├────────────────────────────────────────────────┤
│ Card 2: Data Readiness (if needed)             │
├────────────────────────────────────────────────┤
│ Row: [Stat 1] [Stat 2] [Stat 3]               │
├────────────────────────────────────────────────┤
│ Row: [Nav 1] [Nav 2] [Nav 3] [Nav 4]          │
└────────────────────────────────────────────────┘
```

---

## Key Component Files

### Chat System
| File | Purpose | Key Props |
|------|---------|-----------|
| `ChatView.vue` | Main chat container | - |
| `AgentDebugSidebar.vue` | Debug panel controller | `debugSidebarOpen`, `debugMessages` |
| `DebugMessage.vue` | Individual debug event | `message: DebugMessage` |
| `DebugTimeline.vue` | Agent execution timeline | `messages: DebugMessage[]` |
| `MessageList.vue` | Chat messages display | `messages`, `loading` |
| `InputBox.vue` | Message input | `disabled` |

### Quant System
| File | Purpose | Key Data |
|------|---------|----------|
| `QuantView.vue` | Hub/overview | Pipeline status, stats |
| `QuantAnalysisView.vue` | Deep analysis | Tech metrics, AI analysis |
| `QuantPoolView.vue` | Core target pool | Stock list, rankings |
| `QuantSignalsView.vue` | Trading signals | Buy/sell signals |
| `QuantScreeningView.vue` | Market screening | Screening results |

---

## State Management (Pinia - chat.ts)

### Debug-Related State
```typescript
debugMessages: DebugMessage[]        // Event log
debugSidebarOpen: boolean            // Toggle state
messageDebugMap: Record<string, DebugMessage[]>  // Message ↔ events

// Debug event interface
interface DebugMessage {
  id: string
  debugType: 'classification' | 'routing' | 'agent_start' | 'agent_end' 
            | 'tool_result' | 'handoff' | 'data_sharing'
  agent: string           // Agent code name
  timestamp: number       // Unix seconds
  data: any              // Event details
  role: 'orchestrator' | 'agent' | 'tool' | 'system' | 'handoff'
}
```

### Chat Session State
```typescript
messages: ChatMessage[]                    // Current messages
sessionId: string                         // Active session ID
sessions: ChatSessionSummary[]            // History
debugSidebarOpen: boolean                 // Sidebar visibility
```

### Key Store Methods
```typescript
// Session management
initSession()
switchSession(sessionId)
deleteSession(sessionId)
updateSessionTitle(sessionId, title)

// Message handling
sendMessage(content)
handleStreamEvent(event)
addDebugMessage(debugEvent)

// Persistence
saveMessagesToStorage()
loadMessagesFromStorage()
```

---

## Integration Patterns

### Agent Discussion Sidebar
**Problem**: Show agent thoughts alongside analysis
**Solution**: 
1. Store receives WebSocket debug events → `debugMessages[]`
2. Toggle button → `debugSidebarOpen = !debugSidebarOpen`
3. Sidebar renders `DebugTimeline` + `DebugMessage` components
4. Click agent name → Navigate to `/agents?highlight=agent_name`

**Reusable for other pages?** YES
- Copy `AgentDebugSidebar.vue`, `DebugMessage.vue`, `DebugTimeline.vue`
- Wire to store debug state
- Same WebSocket stream (already in chat.ts)

### Analysis Page + Sidebar Pattern
**File structure for new analysis with sidebar:**
```
views/
├── newanalysis/
│   ├── NewAnalysisView.vue  [Main 3-column layout]
│   ├── components/
│   │   ├── AnalysisPanel.vue  [Analysis display]
│   │   └── DetailsSidebar.vue [Agent discussion]
│   └── [sub-views]/
```

### Route + Menu Integration
1. Add route to `router/index.ts`:
   ```typescript
   { path: '/newanalysis', name: 'NewAnalysis', 
     component: () => import('@/views/newanalysis/NewAnalysisView.vue'),
     meta: { title: '...' requiresAuth: true } }
   ```

2. Add to `App.vue` menuItems:
   ```typescript
   { path: '/newanalysis', title: 'Analysis Name', icon: IconComponent, requiresAuth: true }
   ```

3. Visibility auto-filters based on tier in `visibleMenuItems` computed property

---

## Debug Event Types & Colors

| Type | Icon | Color | Meaning |
|------|------|-------|---------|
| `classification` | info | - | Intent recognition |
| `routing` | arrow-right | - | Agent routing |
| `agent_start` | user-circle | Green | Agent began work |
| `agent_end` | user-circle | Green/Red | Agent completed (success/fail) |
| `tool_result` | tools | Orange | Tool execution result |
| `handoff` | swap | Purple | Agent-to-agent handoff |
| `data_sharing` | - | - | Data passed between agents |

**Role Colors:**
- Orchestrator: Blue (#0052d9)
- Agent: Green (#2ba471)
- Tool: Orange (#e37318)
- System: Gray (#888)
- Handoff: Purple (#7b61ff)

---

## Responsive Breakpoints

| Screen | Session Sidebar | Debug Sidebar | Layout |
|--------|-----------------|---------------|--------|
| Desktop (>1400px) | Collapsible | Fixed | 3-column |
| Tablet (1024-1400px) | Collapsible | Overlay | 2-column |
| Mobile (<1024px) | Drawer | Drawer | 1-column |

---

## Common Patterns to Reuse

### Loading State
```typescript
const loading = ref(false)
// Show in UI: <t-loading v-if="loading" />
```

### Session Time Formatting
```typescript
const formatSessionTime = (timeStr: string) => {
  const date = new Date(timeStr)
  const now = new Date()
  const days = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))
  // Returns: "Today", "Yesterday", "3天前", "12-25"
}
```

### Collapsible Sidebar
```typescript
<div :class="['sidebar', { expanded: showSidebar }]">
  <!-- Content -->
</div>

<style scoped>
.sidebar {
  width: 0;
  overflow: hidden;
  transition: width 0.3s ease;
}
.sidebar.expanded {
  width: 280px;  // Your desired width
}
</style>
```

### Grid Layout (t-row/t-col)
```vue
<t-row :gutter="16">
  <t-col :span="8">
    <t-card>Content 1</t-card>
  </t-col>
  <t-col :span="8">
    <t-card>Content 2</t-card>
  </t-col>
  <t-col :span="8">
    <t-card>Content 3</t-card>
  </t-col>
</t-row>
```

---

## File Paths Reference

| Purpose | Path |
|---------|------|
| Routes | `/frontend/src/router/index.ts` |
| Global Layout | `/frontend/src/App.vue` |
| Chat View | `/frontend/src/views/chat/ChatView.vue` |
| Debug Panel | `/frontend/src/views/chat/components/AgentDebugSidebar.vue` |
| Debug Message | `/frontend/src/views/chat/components/DebugMessage.vue` |
| Debug Timeline | `/frontend/src/views/chat/components/DebugTimeline.vue` |
| Chat Store | `/frontend/src/stores/chat.ts` |
| Quant Views | `/frontend/src/views/quant/` |
| Types | `/frontend/src/types/` |
| API Clients | `/frontend/src/api/chat.ts`, `quant.ts`, etc. |

---

## Quick Debug Checklist

- [ ] Add route to `router/index.ts` with auth guards
- [ ] Add menu item to `App.vue` menuItems
- [ ] Create view component at `views/new-feature/NewView.vue`
- [ ] Create store with Pinia if state needed
- [ ] Create API client if backend calls needed
- [ ] Test with different user tiers
- [ ] Test responsive layout at breakpoints
- [ ] Wire up WebSocket for debug events (if needed)

