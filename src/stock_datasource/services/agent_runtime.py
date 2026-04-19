"""Agent Runtime: Unified control plane based on LangGraph Supervisor.

The ``AgentRuntime`` leverages LangGraph's native multi-agent patterns
(``langgraph_supervisor.create_supervisor``, ``create_react_agent``,
``Command`` + handoff) instead of reimplementing orchestration from scratch.

Architecture
------------
- **Supervisor Graph**: A LangGraph ``create_supervisor`` graph that uses an
  LLM to route user requests to the most appropriate sub-agent.
- **Sub-Agents**: Each business agent is wrapped as a ``create_react_agent``
  with its own tools and system prompt.
- **Handoff**: Uses LangGraph native ``Command(goto=...)`` handoff mechanism.
- **Streaming**: Uses LangGraph's ``astream_events(version="v2")`` for
  real-time SSE event emission.
- **Memory Store**: LangGraph Store for cross-session fact persistence.
- **Middleware Chain**: Before/after hooks for loop detection, summarization,
  guardrails, memory injection, and cross-validation.

Tasks implemented:
- 4.3: SubAgentEnvelope integration for invocation protocol
- 5.2: Observability metrics (cold start, token cost, classification count,
       concurrent failure rate, cache usage)
- Memory: LangGraph Store + FactExtractor + Middleware Chain
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncGenerator
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from .agent_registry import AgentRegistry, AgentRole, get_agent_registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------


def is_runtime_enabled() -> bool:
    """Check whether the new Agent Runtime is enabled.

    Controlled by env var ``AGENT_RUNTIME_ENABLED`` (default ``false``).
    This allows gradual rollout and instant rollback.
    """
    return os.getenv("AGENT_RUNTIME_ENABLED", "false").lower() in ("true", "1", "yes")


# ---------------------------------------------------------------------------
# SSE Event Adapter
# ---------------------------------------------------------------------------


def adapt_langgraph_event_to_sse(event: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a LangGraph astream_events v2 event to legacy SSE format.

    The frontend expects: thinking, content, tool, debug, visualization, done, error.
    This bridges LangGraph's native event model to our SSE contract.
    """
    etype = event.get("event", "")
    data = event.get("data", {})
    name = event.get("name", "")
    tags = event.get("tags", [])

    if etype == "on_chat_model_stream":
        chunk = data.get("chunk")
        if chunk:
            content = None
            if hasattr(chunk, "content") and chunk.content:
                raw = chunk.content
                if isinstance(raw, str):
                    content = raw
                elif isinstance(raw, list):
                    parts = []
                    for block in raw:
                        if isinstance(block, dict):
                            if block.get("type") == "text" and block.get("text"):
                                parts.append(block["text"])
                        elif isinstance(block, str):
                            parts.append(block)
                    if parts:
                        content = "".join(parts)
            elif isinstance(chunk, dict) and chunk.get("content"):
                content = chunk["content"]

            if content and isinstance(content, str):
                return {"type": "content", "content": content}
        return None

    if etype == "on_tool_start":
        tool_input = data.get("input", {})
        return {
            "type": "tool",
            "tool": name,
            "args": tool_input if isinstance(tool_input, dict) else {},
            "agent": _extract_agent_from_tags(tags),
            "status": f"调用工具: {name}",
        }

    if etype == "on_tool_end":
        tool_output = data.get("output", "")
        result_str = str(tool_output)
        summary = result_str[:500] + "..." if len(result_str) > 500 else result_str

        # Extract visualization if present
        viz = _extract_visualization(tool_output)
        events = []
        events.append(
            {
                "type": "debug",
                "debug_type": "tool_result",
                "agent": _extract_agent_from_tags(tags),
                "timestamp": time.time(),
                "data": {
                    "tool": name,
                    "result_summary": summary,
                },
            }
        )
        if viz:
            events.append(
                {
                    "type": "visualization",
                    "visualization": viz,
                    "agent": _extract_agent_from_tags(tags),
                    "tool": name,
                }
            )
        # Return first event; caller handles multi-event case
        return events[0] if len(events) == 1 else events

    if etype == "on_chain_start" and "supervisor" in name.lower():
        return {
            "type": "thinking",
            "agent": "AgentRuntime",
            "status": "正在理解您的需求...",
            "intent": "",
            "stock_codes": [],
        }

    # Skip noisy internal events
    if etype in (
        "on_chain_start",
        "on_chain_end",
        "on_chain_stream",
        "on_chat_model_start",
        "on_chat_model_end",
        "on_prompt_start",
        "on_prompt_end",
    ):
        return None

    return None


def _extract_agent_from_tags(tags: list[str]) -> str:
    """Try to extract agent name from LangGraph event tags."""
    for tag in tags:
        if tag.endswith("Agent") or tag.endswith("_agent"):
            return tag
    return ""


def _extract_visualization(tool_output: Any) -> dict[str, Any] | None:
    """Extract _visualization from tool output."""
    import json as _json

    if isinstance(tool_output, dict) and "_visualization" in tool_output:
        return tool_output["_visualization"]
    if hasattr(tool_output, "content"):
        content = tool_output.content
        if isinstance(content, dict) and "_visualization" in content:
            return content["_visualization"]
        if isinstance(content, str):
            try:
                parsed = _json.loads(content)
                if isinstance(parsed, dict) and "_visualization" in parsed:
                    return parsed["_visualization"]
            except (_json.JSONDecodeError, TypeError):
                pass
    if isinstance(tool_output, str):
        try:
            parsed = _json.loads(tool_output)
            if isinstance(parsed, dict) and "_visualization" in parsed:
                return parsed["_visualization"]
        except (_json.JSONDecodeError, TypeError):
            pass
    return None


# ---------------------------------------------------------------------------
# AgentRuntime
# ---------------------------------------------------------------------------


class AgentRuntime:
    """Unified control plane powered by LangGraph Supervisor.

    Instead of reimplementing parallel/sequential/handoff execution,
    this delegates all orchestration to LangGraph's native
    ``create_supervisor`` which handles:
    - LLM-based routing to the right sub-agent
    - Agent handoff via ``Command(goto=...)``
    - State management via ``MessagesState``
    - Checkpointing via ``MemorySaver``

    Lifecycle
    ---------
    1. Build sub-agents as ``create_react_agent`` from registry
    2. Build a supervisor graph with ``create_supervisor``
    3. Stream events via ``astream_events(version="v2")``
    4. Translate LangGraph events → legacy SSE events
    """

    def __init__(
        self,
        registry: AgentRegistry | None = None,
        default_timeout: int = 120,
    ):
        self.registry = registry or get_agent_registry()
        self.default_timeout = default_timeout
        self._supervisor = None
        self._checkpointer = MemorySaver()
        self._sub_agents: dict[str, Any] = {}
        # Task 5.2: Observability metrics
        self._cold_start_ms: float | None = None
        self._classification_count: int = 0
        self._concurrent_failures: int = 0
        self._total_invocations: int = 0

        # Memory Store + Middleware Chain (feature-flagged)
        self._store = None
        self._middleware_chain: list = []
        self._init_memory_and_middlewares()

        # Trigger explicit agent registrations (no-op if already done)
        try:
            from .agent_registrations import register_all_agents

            register_all_agents()
        except Exception as exc:
            logger.debug("Agent registrations skipped: %s", exc)

    def _init_memory_and_middlewares(self) -> None:
        """Initialize MemoryStore and middleware chain if feature flag is set."""
        try:
            from stock_datasource.agents.middlewares import (
                build_default_middleware_chain,
            )
            from stock_datasource.modules.memory.store import (
                get_memory_store,
                is_memory_store_enabled,
            )

            if is_memory_store_enabled():
                self._store = get_memory_store()
                self._middleware_chain = build_default_middleware_chain(
                    store=self._store
                )
                logger.info(
                    "Memory store + middleware chain initialized (%d middlewares)",
                    len(self._middleware_chain),
                )
            else:
                logger.debug("Memory store disabled (MEMORY_STORE_ENABLED not set)")
        except Exception as exc:
            logger.warning("Failed to init memory/middlewares: %s", exc)

    # ------------------------------------------------------------------
    # Sub-Agent construction
    # ------------------------------------------------------------------

    def _build_sub_agents(self) -> list:
        """Build LangGraph sub-agents from registry descriptors.

        Each registered business agent is wrapped as a ``create_react_agent``
        graph, using the agent's existing tools and system prompt.
        """
        from stock_datasource.agents.base_agent import (
            get_langchain_model,
        )

        self.registry.ensure_fallback_scan()

        agents = []
        model = get_langchain_model()

        for desc in self.registry.list_descriptors(role=AgentRole.AGENT):
            if not desc.enabled:
                continue

            try:
                # Get or create the business agent instance
                agent_instance = self.registry.get_agent(desc.name)
                if agent_instance is None:
                    continue

                # Extract tools and prompt from the existing agent
                tools = agent_instance.get_tools()
                system_prompt = agent_instance.get_system_prompt() + getattr(
                    agent_instance, "COMMON_OUTPUT_RULES", ""
                )

                # Build a LangGraph react agent
                react_agent = create_react_agent(
                    model=model,
                    tools=tools,
                    prompt=system_prompt,
                    name=desc.name,
                )

                agents.append(react_agent)
                self._sub_agents[desc.name] = react_agent
                logger.info("Built sub-agent: %s (%d tools)", desc.name, len(tools))

            except Exception as exc:
                logger.warning("Failed to build sub-agent %s: %s", desc.name, exc)

        return agents

    def _get_supervisor_prompt(self) -> str:
        """Build the supervisor's system prompt with agent descriptions."""
        agent_descs = []
        for desc in self.registry.list_descriptors(role=AgentRole.AGENT):
            if desc.enabled:
                markets = (
                    ", ".join(desc.capability.markets)
                    if desc.capability.markets
                    else "通用"
                )
                intents = (
                    ", ".join(desc.capability.intents)
                    if desc.capability.intents
                    else ""
                )
                agent_descs.append(
                    f"- **{desc.name}**: {desc.description} (市场: {markets})"
                )

        agents_list = "\n".join(agent_descs) if agent_descs else "无可用Agent"

        return f"""你是一个智能股票分析平台的协调者(Supervisor)。你的职责是理解用户的意图并将请求路由到最合适的专业Agent。

## 可用Agent
{agents_list}

## 路由规则
1. 分析用户问题，识别意图（行情分析、财务分析、选股、回测等）
2. 根据意图选择最合适的Agent
3. 如果涉及港股（代码如 00700.HK），技术分析选 MarketAgent，财务分析选 HKReportAgent
4. 如果用户同时需要技术面+基本面分析，可以先调用 MarketAgent 再调用 ReportAgent
5. 如果用户询问研报、公告等文档，选 KnowledgeAgent
6. 一般性对话选 ChatAgent

## 注意事项
- 直接将用户问题转发给选中的Agent，不要自己回答专业问题
- 如果需要多个Agent协作，按顺序逐个调用
- 始终用中文回复用户"""

    def _build_supervisor(self):
        """Build the LangGraph Supervisor graph.

        Uses ``create_supervisor`` from ``langgraph_supervisor`` which
        handles all routing/handoff/state management internally.
        """
        from langgraph_supervisor import create_supervisor

        from stock_datasource.agents.base_agent import get_langchain_model

        t0 = time.time()

        agents = self._build_sub_agents()
        if not agents:
            logger.warning("No sub-agents built, supervisor will be limited")
            return None

        model = get_langchain_model()

        supervisor = create_supervisor(
            agents=agents,
            model=model,
            prompt=self._get_supervisor_prompt(),
            supervisor_name="OrchestratorSupervisor",
            output_mode="full_history",
            add_handoff_back_messages=True,
            include_agent_name="inline",
        )

        # Compile with checkpointer for session persistence
        compile_kwargs = {"checkpointer": self._checkpointer}
        # Inject Memory Store if available (enables graph-level Store access)
        if self._store is not None:
            try:
                compile_kwargs["store"] = self._store.raw_store
            except Exception:
                pass
        self._supervisor = supervisor.compile(**compile_kwargs)

        # Task 5.2: Record cold start time
        self._cold_start_ms = (time.time() - t0) * 1000

        logger.info(
            "Supervisor graph built with %d sub-agents in %.0fms: %s",
            len(agents),
            self._cold_start_ms,
            list(self._sub_agents.keys()),
        )
        return self._supervisor

    def _ensure_supervisor(self):
        """Lazy-build the supervisor on first use."""
        if self._supervisor is None:
            self._build_supervisor()
        return self._supervisor

    # ------------------------------------------------------------------
    # Public streaming API
    # ------------------------------------------------------------------

    async def execute_stream(
        self,
        query: str,
        context: dict[str, Any] = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute a query via LangGraph Supervisor, yielding raw events.

        Uses ``astream_events(version="v2")`` for real-time streaming.
        """
        context = context or {}
        session_id = context.get("session_id", "default")
        user_id = context.get("user_id", "default")

        supervisor = self._ensure_supervisor()
        if supervisor is None:
            yield {
                "event": "error",
                "data": {"error": "No supervisor available (no agents built)"},
            }
            return

        config = {
            "configurable": {"thread_id": session_id},
            "recursion_limit": 50,
            "metadata": {
                "langfuse_user_id": user_id,
                "langfuse_session_id": session_id,
                "langfuse_tags": ["AgentRuntime"],
            },
        }

        # Add langfuse callbacks if available
        try:
            from stock_datasource.agents.base_agent import get_langfuse_handler

            handler = get_langfuse_handler()
            if handler:
                config["callbacks"] = [handler]
        except Exception:
            pass

        messages = [{"role": "user", "content": query}]

        try:
            async for event in supervisor.astream_events(
                {"messages": messages},
                config=config,
                version="v2",
            ):
                yield event
        except TimeoutError:
            yield {
                "event": "error",
                "data": {"error": f"执行超时 ({self.default_timeout}s)"},
            }
        except Exception as exc:
            logger.error("Supervisor execution failed: %s", exc)
            yield {
                "event": "error",
                "data": {"error": str(exc)},
            }

    async def execute_stream_sse(
        self,
        query: str,
        context: dict[str, Any] = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute and yield legacy SSE-compatible events.

        Translates LangGraph ``astream_events`` into the frontend's
        expected format (thinking, content, tool, done, etc.).

        Task 4.3: Builds a ``SubAgentEnvelope`` to record invocation
        metadata.
        Task 5.2: Bumps observability counters.
        """
        context = context or {}
        session_id = context.get("session_id", "default")
        user_id = context.get("user_id", "default")

        # --- Middleware before() phase ---
        mw_context = None
        mw_trace_id = "-"
        if self._middleware_chain:
            try:
                from stock_datasource.agents.middlewares.base import AgentContext
                from stock_datasource.utils.request_context import (
                    generate_middleware_trace_id,
                    middleware_trace_id_var,
                )

                mw_trace_id = generate_middleware_trace_id()
                middleware_trace_id_var.set(mw_trace_id)

                mw_context = AgentContext(
                    query=query,
                    session_id=session_id,
                    user_id=user_id,
                )
                for mw in self._middleware_chain:
                    if mw.enabled:
                        mw_context = await mw.before_with_logging(mw_context)

                # Inject memory block into context for downstream use
                if mw_context.memory_block:
                    context["memory_block"] = mw_context.memory_block
                # Check if query was flagged as non-financial
                if not mw_context.is_financial_query:
                    yield {
                        "type": "content",
                        "content": "抱歉，我是一个专业的股票分析助手，只能回答与金融投资相关的问题。\n\n"
                        "您可以试试以下问题：\n"
                        "- 查询某只股票的行情和走势\n"
                        "- 对股票进行技术面或基本面分析\n"
                        "- 筛选符合条件的股票\n"
                        "- 制定投资策略和回测\n\n"
                        f"您的问题：{query}",
                    }
                    yield {
                        "type": "done",
                        "metadata": {"agent": "AgentRuntime", "redirected": True},
                    }
                    return
            except Exception as exc:
                logger.warning("Middleware before() chain failed: %s", exc)
                mw_context = None

        # Task 4.3: Create envelope for this invocation
        from .session_memory_service import SubAgentEnvelope, get_session_memory_service

        envelope = SubAgentEnvelope(
            agent_name="AgentRuntime",
            session_id=session_id,
            user_id=user_id,
            query=query,
        )

        # Task 5.2: Bump counters
        self._total_invocations += 1
        self._classification_count += 1
        mem_svc = get_session_memory_service()
        mem_svc.record_stat("runtime_invocations")

        t0 = time.time()

        # Emit initial thinking
        yield {
            "type": "thinking",
            "agent": "AgentRuntime",
            "status": "正在理解您的需求...",
            "intent": "",
            "stock_codes": [],
        }

        has_content = False
        has_error = False
        content_parts: list[str] = []

        async for raw_event in self.execute_stream(query, context):
            # Handle error events from our own wrapper
            if raw_event.get("event") == "error":
                yield {
                    "type": "error",
                    "error": raw_event.get("data", {}).get("error", "Unknown error"),
                }
                has_error = True
                self._concurrent_failures += 1
                mem_svc.record_stat("runtime_errors")
                continue

            sse_event = adapt_langgraph_event_to_sse(raw_event)
            if sse_event is None:
                continue

            # Handle multi-event case (tool_end with visualization)
            if isinstance(sse_event, list):
                for e in sse_event:
                    yield e
                    if e.get("type") == "content":
                        has_content = True
                        content_parts.append(e.get("content", ""))
            else:
                yield sse_event
                if sse_event.get("type") == "content":
                    has_content = True
                    content_parts.append(sse_event.get("content", ""))

        # Task 5.2: Record execution duration
        duration_ms = int((time.time() - t0) * 1000)
        mem_svc.record_stat("runtime_total_duration_ms", duration_ms)

        # Task 4.3: Fill envelope response
        envelope.response = "".join(content_parts)
        envelope.success = not has_error
        envelope.metadata = {
            "duration_ms": duration_ms,
            "has_content": has_content,
        }

        # --- Middleware after() phase ---
        if self._middleware_chain and mw_context is not None:
            try:
                from stock_datasource.agents.middlewares.base import AgentResponse

                mw_response = AgentResponse(
                    content=envelope.response,
                    success=envelope.success,
                    metadata=envelope.metadata,
                    tool_calls=[],
                )
                for mw in reversed(self._middleware_chain):
                    if mw.enabled:
                        mw_response = await mw.after_with_logging(
                            mw_context, mw_response
                        )

                # Apply middleware modifications
                if mw_response.warnings:
                    # Append warnings to content
                    for warning in mw_response.warnings:
                        content_parts.append(f"\n\n{warning}")
                    envelope.response = "".join(content_parts)
                if mw_response.validation_result:
                    context["validation_result"] = mw_response.validation_result
            except Exception as exc:
                logger.warning("Middleware after() chain failed: %s", exc)

        # Emit done
        yield {
            "type": "done",
            "metadata": {
                "agent": "AgentRuntime",
                "available_agents": self.registry.list_available(),
                "has_error": has_error,
                "duration_ms": duration_ms,
                "middleware_trace_id": mw_trace_id,
                "middleware_trace": mw_context.middleware_trace if mw_context else [],
            },
        }

        # Reset middleware trace context
        if mw_trace_id != "-":
            try:
                from stock_datasource.utils.request_context import (
                    middleware_trace_id_var,
                )

                middleware_trace_id_var.set("-")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Non-streaming API
    # ------------------------------------------------------------------

    async def execute(
        self,
        query: str,
        context: dict[str, Any] = None,
    ) -> dict[str, Any]:
        """Execute synchronously by collecting all SSE events."""
        content_parts = []
        metadata = {}
        tool_calls = []

        async for event in self.execute_stream_sse(query, context):
            etype = event.get("type")
            if etype == "content":
                content_parts.append(event.get("content", ""))
            elif etype == "done":
                metadata = event.get("metadata", {})
            elif etype == "tool":
                tool_calls.append(
                    {
                        "name": event.get("tool", ""),
                        "args": event.get("args", {}),
                    }
                )

        return {
            "response": "".join(content_parts),
            "success": not metadata.get("has_error", False),
            "metadata": metadata,
            "tool_calls": tool_calls,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def agent_names(self) -> set[str]:
        """Names of agents available in the supervisor."""
        return set(self._sub_agents.keys())

    @property
    def stats(self) -> dict[str, Any]:
        """Task 5.2: Return observability snapshot."""
        return {
            "cold_start_ms": self._cold_start_ms,
            "total_invocations": self._total_invocations,
            "classification_count": self._classification_count,
            "concurrent_failures": self._concurrent_failures,
            "failure_rate": (
                self._concurrent_failures / self._total_invocations
                if self._total_invocations > 0
                else 0.0
            ),
            "sub_agent_count": len(self._sub_agents),
        }

    def reset(self) -> None:
        """Reset the supervisor (e.g., after agent registration changes)."""
        self._supervisor = None
        self._sub_agents.clear()
        self._cold_start_ms = None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_runtime: AgentRuntime | None = None


def get_agent_runtime() -> AgentRuntime:
    global _runtime
    if _runtime is None:
        _runtime = AgentRuntime()
    return _runtime
