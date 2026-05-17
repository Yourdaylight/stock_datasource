# Multi-Agent Architecture - Quick Reference Guide

## Finding Key Components

### Agent Files
```bash
# All specialized agents (18+)
find src/stock_datasource/agents -name "*_agent.py" -type f

# Base agent interface
src/stock_datasource/agents/base_agent.py

# Main orchestrator
src/stock_datasource/agents/orchestrator.py

# Middleware implementations
ls -la src/stock_datasource/agents/middlewares/
```

### Arena System (Multi-Agent Competition)
```bash
# Arena orchestrator
src/stock_datasource/arena/arena_manager.py

# Discussion coordinator
src/stock_datasource/arena/discussion_orchestrator.py

# Competition engine
src/stock_datasource/arena/competition_engine.py

# Arena-specific agents
ls -la src/stock_datasource/arena/agents/
```

### Core Services
```bash
# Unified runtime
src/stock_datasource/services/agent_runtime.py

# Routing configuration
src/stock_datasource/services/execution_planner.py

# Agent discovery
src/stock_datasource/services/agent_registry.py

# Session memory
src/stock_datasource/services/session_memory_service.py

# Skill registry
src/stock_datasource/services/skill_registry.py

# Caching layer
src/stock_datasource/services/agent_cache.py
```

### Configuration
```bash
# Runtime config (persistent)
src/stock_datasource/config/runtime_config.py

# Environment settings
src/stock_datasource/config/settings.py

# Config file location (Docker volume)
data/runtime_config.json
```

---

## Agent Discovery & Registration

### How Agents are Found

**Method 1: Scanning** (Backward Compatible)
```python
# In orchestrator.py
def _discover_agents(self):
    import stock_datasource.agents as agents_pkg
    for module_info in pkgutil.iter_modules(agents_pkg.__path__):
        if module_name.endswith(AGENT_MODULE_SUFFIX):  # "*_agent.py"
            # Extract LangGraphAgent classes
```

**Method 2: Registry** (Recommended, New)
```python
# Get registry instance
registry = get_agent_registry()

# Register an agent
descriptor = AgentDescriptor(
    name="MyAgent",
    description="...",
    agent_class=MyAgent,
    role=AgentRole.AGENT,
    capability=CapabilityDescriptor(
        intents=["my_intent"],
        markets=["A"],
        tags=["tag1", "tag2"]
    )
)
registry.register(descriptor)

# Get agent instance
agent = registry.get_agent("MyAgent")
```

---

## Request Flow (End-to-End)

### 1. User Input Entry Points
- **CLI:** `cli.py` → command handlers
- **HTTP:** `src/stock_datasource/api/` → FastAPI routes
- **WebChat:** `src/stock_datasource/modules/chat/` → chat service
- **MCP:** `src/stock_datasource/services/mcp_server.py` → MCP tools
- **WeChat:** `src/stock_datasource/modules/wechat_bridge/` → WeChat integration

### 2. Orchestration
```
OrchestratorAgent (LangGraph Supervisor)
├─ Intent extraction (LLM)
├─ Stock code extraction
└─ Route to agent(s)
```

### 3. Middleware Chain (Before)
```
1. MemoryInjectionMiddleware    - Load user context
2. LoopDetectionMiddleware       - Detect infinite loops
3. GuardrailMiddleware           - Validate compliance
4. SignalExtractionMiddleware    - Extract trading signals
5. CrossValidationMiddleware     - Prepare validation
```

### 4. Agent Execution
- Single agent or concurrent agents (safe groups)
- Tool invocation
- LLM reasoning
- Response formatting

### 5. Middleware Chain (After)
```
1. CrossValidationMiddleware     - Verify consistency
2. GuardrailMiddleware           - Apply safety filters
3. SummarizationMiddleware       - Compress if needed
4. MemoryInjectionMiddleware     - Save to user memory
```

### 6. Output
- SSE streaming events to frontend
- Events: thinking → content → tool → debug → done

---

## Concurrent Agent Execution

### Safe Groups (Can Run in Parallel)
```python
CONCURRENT_AGENT_GROUPS = [
    {"MarketAgent", "ReportAgent"},
    {"IndexAgent", "EtfAgent"},
    {"OverviewAgent", "TopListAgent"},
    {"MarketAgent", "HKReportAgent"},
    {"KnowledgeAgent", "MarketAgent"},
    {"KnowledgeAgent", "ReportAgent"},
]
```

### Handoff Map (Sequential with State Passing)
```python
AGENT_HANDOFF_MAP = {
    "MarketAgent": ["ReportAgent", "HKReportAgent", "BacktestAgent"],
    "ScreenerAgent": ["MarketAgent", "ReportAgent"],
    "ReportAgent": ["BacktestAgent", "MarketAgent", "HKReportAgent"],
    "HKReportAgent": ["MarketAgent", "ReportAgent"],
    "OverviewAgent": ["MarketAgent", "IndexAgent"],
}
```

### How to Execute
```python
# In execution_planner.py
can_run_concurrently(["MarketAgent", "ReportAgent"])  # True
get_handoff_targets("MarketAgent")  # List of possible targets
```

---

## Memory Architecture

### Layer A: LangGraph MemorySaver
- Automatic checkpointing
- State recovery on failure
- Thread-safe storage

### Layer B: Tool Result Compression
- Reduce context size
- Keep semantic meaning
- Remove redundant data

### Layer D: Shared State Storage
- Cross-turn caching
- Cross-agent data passing
- TTL management

### Layer E: Long-Term Memory
- User preferences
- Investment history
- Portfolio tracking
- Stored in DB

---

## Arena System (Multi-Agent Competition)

### Creating an Arena
```python
from stock_datasource.arena import MultiAgentArena, ArenaConfig

config = ArenaConfig(
    name="My Strategy Arena",
    agent_count=5,
    symbols=["600000", "000858"],
    discussion_mode="debate",
    backtest_period="3M"
)

arena = MultiAgentArena(config, user_id="user123")
await arena.initialize()
```

### Discussion Modes
- **DEBATE:** Agents challenge each other
- **COLLABORATION:** Agents refine together
- **REVIEW:** Some generate, others review

### Competition Lifecycle
1. Initialize N agents
2. Run discussion rounds
3. Backtest generated strategies
4. Rank by performance
5. Simulate trading (top strategies)
6. Periodic elimination
7. Strategy replenishment

### SSE Streaming
```python
# Client subscribes to:
GET /api/arena/{id}/thinking-stream

# Receives events:
{
    "type": "thinking",
    "content": "分析中...",
    "agent": "StrategyGeneratorAgent",
    "timestamp": 1234567890
}
```

---

## Plugin & Skill System

### Plugin Types (30+ modules)
- **Data plugins:** Market, report, index, ETF
- **Feature plugins:** Auth, portfolio, analysis
- **Integration plugins:** WeChat, MCP API Key
- **System plugins:** Logs, token usage

### Plugin Registration
```python
# Automatic via plugin manager
from stock_datasource.core.plugin_manager import plugin_manager

plugin_manager.discover_plugins()
plugin_manager.register_plugin("my_plugin")
```

### Skill Registry
```python
from stock_datasource.services.skill_registry import skill_registry

# Register a tool
skill_registry.register_skill({
    "name": "my_tool",
    "description": "...",
    "parameters": {...},
    "callable": my_function
})
```

---

## Configuration Management

### Runtime Config (Persistent)
File: `data/runtime_config.json`

```bash
# Access programmatically
from stock_datasource.config.runtime_config import (
    load_runtime_config,
    save_runtime_config,
    get_schedule_config
)

config = load_runtime_config()
save_runtime_config(
    schedule={"enabled": True, "execute_time": "18:00"}
)
```

### Environment Settings
File: `.env` or environment variables

```bash
# Key variables
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4
CLICKHOUSE_HOST=localhost
REDIS_URL=redis://localhost:6379
AGENT_RUNTIME_ENABLED=false
```

---

## Strategy System

### Built-in Strategies
```bash
src/stock_datasource/strategies/builtin/
├── ma_strategy.py              # Moving Average
├── macd_strategy.py            # MACD
├── rsi_strategy.py             # RSI
├── kdj_strategy.py             # KDJ
├── turtle_strategy.py          # Turtle Trading
└── [more]
```

### AI-Generated Strategies
```python
from stock_datasource.strategies.ai_generator import AIStrategyGenerator

generator = AIStrategyGenerator(llm_model="gpt-4")
strategy = await generator.generate_strategy(
    intent="找出低估值股票",
    stock_codes=["600000"],
    context={"market_condition": "bear"}
)
```

### Strategy Registry
```python
from stock_datasource.strategies.registry import strategy_registry

# Register
strategy_registry.register(strategy_instance)

# Get
strategy = strategy_registry.get("ma_strategy_v1")

# List
all_strategies = strategy_registry.list_all()
```

---

## Debugging & Observability

### Middleware Trace
```python
# In middleware.py
context.trace(middleware_name="MyMiddleware", action="before")
```

### Langfuse Tracing
```python
# Automatic instrumentation via handlers
# View traces at: https://cloud.langfuse.com
```

### Debug Events
```python
# OrchestratorAgent publishes debug events
{
    "type": "debug",
    "debug_type": "agent_selection",
    "data": {
        "intent": "...",
        "selected_agents": ["MarketAgent"],
        "confidence": 0.95
    }
}
```

### Logging
```python
# Use structured logging
from stock_datasource.utils.logger import logger

logger.info("Message", extra={"context": "value"})
logger.error("Error", extra={"agent": "MarketAgent"})
```

---

## Design Specs (OpenSpec)

### Active Proposals
```bash
# Multi-Agent Strategy Arena
openspec/changes/add-multi-agent-strategy-arena/
├── proposal.md
├── tasks.md
└── specs/

# Unified Runtime
openspec/changes/refactor-agent-runtime-extensibility/
├── proposal.md
├── tasks.md
└── specs/
```

### Checking Specs
```bash
# List all specs
openspec list

# Show specific spec
openspec show agent-debug-sidebar

# Validate changes
openspec validate add-multi-agent-strategy-arena --strict
```

---

## Common Tasks

### Adding a New Agent
1. Create `src/stock_datasource/agents/my_agent.py`
2. Inherit from `LangGraphAgent`
3. Implement `astream_events()` method
4. Register via AgentRegistry or create `*_agent.py` file
5. Update README agent list

### Adding a Tool to an Agent
```python
# In agent class
def __init__(self):
    self.tools = [
        {
            "name": "my_tool",
            "description": "...",
            "schema": {...}
        }
    ]
```

### Adding a Middleware
1. Create in `src/stock_datasource/agents/middlewares/`
2. Inherit from `BaseMiddleware`
3. Implement `before()` and `after()` methods
4. Register in middleware chain

### Adding Configuration Option
1. Update `DEFAULT_CONFIG` in `config/runtime_config.py`
2. Add getter/setter functions
3. Add HTTP endpoint to update it
4. Document in README

---

## Performance Tips

### Reduce Cold Start
- Use lazy loading for agents
- Enable agent caching
- Pre-warm critical agents

### Reduce Token Cost
- Use tool result compression
- Summarize long responses
- Cache tool results

### Improve Concurrency
- Use safe agent groups
- Execute in parallel when possible
- Avoid deep sequential chains

### Optimize Memory
- Use TTL for cache entries
- Compress old messages
- Archive long histories

---

## Troubleshooting

### Agent Not Found
```python
# Check discovery
from stock_datasource.agents.orchestrator import OrchestratorAgent
orchestrator = OrchestratorAgent()
orchestrator._discover_agents()
print(orchestrator._agents.keys())
```

### Config Not Persisting
```bash
# Verify data directory is writable
ls -la data/
# Check runtime_config.json
cat data/runtime_config.json
```

### Agent Timeout
```python
# In base_agent.py config
agent_config.recursion_limit = 100  # Increase if needed
```

### Memory Issues
```python
# Reduce context size
agent_config.max_history_messages = 10
agent_config.max_history_chars = 5000
```

---

## File Location Quick Map

| Component | Location |
|-----------|----------|
| **Agents** | `src/stock_datasource/agents/` |
| **Arena** | `src/stock_datasource/arena/` |
| **Services** | `src/stock_datasource/services/` |
| **Modules** | `src/stock_datasource/modules/` |
| **Config** | `src/stock_datasource/config/` |
| **API** | `src/stock_datasource/api/` |
| **CLI** | `cli.py` (root) |
| **Specs** | `openspec/` |
| **Frontend** | `frontend/src/` |
| **Docker** | `docker/` |

---

## Next Steps

1. **Read:** Full ARCHITECTURE.md for comprehensive overview
2. **Explore:** Key files linked in this guide
3. **Review:** OpenSpec proposals for future direction
4. **Experiment:** Try running `openspec list` and `openspec show`
5. **Code:** Start with agent discovery and middleware chain
