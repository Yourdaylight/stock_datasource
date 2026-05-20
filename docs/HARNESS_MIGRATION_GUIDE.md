# LangGraph Harness 迁移指南

> 审计日期: 2026-05-20 | 状态: 审计完成，待实施

## 一、背景

项目已使用 `deepagents>=0.1.0` + `langgraph>=1.0.0`。`create_deep_agent` 支持 Harness 完整能力（middleware, subagents, skills, memory, backend, interrupt_on, store, cache），但当前只用了 4 个基础参数：`model, tools, system_prompt, checkpointer`。

大量本应由框架处理的逻辑被手写在 `OrchestratorAgent`(1575行) 和 `base_agent.py`(950+行) 中。

## 二、`create_deep_agent` 完整签名

```python
create_deep_agent(
    model,                    # ✅ 已使用
    tools,                    # ✅ 已使用
    system_prompt,            # ✅ 已使用
    middleware=[],            # ❌ 未使用 — 自建7个middleware未接入
    subagents=[],             # ❌ 未使用 — 手写orchestrator路由
    skills=[],                # ❌ 未使用 — YAML声明了但从不加载
    memory=[],                # ❌ 未使用 — 手写SessionMemoryService
    response_format=None,     # ❌ 未使用
    context_schema=None,      # ❌ 未使用
    checkpointer=None,        # ✅ 已使用
    store=None,               # ❌ 未使用 — 自建MemoryStore wrapper
    backend=None,             # ❌ 未使用
    interrupt_on=None,        # ❌ 未使用
    cache=None,               # ❌ 未使用
)
```

## 三、需要 Harness 改造的 8 个模块

### 1. OrchestratorAgent → SubAgentMiddleware (P0)

| 维度 | 当前 | 改造后 |
|------|------|--------|
| 文件 | `agents/orchestrator.py` (1575行) | ~200行 |
| 路由 | 手写LLM intent分类 + 手动dispatch | SubAgentMiddleware 自动路由 |
| 并行 | 手动 asyncio.gather + Queue | 框架内建并行调度 |
| 缓存 | 手动 agent instance dict | 框架管理 |
| Fallback | 手写 MCP ReAct 3种模式 | tools 参数直接传 MCP tools |

```python
# BEFORE (1575 lines)
class OrchestratorAgent:
    async def execute_stream(self, query, context):
        intent, agent_name, rationale = await self._classify_with_llm(query)
        plan = self._build_multi_agent_plan(agent_name, stock_codes, query)
        # ... 400 lines of manual routing, queue, parallel execution ...

# AFTER (~50 lines)
from deepagents import create_deep_agent, SubAgent, SubAgentMiddleware

subagents = [
    SubAgent(name="MarketAgent", description="A股行情技术分析", system_prompt=MARKET_PROMPT, tools=market_tools),
    SubAgent(name="ReportAgent", description="A股财报深度分析", system_prompt=REPORT_PROMPT, tools=report_tools),
    SubAgent(name="NewsAgent", description="新闻舆情分析", system_prompt=NEWS_PROMPT, tools=news_tools),
    SubAgent(name="ScreenerAgent", description="智能选股筛选", system_prompt=SCREENER_PROMPT, tools=screener_tools),
]

orchestrator = create_deep_agent(
    model=model,
    tools=mcp_tools,  # MCP tools 作为 fallback
    system_prompt=ORCHESTRATOR_PROMPT,
    middleware=[SubAgentMiddleware(subagents=subagents)],
    checkpointer=True,
    store=memory_store,
)
```

### 2. SessionMemoryService → MemoryMiddleware (P0)

| 维度 | 当前 | 改造后 |
|------|------|--------|
| 文件 | `services/session_memory_service.py` (~200行) | 删除 |
| 历史管理 | 手写dict + TTL + 截断 | MemoryMiddleware 自动 |
| 持久化 | 无（内存丢失） | LangGraph Store 自动持久化 |
| 摘要 | 手写 `_summarize` 按字符截断 | 框架 fraction-based 触发 |

```python
# BEFORE
class SessionMemoryService:
    def __init__(self):
        self._sessions: dict[str, list] = {}
    def add_message(self, session_id, role, content, max_messages=20): ...
    def get_history(self, session_id, ttl_seconds=3600, max_chars=12000): ...

# AFTER
from deepagents import MemoryMiddleware
agent = create_deep_agent(
    ...,
    middleware=[MemoryMiddleware(backend=sqlite_backend, sources=["AGENTS.md"])],
    memory=["user_preferences", "analysis_conclusions"],
)
```

### 3. MemorySaver 管理 → checkpointer=True (P1)

```python
# BEFORE (base_agent.py L194-211)
_memory_saver = None
def get_memory_saver():
    global _memory_saver
    if _memory_saver is None:
        from langgraph.checkpoint.memory import MemorySaver
        _memory_saver = MemorySaver()
    return _memory_saver

# AFTER
agent = create_deep_agent(..., checkpointer=True)
```

### 4. 工具压缩 → FilesystemMiddleware (P2)

```python
# BEFORE (base_agent.py compress_tool_result, ~40行)
def compress_tool_result(result, max_len=2000): ...

# AFTER
from deepagents import FilesystemMiddleware
agent = create_deep_agent(
    ...,
    middleware=[FilesystemMiddleware(tool_token_limit_before_evict=20000)],
)
```

### 5. Skills YAML → skills 参数 (P1)

```yaml
# BEFORE (config/builtin_agents.yaml) — 声明了但从未加载
- id: market_agent
  skills: [get_stock_daily, get_stock_info, calculate_technical_indicators]
```

```python
# AFTER — 真正按需加载
agent = create_deep_agent(
    ...,
    skills=["market_analysis", "technical_indicators", "kline_charting"],
)
```

### 6. Store 集成 → store 参数 (P1)

```python
# BEFORE (modules/memory/store.py 自建wrapper, 376行)
class MemoryStore:
    def __init__(self):
        self._store = InMemoryStore()
    def put_fact(self, user_id, fact_id, fact): ...

# AFTER — 直接传给框架
from langgraph.store.memory import InMemoryStore
store = InMemoryStore()
agent = create_deep_agent(..., store=store)
# Agent 内部节点可直接 store.put/search
```

### 7. 自建 Middleware → AgentMiddleware 接口 (P0)

当前 7 个自建 middleware (`agents/middlewares/`):
- `loop_detection.py` — 循环检测
- `summarization.py` — 摘要
- `guardrail.py` — 安全护栏
- `memory_injection.py` — 记忆注入
- `cross_validation.py` — 交叉验证
- `signal_extraction.py` — 信号提取
- `base.py` — 自建接口

**问题**：使用自定义 `BaseMiddleware` 接口，与 `create_deep_agent` 的 `middleware` 参数不兼容。

**改造**：适配为 `langchain.agents.middleware.types.AgentMiddleware` 接口。

### 8. ExecutionPlanner → 声明式配置 (P2)

```python
# BEFORE (services/execution_planner.py)
AGENT_HANDOFF_MAP = {"MarketAgent": ["ReportAgent", "NewsAgent"], ...}
def can_run_concurrently(agents): ...

# AFTER — SubAgent 声明自带编排关系
SubAgent(name="MarketAgent", ..., interrupt_on={"handoff": True})
```

## 四、实施路线图

```
Phase 0 (1天): 兼容性验证
├─ 升级 deepagents/langgraph 到最新版
├─ 确认 SubAgent/MemoryMiddleware API 可用
└─ 创建 HarnessMarketAgent 原型验证

Phase 1 (3天): P0 模块改造
├─ OrchestratorAgent → SubAgentMiddleware
├─ Middleware 接口适配 (7个)
└─ SessionMemory → MemoryMiddleware

Phase 2 (2天): P1 模块改造
├─ checkpointer=True
├─ skills 参数接入
└─ store 参数接入

Phase 3 (1天): P2 + 回归测试
├─ FilesystemMiddleware 接入
├─ ExecutionPlanner 声明式重构
└─ 全量回归测试
```

## 五、风险

| 风险 | 缓解 |
|------|------|
| SubAgentMiddleware 不支持自定义 SSE event 格式 | 保留 execute_stream wrapper，只替内部逻辑 |
| MemoryMiddleware 与现有 FactExtractor 冲突 | 两者并行运行，MemoryMiddleware 管会话级，FactExtractor 管知识级 |
| deepagents 版本不稳定 | pin 版本，封装 adapter 层 |
| 迁移期间功能回退 | 历史方案曾使用 feature flag；当前默认走 `ConfigDrivenHarnessAgent` |
