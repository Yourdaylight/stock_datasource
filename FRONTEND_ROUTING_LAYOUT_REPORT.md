# Frontend Routing & Layout Structure - Comprehensive Report

## Project: /root/lzh/stock_datasource

---

## 1. ROUTE DEFINITIONS

### Router Entry Point
- **File**: `/frontend/src/router/index.ts`
- **Type**: Vue Router v4 with lazy-loading route components
- **Authentication Pattern**: Tier-based access control (free/pro/admin)

### Route Categories

#### Public Routes (No Auth Required)
```
/login              → LoginView
/market             → MarketView  
/research           → ResearchView (+ children for company list, report list, detail)
```

#### Authentication-Required Routes
**Chat & Analysis:**
- `/chat` → ChatView (main intelligent chat interface)

**Market Analysis:**
- `/news` → NewsView
- `/screener` → ScreenerView (stock screening)
- `/portfolio` → PortfolioView (holdings management)
- `/etf` → EtfView (ETF selection)
- `/index` → IndexScreenerView (index overview)

**Quant System** (requires 'pro' tier):
- `/quant` → QuantView (model overview hub)
- `/quant/screening` → QuantScreeningView (full market screening)
- `/quant/pool` → QuantPoolView (core target pool)
- `/quant/rps` → QuantRpsView (RPS ranking)
- `/quant/analysis` → QuantAnalysisView (deep analysis)
- `/quant/signals` → QuantSignalsView (trading signals)
- `/quant/config` → QuantConfigView (model configuration)

**Strategy & Agent Management** (requires 'pro' tier):
- `/strategy` → StrategyWorkbench
- `/backtest` → BacktestView
- `/orchestration` → OrchestrationList (Agent teams)
- `/orchestration/:id` → OrchestrationEditor
- `/agents` → AgentList (Agent management)
- `/agents/:id/edit` → AgentEditor
- `/arena` → ArenaManagement (Multi-Agent arena)
- `/arena/:id` → ArenaDetail
- `/arena/:arenaId/strategy/:strategyId` → ArenaStrategyDetail

**System Admin** (requires admin flag):
- `/system-logs` → SystemLogs
- `/datamanage` → DataManageView
- `/datamanage/explorer` → DataExplorerView
- `/datamanage/tasks` → SyncTasksView
- `/datamanage/config` → DataConfigView
- `/datamanage/knowledge` → KnowledgeView
- `/api-access` → ApiAccessView
- `/wechat-bridge` → WechatBridgeView

**User:**
- `/user` → UserCenter
- `/user/llm-config` → UserCenter (same component)
- `/user/mcp-usage` → UserCenter (same component)

**Legacy Redirects:**
- `/` → redirects to `/chat`
- `/memory` → redirects to `/portfolio`
- `/workflow` → redirects to `/orchestration`
- `/report` → redirects to `/research`

---

## 2. LAYOUT & PAGE STRUCTURE

### Global Layout
**File**: `/frontend/src/App.vue`
- **Pattern**: Two-tier layout
  - Sidebar (left): Navigation menu with icons and nested submenus
  - Main content area (right): Header + Router view container

**Sidebar Structure:**
```
- Chat (智能对话)
- Market Center (行情中心)
  ├─ Market Analysis (行情分析)
  ├─ Index Overview (指数行情)
  ├─ Smart ETF (智能选ETF)
- Financial Reports (财报分析)
- News Center (资讯中心)
- Stock Screener (智能选股)
- Holdings Management (持仓管理)
- Strategy System (策略系统) [PRO]
  ├─ Strategy Workbench
  ├─ Agent Arena
- Quant Selection (量化选股) [PRO]
  ├─ Model Overview
  ├─ Full Market Screening
  ├─ Core Pool
  ├─ RPS Ranking
  ├─ Deep Analysis
  ├─ Trading Signals
  ├─ Model Config
- Agent Center (Agent中心)
  ├─ Agent Management
  ├─ Agent Teams
  ├─ Runtime Management
  ├─ Sentinel Stock Screening
- WeChat Integration (微信联动) [ADMIN]
- Data Management (数据管理) [ADMIN]
  ├─ Data Overview
  ├─ Data Browser
  ├─ Sync Tasks
  ├─ Knowledge Base
  ├─ Data Config
- System Logs (系统日志) [ADMIN]
- Open API (开放API) [ADMIN]
```

**Menu Visibility Logic:**
- Tier hierarchy: `free (0) < pro (1) < admin (2)`
- Routes with `requiresAuth=true` + `requiresTier='pro'` only visible to pro/admin users
- Routes with `requiresAdmin=true` only visible to admin users

---

## 3. CHAT VIEW - INTELLIGENT DISCUSSION INTERFACE

### Main Chat Component
**File**: `/frontend/src/views/chat/ChatView.vue`

#### Layout Structure (3-column flex)
```
┌─────────────────────────────────────────────────────────────┐
│                       Chat Header                           │
├─────────────┬──────────────────────────┬────────────────────┤
│             │                          │                    │
│ Sessions    │    Main Chat Area        │ Agent Debug        │
│ Sidebar     │  - Tab Bar (Chat/Akinator)│ Sidebar (toggle)  │
│ (collapse)  │  - Message List          │ 360px width       │
│             │  - Suggestions           │ Auto-scroll       │
│             │  - InputBox              │                    │
│             │  - Agent Teams Panel     │                    │
│             │                          │                    │
└─────────────┴──────────────────────────┴────────────────────┘
```

#### Key UI Components

**Sessions Sidebar** (`expanded: 280px`)
- Function: Navigate between chat sessions
- Groups sessions by: Today, Yesterday, This Week, Earlier
- Actions: Edit title, delete, switch session
- New conversation button

**Main Chat Container**
- Header with session title and action buttons:
  - Toggle sessions sidebar
  - Clear conversation (if messages exist)
  - **Debug button** (toggles AgentDebugSidebar)
  - New conversation

**Message Area**
- Scrollable container
- Displays user/assistant messages
- Shows typing indicators

**Input Area**
- Suggestion tags (quick actions)
- Agent Teams button
- InputBox component
- Agent Teams Panel (collapsible list)

#### Tab Structure
- `chat` tab (default): Traditional chat interface
- `akinator` tab: 🔮 Akinator game interface (guessing game for stock analysis)

---

## 4. DEBUG SIDEBAR - AGENT EXECUTION VISUALIZATION

### AgentDebugSidebar Component
**File**: `/frontend/src/views/chat/components/AgentDebugSidebar.vue`
**Size**: 360px fixed width (right side of chat view)
**Toggle**: Header button "调试" (Debug)

#### Layout Structure
```
┌─────────────────────────────────┐
│ Header: Agent Debug [count]  [X]│
├─────────────────────────────────┤
│                                 │
│ Timeline Overview               │
│ (DebugTimeline component)       │
│                                 │
├─────────────────────────────────┤
│                                 │
│ Messages List (scrollable)      │
│ (DebugMessage components)       │
│ Auto-scroll to latest           │
│                                 │
│ Empty state: "Send message,     │
│  Agent's thoughts appear here"  │
│                                 │
└─────────────────────────────────┘
```

#### Sub-Components

**DebugTimeline** (`/components/DebugTimeline.vue`)
- **Purpose**: Visual timeline of agent execution
- **Data**: Computed from `agent_start` and `agent_end` debug events
- **Display**: Horizontal bars showing agent execution duration
- **Features**:
  - Color-coded per agent (6-color palette)
  - Shows success/failure status
  - Displays total execution time
  - Labels with duration (ms/s)
  - Agent names aligned on left

**DebugMessage** (`/components/DebugMessage.vue`)
- **Purpose**: Individual debug event display
- **Data**: `DebugMessage` objects from chat store
- **Expandable**: Shows detailed information on click
- **Role-based coloring**: 
  - Orchestrator (blue #0052d9)
  - Agent (green #2ba471)
  - Tool (orange #e37318)
  - System (gray #888)
  - Handoff (purple #7b61ff)

**Debug Event Types Displayed:**
- `classification`: Intent recognition
- `routing`: Agent routing (parallel or sequential)
- `agent_start`/`agent_end`: Agent execution lifecycle
- `tool_result`: Tool call and results
- `handoff`: Agent-to-agent handoff
- `data_sharing`: Data passed between agents

**Expandable Details Include:**
- Tool parameters
- Result summaries
- Rationale for decisions
- Available tools
- Input data
- Shared data

---

## 5. QUANT ANALYSIS SYSTEM

### Quant View Hub
**File**: `/frontend/src/views/quant/QuantView.vue`

#### Page Layout (stacked cards)
1. **Pipeline Progress Card**
   - 4 stages displayed horizontally with arrows
   - Each stage is clickable → routes to detailed view
   - Shows status tags (完成/进行中/数据缺失/错误)
   - Stage summary statistics

2. **Data Readiness Panel** (conditional)
   - Alert if data missing
   - Table of missing plugins
   - Select checkboxes for batch sync
   - "补充所有缺失数据" (Sync all missing) button

3. **Overview Stats Cards** (3 columns)
   - Core Pool count (clickable → /quant/pool)
   - Supplement Pool count
   - Today's Signals count

4. **Quick Navigation** (grid)
   - 4 cards linking to detailed views

### Quant Analysis View
**File**: `/frontend/src/views/quant/QuantAnalysisView.vue`

#### Layout
```
┌─────────────────────────────┐
│  Deep Analysis [Stock Code] │
│  [Analyze Button]           │
├──────────┬──────────┬───────┤
│          │          │       │
│ Tech     │ AI       │  ...  │
│ Metrics  │ Analysis │       │
│ Card     │ Card     │       │
│          │          │       │
├──────────┴──────────┴───────┤
│                             │
│ Target Pool Analysis Table  │
│ (Tech scores, Credibility)  │
│                             │
└─────────────────────────────┘
```

#### Key Components
- **Tech Indicators Card**: MA25, MA120, MA250, MACD, RSI, volume ratio, MA position
- **AI Analysis Card**: Credibility/Optimism scores, summary, key findings, risk factors, verification points
- **Analysis Dashboard**: Table with stocks from target pool

---

## 6. STATE MANAGEMENT - CHAT STORE

**File**: `/frontend/src/stores/chat.ts` (Pinia)

### Key State Properties

**Message State:**
- `messages: ChatMessage[]` - Current session messages
- `streamingContent: string` - Streaming response content
- `loading: boolean` - Request in flight

**Session State:**
- `sessionId: string` - Current session ID
- `sessions: ChatSessionSummary[]` - User's session history
- `currentSessionTitle: string` - Display title

**Debug/Agent State:**
- `debugMessages: DebugMessage[]` - Debug event log
- `debugSidebarOpen: boolean` - Sidebar visibility toggle
- `messageDebugMap: Record<string, DebugMessage[]>` - Maps message ID to debug events
- `thinking: boolean` - Agent thinking status
- `currentAgent: string` - Active agent name
- `currentIntent: string` - Detected intent
- `currentTool: string` - Current tool call
- `currentPlan: PlanStep[]` - Execution plan steps

**Visualization State:**
- `messageVisualizations: Record<string, VisualizationEvent['visualization'][]>` - Maps message ID to visualization payloads

### Key Methods

**Session Management:**
- `initSession()` - Create new session
- `restoreOrInitSession()` - Restore from localStorage or create
- `loadSessions(limit, offset)` - Load session history
- `switchSession(sessionId)` - Switch between sessions
- `deleteSession(sessionId)` - Delete a session
- `updateSessionTitle(sessionId, title)` - Rename session
- `clearCurrentConversation()` - Clear messages in current session

**Message Handling:**
- `sendMessage(content)` - Send user message, stream response
- `handleStreamEvent(event)` - Process WebSocket stream events
- `addDebugMessage(debugEvent)` - Add debug event to sidebar

**LocalStorage Persistence:**
- `saveMessagesToStorage()` - Persist messages (max 100 per session)
- `loadMessagesFromStorage()` - Restore from cache
- `saveSessionToStorage()` - Remember last session
- `loadSessionFromStorage()` - Restore last session

### Debug Message Interface
```typescript
interface DebugMessage {
  id: string
  debugType: 'classification' | 'routing' | 'agent_start' | 'agent_end' | 'tool_result' | 'handoff' | 'data_sharing'
  agent: string                    // Agent code name
  timestamp: number                // Unix seconds
  data: any                        // Event data (intent, tool args, results, etc.)
  targetAgent?: string
  parentAgent?: string
  laneId?: string                  // For parallel execution tracking
  role: 'orchestrator' | 'agent' | 'tool' | 'system' | 'handoff'
}
```

---

## 7. KEY PATTERNS & INTEGRATION POINTS

### Sidebar Integration Pattern
1. **Chat View** opens/closes sessions sidebar (left) via button toggle
2. **AgentDebugSidebar** appears on right when debug button clicked
3. **Both sidebars preserve message area** - Responsive design:
   - Desktop (>1400px): Fixed side panels + main content
   - Medium (1024-1400px): Debug sidebar overlay on right
   - Mobile (<1024px): Debug sidebar as drawer

### Agent-to-View Communication
1. **Chat → Debug Events**: WebSocket stream sends `DebugEvent` objects
2. **Store processes events**: `handleStreamEvent()` populates `debugMessages[]`
3. **Components render**: `DebugMessage` and `DebugTimeline` display execution trace
4. **Navigation links**: Click agent name in debug message → `/agents?highlight=agent_db_name`

### Tier-Based Access Control
- **Router guards** (`beforeEach`): Check `requiresAuth`, `requiresAdmin`, `requiresTier`
- **Menu filtering**: `visibleMenuItems` computed property filters based on user tier
- **Redirect logic**: Route to `/market` if lacking permissions

### Analysis Page Patterns
- **Quant pages** follow similar structure:
  1. Card-based layout with grid system (t-row, t-col)
  2. Input controls in card actions
  3. Data table for results
  4. Real-time progress via store polling

---

## 8. FILE STRUCTURE SUMMARY

```
frontend/src/
├── router/
│   └── index.ts                    [Route definitions + guards]
├── views/
│   ├── chat/
│   │   ├── ChatView.vue           [Main chat 3-column layout]
│   │   └── components/
│   │       ├── AgentDebugSidebar.vue  [Debug panel controller]
│   │       ├── DebugTimeline.vue      [Timeline visualization]
│   │       ├── DebugMessage.vue       [Debug event display]
│   │       ├── MessageList.vue        [Chat messages]
│   │       ├── InputBox.vue           [Message input]
│   │       └── AkinatorPanel.vue      [Akinator game]
│   ├── quant/
│   │   ├── QuantView.vue           [Model hub overview]
│   │   ├── QuantAnalysisView.vue   [Deep analysis with tech/AI cards]
│   │   ├── QuantPoolView.vue       [Core pool display]
│   │   ├── QuantRpsView.vue        [RPS ranking]
│   │   ├── QuantScreeningView.vue  [Market screening]
│   │   ├── QuantSignalsView.vue    [Trading signals]
│   │   └── QuantConfigView.vue     [Model config]
│   └── [other-views]/
├── stores/
│   ├── chat.ts                     [Chat/debug state + methods]
│   ├── quant.ts                    [Quant model state]
│   └── [other-stores]/
├── api/
│   ├── chat.ts                     [Chat API + WebSocket events]
│   ├── quant.ts                    [Quant API]
│   └── [other-apis]/
├── App.vue                         [Global 2-column layout]
└── main.ts                         [Entry point - Pinia + Router]
```

---

## 9. KEY TAKEAWAYS FOR EXTENSION

### For Adding Sidebar to Analysis Pages
1. **Mirror ChatView pattern**: Use flex layout with main content + collapsible sidebar
2. **Store agent discussions**: Track debug messages per analysis in store
3. **Reuse components**: 
   - `AgentDebugSidebar.vue` can be copied/adapted
   - `DebugMessage.vue` and `DebugTimeline.vue` are generic
4. **WebSocket events**: Listen to same debug event stream (already in chat store)

### For Creating New Analysis Views
1. **Follow Quant page structure**: Card-based with t-row/t-col grid
2. **Leverage stores**: Use Pinia for state management
3. **Route definition**: Add to `router/index.ts` with auth guards
4. **Menu entry**: Add to `App.vue` menuItems array

### API Integration
- Chat API: WebSocket for streaming + REST for session management
- Quant API: REST polling + store actions
- Both use auth header from `authStore`

---

## 10. RESPONSIVE DESIGN PATTERNS

**Mobile Breakpoints (TDesign):**
- Desktop (>1400px): All sidebars visible
- Tablet (1024-1400px): Debug sidebar overlay
- Mobile (<1024px): Drawer mode for sidebars

**Component Responsiveness:**
- Session sidebar: Width collapsible (0 → 280px)
- Debug sidebar: Position overlay at 1024px threshold
- Main content: Flex fill remaining space

