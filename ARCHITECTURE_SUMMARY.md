# Stock Datasource - Architecture Summary

**Date**: 2026-05-15  
**Project Location**: `/root/lzh/stock_datasource`

---

## Quick Reference

### Three Documentation Files Created:
1. **EXPLORATION_REPORT.md** - Detailed technical breakdown (15KB)
2. **MENU_STRUCTURE_VISUAL.txt** - ASCII visual diagrams (17KB)
3. **ARCHITECTURE_SUMMARY.md** - This file

---

## Key Findings

### 1. Frontend Architecture

**Framework**: Vue 3 + TypeScript with T-Design UI  
**State Management**: Pinia stores (21 dedicated stores)  
**Routing**: Vue Router with lazy-loaded components  
**Current Menu**: 14 main items (2 public, 9 auth, 3 submenus)

**Tier System**:
- Free: Basic features (public + free-auth items)
- Pro: Advanced features (strategy, quant, workflow)
- Admin: System management (data, logs, API)

### 2. Market Views Structure

Three closely related market views that could be consolidated:

| View | Path | Purpose | Components | Auth |
|------|------|---------|-----------|------|
| **Market Analysis** | `/market` | Overview dashboard | Heatmap, sentiment, indices, hot stocks/ETFs | Public |
| **Index Quotes** | `/index` | Index screening tool | Filters, table, detail panel, analysis | Auth |
| **ETF Screener** | `/etf` | ETF discovery & benchmarks | Tabs (quotes/benchmarks), analysis | Auth |

**Consolidation Opportunity**: Group into "行情中心" (Market Center) submenu

### 3. Database Infrastructure

**Primary Storage**: ClickHouse 24 (time-series optimized)
- Main DB: `stock_data`
- Cache: Redis 7 (1GB, LRU)

**Current Tables**:
- `system_structured_logs` - Request tracing (90-day TTL)
- `sentinel_alerts` - Alert events (90-day TTL)
- `sentinel_analyst_reports` - Analysis reports (90-day TTL)
- `sentinel_decisions` - Trading decisions (365-day TTL)

**Workflow Storage**: File-based JSON at `/data/workflows/{id}.json`

### 4. Agent/Workflow Configuration

**Current Model** (`models/workflow.py`):
```python
AIWorkflow {
  id: UUID
  name, description
  system_prompt: str         # AI role definition
  user_prompt_template: str  # {{variable}} substitution
  selected_tools: list[str]  # MCP tools
  variables: [WorkflowVariable]
  is_template, category, tags
  created_at, updated_at
}
```

**Built-in Templates**:
1. Single stock analysis
2. Stock comparison
3. Value investing screening
4. Technical analysis

**API Endpoints**: `/api/workflows/*` (CRUD + execute + generate)

---

## Data Flow Diagrams

### Frontend → Backend → Database

```
Frontend (Vue3)
    ↓
Stores (Pinia)
    ├─ auth.ts (user/tier/permissions)
    ├─ workflow.ts (configurations)
    ├─ overview.ts (market data)
    ├─ index.ts (index screener)
    ├─ etf.ts (ETF data)
    └─ [18 other stores]
    ↓
API Layer
    ├─ /api/workflows/* (CRUD)
    ├─ /api/market/* (quotes)
    ├─ /api/index/* (screener)
    └─ [many other endpoints]
    ↓
Services Layer
    ├─ WorkflowService (file-based JSON)
    ├─ OverviewService (data aggregation)
    └─ [domain-specific services]
    ↓
Database
    ├─ ClickHouse (operational data)
    ├─ Redis (cache)
    └─ JSON files (workflows)
```

### Workflow Execution Flow

```
Frontend UI
    ↓
WorkflowStore.execute(workflowId, variables)
    ↓
API POST /api/workflows/{id}/execute
    ↓
WorkflowService.execute()
    ↓
Claude API (with MCP tools)
    ├─ System prompt
    ├─ User prompt (variables substituted)
    └─ Selected MCP tools
    ↓
Streaming Response
    ├─ Thinking blocks
    ├─ Tool calls
    ├─ Content
    └─ Results
    ↓
Frontend Display (streaming UI)
```

---

## Recommendations

### For Merging Market Pages

**Current state** (9 top-level items):
- ❌ Menu cluttered
- ❌ Related items scattered
- ❌ Hard to extend

**Proposed**: Add submenu "行情中心" (Market Center)
```typescript
{
  path: '/market',
  title: '行情中心',
  icon: ChartLineIcon,
  public: true,
  children: [
    { path: '/market', title: '市场概览', icon: ChartLineIcon },
    { path: '/index', title: '指数行情', icon: TrendingUpIcon },
    { path: '/etf', title: '智能选ETF', icon: ControlPlatformIcon }
  ]
}
```

**Benefits**:
✓ Reduces top-level items to 7  
✓ Clear visual grouping  
✓ Better organization for adding features  
✓ Maintains backward compatibility (routes unchanged)

### For Agent Config Storage

**Current**: File-based JSON (limitations: not queryable, no audit trail)

**Recommended**: ClickHouse table

```sql
CREATE TABLE agent_configurations (
    id String,
    name String,
    category String,
    description String,
    system_prompt String,
    user_prompt_template String,
    selected_tools Array(String),
    variables String,              -- JSON
    config_metadata String,         -- JSON
    is_active Boolean,
    is_template Boolean,
    created_by String,
    created_at DateTime,
    updated_at DateTime
) ENGINE = MergeTree()
ORDER BY (category, created_at)
```

**Benefits**:
✓ Full audit trail  
✓ Query-able (filter by category, creator, etc.)  
✓ Integrates with observability layer  
✓ Scales better than file storage  
✓ Supports versioning/history

---

## File Locations Reference

### Frontend
```
frontend/src/
├── App.vue                          # Main menu definition
├── router/index.ts                  # Route definitions
├── stores/                          # 21 Pinia stores
│   ├── workflow.ts                  # Workflow state
│   ├── overview.ts                  # Market overview
│   ├── index.ts                     # Index data
│   ├── etf.ts                       # ETF data
│   └── [17 others]
├── views/
│   ├── market/MarketView.vue        # Market dashboard
│   ├── index/IndexScreenerView.vue  # Index screener
│   ├── etf/EtfView.vue              # ETF screener
│   └── [21 other views]
└── api/
    └── workflow.ts                  # API client
```

### Backend
```
src/stock_datasource/
├── models/
│   ├── workflow.py                  # AIWorkflow model
│   ├── database.py                  # ClickHouse client
│   └── schemas.py
├── api/
│   └── workflow_routes.py           # Workflow endpoints
├── services/
│   └── workflow_service.py          # Workflow CRUD
├── modules/
│   └── sentinel/
│       └── persistence/
│           └── tables.py            # Sentinel tables
└── agents/
    ├── base_agent.py
    ├── workflow_agent.py
    └── [other agents]
```

### Infrastructure
```
docker/
├── init-clickhouse.sql              # DB initialization
└── migrations/
    ├── 001_create_system_structured_logs.sql
    └── 002_add_middleware_trace_id.sql

data/
└── workflows/                       # JSON workflow storage
    └── {workflow_id}.json
```

---

## Technology Stack at a Glance

| Component | Technology | Details |
|-----------|-----------|---------|
| **Frontend Framework** | Vue 3 | Progressive framework, composition API |
| **Language (Frontend)** | TypeScript | Type safety, better IDE support |
| **UI Library** | T-Design Vue Next | Professional components from Tencent |
| **State Management** | Pinia | Lightweight Vue 3 store |
| **Routing** | Vue Router | Nested routes, lazy loading |
| **HTTP Client** | Custom Axios wrapper | Built-in auth interceptor |
| **Database** | ClickHouse 24 | Time-series optimized, columnar |
| **Cache Layer** | Redis 7 | In-memory, 1GB LRU |
| **Config Storage** | JSON files | Currently in `/data/workflows/` |
| **Backend Framework** | FastAPI | (inferred from routes) |
| **Language (Backend)** | Python | (inferred from .py files) |
| **AI Integration** | Claude API | (inferred from models) |
| **Tool Framework** | MCP | Multi-tool support via prompts |

---

## Monitoring & Observability

**Structured Logging**:
- Table: `system_structured_logs`
- Partitioned by date, 90-day TTL
- Columns: timestamp, level, request_id, user_id, module, function, line, message, exception, extra

**Workflow Execution Events**:
- Real-time streaming via SSE/WebSocket
- Events: thinking, content, tool_call, done, error
- Stored in `sentinel_*` tables for analysis

---

## Security & Access Control

### Authentication Layer
- Token-based auth (JWT assumed)
- Dependency: `get_current_user` in API routes
- Admin check: `require_admin` dependency

### Authorization Rules
1. **Public Routes**: `/login`, `/market`, `/research`
2. **Auth Required**: Most features require login
3. **Tier Restrictions**: 
   - Pro tier: Strategy, Quant, Workflow modules
   - Admin: System logs, data management, API access
4. **Menu Filtering**: Dynamic based on user tier and role

---

## Performance Considerations

### Current Polling Strategy
- **Market real-time**: 30-second interval (trading hours only)
- **Hot ETF refresh**: 300ms debounce
- **System logs**: Continuous collection

### Optimization Opportunities
1. Use WebSocket instead of polling for critical pages
2. Implement Redis caching for frequently accessed data
3. Add pagination to large result sets
4. Consider incremental updates instead of full refreshes

---

## Next Steps (Recommendations)

### Phase 1: Menu Consolidation
- [ ] Create "行情中心" submenu in App.vue
- [ ] Update router with submenu structure
- [ ] Test backward compatibility
- [ ] Update documentation

### Phase 2: Database Migration
- [ ] Create `agent_configurations` ClickHouse table
- [ ] Implement migration from JSON to ClickHouse
- [ ] Add versioning support
- [ ] Maintain JSON export for portability

### Phase 3: Agent Expansion
- [ ] Add new workflow templates
- [ ] Implement agent configuration UI
- [ ] Add configuration history tracking
- [ ] Build analytics on configuration usage

### Phase 4: Real-time Enhancement
- [ ] Implement WebSocket for real-time updates
- [ ] Reduce polling overhead
- [ ] Improve responsiveness on market-related pages

---

## Contact & References

**Created**: 2026-05-15  
**Documentation Version**: 1.0  
**Project Base**: `/root/lzh/stock_datasource`

---

## Appendix: Menu Items Summary

### Free Users (9 visible)
1. 行情分析 (public)
2. 财报分析 (public)
3. 资讯中心
4. 智能对话
5. 智能选股
6. 哨兵选股
7. 持仓管理
8. 指数行情
9. 用户记忆

### Pro Users (add 3)
10. 策略系统 (submenu)
11. 量化选股 (submenu)
12. AI工作流

### Admin Users (add 3)
13. 微信联动
14. 系统日志
15. 开放API
16. 数据管理 (submenu)

**Total**: 16 distinct menu items (some with submenus = 23 leaf items)

