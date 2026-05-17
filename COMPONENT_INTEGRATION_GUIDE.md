# Component Integration Guide - Agent Debug Sidebar Pattern

## Overview
This guide shows how the **AgentDebugSidebar** pattern works and how to reuse it in other analysis pages.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          ChatView.vue                               │
├──────────────────┬─────────────────────────────┬───────────────────┤
│                  │                             │                   │
│ Sessions         │ Main Chat Area              │ AgentDebugSidebar │
│ Sidebar          │ ┌───────────────────────┐   │ ┌─────────────┐   │
│ ┌──────────────┐ │ │ Chat Header [Debug]   │   │ │ Timeline    │   │
│ │ Conversations│ │ │ button                │◄──┼─┤             │   │
│ │ Today        │ │ ├───────────────────────┤   │ ├─────────────┤   │
│ │ Yesterday    │ │ │ Message List          │   │ │ Debug       │   │
│ │ This Week    │ │ │ + Suggestions         │   │ │ Messages    │   │
│ │ Earlier      │ │ ├───────────────────────┤   │ │ (scrollable)│   │
│ │ [NEW]        │ │ │ Input Box             │   │ │             │   │
│ └──────────────┘ │ │ + Teams Panel         │   │ └─────────────┘   │
│                  │ └───────────────────────┘   │                   │
└──────────────────┴─────────────────────────────┴───────────────────┘
           ↑                      ↑                       ↑
         280px              Main flex: 1              360px
        (toggle)                                   (toggle)
```

---

## Data Flow

```
Backend WebSocket Stream
          ↓
    DebugEvent[]
          ↓
Chat API (chat.ts) ──→ handleStreamEvent()
          ↓
    chatStore (stores/chat.ts)
    ├─ debugMessages: DebugMessage[]
    ├─ messageDebugMap: Record<string, DebugMessage[]>
    └─ debugSidebarOpen: boolean
          ↓
   AgentDebugSidebar.vue (renders)
    ├─ DebugTimeline.vue (execution timeline)
    └─ DebugMessage.vue × N (individual events)
```

---

## Component Breakdown

### 1. AgentDebugSidebar.vue (Container)
**Location**: `/frontend/src/views/chat/components/AgentDebugSidebar.vue`
**Role**: Main sidebar container, manages toggle state

**Key Features**:
- Conditionally renders based on `chatStore.debugSidebarOpen`
- Fixed 360px width
- Header with title, count badge, close button
- Scrollable message container
- Empty state message

**Template Structure**:
```vue
<template>
  <div class="debug-sidebar" v-if="chatStore.debugSidebarOpen">
    <div class="debug-sidebar__header">
      <span>Agent 调试</span>
      <span>{{ chatStore.debugMessages.length }}</span>
      <button @click="close"></button>
    </div>
    
    <!-- Sub-component 1: Timeline -->
    <DebugTimeline :messages="chatStore.debugMessages" />
    
    <!-- Sub-component 2: Message list -->
    <div class="debug-sidebar__messages">
      <DebugMessage 
        v-for="msg in chatStore.debugMessages"
        :key="msg.id"
        :message="msg"
      />
    </div>
  </div>
</template>
```

**Props**: None (uses store directly)
**Emits**: None (uses store actions)

---

### 2. DebugTimeline.vue (Timeline Visualization)
**Location**: `/frontend/src/views/chat/components/DebugTimeline.vue`
**Role**: Visual execution timeline of agents

**Key Features**:
- Computed property extracts timeline segments from debug messages
- Horizontal bar chart showing agent execution
- Color-coded per agent
- Displays total execution time
- Shows individual durations (ms/s)

**Input**: `messages: DebugMessage[]`
**Output**: Visual bars with timing info

**Algorithm**:
```typescript
segments = computed(() => {
  const segs = []
  const agentStarts = {}
  
  for (const msg of messages) {
    if (msg.debugType === 'agent_start') {
      agentStarts[msg.agent] = msg
    }
    if (msg.debugType === 'agent_end') {
      const start = agentStarts[msg.agent]
      segs.push({
        agent, displayName, startTime, endTime, durationMs, success, color
      })
    }
  }
  return segs
})
```

**Template**:
```vue
<div class="debug-timeline">
  <div class="timeline-track" v-for="seg in segments">
    <span class="track-label">{{ seg.displayName }}</span>
    <div class="track-bar-container">
      <div class="track-bar" :style="barStyle(seg)">
        {{ formatDuration(seg.durationMs) }}
      </div>
    </div>
  </div>
</div>
```

---

### 3. DebugMessage.vue (Individual Event)
**Location**: `/frontend/src/views/chat/components/DebugMessage.vue`
**Role**: Display single debug event with expandable details

**Key Features**:
- Role-based icon and color
- Expandable detail sections
- Clickable agent names → navigate to `/agents`
- Shows tool parameters, results, rationale
- Error highlighting
- Nested indentation for parallel agents

**Input**: `message: DebugMessage`
**Output**: Formatted debug event UI

**Debug Event Types Handled**:
```typescript
'classification'   → Intent: {{ intent }}
'routing'         → Route → {{ to_agent }} (parallel or sequential)
'agent_start'     → {{ agent }} 开始执行
'agent_end'       → {{ agent }} 完成 ({{ duration }}ms) or failed
'tool_result'     → 调用工具: {{ tool }} with results
'handoff'         → {{ from_agent }} → {{ to_agent }}
'data_sharing'    → 数据共享: {{ from_agent }} → {{ to_agent }}
```

**Expandable Details**:
```
- tools_available: List of tools
- args: Tool parameters (JSON)
- result_summary: Tool output
- data_summary: Shared data
- input_summary: Input data
- error: Error message
```

---

## Integration Checklist for New Pages

### Step 1: Create View with 3-Column Layout
**File**: `views/mynewanalysis/MyAnalysisView.vue`

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import AgentDebugSidebar from '@/views/chat/components/AgentDebugSidebar.vue'

const router = useRouter()
const chatStore = useChatStore()

const toggleDebug = () => {
  chatStore.debugSidebarOpen = !chatStore.debugSidebarOpen
}
</script>

<template>
  <div class="analysis-root">
    <!-- Main Container -->
    <div class="analysis-view">
      <!-- Header -->
      <div class="analysis-header">
        <h2>My Analysis</h2>
        <button @click="toggleDebug" 
                :active="chatStore.debugSidebarOpen">
          Debug
        </button>
      </div>
      
      <!-- Content -->
      <div class="analysis-content">
        <!-- Your analysis UI here -->
      </div>
    </div>
    
    <!-- Debug Sidebar (reused) -->
    <AgentDebugSidebar />
  </div>
</template>

<style scoped>
.analysis-root {
  height: 100%;
  display: flex;
}

.analysis-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.analysis-header {
  padding: 16px;
  border-bottom: 1px solid #e7e7e7;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.analysis-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

/* Responsive: hide debug sidebar on small screens */
@media (max-width: 1024px) {
  /* Debug sidebar switches to overlay */
}
</style>
```

### Step 2: Wire Debug Events
The chat store **already receives WebSocket events globally**, so you don't need to do anything special:
- Backend sends `DebugEvent` objects via WebSocket
- Chat store's `handleStreamEvent()` processes them
- `debugMessages` array auto-updates
- Components auto-render

**Verify**: Open browser DevTools → Network → WS → look for debug events in messages

### Step 3: Add Route
**File**: `router/index.ts`

```typescript
{
  path: '/analysis/mynew',
  name: 'MyAnalysis',
  component: () => import('@/views/mynewanalysis/MyAnalysisView.vue'),
  meta: { title: 'My Analysis', requiresAuth: true, requiresTier: 'pro' }
}
```

### Step 4: Add Menu Item
**File**: `App.vue`

```typescript
{
  path: '/analysis-center',
  title: 'Analysis Center',
  icon: ChartLineIcon,
  requiresAuth: true,
  requiresTier: 'pro',
  children: [
    { path: '/analysis/mynew', title: 'My Analysis', ... }
  ]
}
```

---

## Copy-Paste Components for Reuse

### Quick Copy: 3-Column Layout Template
```vue
<template>
  <div class="three-column-layout">
    <!-- Left Sidebar (optional) -->
    <div :class="['left-sidebar', { expanded: showLeft }]">
      <!-- Content -->
    </div>
    
    <!-- Main Content -->
    <div class="main-content">
      <div class="header">
        <h2>Title</h2>
        <button @click="showLeft = !showLeft">Menu</button>
        <button @click="chatStore.debugSidebarOpen = !chatStore.debugSidebarOpen">Debug</button>
      </div>
      <div class="content">
        <!-- Your analysis content -->
      </div>
    </div>
    
    <!-- Right Debug Sidebar (from chat store) -->
    <AgentDebugSidebar />
  </div>
</template>

<style scoped>
.three-column-layout {
  height: 100%;
  display: flex;
}

.left-sidebar {
  width: 0;
  overflow: hidden;
  transition: width 0.3s ease;
  border-right: 1px solid #e7e7e7;
}

.left-sidebar.expanded {
  width: 280px;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.header {
  padding: 16px;
  border-bottom: 1px solid #e7e7e7;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
</style>
```

---

## WebSocket Event Flow (For Reference)

```
Backend (Python/FastAPI)
    ↓
WebSocket: /api/chat/stream
    ├─ message (ChatMessage)
    ├─ debug (DebugEvent)
    │  ├─ type: 'classification'|'routing'|...
    │  ├─ agent: 'MarketAgent'
    │  ├─ timestamp: 1234567890
    │  └─ data: {...}
    ├─ visualization (VisualizationEvent)
    └─ ...
    ↓
chat.ts (api/chat.ts)
    → handleStreamEvent()
    ↓
chatStore (stores/chat.ts)
    → debugMessages.push(convertEvent(debugEvent))
    ↓
AgentDebugSidebar.vue watches store
    ↓
DebugTimeline + DebugMessage render
```

**To intercept debug events** (for custom processing):
```typescript
// In your component:
watch(() => chatStore.debugMessages, (newMsgs) => {
  console.log('New debug events:', newMsgs)
  // Do something with events
})
```

---

## Styling Tips

### Inherit TDesign Theme
```vue
<style scoped>
.my-element {
  color: var(--td-text-color-primary, #333);
  background: var(--td-bg-color-container, #fff);
  border: 1px solid var(--td-component-stroke, #e7e7e7);
}
</style>
```

### Common Colors (from chat components)
| Variable | Color | Use |
|----------|-------|-----|
| `--td-brand-color` | #0052d9 | Primary (blue) |
| `--td-success-color` | #2ba471 | Success (green) |
| `--td-warning-color` | #ff9500 | Warning (orange) |
| `--td-error-color` | #d54941 | Error (red) |
| `--td-text-color-primary` | #333 | Main text |
| `--td-text-color-secondary` | #666 | Secondary text |
| `--td-bg-color-container` | #fff | Card background |
| `--td-bg-color-secondarycontainer` | #f5f5f5 | Light background |

---

## Debugging Tips

### Check if debug events are received:
```javascript
// In browser console:
localStorage.getItem('__REDUX_DEVTOOLS_EXTENSION_COMPOSE__')
// Or use Vue DevTools → Pinia → chat store → debugMessages
```

### Manually trigger debug message (for testing):
```typescript
// In store action:
debugMessages.value.push({
  id: 'test-' + Date.now(),
  debugType: 'agent_start',
  agent: 'TestAgent',
  timestamp: Math.floor(Date.now() / 1000),
  data: { test: true },
  role: 'agent'
})
```

### Debug event payload structure:
```typescript
interface DebugEvent {
  debug_type: string
  data: {
    intent?: string
    to_agent?: string
    from_agent?: string
    tool?: string
    args?: object
    result_summary?: string
    duration_ms?: number
    success?: boolean
    error?: string
    // ... other fields per type
  }
}
```

---

## Real-World Example: Adding to QuantAnalysisView

**Current**: `/views/quant/QuantAnalysisView.vue` (single-column)
**Goal**: Add debug sidebar to show agent thoughts during analysis

**Changes needed**:

1. Import AgentDebugSidebar:
```typescript
import AgentDebugSidebar from '@/views/chat/components/AgentDebugSidebar.vue'
```

2. Wrap content in flex container:
```vue
<template>
  <div class="quant-analysis-root">
    <div class="quant-analysis-view">
      <!-- Current content here -->
    </div>
    <AgentDebugSidebar />
  </div>
</template>
```

3. Add styles:
```css
.quant-analysis-root {
  height: 100%;
  display: flex;
}

.quant-analysis-view {
  flex: 1;
  overflow: hidden;
}
```

4. Add debug button to header (optional):
```vue
<button @click="chatStore.debugSidebarOpen = !chatStore.debugSidebarOpen">
  Debug {{chatStore.debugMessages.length}}
</button>
```

**That's it!** The sidebar will auto-populate when agents run.

