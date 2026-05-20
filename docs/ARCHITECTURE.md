# Multi-Agent Architecture Exploration Report

## Executive Summary

This is a **sophisticated multi-agent financial AI platform** with a **hierarchical, event-driven orchestration system**. The codebase implements a comprehensive agent-based architecture using LangGraph, featuring 18+ specialized agents, multiple orchestration layers, a competitive arena system for strategy refinement, and extensive middleware for safety and memory management.

---

## 1. Top-Level Directory Structure

```
/root/lzh/stock_datasource/
├── src/stock_datasource/           # Main source code
│   ├── agents/                      # Agent implementations (18+ agents)
│   ├── arena/                       # Multi-agent strategy competition system
│   ├── services/                    # Core services & orchestration
│   ├── strategies/                  # Trading strategy framework
│   ├── modules/                     # Feature modules (30+ modules)
│   ├── config/                      # Configuration management
│   ├── core/                        # Core utilities
│   ├── cli/                         # Command-line interfaces
│   ├── api/                         # HTTP APIs
│   ├── llm/                         # LLM integration
│   ├── models/                      # Data models
│   ├── tasks/                       # Task definitions
│   ├── dags/                        # Airflow DAGs
│   ├── backtest/                    # Backtesting framework
│   ├── utils/                       # Utilities
│   └── plugins/                     # Plugin system
├── openspec/                        # Design specs (OpenSpec framework)
│   ├── specs/                       # Capability specifications
│   ├── changes/                     # Pending & archived proposals
│   └── project.md                   # Project conventions
├── frontend/                        # React frontend
├── docker/                          # Docker configuration
├── skills/                          # MCP skills
├── tests/                           # Test suite
├── cli.py                           # Main CLI entry point
├── README.md                        # Project documentation
└── pyproject.toml                   # Python project config
```

---

## 2. Agent-Related Files & Architecture

### 2.1 Core Agent Directory Structure

```
src/stock_datasource/agents/
├── base_agent.py                    # LangGraphAgent base class
├── orchestrator.py                  # Lightweight config-driven routing agent
├── config_driven_harness_agent.py   # DB-configured Harness agent
├── chat_agent.py                    # ChatAgent - conversational interface
├── [specialized agents]             # Legacy direct-import compatibility
├── middlewares/                     # Safety & memory middleware
│   ├── base.py                      # Middleware base class
│   ├── cross_validation.py          # Cross-validation middleware
│   ├── guardrail.py                 # Safety guardrails
│   ├── loop_detection.py            # Loop detection
│   ├── memory_injection.py          # Memory injection
│   ├── signal_extraction.py         # Signal extraction
│   └── summarization.py             # Auto-summarization
└── tools.py                         # Shared tools
```

### 2.2 Specialized Agent Names

Most chat-facing agents are now DB configurations executed by `ConfigDrivenHarnessAgent`. Some Python agent files remain only for direct-import compatibility.

| Agent Name | Purpose | Key Responsibilities |
|------------|---------|----------------------|
| **OverviewAgent** | Market overview | DB-configured market sentiment and aggregate analysis |
| **MarketAgent** | Technical analysis | Legacy direct-import compatibility for market tools |
| **ScreenerAgent** | Intelligent stock screening | Find stocks matching criteria, quantitative filtering |
| **ReportAgent** | Financial analysis | Legacy direct-import compatibility for report tools |
| **HKReportAgent** | Hong Kong stocks | HK-specific financial analysis |
| **PortfolioAgent** | Portfolio management | Legacy direct-import compatibility for portfolio tools |
| **BacktestAgent** | Strategy backtesting | Historical testing, performance evaluation |
| **IndexAgent** | Index analysis | Index tracking, comparative analysis |
| **EtfAgent** | ETF analysis | ETF holdings, performance, tracking error |
| **TopListAgent** | Limit-up/limit-down boards | Trading sentiment, institutional activity |
| **NewsAnalystAgent** | News analysis | Market news interpretation, sentiment analysis |
| **KnowledgeAgent** | Knowledge retrieval | Research reports, announcements (RAG system) |
| **DataManageAgent** | Data management | Data refresh, quality checks, maintenance |
| **ChatAgent** | General conversation | Fallback for unmatched queries |

### 2.3 Arena System (Multi-Agent Competition)

```
src/stock_datasource/arena/
├── arena_manager.py                 # MultiAgentArena orchestrator
├── discussion_orchestrator.py        # AgentDiscussionOrchestrator - debate/collaboration
├── competition_engine.py             # StrategyCompetitionEngine - competition lifecycle
├── stream_processor.py               # ThinkingStreamProcessor - SSE streaming
├── models.py                         # Arena domain models
├── persistence.py                    # Arena state persistence
├── exceptions.py                     # Custom exceptions
└── agents/                           # Arena-specific agents
    ├── base.py                       # ArenaAgentBase class
    ├── market_sentiment.py           # MarketSentimentAgent
    ├── quant_researcher.py           # QuantResearcherAgent
    ├── risk_analyst.py               # RiskAnalystAgent
    ├── strategy_generator.py         # StrategyGeneratorAgent
    └── strategy_reviewer.py          # StrategyReviewerAgent
```

**Arena Lifecycle:**
1. Create arena with N agents
2. Initialize discussion orchestrator
3. Run discussion rounds (DEBATE, COLLABORATION, REVIEW modes)
4. Execute backtests on generated strategies
5. Promote winners to simulated trading
6. Periodic evaluation and elimination
7. Strategy replenishment

---

## 3. Core Orchestration Services

### 3.1 Config-Driven Harness Runtime

**Purpose:** Build and execute agents from ClickHouse `agent_configs` records.

**Architecture:**
- `OrchestratorAgent` performs lightweight intent classification.
- `ConfigDrivenHarnessAgent` loads the selected DB config and builds a DeepAgents harness.
- `tool_registry.py` resolves configured skills/tool names to callable functions.
- No `AGENT_RUNTIME_ENABLED` or `HARNESS_MODE_ENABLED` switch is required.

### 3.2 Execution Planner (`services/execution_planner.py`)

**Purpose:** Agent routing configuration and metadata

**Key Data Structures:**

```python
# Concurrent execution groups
CONCURRENT_AGENT_GROUPS = [
    {"MarketAgent", "ReportAgent"},
    {"IndexAgent", "EtfAgent"},
    {"OverviewAgent", "TopListAgent"},
    # ... more
]

# Agent handoff map
AGENT_HANDOFF_MAP = {
    "MarketAgent": ["ReportAgent", "HKReportAgent", "BacktestAgent"],
    "ScreenerAgent": ["MarketAgent", "ReportAgent"],
    # ... more
}

# Execution modes
ExecutionMode = ROUTE_ONLY | PARALLEL_AGGREGATE | SEQUENTIAL_HANDOFF | 
                WORKFLOW_DRIVEN | DISCUSSION_ARENA | SUPERVISOR
```

**Utility Functions:**
- `expand_agent_list()`: Multi-agent expansion logic
- `can_run_concurrently()`: Concurrency validation
- `get_handoff_targets()`: Handoff planning

### 3.3 Agent Registry (`services/agent_registry.py`)

**Purpose:** Centralized agent discovery and registration

**Key Concepts:**

```python
class AgentRole(Enum):
    AGENT = "agent"              # Direct routing
    SUB_AGENT = "sub_agent"      # Coordinator only
    ADAPTER = "adapter"          # Wraps workflow/arena

@dataclass
class AgentDescriptor:
    name: str
    description: str
    agent_class: type
    role: AgentRole
    capability: CapabilityDescriptor
    priority: int
    enabled: bool
```

**Registration Modes:**
- Explicit registration via descriptors
- Package scanning fallback for backward compatibility
- Lazy instance creation

### 3.4 Session & Memory Service (`services/session_memory_service.py`)

**Purpose:** Unified memory and session management

**Memory Layers:**
- **A: LangGraph MemorySaver** - Automatic checkpoint
- **B: Tool result compression** - Context size reduction
- **D: Shared state storage** - Cross-turn caching
- **E: Long-term memory** - User preferences & history

### 3.5 Skill Registry (`services/skill_registry.py`)

**Purpose:** Unified skill/tool management across MCP, builtins, workspace

**Capabilities:**
- Tool descriptor registration
- MCP tool wrapping
- Workspace skill discovery
- Plugin export capabilities

---

## 4. Configuration Files

### 4.1 Runtime Configuration (`config/runtime_config.py`)

**Location:** Persistent `data/runtime_config.json` (volume-mounted in Docker)

**Configuration Sections:**

```python
DEFAULT_CONFIG = {
    "proxy": {              # Proxy settings
        "enabled": False,
        "host": "", "port": 0
    },
    "sync": {               # Sync concurrency
        "max_concurrent_tasks": 1,
        "max_date_threads": 1
    },
    "schedule": {           # Data scheduler
        "enabled": False,
        "execute_time": "18:00",
        "frequency": "weekday"
    },
    "realtime": {           # Real-time data
        "enabled": False,
        "watchlist_monitor_enabled": False
    },
    "plugin_schedules": {}  # Per-plugin schedule config
}
```

**API:**
- `load_runtime_config()` - Read current config
- `save_runtime_config()` - Persist updates
- `get_plugin_schedule_config()` - Per-plugin schedule

### 4.2 Settings (`config/settings.py`)

**Environment-Based Configuration:**
- Database connections (ClickHouse)
- API keys (OpenAI, Tushare)
- Feature flags
- Path configurations

---

## 5. Multi-Agent Communication Patterns

### 5.1 Orchestrator Pattern (OrchestratorAgent)

**Flow:**
```
User Input
    ↓
OrchestratorAgent (LangGraph)
    ├── Middleware chain (before)
    │   ├── Intent extraction
    │   ├── Stock code extraction
    │   ├── Memory injection
    │   ├── Loop detection
    │   └── Signal extraction
    ├── LLM routing decision
    │   ├── Analyze user intent
    │   ├── Create execution plan
    │   └── Route to specialist agent(s)
    ├── Agent execution (serial or parallel)
    ├── Middleware chain (after)
    │   ├── Cross-validation
    │   ├── Guardrails
    │   ├── Summarization
    │   └── Memory update
    └── Streaming SSE events
        (thinking → content → tool → debug → done)
```

### 5.2 Arena Discussion Pattern (MultiAgentArena)

**Flow:**
```
Arena Created
    ↓
Initialize Agents (N agents with different roles)
    ├── StrategyGeneratorAgent × M
    ├── StrategyReviewerAgent
    ├── RiskAnalystAgent
    ├── MarketSentimentAgent
    └── QuantResearcherAgent
    ↓
Discussion Round (e.g., DEBATE mode)
    ├── Market context injection
    ├── Concurrent agent thinking
    ├── Message exchange
    ├── Strategy refinement
    └── Publish via ThinkingStreamProcessor (SSE)
    ↓
Competition Phase
    ├── Backtest strategies (N agents)
    ├── Rank by performance
    ├── Simulate trading (top K)
    └── Periodic elimination & replenishment
```

### 5.3 Config-Driven Agent Pattern

**Flow:**
```
Agent config (ClickHouse)
    ├── system_prompt
    ├── skills / tool names
    ├── model_config
    └── runtime_config
    ↓
ConfigDrivenHarnessAgent executes request
    ├── Resolve tools via tool_registry
    ├── Build create_deep_agent harness
    ├── Stream SSE-compatible events
    └── Persist session metadata
```

### 5.4 Middleware Chain (Safety & Memory)

**Execution Order:**

```
BEFORE PHASE:
  1. MemoryInjectionMiddleware
     → Retrieve user preferences, session history
  2. LoopDetectionMiddleware
     → Check for conversation loops
  3. GuardrailMiddleware
     → Validate financial query compliance
  4. SignalExtractionMiddleware
     → Detect trading signals
  5. CrossValidationMiddleware
     → Prepare validation

AGENT EXECUTION:
  → LLM + tools

AFTER PHASE:
  1. CrossValidationMiddleware
     → Verify AI response consistency
  2. GuardrailMiddleware
     → Apply safety filters
  3. SummarizationMiddleware
     → Compress long responses
  4. MemoryInjectionMiddleware (storage phase)
     → Update user memory
```

---

## 6. Communication Protocols

### 6.1 SSE Event Model

**Event Types:**
```python
{
    "type": "thinking",           # AI reasoning
    "type": "content",            # AI response text
    "type": "tool",               # Tool invocation
    "type": "debug",              # Debug metadata
    "type": "visualization",      # Chart/visual data
    "type": "done",               # Completion signal
    "type": "error"               # Error message
}
```

### 6.2 Agent Result Format

```python
@dataclass
class AgentResult:
    response: str                 # Main response text
    success: bool                 # Execution success
    metadata: dict                # Additional data
    tool_calls: list              # Tools invoked
```

### 6.3 Context Propagation

```python
@dataclass
class AgentContext:
    session_id: str
    user_id: str
    stock_codes: list[str]
    preferences: dict
    history: list
    intent: str
```

---

## 7. Entry Points

### 7.1 CLI Entry Point (`cli.py`)

**Main Commands:**
```bash
# Database management
uv run cli.py init-db
uv run cli.py load-hk-basic

# Data ingestion
uv run cli.py ingest --plugin <name>

# Workflow execution
uv run cli.py run-workflow <workflow-id>

# System management
uv run cli.py logs archive
```

### 7.2 HTTP API Entry Points

**Key Endpoints:**
```
POST   /api/chat                     # Chat query
GET    /api/agents                   # List agents
POST   /api/workflow/create          # Create workflow
POST   /api/arena/create             # Create arena
GET    /api/arena/{id}/thinking-stream  # SSE stream
```

### 7.3 MCP Server Entry Point

**Location:** `services/mcp_server.py`
- Exposes agents as MCP tools
- Callable from Claude Code, Cursor, etc.

---

## 8. Configuration & Strategy Systems

### 8.1 Strategy Framework (`strategies/`)

```
base.py                  # BaseStrategy interface
ai_generator.py          # AI strategy generation
optimizer.py             # Strategy optimization
registry.py              # Strategy registry
builtin/                 # Built-in strategy implementations
├── ma_strategy.py       # Moving average
├── macd_strategy.py     # MACD
├── rsi_strategy.py      # RSI
├── kdj_strategy.py      # KDJ
├── turtle_strategy.py   # Turtle trading
└── [more]
```

**Strategy Components:**
```python
@dataclass
class StrategyMetadata:
    id, name, description
    category (TREND, MEAN_REVERSION, MOMENTUM, AI_GENERATED)
    is_ai_generated: bool
    generation_prompt: str
    confidence_score: float

@dataclass
class TradingSignal:
    timestamp, symbol
    action (buy/sell/hold)
    price, quantity
    confidence, reason
```

### 8.2 Backtest System (`backtest/`)

**Integration:**
- Strategy execution framework
- Historical data playback
- Performance metrics calculation
- Risk analysis

---

## 9. Feature Modules (30+)

The `modules/` directory organizes features by domain:

```
modules/
├── auth/                     # User authentication
├── chat/                     # Chat interface
├── arena/                    # Arena UI/API
├── market/                   # Market data
├── portfolio/                # Portfolio management
├── financial_analysis/       # Report analysis
├── news/                     # News aggregation
├── memory/                   # User memory
├── signal_aggregator/        # Trading signals
├── realtime_kline/           # Real-time candlesticks
├── token_usage/              # Usage tracking
├── wechat_bridge/            # WeChat integration
├── system_logs/              # Logging
└── [20+ more]
```

Each module provides:
- Database models
- Business logic
- HTTP routes
- MCP tools

---

## 10. Design Specifications (OpenSpec)

### 10.1 Active Change Proposals

**Multi-Agent Strategy Arena** (`add-multi-agent-strategy-arena/`)
- Status: Active proposal
- Scope: Competition system for N agents
- Features: Discussion modes, backtesting, elimination
- Specs affected: `multi-agent-arena`, `strategy-competition`, `agent-discussion`

**Orchestrator Simplification** (`refactor-orchestrator-simplify/`)
- Status: Active proposal
- Scope: Config-driven Harness as the chat orchestration path
- Goals: Remove feature-flagged runtime layers and deprecated agent files
- Key changes: Lightweight OrchestratorAgent, ConfigDrivenHarnessAgent dispatch, tool registry resolution

**Intelligent Strategy System** (`add-intelligent-strategy-system/`)
- Status: Archived 2026-01-11
- Features: AI strategy generation, optimization, backtesting

### 10.2 Specs Directory Structure

```
openspec/specs/
├── agent-debug-sidebar/          # Agent monitoring UI
├── chat-orchestration/           # Chat orchestration model
├── chat-visualization/           # Chat visualization
├── data-management/              # Data management interface
└── financial-report-analysis/    # Report analysis
```

---

## 11. Hierarchical Execution Patterns

### 11.1 Two-Tier Chat Hierarchy

**Tier 1: OrchestratorAgent**
- Top-level chat router
- Intent classification
- Config-driven agent selection
- SSE metadata normalization

**Tier 2: ConfigDrivenHarnessAgent**
- Loads DB agent configuration
- Resolves tools through `tool_registry`
- Builds the DeepAgents harness
- Streams tool/content/done events

### 11.2 Agent Discovery & Loading

**Process:**
1. Orchestrator reads visible agent configs from ClickHouse `agent_configs`.
2. LLM classification selects an `agent_name` from that catalog.
3. `get_config_driven_agent(agent_name)` loads and caches the harness agent.
4. Skills/tool names resolve through `tool_registry`.

---

## 12. Key Design Patterns

### 12.1 Plugin Pattern
Each data provider/feature is a plugin with:
- Schema definition
- Data ingestion logic
- HTTP route exposure
- MCP tool registration

### 12.2 Middleware Pattern
Request/response transformation chain:
- Before hook: context enrichment
- After hook: response filtering
- Each middleware is independent

### 12.3 Agent Pattern
All agents inherit from `LangGraphAgent`:
- LLM integration
- Tool binding
- Memory support
- Streaming capability

### 12.4 Registry Pattern
Centralized discovery:
- Agent registry
- Skill registry
- Strategy registry
- Plugin registry

### 12.5 Adapter Pattern
External systems can adapt domain-specific requests by creating or selecting DB agent configurations and invoking the config-driven harness path.

---

## 13. Data Flow Example: Market Analysis

```
User: "分析贵州茅台的走势和估值"
      ↓
OrchestratorAgent
  ├── Extract intent: "technical_and_fundamental_analysis"
  ├── Extract stock_codes: ["600519"]
  ├── Middleware before:
  │   ├── Memory: Retrieve user preferences (risk level, etc.)
  │   ├── Intent: Confirm analysis type
  │   └── Route plan: Need both MarketAgent and ReportAgent
  │
  ├── Execute parallel:
  │   ├── MarketAgent
  │   │   ├── Get technical indicators (MACD, RSI, MA)
  │   │   ├── Analyze price trends
  │   │   └── Return: "走势分析: ..."
  │   │
  │   └── ReportAgent
  │       ├── Get latest financials
  │       ├── Calculate valuation (P/E, P/B, etc.)
  │       └── Return: "估值分析: ..."
  │
  ├── Middleware after:
  │   ├── Cross-validation: Check consistency
  │   ├── Guardrails: Verify no overpromising
  │   └── Summarize: Compress if needed
  │
  └── Aggregate results
        ↓
      SSE Stream to Frontend
```

---

## 14. Technology Stack

**Core:**
- Python 3.11+
- FastAPI (HTTP API)
- LangGraph (agent orchestration)
- LangChain (LLM integration)

**LLM & Integration:**
- OpenAI GPT-4 (primary model)
- Deepseek (alternative)
- MCP (tool protocol)

**Data & Storage:**
- ClickHouse (time-series data)
- Redis (caching, sessions, queue)
- SQLAlchemy (ORM)

**Async & Events:**
- asyncio (concurrency)
- Celery (task queue)
- SSE (real-time streaming)

**Frontend:**
- React with TypeScript
- WebSocket/SSE for streaming

**Deployment:**
- Docker & Docker Compose
- Kubernetes-ready
- Volume-mounted config

---

## 15. Summary: Multi-Agent Architecture Highlights

### Strengths:
1. **Config-Driven Design**: Chat-facing agents are managed through DB configuration.
2. **Simplified Orchestration**: Orchestrator performs classification and delegates to one harness path.
3. **Tool Registry**: Skills map consistently to callable tool functions.
4. **Observability**: Langfuse tracing, SSE event streaming, debug metadata.
5. **Extensibility**: Plugin system, skill registry, strategy registry.
6. **Arena Competition**: Separate multi-agent debate system for strategy refinement.

### Complexity Points:
1. DB agent catalog availability now determines chat routing coverage.
2. Some legacy direct-import agents remain for compatibility.
3. Arena state machine remains separate from the lightweight chat orchestrator.

### Future Evolution (Planned):
1. Continue config-driven Harness consolidation
2. Explicit Skill Registry standardization
3. SubAgent protocol for better sub-task isolation
4. High-cost path optimization (reduce redundant classification/context)
5. Skill versioning and permission system

---

## 16. File Reference Map

**Key Agent Files:**
- `src/stock_datasource/agents/base_agent.py` - LangGraphAgent interface
- `src/stock_datasource/agents/orchestrator.py` - Lightweight config-driven orchestrator
- `src/stock_datasource/agents/config_driven_harness_agent.py` - DB-configured Harness agent
- `src/stock_datasource/agents/tools.py` - Shared tool functions

**Key Service Files:**
- `src/stock_datasource/services/tool_registry.py` - Skill/tool resolution
- `src/stock_datasource/services/execution_planner.py` - Routing config
- `src/stock_datasource/services/agent_registry.py` - Agent discovery
- `src/stock_datasource/services/agent_cache.py` - Shared caching

**Arena System:**
- `src/stock_datasource/arena/arena_manager.py` - Arena orchestrator
- `src/stock_datasource/arena/discussion_orchestrator.py` - Discussion coordinator
- `src/stock_datasource/arena/competition_engine.py` - Competition logic

**Configuration:**
- `src/stock_datasource/config/runtime_config.py` - Runtime settings
- `src/stock_datasource/config/settings.py` - Environment config

**Specs:**
- `openspec/changes/add-multi-agent-strategy-arena/proposal.md`
- `openspec/changes/refactor-agent-runtime-extensibility/proposal.md`

**Entry Points:**
- `cli.py` - CLI interface
- `src/stock_datasource/api/` - HTTP API routes
- `src/stock_datasource/services/http_server.py` - FastAPI server
- `src/stock_datasource/services/mcp_server.py` - MCP server

---

## Conclusion

This is a **production-grade multi-agent system** with sophisticated orchestration capabilities. The architecture demonstrates clear separation of concerns between:
- **Agents** (specialists doing domain work)
- **Orchestrators** (coordinators managing flow)
- **Services** (infrastructure for runtime, registry, memory)
- **Middleware** (cross-cutting concerns like safety and memory)

The chat orchestration path now favors a lightweight `OrchestratorAgent` plus `ConfigDrivenHarnessAgent`, with legacy direct-import agents retained only where external modules still depend on them.

